from .analysis_artifacts import AnalysisStore
from .analysis_models import MemoryDelta, MemoryEntry, MemoryStatistics
from .context_artifacts import read_reference
from .context_errors import EvidenceIntegrity
from .context_models import Edge
from .graph_repository import read_ref
from .jsonio import digest, encode


def memory_key(job_id, classification_ref):
    return digest(
        {
            "investigation": job_id,
            "classification": classification_ref.sha256,
            "policy": "procedural-memory-v1",
        }
    )


def compute_entry(probe, family_id, scope, existing):
    identity = digest(
        {"probe": probe.probeId, "family": family_id, "scope": scope.model_dump()}
    )
    if existing:
        Edge(
            type="EFFECTIVE_FOR",
            source_label="Probe",
            source_id=probe.probeId,
            target_label="FaultFamily",
            target_id=family_id,
            properties=existing,
        )
        before = MemoryStatistics(
            attempts=existing["attempts"],
            successes=existing["successes"],
            avgCostMs=existing["avg_cost_ms"],
            lastSeenAt=existing["last_seen_at"],
        )
    else:
        before = MemoryStatistics(
            attempts=0, successes=0, avgCostMs=0.0, lastSeenAt=probe.observedAt
        )
    increment = int(probe.contribution is not None)
    after = MemoryStatistics(
        attempts=before.attempts + 1,
        successes=before.successes + increment,
        avgCostMs=round(
            (before.avgCostMs * before.attempts + probe.durationMs)
            / (before.attempts + 1),
            6,
        ),
        lastSeenAt=probe.observedAt,
    )
    return MemoryEntry(
        edgeId=identity,
        probeId=probe.probeId,
        familyId=family_id,
        selectionId=probe.selectionId,
        evidenceRefs=[probe.planRef, probe.resultRef, probe.reportRef],
        successIncrement=increment,
        reason=probe.contribution or "observed_only",
        costMs=probe.durationMs,
        before=before,
        after=after,
    )


class MemoryWriter:
    def __init__(self, store):
        self.store = store

    def prepare(self, record, evidence, manifest):
        for file in manifest.files:
            read_reference(self.store.root, file)
        entries, originals = [], {}
        if record.snapshot.conclusion.familyId:
            family = record.snapshot.conclusion.familyId
            for probe in evidence.profile.probes:
                identity = digest(
                    {
                        "probe": probe.probeId,
                        "family": family,
                        "scope": evidence.profile.scope.model_dump(),
                    }
                )
                rows = self.store.repository._query(
                    "edge-identities", {"ids": [identity]}
                )
                if len(rows) > 1:
                    raise EvidenceIntegrity()
                existing = dict(rows[0][3]) if rows else None
                if existing:
                    read_reference(self.store.root, read_ref(existing["source_id"]))
                entry = compute_entry(probe, family, evidence.profile.scope, existing)
                if existing:
                    entry.evidenceRefs.append(read_ref(existing["source_id"]))
                entries.append(entry)
                originals[identity] = existing or {}
        delta = MemoryDelta(
            investigationId=record.snapshot.id,
            commitKey=memory_key(record.snapshot.id, record.classificationRef),
            classificationRef=record.classificationRef,
            exportManifestRef=record.exportRef,
            scope=evidence.profile.scope,
            entries=entries,
            state="recorded" if entries else "ineligible",
            reason=None
            if entries
            else "No supported family or eligible completed experiments.",
        )
        ref = AnalysisStore(
            self.store.root, record.snapshot.id, "classification"
        ).document("memory", delta)
        updates = []
        for entry in entries:
            props = dict(
                id=entry.edgeId,
                created_at=originals[entry.edgeId].get(
                    "created_at", entry.after.lastSeenAt
                ),
                source_kind="verified_classification",
                source_id=encode(ref.model_dump()).decode(),
                attempts=entry.after.attempts,
                successes=entry.after.successes,
                avg_cost_ms=entry.after.avgCostMs,
                last_seen_at=entry.after.lastSeenAt,
                version_scope=encode(delta.scope.model_dump()).decode(),
            )
            Edge(
                type="EFFECTIVE_FOR",
                source_label="Probe",
                source_id=entry.probeId,
                target_label="FaultFamily",
                target_id=entry.familyId,
                properties=props,
            )
            updates.append(
                {
                    "probeId": entry.probeId,
                    "familyId": entry.familyId,
                    "properties": props,
                    "beforeAttempts": entry.before.attempts,
                    "beforeProperties": originals[entry.edgeId],
                }
            )
        return delta, ref, updates
