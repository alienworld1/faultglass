from datetime import UTC, datetime
from importlib.resources import files

from falkordb import FalkorDB
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from .canonicalize import CANONICALIZATION_VERSION
from .context_artifacts import load_evidence, read_reference, verify_sidecar
from .context_config import ContextConfig
from .context_errors import (
    ContextError,
    ContextUnavailable,
    EvidenceIntegrity,
    IdentityConflict,
    SchemaIncompatible,
)
from .context_lock import ContextLease
from .context_models import (
    CONTEXT_SCHEMA_VERSION,
    ENDPOINTS,
    Edge,
    FingerprintHistory,
    HistoryCandidate,
    InvestigationContext,
    Node,
    PairedRunContext,
    Phase,
    SavedContext,
    SchemaReady,
    VersionScope,
    evidence_id,
    fingerprint_id,
)
from .context_phase import build_phase, engine_identity
from .feature_catalog import CATALOG, FEATURE_IDS
from .fingerprint import FINGERPRINT_VERSION
from .jsonio import digest, encode, loads

LABELS = tuple(
    dict.fromkeys(label for endpoints in ENDPOINTS.values() for label in endpoints)
)
INDEXES = [(label, "id") for label in LABELS] + [
    (label, "status") for label in ("Investigation", "FaultFamily")
]


def query_text(name):
    return files("faultglass").joinpath("queries", name + ".cypher").read_text()


class GraphRepository:
    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig.from_environment()
        self.client = None
        self.graph = None

    def close(self):
        if self.client:
            self.client.close()
        self.client = self.graph = None

    def _connect(self):
        if self.graph is None:
            try:
                self.client = FalkorDB(
                    host=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    socket_connect_timeout=2,
                    socket_timeout=5,
                    retry=Retry(NoBackoff(), 0),
                    retry_on_error=[],
                    cluster_error_retry_attempts=0,
                )
                self.graph = self.client.select_graph(self.config.graph)
            except (RedisError, OSError, ValueError):
                self.close()
                raise ContextUnavailable() from None

    def _query(self, name, params=None, *, write=False, timeout=2000):
        self._connect()
        try:
            method = self.graph.query if write else self.graph.ro_query
            return method(query_text(name), params or {}, timeout=timeout).result_set
        except (RedisError, OSError):
            raise ContextUnavailable() from None

    def _audit(self):
        if (
            self._query("schema-audit")
            or self._query("edge-duplicates")
            or self._query("feature-audit", {"ids": list(FEATURE_IDS)})
        ):
            raise SchemaIncompatible()
        if any(row[0] not in LABELS for row in self._query("labels")):
            raise SchemaIncompatible()
        for kind, source, target in self._query("edge-audit"):
            if (
                kind not in ENDPOINTS
                or source != [ENDPOINTS[kind][0]]
                or target != [ENDPOINTS[kind][1]]
            ):
                raise SchemaIncompatible()
        for row in self._query("versions"):
            if row != [
                CONTEXT_SCHEMA_VERSION,
                CANONICALIZATION_VERSION,
                FINGERPRINT_VERSION,
            ]:
                raise SchemaIncompatible()

    def _indexes(self):
        found = set()
        for label, properties, types, entity, status in self._query(
            "indexes", timeout=2000
        ):
            if label not in LABELS or entity != "NODE" or status != "OPERATIONAL":
                raise SchemaIncompatible()
            for prop in properties:
                if types.get(prop) != ["RANGE"]:
                    raise SchemaIncompatible()
                found.add((label, prop))
        return found

    def _catalog(self):
        rows = self._query("identities", {"ids": list(FEATURE_IDS)})
        actual = {}
        for labels, props in rows:
            if labels != ["Feature"] or props["id"] in actual:
                raise SchemaIncompatible()
            expected = next(
                (entry for entry in CATALOG if entry["id"] == props["id"]), None
            )
            if not expected or any(
                props.get(key) != value for key, value in expected.items()
            ):
                raise SchemaIncompatible()
            try:
                Node(label="Feature", properties=dict(props))
            except ValueError:
                raise SchemaIncompatible() from None
            actual[props["id"]] = props
        return actual

    def ensure_schema(self) -> SchemaReady:
        with ContextLease():
            # GRAPH.QUERY introspection initializes a genuinely empty graph without fake nodes.
            self._query("indexes", write=True)
            self._audit()
            actual = self._catalog()
            found = self._indexes()
            for label, prop in INDEXES:
                if (label, prop) not in found:
                    suffix = "-status" if prop == "status" else ""
                    self._query("index-" + label + suffix, write=True, timeout=10000)
            if not set(INDEXES).issubset(self._indexes()):
                raise SchemaIncompatible()
            now = datetime.now(UTC).isoformat()
            self._query(
                "catalog",
                {
                    "features": [
                        {**entry, "created_at": now}
                        for entry in CATALOG
                        if entry["id"] not in actual
                    ]
                },
                write=True,
            )
            self._assert_ready()
            return SchemaReady(indexes=len(INDEXES), features=len(FEATURE_IDS))

    def _assert_ready(self):
        self._connect()
        try:
            for name, expected in (("TIMEOUT_MAX", 10000), ("TIMEOUT_DEFAULT", 2000)):
                values = self.client.connection.execute_command(
                    "GRAPH.CONFIG", "GET", name
                )
                if int(values[1]) != expected:
                    raise SchemaIncompatible()
        except (RedisError, OSError):
            raise ContextUnavailable() from None
        self._audit()
        if not set(INDEXES).issubset(self._indexes()) or set(self._catalog()) != set(
            FEATURE_IDS
        ):
            raise SchemaIncompatible()
        self._connect()
        try:
            plan = str(self.graph.explain(query_text("lookup"), {"id": "readiness"}))
            if "Index Scan" not in plan:
                raise SchemaIncompatible()
        except RedisError:
            raise ContextUnavailable() from None

    def _lookup(self, identity):
        rows = self._query("lookup", {"id": identity})
        if len(rows) > 1:
            raise IdentityConflict()
        return dict(rows[0][0]) if rows else None

    def _receipt(self, phase):
        existing = self._lookup(phase.investigation_id)
        if existing is None:
            return None
        if (
            existing.get("context_phase_key") != phase.phase_key
            or existing.get("context_payload_sha256") != phase.payload_sha256
            or not existing.get("context_recorded_at")
        ):
            raise IdentityConflict()
        self._inspect(phase.investigation_id)
        return SavedContext(
            investigation_id=phase.investigation_id,
            fault_case_id=phase.fault_case_id,
            fingerprint_id=phase.fingerprint_id,
            context_phase_key=phase.phase_key,
            context_payload_sha256=phase.payload_sha256,
            reused=True,
        )

    def record_seed_context(self, seed_evidence_id: str) -> SavedContext:
        evidence_id(seed_evidence_id)
        with ContextLease():
            phase = build_phase(self.config.artifact_root, seed_evidence_id)
            self._assert_ready()
            receipt = self._receipt(phase)
            if receipt:
                return receipt
            self._check_immutable(phase)
            try:
                self._query("record-seed", self._parameters(phase), write=True)
            except ContextUnavailable:
                self.close()
                receipt = self._receipt(phase)
                if receipt:
                    return receipt
                raise ContextError(
                    "Saving was interrupted. Retry with the same evidence ID to check completion."
                ) from None
            receipt = self._receipt(phase)
            if receipt is None:
                raise ContextError(
                    "Saving was interrupted. Retry with the same evidence ID to check completion."
                )
            return receipt.model_copy(update={"reused": False})

    def _check_immutable(self, phase: Phase, *, require_complete=False):
        expected = {node.properties["id"]: node for node in phase.nodes}
        seen = set()
        for labels, props in self._query("identities", {"ids": list(expected)}):
            identity = props["id"]
            node = expected[identity]
            if identity in seen or labels != [node.label]:
                raise IdentityConflict()
            seen.add(identity)
            Node(label=node.label, properties=dict(props))
            representative = (
                {"created_at", "artifact_ref", "title"}
                if node.label in ("FaultCase", "Fingerprint", "EngineVersion")
                else set()
            )
            if node.label == "Investigation" and props.get("runtime_version"):
                representative |= {
                    "status",
                    "updated_at",
                    "terminal_reason",
                    "created_at",
                }
                if not props.get("context_recorded_at") and not require_complete:
                    representative |= set(node.properties) - set(props)
                elif props.get("seed_status") != node.properties.get("status"):
                    raise IdentityConflict()
            for key, value in node.properties.items():
                if key not in representative and props.get(key) != value:
                    raise IdentityConflict()
        if require_complete and seen != set(expected):
            raise EvidenceIntegrity()
        expected_edges = {edge.properties["id"]: edge for edge in phase.edges}
        seen = set()
        for kind, source, target, props in self._query(
            "edge-identities", {"ids": list(expected_edges)}
        ):
            identity = props["id"]
            edge = expected_edges[identity]
            if identity in seen or (kind, source, target) != (
                edge.type,
                edge.source_id,
                edge.target_id,
            ):
                raise IdentityConflict()
            seen.add(identity)
            Edge(
                type=kind,
                source_label=edge.source_label,
                source_id=source,
                target_label=edge.target_label,
                target_id=target,
                properties=dict(props),
            )
            for key, value in edge.properties.items():
                if (
                    key
                    not in (
                        ("source_id", "created_at")
                        if kind in ("HAS_FINGERPRINT", "USES_FEATURE")
                        else ()
                    )
                    and props.get(key) != value
                ):
                    raise IdentityConflict()

        if require_complete and seen != set(expected_edges):
            raise EvidenceIntegrity()

    def _parameters(self, phase):
        by_label = {}
        for node in phase.nodes:
            by_label.setdefault(node.label, []).append(node.properties)

        def edge(kind, role=None):
            candidates = [e for e in phase.edges if e.type == kind]
            return (
                candidates[0 if role != "target" else 1].properties
                if candidates
                else {}
            )

        return {
            "investigation": by_label["Investigation"][0],
            "case_node": by_label["FaultCase"][0],
            "fingerprint": by_label["Fingerprint"][0],
            "baseline_run": by_label["Run"][0],
            "target_run": by_label["Run"][1],
            "baseline_engine": by_label["EngineVersion"][0],
            "target_engine": by_label["EngineVersion"][1],
            "divergences": by_label.get("Divergence", []),
            "feature_ids": [
                e.target_id for e in phase.edges if e.type == "USES_FEATURE"
            ],
            "uses_features": [
                e.model_dump() for e in phase.edges if e.type == "USES_FEATURE"
            ],
            "started_from": edge("STARTED_FROM"),
            "has_fingerprint": edge("HAS_FINGERPRINT"),
            "executed_baseline": edge("EXECUTED_AS"),
            "executed_target": edge("EXECUTED_AS", "target"),
            "on_baseline": edge("ON_VERSION"),
            "on_target": edge("ON_VERSION", "target"),
            "produced_baseline": edge("PRODUCED"),
            "produced_target": edge("PRODUCED", "target"),
            "payload_sha256": phase.payload_sha256,
            "recorded_at": datetime.now(UTC).isoformat(),
        }

    def get_investigation_context(self, seed_evidence_id: str) -> InvestigationContext:
        evidence_id(seed_evidence_id)
        self._assert_ready()
        return self._inspect(seed_evidence_id)

    def _inspect(self, run_id):
        try:
            return self._read_investigation(run_id)
        except ContextError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError):
            raise EvidenceIntegrity() from None

    def _read_investigation(self, run_id):
        rows = self._query(
            "investigation", {"id": run_id, "version": FINGERPRINT_VERSION}
        )
        if not rows:
            if self._lookup(run_id):
                raise EvidenceIntegrity()
            raise ContextError("We couldn't find that saved investigation.")
        if len(rows) != 2:
            raise EvidenceIntegrity()
        i, case, fp, features = rows[0][:4]
        roles = [row[4].get("role") for row in rows]
        if roles != ["baseline", "target"] or any(
            row[:4] != rows[0][:4] for row in rows
        ):
            raise EvidenceIntegrity()
        root = self.config.artifact_root
        phase = build_phase(root, run_id, persist=False)
        self._check_immutable(phase, require_complete=True)
        if (
            i.get("context_payload_sha256") != phase.payload_sha256
            or i.get("context_phase_key") != phase.phase_key
            or fp["id"] != phase.fingerprint_id
            or case["id"] != phase.fault_case_id
        ):
            raise EvidenceIntegrity()
        expected_features = sorted(
            e.target_id for e in phase.edges if e.type == "USES_FEATURE"
        )
        if sorted(features) != expected_features:
            raise EvidenceIntegrity()
        _source_case, report, _, engines, _ = load_evidence(root, run_id)
        sidecar = verify_sidecar(root, run_id)
        artifacts = [*sidecar, read_ref(i["report_artifact_ref"])]
        divergence = None
        for row, role, engine in zip(rows, roles, engines, strict=True):
            run, graph_engine, diff = row[4:]
            if graph_engine["id"] != engine_identity(engine) or run[
                "observation_sha256"
            ] != digest(getattr(report.observations, role).model_dump()):
                raise EvidenceIntegrity()
            artifacts.append(read_ref(run["artifact_ref"]))
            if diff:
                if (
                    not report.divergence
                    or diff["signature"] != report.divergence.signature
                    or diff["stable"] is not False
                ):
                    raise EvidenceIntegrity()
                divergence = Node(label="Divergence", properties=dict(diff))
            elif report.divergence:
                raise EvidenceIntegrity()
        for props in (case, fp):
            read_reference(root, read_ref(props["artifact_ref"]))
        for ref in artifacts:
            read_reference(root, ref)
        return InvestigationContext(
            investigation=Node(label="Investigation", properties=dict(i)),
            case=Node(label="FaultCase", properties=dict(case)),
            fingerprint=Node(label="Fingerprint", properties=dict(fp)),
            features=sorted(features),
            runs=[
                PairedRunContext(
                    run=Node(label="Run", properties=dict(row[4])),
                    engine=Node(label="EngineVersion", properties=dict(row[5])),
                )
                for row in rows
            ],
            divergence=divergence,
            artifacts=list({ref.id: ref for ref in artifacts}.values()),
        )

    def get_fingerprint_history(
        self,
        identity: str,
        scope: VersionScope | None = None,
        limit: int = 25,
        exclude_id: str | None = None,
        *,
        overflow_check: bool = False,
    ) -> FingerprintHistory:
        fingerprint_id(identity)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Choose a history limit from 1 to 100.")
        if exclude_id is not None:
            evidence_id(exclude_id)
        if scope is not None:
            scope = VersionScope.model_validate(
                scope.model_dump() if isinstance(scope, VersionScope) else scope
            )
        self._assert_ready()
        rows = self._query("identities", {"ids": [identity]})
        if not rows:
            raise ContextError("We couldn't find that fingerprint.")
        if len(rows) != 1 or rows[0][0] != ["Fingerprint"]:
            raise EvidenceIntegrity()
        read_reference(self.config.artifact_root, read_ref(rows[0][1]["artifact_ref"]))
        candidates = []
        rows = self._query(
            "history",
            {
                "id": identity,
                "exclude_id": exclude_id or "",
                "limit": 101 if overflow_check else limit,
            },
        )
        if overflow_check and len(rows) > 100:
            raise ContextError("Related evidence exceeds the supported planning limit.")
        for family, probe, stats, features in rows:
            try:
                Node(label="FaultFamily", properties=dict(family))
                Node(label="Probe", properties=dict(probe))
                if (
                    stats.get("source_kind") != "verified_classification"
                    or not stats.get("id")
                    or not stats.get("created_at")
                ):
                    raise EvidenceIntegrity()
                read_reference(self.config.artifact_root, read_ref(stats["source_id"]))
                version_scope = VersionScope.model_validate(
                    loads(stats["version_scope"])
                )
                if (
                    encode(version_scope.model_dump()).decode()
                    != stats["version_scope"]
                ):
                    raise EvidenceIntegrity()
                sources = self._query(
                    "history-provenance",
                    {
                        "family_id": family["id"],
                        "exclude_id": exclude_id or "",
                        "scope": stats["version_scope"],
                    },
                )
                supporting = []
                for episode_id, source_id, weight, edge_id in sources:
                    if (
                        not edge_id
                        or not isinstance(weight, (float, int))
                        or isinstance(weight, bool)
                        or not 0 <= weight < float("inf")
                    ):
                        raise EvidenceIntegrity()
                    reference = read_ref(source_id)
                    read_reference(self.config.artifact_root, reference)
                    episode = self._inspect(evidence_id(episode_id))
                    actual_scope = VersionScope(
                        baseline=episode.runs[0].engine.properties["id"],
                        target=episode.runs[1].engine.properties["id"],
                        comparison_version=episode.divergence.properties[
                            "comparison_version"
                        ],
                    )
                    if actual_scope != version_scope:
                        raise EvidenceIntegrity()
                    supporting.append(episode)
                candidates.append(
                    HistoryCandidate(
                        family_id=family["id"],
                        family_status=family["status"],
                        probe_id=probe["id"],
                        probe_type=probe["type"],
                        template_version=probe["template_version"],
                        feature_ids=sorted(features),
                        feature_overlap=len(features),
                        attempts=stats["attempts"],
                        successes=stats["successes"],
                        avg_cost_ms=stats["avg_cost_ms"],
                        version_scope=version_scope,
                        exact_pair_match=scope is not None and version_scope == scope,
                        supporting_episodes=supporting,
                        path_edges=self._history_edges(
                            identity, family["id"], probe["id"], stats, sources
                        ),
                    )
                )
            except (ValueError, KeyError, TypeError, AttributeError):
                raise ContextError("Related evidence could not be verified.") from None
        return FingerprintHistory(fingerprint_id=identity, candidates=candidates)

    def _history_edges(self, fingerprint, family, probe, stats, sources):
        edges = [
            Edge(
                type="EFFECTIVE_FOR",
                source_label="Probe",
                source_id=probe,
                target_label="FaultFamily",
                target_id=family,
                properties=dict(stats),
            )
        ]
        for kind, source, target, props in self._query(
            "history-paths",
            {
                "fingerprint": fingerprint,
                "family": family,
                "probe": probe,
                "classifications": [row[3] for row in sources],
            },
        ):
            source_label, target_label = ENDPOINTS[kind]
            edge = Edge(
                type=kind,
                source_label=source_label,
                source_id=source,
                target_label=target_label,
                target_id=target,
                properties=dict(props),
            )
            if kind in ("INVOLVES_FEATURE", "MATCHES_FAMILY"):
                read_reference(self.config.artifact_root, read_ref(props["source_id"]))
            edges.append(edge)
        return sorted(
            {edge.properties["id"]: edge for edge in edges}.values(),
            key=lambda edge: edge.properties["id"],
        )


def read_ref(value):
    from .context_models import EvidenceReference

    return EvidenceReference.model_validate(loads(value))
