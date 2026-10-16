import time
from uuid import NAMESPACE_URL, uuid5

from .agent_models import AgentInterpretation
from .analysis_artifacts import AnalysisStore
from .analysis_models import ClassificationEvidence, Conclusion, ExportManifest
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .context_models import Node, Phase
from .context_phase import child_id
from .explorer import load_run
from .explorer import summary as agent_summary
from .family_classifier import decide
from .family_evidence import classification_inputs
from .investigation_models import Status
from .jsonio import digest, encode, loads
from .memory_writer import MemoryWriter, memory_key
from .models import read_case
from .probe_phase import link
from .regression_export import regression_bytes, report_bytes


def phase_for(record, name, refs, nodes=(), edges=()):
    return Phase(
        investigation_id=record.snapshot.id,
        fault_case_id=record.snapshot.reduction.currentCaseId,
        fingerprint_id=record.snapshot.fingerprintId,
        phase_key=digest({"investigation": record.snapshot.id, "phase": name}),
        payload_sha256=digest(
            {
                "nodes": [n.model_dump() for n in nodes],
                "edges": [e.model_dump() for e in edges],
                "refs": [r.model_dump() for r in refs],
            }
        ),
        nodes=list(nodes),
        edges=list(edges),
        artifacts=list(refs),
    )


class FinishingHandler:
    def __init__(self, worker):
        self.worker, self.store = worker, worker.store
        self.memory = MemoryWriter(self.store)

    def classify(self, record, deadline):
        if time.monotonic() >= deadline - 10:
            return self.worker.stop(
                record,
                Status.UNRESOLVED,
                "budget_exhausted",
                "The analysis budget was reached. Verified evidence is preserved.",
            )
        if record.classificationRef is None:
            evidence = classification_inputs(self.store, record)
            storage = AnalysisStore(
                self.store.root, record.snapshot.id, "classification"
            )
            ref = storage.document("evidence", evidence)
            state, winner = decide(
                evidence.candidates, provisional_eligible=bool(evidence.profile.probes)
            )
            family_id = (
                winner.familyId
                if winner
                else str(
                    uuid5(NAMESPACE_URL, "faultglass:family:" + record.snapshot.id)
                )
                if state == "provisional"
                else None
            )
            family_status = (
                winner.familyStatus if winner else "provisional" if family_id else None
            )
            family_name = (
                "Procedure call with a trailing required match" if family_id else None
            )
            if winner:
                rows = self.worker.repository._query("identities", {"ids": [family_id]})
                if len(rows) != 1 or rows[0][0] != ["FaultFamily"]:
                    raise EvidenceIntegrity()
                family_name = Node(
                    label="FaultFamily", properties=dict(rows[0][1])
                ).properties["name"]
            conclusion = Conclusion(
                state=state,
                familyId=family_id,
                familyStatus=family_status,
                familyName=family_name,
                evidenceRef=ref,
                observed=[
                    f"Baseline: {evidence.profile.sourceStatuses[0]}. Target: {evidence.profile.sourceStatuses[1]}.",
                    "The same source signature was observed in two fresh comparisons.",
                ],
                unknowns=evidence.unknowns,
                reasonCode="supported_behavioral_grouping"
                if family_id
                else "insufficient_separation",
                createdAt=evidence.createdAt,
            )
            for probe in evidence.profile.probes:
                if probe.contribution == "semantic_contrast":
                    conclusion.observed.append(
                        "The optional-match experiment removed the target crash while the baseline still reported an error. This bounds the observed behavior; it does not establish a root cause."
                    )
            nodes, edges = [], []
            if family_id:
                if not winner:
                    nodes.append(
                        Node(
                            label="FaultFamily",
                            properties=dict(
                                id=family_id,
                                slug="behavior-" + family_id[:12],
                                name=family_name,
                                status="provisional",
                                created_at=evidence.createdAt,
                                updated_at=evidence.createdAt,
                            ),
                        )
                    )
                edge = link(
                    "MATCHES_FAMILY",
                    child_id(record.snapshot.id, "divergence"),
                    family_id,
                    evidence.createdAt,
                    ref,
                    status=family_status,
                    evidence_weight=winner.score if winner else 0.0,
                    version_scope=encode(evidence.profile.scope.model_dump()).decode(),
                )
                edge.properties["source_kind"] = "verified_classification"
                edges.append(edge)
                # A family describes the controlled constructs in this exact verified profile.
                for feature in evidence.profile.features:
                    edge = link(
                        "INVOLVES_FEATURE", family_id, feature, evidence.createdAt, ref
                    )
                    edge.properties["source_kind"] = "verified_classification"
                    edge.properties["id"] = digest(
                        {"edge": edge.properties["id"], "evidence": ref.sha256}
                    )
                    edges.append(edge)
            phase = phase_for(record, "classification", [ref], nodes, edges)
            return self.store.commit(
                record.snapshot.id,
                "family." + state,
                {
                    "matched": "Matched behavioral family",
                    "provisional": "Provisional behavioral family",
                    "unresolved": "The difference is verified, but its family remains unresolved.",
                }[state],
                update={
                    "conclusion": conclusion.model_dump(),
                    "record": {"classificationRef": ref.model_dump()},
                },
                outputs=[ref],
                phase=phase,
            )
        evidence = ClassificationEvidence.model_validate(
            loads(read_reference(self.store.root, record.classificationRef))
        )
        run = load_run(self.store, record)
        if run and run.status in {"pending", "running"}:
            if run.stage == "classification":
                facts = {
                    "evidenceIds": [
                        record.classificationRef.sha256,
                        evidence.sourceRef.sha256,
                        evidence.stabilityRef.sha256,
                        evidence.retainedVerificationRef.sha256,
                    ],
                    "profile": evidence.profile.model_dump(),
                    "family": record.snapshot.conclusion.model_dump(),
                    "candidateScores": [c.model_dump() for c in evidence.candidates],
                    "unknowns": evidence.unknowns,
                }
                fresh, request = self.worker.explorer.request(
                    record,
                    run,
                    facts,
                    origins=[c.sourceInvestigationId for c in evidence.candidates],
                )
                if request is None:
                    return fresh
                return self.worker.explorer.result(
                    fresh,
                    run,
                    request,
                    facts,
                    [record.classificationRef],
                    "interpretation",
                )
            if run.stage == "interpretation":
                facts = {
                    "evidenceIds": [
                        record.classificationRef.sha256,
                        evidence.sourceRef.sha256,
                        evidence.retainedVerificationRef.sha256,
                    ],
                    "profile": evidence.profile.model_dump(),
                    "conclusion": record.snapshot.conclusion.model_dump(),
                    "unknowns": evidence.unknowns,
                }
                fresh, interpretation = self.worker.explorer.request(
                    record,
                    run,
                    facts,
                    operation="interpretation",
                    origins=[c.sourceInvestigationId for c in evidence.candidates],
                )
                if interpretation is None:
                    return fresh
                ref = run.turns[-1].responseRef
                run.outputRefs.append(ref)
                run.stage, run.status = "done", "completed"
                conclusion = fresh.snapshot.conclusion.model_copy(
                    update={"interpretationRef": ref}
                )
                # The validated response and its completion marker remain separate from deterministic evidence.
                agent_ref = AnalysisStore(
                    self.store.root, fresh.snapshot.id, "agent"
                ).document("run", run)
                return self.store.commit(
                    fresh.snapshot.id,
                    "phase.started",
                    "Preparing downloads…",
                    status=Status.EXPORTING,
                    update={
                        "conclusion": conclusion.model_dump(),
                        "agent": agent_summary(run).model_dump(),
                        "record": {"agentRef": agent_ref.model_dump()},
                        "memoryState": "pending",
                    },
                )
            raise EvidenceIntegrity()
        return self.store.commit(
            record.snapshot.id,
            "phase.started",
            "Preparing downloads…",
            status=Status.EXPORTING,
            update={"memoryState": "pending"},
        )

    def export(self, record, deadline):
        if time.monotonic() >= deadline:
            return self.worker.stop(
                record,
                Status.FAILED,
                "export_failure" if not record.exportRef else "memory_failure",
                "The finishing budget was reached. Verified evidence is preserved.",
            )
        evidence = ClassificationEvidence.model_validate(
            loads(read_reference(self.store.root, record.classificationRef))
        )
        if record.exportRef:
            return self.publish_memory(record, evidence)
        storage = AnalysisStore(self.store.root, record.snapshot.id, "export")
        try:
            case = read_case(read_reference(self.store.root, evidence.retainedCaseRef))
            report = load_evidence(
                self.store.root, evidence.retainedVerificationRef.owner
            )[1]
            code, basis = regression_bytes(case, report, evidence)
            run = load_run(self.store, record)
            interpretation = (
                AgentInterpretation.model_validate(
                    loads(
                        read_reference(
                            self.store.root,
                            record.snapshot.conclusion.interpretationRef,
                        )
                    )
                )
                if record.snapshot.conclusion.interpretationRef
                else None
            )
            report_data = report_bytes(
                case,
                report,
                evidence,
                record.snapshot.conclusion,
                record.snapshot.reduction,
                run,
                interpretation,
                memory_key(record.snapshot.id, record.classificationRef),
            )
            slug = "behavior-" + record.snapshot.id[:12]
            files = [
                storage.put(
                    slug + ".faultglass.json", encode(case.model_dump()), key="case"
                ),
                storage.put(slug + "_regression_test.py", code, key="regression-test"),
                storage.put("report.md", report_data, key="report"),
            ]
            manifest = ExportManifest(
                investigationId=record.snapshot.id,
                regressionTestId=str(
                    uuid5(NAMESPACE_URL, "faultglass:regression:" + record.snapshot.id)
                ),
                sourceCaseId=evidence.retainedCaseId,
                classificationEvidenceRef=record.classificationRef,
                files=files,
                expectationBasis=basis,
                createdAt=evidence.createdAt,
            )
            ref = storage.document("manifest", manifest)
            node = Node(
                label="RegressionTest",
                properties=dict(
                    id=manifest.regressionTestId,
                    investigation_id=record.snapshot.id,
                    created_at=manifest.createdAt,
                    case_sha256=files[0].sha256,
                    pytest_sha256=files[1].sha256,
                    case_artifact_ref=encode(files[0].model_dump()).decode(),
                    pytest_artifact_ref=encode(files[1].model_dump()).decode(),
                ),
            )
            edge = link(
                "DERIVED_TEST",
                evidence.retainedCaseId,
                manifest.regressionTestId,
                manifest.createdAt,
                ref,
            )
            phase = phase_for(record, "regression-export", [ref], [node], [edge])
            return self.store.commit(
                record.snapshot.id,
                "export.ready",
                "Downloads are ready. Saving investigation memory…",
                update={
                    "exportsReady": True,
                    "record": {"exportRef": ref.model_dump()},
                },
                outputs=[ref],
                phase=phase,
            )
        except (OSError, ValueError, EvidenceIntegrity):
            return self.worker.stop(
                record,
                Status.FAILED,
                "export_failure",
                "We could not prepare the downloads. Verified evidence is preserved.",
            )

    def publish_memory(self, record, evidence):
        manifest = ExportManifest.model_validate(
            loads(read_reference(self.store.root, record.exportRef))
        )
        try:
            delta, ref, updates = self.memory.prepare(record, evidence, manifest)
            complete = bool(
                record.snapshot.conclusion.familyId and delta.state == "recorded"
            )
            return self.store.commit(
                record.snapshot.id,
                "investigation.complete" if complete else "investigation.unresolved",
                "Investigation memory saved"
                if complete
                else "Evidence saved. No procedural update was made.",
                status=Status.COMPLETE if complete else Status.UNRESOLVED,
                update={
                    "memoryState": delta.state,
                    "terminalReason": {
                        "code": "evidence_complete"
                        if complete
                        else "family_unresolved",
                        "message": "Evidence, downloads, and investigation memory are verified."
                        if complete
                        else "The difference is verified, but its family remains unresolved.",
                    },
                    "record": {"memoryRef": ref.model_dump()},
                },
                outputs=[ref],
                memory_updates=updates,
            )
        except (OSError, ValueError, EvidenceIntegrity):
            return self.worker.stop(
                record,
                Status.FAILED,
                "memory_failure",
                "Downloads are ready, but investigation memory was not saved.",
            )
