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
export type Commitsha = string;
export type Id1 = string;
export type Imagedigest = string;
export type Imageref = string;
export type Label = string;
export type Lineage = "legacy-c" | "rust";
export type Repository = "FalkorDB/FalkorDB";
export type Baselineid = string;
export type Id2 = string;
export type Label1 = string;
export type Targetid = string;
export type Bytes = number;
export type Id3 = string;
export type Kind1 = string;
export type Mediatype = string;
export type Path = string;
export type Sha256 = string;
export type Artifacts = ArtifactRef[];
export type Casecontenthash = string;
export type Baselineobservationdigest = string;
export type Changeddimensions = string[];
export type Comparisonversion = string;
export type Kind2 = "status" | "error" | "result" | "postcondition" | "mixed";
export type Signature = string;
export type Targetobservationdigest = string;
export type Code = string;
export type Enginerole = ("baseline" | "target") | null;
export type Message = string;
export type Stage = string;
export type Finishedat = string;
export type Engineversionid = string;
export type Category =
  | "PARSE"
  | "SEMANTIC"
  | "TYPE"
  | "CONSTRAINT"
  | "RUNTIME"
  | "TIMEOUT"
  | "CRASH"
  | "UNKNOWN";
export type Detail = string;
export type Normalizedcode = string | null;
export type Name1 = string;
export type Status = "result" | "error";
export type Value = Result | EngineError;
export type Columns1 = string[];
export type Ordered = boolean;
export type Rows1 = JsonValue[][];
export type Postconditions1 = CheckObservation[];
export type Status1 = "result" | "error" | "timeout" | "crash";
export type Durationms = number;
export type Oracleassessment = {
  [k: string]: "match" | "mismatch" | "not_evaluated";
} | null;
export type Outcome = "reproduced" | "not_reproduced" | "failed";
export type Pairid = string;
export type Runid = string;
export type Startedat = string;

export interface EvidenceContracts {
  case: FaultCase;
  engine: EngineSpec;
  pair: EnginePair;
  report: RunReport;
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
export interface EngineSpec {
  commitSha: Commitsha;
  id: Id1;
  imageDigest: Imagedigest;
  imageRef: Imageref;
  label: Label;
  lineage: Lineage;
  repository: Repository;
}
export interface EnginePair {
  baselineId: Baselineid;
  id: Id2;
  label: Label1;
  targetId: Targetid;
}
export interface RunReport {
  artifacts: Artifacts;
  caseContentHash: Casecontenthash;
  divergence?: Divergence | null;
  failure?: Failure | null;
  finishedAt: Finishedat;
  observations?: PairedObservation | null;
  oracleAssessment?: Oracleassessment;
  outcome: Outcome;
  pairId: Pairid;
  runId: Runid;
  startedAt: Startedat;
}
export interface ArtifactRef {
  bytes: Bytes;
  id: Id3;
  kind: Kind1;
  mediaType: Mediatype;
  path: Path;
  sha256: Sha256;
}
export interface Divergence {
  baselineObservationDigest: Baselineobservationdigest;
  changedDimensions: Changeddimensions;
  comparisonVersion: Comparisonversion;
  kind: Kind2;
  signature: Signature;
  targetObservationDigest: Targetobservationdigest;
}
export interface Failure {
  code: Code;
  engineRole?: Enginerole;
  message: Message;
  stage: Stage;
}
export interface PairedObservation {
  baseline: EngineObservation;
  target: EngineObservation;
}
export interface EngineObservation {
  engineVersionId: Engineversionid;
  error?: EngineError | null;
  postconditions?: Postconditions1;
  result?: Result | null;
  status: Status1;
  timing: Timing;
}
export interface EngineError {
  category: Category;
  detail: Detail;
  normalizedCode?: Normalizedcode;
}
export interface CheckObservation {
  name: Name1;
  status: Status;
  value: Value;
}
export interface Result {
  columns: Columns1;
  ordered: Ordered;
  rows: Rows1;
}
export interface Timing {
  durationMs: Durationms;
}
