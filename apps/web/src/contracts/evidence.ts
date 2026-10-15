export type Casefile = string;
export type Pairid = string;
export type Description = string | null;
export type Errorcategory =
  | (
      | "PARSE"
      | "SEMANTIC"
      | "TYPE"
      | "CONSTRAINT"
      | "RUNTIME"
      | "TIMEOUT"
      | "CRASH"
      | "UNKNOWN"
    )
  | null;
export type Kind =
  "baseline_matches_expected" | "explicit_result" | "explicit_error" | "none";
export type Columns = string[];
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | {
      [k: string]: JsonValue;
    };
export type Rows = JsonValue[][];
export type Id = string | null;
export type Notes = string | null;
export type Source = string | null;
export type Compareresult = boolean;
export type Ordering = "auto" | "ordered" | "unordered";
/**
 * @maxItems 8
 */
export type Postconditions =
  | []
  | [StateCheck]
  | [StateCheck, StateCheck]
  | [StateCheck, StateCheck, StateCheck]
  | [StateCheck, StateCheck, StateCheck, StateCheck]
  | [StateCheck, StateCheck, StateCheck, StateCheck, StateCheck]
  | [StateCheck, StateCheck, StateCheck, StateCheck, StateCheck, StateCheck]
  | [
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
    ]
  | [
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
      StateCheck,
    ];
export type Name = string;
export type Query = string;
export type Query1 = string;
export type Schemaversion = 1;
/**
 * @maxItems 32
 */
export type Setup = string[];
export type Title = string;
export type AdmissionSeconds = number;
/**
 * @maxItems 2
 */
export type Candidates =
  [] | [RankedCandidate] | [RankedCandidate, RankedCandidate];
export type Attempts = number;
export type AvgCostMs = number;
export type ChosenHistoryKey = string | null;
export type CostClass = "small" | "medium" | "large";
export type DefinitionSha256 = string;
export type After = string;
export type Before = string;
export type End = number;
export type Start = number;
export type Applicable = boolean;
export type InputCaseId = string;
export type OutputCaseId = string | null;
export type ProbeId = string;
export type ReasonCode =
  | "applicable"
  | "unsupported_shape"
  | "unmet_precondition"
  | "disabled"
  | "invalid_output"
  | "unchanged_output";
export type Bytes = number;
export type Id1 = string;
export type Kind1 = string;
export type Mediatype = string;
export type Owner = string;
export type Path = string;
export type Sha256 = string;
export type FeatureFit = number;
export type HistoricalYield = number;
export type InputCaseId1 = string;
export type MatchedFeatureIds = string[];
export type NormalizedCost = number;
export type Novelty = number;
export type OutputCaseId1 = string;
export type PairCapMs = 60000;
export type ProbeId1 = string;
export type Rank = number;
export type Reason = string;
export type Source1 = "history" | "structural";
export type Successes = number;
export type TargetFeatureIds = string[];
export type TemplateVersion = string;
export type Utility = number;
export type VersionAffinity = number;
export type CreatedAt = string;
export type FingerprintId = string;
export type InvestigationId = string;
export type Artifactbytes = number;
export type Cleanupseconds = number;
export type Logbytes = number;
export type Outputbytes = number;
export type Pairseconds = number;
export type Queryseconds = number;
export type Rows1 = number;
export type Startupseconds = number;
export type Novel = boolean;
export type Outcome = "selected" | "not_reproduced" | "unresolved";
export type PlannerVersion = "planner-v1";
export type RegistrySha256 = string;
export type Applicable1 = false;
export type HistoryKey = string | null;
export type InputCaseId2 = string;
export type OutputCaseId2 = null;
export type ProbeId2 = string;
export type ReasonCode1 =
  | "unsupported_shape"
  | "unmet_precondition"
  | "disabled"
  | "invalid_output"
  | "unchanged_output"
  | "duplicate_output"
  | "unknown_definition"
  | "incompatible_scope";
export type TransformedCaseRef = null;
/**
 * @maxItems 202
 */
export type Rejections = Rejection[];
export type Baseline = string;
export type ComparisonVersion = string;
export type Target = string;
export type SeedCaseId = string;
export type SeedManifestSha256 = string;
export type SelectedProbeId = string | null;
export type SelectionId = string;
export type Sequence = number;
export type TerminalReason =
  ("no_applicable_probe" | "budget_exhausted") | null;
export type Commitsha = string;
export type Id2 = string;
export type Imagedigest = string;
export type Imageref = string;
export type Label = string;
export type Lineage = "legacy-c" | "rust";
export type Repository = "FalkorDB/FalkorDB";
export type At = string;
export type Childid = string | null;
export type Probesequence = number;
/**
 * @maxItems 3
 */
export type References =
  | []
  | [EvidenceReference]
  | [EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference];
export type Revision = number;
export type Status =
  | "QUEUED"
  | "FINGERPRINTING"
  | "REPRODUCING"
  | "PLANNING"
  | "PROBING"
  | "REDUCING"
  | "CLASSIFYING"
  | "EXPORTING"
  | "COMPLETE"
  | "NOT_REPRODUCED"
  | "UNRESOLVED"
  | "CANCELLED"
  | "FAILED";
export type Id3 = string;
export type Investigationid = string;
export type Sequence1 = number;
export type Summary = string;
export type Type =
  | "investigation.created"
  | "phase.started"
  | "fingerprint.completed"
  | "graph.read"
  | "probe.candidates"
  | "probe.selected"
  | "engine.observed"
  | "divergence.detected"
  | "graph.write"
  | "cancellation.requested"
  | "investigation.not_reproduced"
  | "investigation.unresolved"
  | "investigation.cancelled"
  | "investigation.failed";
export type Decision1 = string | null;
export type Kind2 = "seed" | "selection" | "result";
/**
 * @maxItems 32
 */
export type Columns1 = string[];
export type Detail = string | null;
export type Engineversionid = string;
export type Errorcategory1 = string | null;
export type Rowcount = number | null;
export type Status1 = "result" | "error" | "timeout" | "crash";
export type Query2 = string | null;
/**
 * @maxItems 10
 */
export type References1 =
  | []
  | [EvidenceReference]
  | [EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference, EvidenceReference]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ];
export type Sequence2 = number;
/**
 * @maxItems 25
 */
export type Items = EvidenceItem[];
export type Nextcursor = number | null;
export type Revision1 = number;
export type Chargedbytes = number;
export type Maxartifactbytes = 67108864;
export type Maxevents = 512;
export type Maxprobes = 4;
export type Maxseconds = 900;
export type Reducercandidates = 0;
export type Reservedprobes = number;
export type Cancelrequestedat = string | null;
export type Classifying = false;
export type Exporting = false;
export type Reducing = false;
export type Createdat = string;
export type Deadlineat = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Engines = [EngineSpec, EngineSpec];
/**
 * @maxItems 80
 */
export type Evidence = EvidenceReference[];
export type Fingerprintid = string | null;
export type Finishedat = string | null;
export type Id4 = string;
export type Lasteventsequence = number;
export type Pairid1 = string;
export type Status2 =
  | "QUEUED"
  | "FINGERPRINTING"
  | "REPRODUCING"
  | "PLANNING"
  | "PROBING"
  | "REDUCING"
  | "CLASSIFYING"
  | "EXPORTING"
  | "COMPLETE"
  | "NOT_REPRODUCED"
  | "UNRESOLVED"
  | "CANCELLED"
  | "FAILED";
export type Phaseattempt = number;
export type Probesequence1 = number;
export type Revision2 = number;
export type Schemaversion1 = 1;
export type Seedevidenceid = string | null;
export type Startedat = string | null;
export type Status3 =
  | "QUEUED"
  | "FINGERPRINTING"
  | "REPRODUCING"
  | "PLANNING"
  | "PROBING"
  | "REDUCING"
  | "CLASSIFYING"
  | "EXPORTING"
  | "COMPLETE"
  | "NOT_REPRODUCED"
  | "UNRESOLVED"
  | "CANCELLED"
  | "FAILED";
export type Code =
  | "no_applicable_probe"
  | "budget_exhausted"
  | "analysis_unavailable"
  | "not_reproduced"
  | "cancelled"
  | "recovery_required"
  | "integrity_failure"
  | "execution_failure"
  | "storage_failure"
  | "cleanup_required"
  | "registry_changed";
export type Message = string;
export type Title1 = string;
export type Updatedat = string;
export type Workspaceid = "falkordb-core";
export type Baselineid = string;
export type Id5 = string;
export type Label1 = string;
export type Targetid = string;
export type Bytes1 = number;
export type Id6 = string;
export type Kind3 = string;
export type Mediatype1 = string;
export type Path1 = string;
export type Sha2561 = string;
export type Artifacts = ArtifactRef[];
export type Casecontenthash = string;
export type Baselineobservationdigest = string;
export type Changeddimensions = string[];
export type Comparisonversion = string;
export type Kind4 = "status" | "error" | "result" | "postcondition" | "mixed";
export type Signature = string;
export type Targetobservationdigest = string;
export type Code1 = string;
export type Enginerole = ("baseline" | "target") | null;
export type Message1 = string;
export type Stage = string;
export type Finishedat1 = string;
export type Engineversionid1 = string;
export type Category =
  | "PARSE"
  | "SEMANTIC"
  | "TYPE"
  | "CONSTRAINT"
  | "RUNTIME"
  | "TIMEOUT"
  | "CRASH"
  | "UNKNOWN";
export type Detail1 = string;
export type Normalizedcode = string | null;
export type Name1 = string;
export type Status4 = "result" | "error";
export type Value = Result | EngineError;
export type Columns2 = string[];
export type Ordered = boolean;
export type Rows2 = JsonValue[][];
export type Postconditions1 = CheckObservation[];
export type Status5 = "result" | "error" | "timeout" | "crash";
export type Durationms = number;
export type Oracleassessment = {
  [k: string]: "match" | "mismatch" | "not_evaluated";
} | null;
export type Outcome1 = "reproduced" | "not_reproduced" | "failed";
export type Pairid2 = string;
export type Runid = string;
export type Startedat1 = string;

export interface EvidenceContracts {
  admission: Admission;
  case: FaultCase;
  decision: Decision;
  engine: EngineSpec;
  event: Event;
  evidence: EvidencePage;
  investigation: Snapshot;
  pair: EnginePair;
  report: RunReport;
}
export interface Admission {
  caseFile: Casefile;
  pairId: Pairid;
}
export interface FaultCase {
  description?: Description;
  expectation?: Expectation | null;
  id?: Id;
  metadata?: Metadata | null;
  observation: ObservationSpec;
  parameters?: Parameters1;
  query: Query1;
  schemaVersion: Schemaversion;
  setup: Setup;
  title: Title;
}
export interface Expectation {
  errorCategory?: Errorcategory;
  kind: Kind;
  value?: ExpectedResult | null;
}
export interface ExpectedResult {
  columns: Columns;
  rows: Rows;
}
export interface Metadata {
  notes?: Notes;
  source?: Source;
}
export interface ObservationSpec {
  compareResult: Compareresult;
  ordering: Ordering;
  postconditions?: Postconditions;
}
export interface StateCheck {
  name: Name;
  parameters?: Parameters;
  query: Query;
}
export interface Parameters {
  [k: string]: JsonValue;
}
export interface Parameters1 {
  [k: string]: JsonValue;
}
export interface Decision {
  admission_seconds?: AdmissionSeconds;
  candidates: Candidates;
  created_at: CreatedAt;
  fingerprint_id: FingerprintId;
  investigation_id: InvestigationId;
  limits: RunLimits;
  novel: Novel;
  outcome: Outcome;
  planner_version?: PlannerVersion;
  registry_sha256: RegistrySha256;
  rejections: Rejections;
  scope: VersionScope;
  seed_case_id: SeedCaseId;
  seed_manifest_sha256: SeedManifestSha256;
  selected_probe_id: SelectedProbeId;
  selection_id: SelectionId;
  sequence?: Sequence;
  source_snapshot_ref: EvidenceReference;
  terminal_reason?: TerminalReason;
  transformed_case_ref: EvidenceReference | null;
}
export interface RankedCandidate {
  attempts: Attempts;
  avg_cost_ms: AvgCostMs;
  chosen_history_key: ChosenHistoryKey;
  cost_class: CostClass;
  definition_sha256: DefinitionSha256;
  edit: SourceEdit;
  eligibility: ProbeEligibility;
  feature_fit: FeatureFit;
  historical_yield: HistoricalYield;
  input_case_id: InputCaseId1;
  matched_feature_ids: MatchedFeatureIds;
  normalized_cost: NormalizedCost;
  novelty: Novelty;
  output_case_id: OutputCaseId1;
  pair_cap_ms?: PairCapMs;
  probe_id: ProbeId1;
  rank: Rank;
  reason: Reason;
  source: Source1;
  successes: Successes;
  target_feature_ids: TargetFeatureIds;
  template_version: TemplateVersion;
  transformed_case_ref: EvidenceReference;
  utility: Utility;
  version_affinity: VersionAffinity;
}
export interface SourceEdit {
  after: After;
  before: Before;
  end: End;
  start: Start;
}
export interface ProbeEligibility {
  applicable: Applicable;
  input_case_id: InputCaseId;
  output_case_id?: OutputCaseId;
  probe_id: ProbeId;
  reason_code: ReasonCode;
  transformed_case_ref?: EvidenceReference | null;
}
export interface EvidenceReference {
  bytes: Bytes;
  id: Id1;
  kind: Kind1;
  mediaType: Mediatype;
  owner: Owner;
  path: Path;
  sha256: Sha256;
}
export interface RunLimits {
  artifactBytes?: Artifactbytes;
  cleanupSeconds?: Cleanupseconds;
  logBytes?: Logbytes;
  outputBytes?: Outputbytes;
  pairSeconds?: Pairseconds;
  querySeconds?: Queryseconds;
  rows?: Rows1;
  startupSeconds?: Startupseconds;
}
export interface Rejection {
  applicable?: Applicable1;
  history_key?: HistoryKey;
  input_case_id: InputCaseId2;
  output_case_id?: OutputCaseId2;
  probe_id: ProbeId2;
  reason_code: ReasonCode1;
  transformed_case_ref?: TransformedCaseRef;
}
export interface VersionScope {
  baseline: Baseline;
  comparison_version: ComparisonVersion;
  target: Target;
}
export interface EngineSpec {
  commitSha: Commitsha;
  id: Id2;
  imageDigest: Imagedigest;
  imageRef: Imageref;
  label: Label;
  lineage: Lineage;
  repository: Repository;
}
export interface Event {
  at: At;
  data: EventData;
  id: Id3;
  investigationId: Investigationid;
  phase: Status;
  sequence: Sequence1;
  summary: Summary;
  type: Type;
}
export interface EventData {
  childId?: Childid;
  probeSequence: Probesequence;
  references?: References;
  revision: Revision;
  status: Status;
}
export interface EvidencePage {
  items: Items;
  nextCursor: Nextcursor;
  revision: Revision1;
}
export interface EvidenceItem {
  decision?: Decision1;
  kind: Kind2;
  observations?: PairedSummary | null;
  query?: Query2;
  references: References1;
  sequence: Sequence2;
}
export interface PairedSummary {
  baseline: ObservationSummary;
  target: ObservationSummary;
}
export interface ObservationSummary {
  columns: Columns1;
  detail: Detail;
  engineVersionId: Engineversionid;
  errorCategory: Errorcategory1;
  rowCount: Rowcount;
  status: Status1;
}
export interface Snapshot {
  budget: Budget;
  cancelRequestedAt: Cancelrequestedat;
  capabilities: Capabilities;
  createdAt: Createdat;
  deadlineAt: Deadlineat;
  engines: Engines;
  evidence: Evidence;
  fingerprintId: Fingerprintid;
  finishedAt: Finishedat;
  id: Id4;
  lastEventSequence: Lasteventsequence;
  pairId: Pairid1;
  phase: Status2;
  phaseAttempt: Phaseattempt;
  probeSequence: Probesequence1;
  revision: Revision2;
  schemaVersion: Schemaversion1;
  seedEvidenceId: Seedevidenceid;
  startedAt: Startedat;
  status: Status3;
  terminalReason: Reason1 | null;
  title: Title1;
  updatedAt: Updatedat;
  workspaceId: Workspaceid;
}
export interface Budget {
  chargedBytes: Chargedbytes;
  maxArtifactBytes: Maxartifactbytes;
  maxEvents: Maxevents;
  maxProbes: Maxprobes;
  maxSeconds: Maxseconds;
  reducerCandidates: Reducercandidates;
  reservedProbes: Reservedprobes;
}
export interface Capabilities {
  classifying: Classifying;
  exporting: Exporting;
  reducing: Reducing;
}
export interface Reason1 {
  code: Code;
  message: Message;
}
export interface EnginePair {
  baselineId: Baselineid;
  id: Id5;
  label: Label1;
  targetId: Targetid;
}
export interface RunReport {
  artifacts: Artifacts;
  caseContentHash: Casecontenthash;
  divergence?: Divergence | null;
  failure?: Failure | null;
  finishedAt: Finishedat1;
  observations?: PairedObservation | null;
  oracleAssessment?: Oracleassessment;
  outcome: Outcome1;
  pairId: Pairid2;
  runId: Runid;
  startedAt: Startedat1;
}
export interface ArtifactRef {
  bytes: Bytes1;
  id: Id6;
  kind: Kind3;
  mediaType: Mediatype1;
  path: Path1;
  sha256: Sha2561;
}
export interface Divergence {
  baselineObservationDigest: Baselineobservationdigest;
  changedDimensions: Changeddimensions;
  comparisonVersion: Comparisonversion;
  kind: Kind4;
  signature: Signature;
  targetObservationDigest: Targetobservationdigest;
}
export interface Failure {
  code: Code1;
  engineRole?: Enginerole;
  message: Message1;
  stage: Stage;
}
export interface PairedObservation {
  baseline: EngineObservation;
  target: EngineObservation;
}
export interface EngineObservation {
  engineVersionId: Engineversionid1;
  error?: EngineError | null;
  postconditions?: Postconditions1;
  result?: Result | null;
  status: Status5;
  timing: Timing;
}
export interface EngineError {
  category: Category;
  detail: Detail1;
  normalizedCode?: Normalizedcode;
}
export interface CheckObservation {
  name: Name1;
  status: Status4;
  value: Value;
}
export interface Result {
  columns: Columns2;
  ordered: Ordered;
  rows: Rows2;
}
export interface Timing {
  durationMs: Durationms;
}
