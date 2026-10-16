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
export type Calls = number;
export type Createdat = string;
export type Elapsedms = number;
/**
 * @maxItems 80
 */
export type Inputartifacthashes = string[];
export type Investigationid = string;
export type Mode = "agent" | "deterministic_diagnostic";
export type Model = string | null;
/**
 * @maxItems 4
 */
export type Outputrefs =
  | []
  | [EvidenceReference]
  | [EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ];
export type Bytes = number;
export type Id1 = string;
export type Kind1 = string;
export type Mediatype = string;
export type Owner = string;
export type Path = string;
export type Sha256 = string;
export type Promptversion = "explorer-v1" | "explorer-v2";
export type Provider = "gemini" | null;
export type Reasoncode = string | null;
/**
 * @maxItems 12
 */
export type Results =
  | []
  | [AgentToolResult]
  | [AgentToolResult, AgentToolResult]
  | [AgentToolResult, AgentToolResult, AgentToolResult]
  | [AgentToolResult, AgentToolResult, AgentToolResult, AgentToolResult]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ]
  | [
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
      AgentToolResult,
    ];
/**
 * @maxItems 12
 */
export type References =
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
      EvidenceReference,
      EvidenceReference,
    ];
export type Requestid = string;
export type Resulthash = string;
export type Tool =
  | "read_investigation_context"
  | "rank_supported_probes"
  | "execute_ranked_probe"
  | "read_probe_evidence"
  | "continue_verified_analysis"
  | "read_classification_evidence";
export type Schemaversion1 = 1;
export type Stage =
  | "context"
  | "rank"
  | "execute"
  | "evidence"
  | "continue"
  | "classification"
  | "interpretation"
  | "done";
export type Status =
  "pending" | "running" | "completed" | "degraded" | "data_excluded";
/**
 * @maxItems 12
 */
export type Turns =
  | []
  | [AgentTurn]
  | [AgentTurn, AgentTurn]
  | [AgentTurn, AgentTurn, AgentTurn]
  | [AgentTurn, AgentTurn, AgentTurn, AgentTurn]
  | [AgentTurn, AgentTurn, AgentTurn, AgentTurn, AgentTurn]
  | [AgentTurn, AgentTurn, AgentTurn, AgentTurn, AgentTurn, AgentTurn]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ]
  | [
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
      AgentTurn,
    ];
export type Elapsedms1 = number;
export type Failure = string | null;
export type Id2 = string;
export type Inputhash = string;
export type Operation =
  | "request_tool"
  | "explain_family"
  | "narrate_investigation"
  | "enrich_fingerprint"
  | "suggest_reduction";
export type Reservedat = string;
export type Revision = number;
export type Updatedat = string;
/**
 * @maxItems 10
 */
export type Candidates =
  | []
  | [FamilyCandidate]
  | [FamilyCandidate, FamilyCandidate]
  | [FamilyCandidate, FamilyCandidate, FamilyCandidate]
  | [FamilyCandidate, FamilyCandidate, FamilyCandidate, FamilyCandidate]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ]
  | [
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
      FamilyCandidate,
    ];
export type Behavior = number;
export type Compatible = boolean;
/**
 * @maxItems 4
 */
export type Contradictoryprobeids =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string];
export type Eligible = boolean;
export type Familyid = string;
export type Familystatus = "provisional" | "confirmed";
export type Feature = number;
/**
 * @maxItems 64
 */
export type Pathrefs = string[];
/**
 * @maxItems 12
 */
export type Reasons =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ];
export type Reducedshape = number;
export type Score = number;
export type Sourceinvestigationid = string;
/**
 * @maxItems 4
 */
export type Supportingprobeids =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string];
export type Version = number;
/**
 * @maxItems 12
 */
export type Contradictions =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ];
/**
 * @maxItems 64
 */
export type Features = string[];
/**
 * @maxItems 4
 */
export type Probes =
  | []
  | [ProbeEvidence]
  | [ProbeEvidence, ProbeEvidence]
  | [ProbeEvidence, ProbeEvidence, ProbeEvidence]
  | [ProbeEvidence, ProbeEvidence, ProbeEvidence, ProbeEvidence];
export type Contribution = ("repeated_source" | "semantic_contrast") | null;
export type Definitionsha256 = string;
export type Durationms = number;
export type Inputcaseid = string;
export type Observedat = string;
export type Outputcaseid = string;
export type Probeid = string;
export type Relationship = "preserved" | "eliminated" | "changed";
export type Selectionid = string;
export type Sequence = number;
export type Signature = string | null;
export type Templateversion = string;
export type Referencesignature = string;
export type Retainedcaseid = string;
export type Retainedisrepeatedsource = boolean;
export type Baseline = string;
export type ComparisonVersion = string;
export type Target = string;
export type Createdat1 = string;
export type Familyid1 = string | null;
export type Familyname = string | null;
export type Familystatus1 = ("provisional" | "confirmed") | null;
/**
 * @maxItems 12
 */
export type Observed =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ];
export type Reasoncode1 = string;
export type State = "matched" | "provisional" | "unresolved";
/**
 * @maxItems 12
 */
export type Unknowns =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
    ];
export type Createdat2 = string;
export type Expectationbasis =
  "explicit_result" | "explicit_error" | "baseline_observation" | "unasserted";
/**
 * @minItems 3
 * @maxItems 3
 */
export type Files = [DownloadReference, DownloadReference, DownloadReference];
export type Bytes1 = number;
export type Id3 = string;
export type Key = "case" | "regression-test" | "report";
export type Kind2 = string;
export type Mediatype1 = string;
export type Owner1 = string;
export type Path1 = string;
export type Sha2561 = string;
export type Investigationid1 = string;
export type Regressiontestid = string;
export type Schemaversion2 = 1;
export type Sourcecaseid = string;
export type Changed = boolean;
/**
 * @maxItems 256
 */
export type Pathrefs1 = string[];
/**
 * @maxItems 100
 */
export type Priorinvestigationids = string[];
export type Selectedprobeid = string | null;
/**
 * @maxItems 2
 */
export type Withhistory = [] | [InfluenceRank] | [InfluenceRank, InfluenceRank];
export type Probeid1 = string;
export type Rank = number;
export type Score1 = number;
/**
 * @maxItems 2
 */
export type Withouthistory =
  [] | [InfluenceRank] | [InfluenceRank, InfluenceRank];
/**
 * @minItems 1
 * @maxItems 1
 */
export type Evidenceids = [string];
export type Text = string;
export type Proposedname = string;
export type Commitkey = string;
export type Costprecision = "milliseconds-6dp";
/**
 * @maxItems 4
 */
export type Entries =
  | []
  | [MemoryEntry]
  | [MemoryEntry, MemoryEntry]
  | [MemoryEntry, MemoryEntry, MemoryEntry]
  | [MemoryEntry, MemoryEntry, MemoryEntry, MemoryEntry];
export type Attempts = number;
export type Avgcostms = number;
export type Lastseenat = string;
export type Successes = number;
export type Costms = number;
export type Edgeid = string;
/**
 * @maxItems 4
 */
export type Evidencerefs =
  | []
  | [EvidenceReference]
  | [EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference]
  | [
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
      EvidenceReference,
    ];
export type Familyid2 = string;
export type Probeid2 = string;
export type Reason = "repeated_source" | "semantic_contrast" | "observed_only";
export type Selectionid1 = string;
export type Successincrement = 0 | 1;
export type Investigationid2 = string;
export type Reason1 = string | null;
export type Schemaversion3 = 1;
export type State1 = "recorded" | "ineligible";
export type Nextcursor = number | null;
export type Revision1 = number;
export type AdmissionSeconds = number;
/**
 * @maxItems 2
 */
export type Candidates1 =
  [] | [RankedCandidate] | [RankedCandidate, RankedCandidate];
export type Attempts1 = number;
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
export type FeatureFit = number;
export type HistoricalYield = number;
export type InputCaseId1 = string;
export type MatchedFeatureIds = string[];
export type NormalizedCost = number;
export type Novelty = number;
export type OutputCaseId1 = string;
export type PairCapMs = 60000;
export type ProbeId1 = string;
export type Rank1 = number;
export type Reason2 = string;
export type Source1 = "history" | "structural";
export type Successes1 = number;
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
export type SeedCaseId = string;
export type SeedManifestSha256 = string;
export type SelectedProbeId = string | null;
export type SelectionId = string;
export type Sequence1 = number;
export type TerminalReason =
  ("no_applicable_probe" | "budget_exhausted") | null;
export type Commitsha = string;
export type Id4 = string;
export type Imagedigest = string;
export type Imageref = string;
export type Label = string;
export type Lineage = "legacy-c" | "rust";
export type Repository = "FalkorDB/FalkorDB";
export type At = string;
export type Attemptid = string | null;
export type Attemptordinal = number | null;
export type Childid = string | null;
export type Currentcaseid = string | null;
export type Probesequence = number;
/**
 * @maxItems 3
 */
export type References1 =
  | []
  | [EvidenceReference]
  | [EvidenceReference, EvidenceReference]
  | [EvidenceReference, EvidenceReference, EvidenceReference];
export type Revision2 = number;
export type Status1 =
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
export type Id5 = string;
export type Investigationid3 = string;
export type Sequence2 = number;
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
  | "reduction.started"
  | "reduction.verifying"
  | "reduction.accepted"
  | "reduction.rejected"
  | "reduction.finished"
  | "agent.action"
  | "agent.degraded"
  | "family.matched"
  | "family.provisional"
  | "family.unresolved"
  | "export.ready"
  | "memory.updated"
  | "investigation.complete"
  | "cancellation.requested"
  | "investigation.not_reproduced"
  | "investigation.unresolved"
  | "investigation.cancelled"
  | "investigation.failed";
export type Decision1 = string | null;
export type Kind3 = "seed" | "selection" | "result";
/**
 * @maxItems 32
 */
export type Columns1 = string[];
export type Detail = string | null;
export type Engineversionid = string;
export type Errorcategory1 = string | null;
export type Rowcount = number | null;
export type Status2 = "result" | "error" | "timeout" | "crash";
export type Query2 = string | null;
/**
 * @maxItems 10
 */
export type References2 =
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
export type Sequence3 = number;
/**
 * @maxItems 25
 */
export type Items = EvidenceItem[];
export type Nextcursor1 = number | null;
export type Revision3 = number;
export type Calls1 = number;
export type Mode1 = "agent" | "deterministic_diagnostic";
export type Model1 = string | null;
export type Reasoncode2 = string | null;
export type Status3 =
  "pending" | "running" | "completed" | "degraded" | "data_excluded";
export type Chargedbytes = number;
export type Consideredattempts = number;
export type Maxartifactbytes = 67108864;
export type Maxevents = 512;
export type Maxprobes = 4;
export type Maxseconds = 900;
export type Reducercandidates = 0 | 4;
export type Reservedcandidates = number;
export type Reservedprobes = number;
export type Stabilitychecks = number;
export type Cancelrequestedat = string | null;
export type Classifying = boolean;
export type Exporting = boolean;
export type Reducing = boolean;
export type Createdat3 = string;
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
export type Exportsready = boolean;
export type Fingerprintid = string | null;
export type Finishedat = string | null;
export type Id6 = string;
export type Lasteventsequence = number;
export type Memorystate =
  ("pending" | "recorded" | "ineligible" | "failed") | null;
export type Pairid1 = string;
export type Status4 =
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
export type Acceptedcount = number;
export type Consideredcount = number;
export type Currentcaseid1 = string;
export type Executablebytes = number;
export type Querytokens = number;
export type Setupstatements = number;
export type Setuptokens = number;
export type Rejectedcount = number;
export type Reservedcandidates1 = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Engines1 = [EngineSpec, EngineSpec];
export type Reducerversion = "reducer-v1";
export type Baselineobservationdigest = string;
export type Changeddimensions = string[];
export type Comparisonversion = string;
export type Kind4 = "status" | "error" | "result" | "postcondition" | "mixed";
export type Signature1 = string;
export type Targetobservationdigest = string;
export type Sourcecaseid1 = string;
export type Sourceevidenceid = string;
export type Sourcekind = "seed" | "probe";
export type Sourceprobesequence = number | null;
export type Stabilityevidenceid = string | null;
export type Stable = boolean;
export type State2 =
  "checking" | "proposing" | "verifying" | "finished" | "cancelled" | "failed";
export type Stopreason =
  | (
      | "supported_passes_exhausted"
      | "unsupported_shape"
      | "candidate_limit"
      | "consideration_limit"
      | "time_limit"
      | "storage_limit"
      | "event_limit"
      | "unstable_source"
      | "cancelled"
      | "verification_failed"
    )
  | null;
export type Verificationfailures = number;
export type Revision4 = number;
export type Schemaversion4 = 1;
export type Seedevidenceid = string | null;
export type Startedat = string | null;
export type Status5 =
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
  | "registry_changed"
  | "evidence_complete"
  | "family_unresolved"
  | "export_failure"
  | "memory_failure";
export type Message = string;
export type Title1 = string;
export type Updatedat1 = string;
export type Workspaceid = "falkordb-core";
export type Baselineid = string;
export type Id7 = string;
export type Label1 = string;
export type Targetid = string;
/**
 * @maxItems 10
 */
export type Attempts2 =
  | []
  | [ReductionAttemptView]
  | [ReductionAttemptView, ReductionAttemptView]
  | [ReductionAttemptView, ReductionAttemptView, ReductionAttemptView]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ]
  | [
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
      ReductionAttemptView,
    ];
/**
 * @maxItems 10
 */
export type Artifactrefs =
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
export type Candidatecaseid = string | null;
export type Candidatepayloadsha256 = string;
export type Description1 = string;
export type End1 = number | null;
export type Originaltextsha256 = string;
export type Setupindex = number | null;
export type Start1 = number | null;
export type Createdat4 = string;
export type Id8 = string;
export type Ordinal = number;
export type Parentcaseid = string;
export type Phase = "query" | "fixture";
export type Reason4 =
  | (
      | "invalid_candidate"
      | "unsupported_shape"
      | "not_smaller"
      | "duplicate"
      | "difference_eliminated"
      | "signature_changed"
      | "verified"
      | "execution_failure"
      | "integrity_failure"
    )
  | null;
export type Resolvedat = string | null;
export type State3 =
  "proposed" | "verifying" | "accepted" | "rejected" | "failed";
export type Transformid =
  | "remove-with-v1"
  | "remove-optional-v1"
  | "remove-match-v1"
  | "remove-setup-v1";
export type Verificationevidenceid = string | null;
export type Caseid = string;
export type Nextsetupcursor = number | null;
export type Query3 = string;
/**
 * @maxItems 8
 */
export type Setup1 =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type Setuptotal = number;
export type Nextcursor2 = number | null;
export type Revision5 = number;
export type Query4 = string;
export type Bytes2 = number;
export type Id9 = string;
export type Kind5 = string;
export type Mediatype2 = string;
export type Path2 = string;
export type Sha2562 = string;
export type Artifacts = ArtifactRef[];
export type Casecontenthash = string;
export type Code1 = string;
export type Enginerole = ("baseline" | "target") | null;
export type Message1 = string;
export type Stage1 = string;
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
export type Status6 = "result" | "error";
export type Value = Result | EngineError;
export type Columns2 = string[];
export type Ordered = boolean;
export type Rows2 = JsonValue[][];
export type Postconditions1 = CheckObservation[];
export type Status7 = "result" | "error" | "timeout" | "crash";
export type Durationms1 = number;
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
  conclusion: ConclusionPage;
  decision: Decision;
  engine: EngineSpec;
  event: Event;
  evidence: EvidencePage;
  investigation: Snapshot;
  pair: EnginePair;
  reduction: ReductionPage;
  reductionSuggestion: ReductionSuggestion;
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
export interface ConclusionPage {
  agent: AgentRun | null;
  candidates: Candidates;
  classification: ClassificationSummary | null;
  conclusion: Conclusion | null;
  exports: ExportManifest | null;
  influence: HistoricalInfluence | null;
  interpretation: AgentInterpretation | null;
  memory: MemoryDelta | null;
  nextCursor: Nextcursor;
  revision: Revision1;
}
export interface AgentRun {
  calls?: Calls;
  createdAt: Createdat;
  elapsedMs?: Elapsedms;
  inputArtifactHashes?: Inputartifacthashes;
  investigationId: Investigationid;
  mode: Mode;
  model?: Model;
  outputRefs?: Outputrefs;
  promptVersion?: Promptversion;
  provider?: Provider;
  reasonCode?: Reasoncode;
  results?: Results;
  schemaVersion?: Schemaversion1;
  stage?: Stage;
  status: Status;
  turns?: Turns;
  updatedAt: Updatedat;
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
export interface AgentToolResult {
  references: References;
  requestId: Requestid;
  resultHash: Resulthash;
  tool: Tool;
}
export interface AgentTurn {
  elapsedMs?: Elapsedms1;
  failure?: Failure;
  id: Id2;
  inputHash: Inputhash;
  inputRef?: EvidenceReference | null;
  operation: Operation;
  providerResponseRef?: EvidenceReference | null;
  reservedAt: Reservedat;
  responseRef?: EvidenceReference | null;
  revision: Revision;
}
export interface FamilyCandidate {
  behavior: Behavior;
  compatible: Compatible;
  contradictoryProbeIds: Contradictoryprobeids;
  eligible: Eligible;
  familyEvidenceRef: EvidenceReference;
  familyId: Familyid;
  familyStatus: Familystatus;
  feature: Feature;
  pathRefs: Pathrefs;
  reasons: Reasons;
  reducedShape: Reducedshape;
  score: Score;
  sourceInvestigationId: Sourceinvestigationid;
  supportingProbeIds: Supportingprobeids;
  version: Version;
}
export interface ClassificationSummary {
  contradictions: Contradictions;
  features: Features;
  probes: Probes;
  referenceSignature: Referencesignature;
  retainedCaseId: Retainedcaseid;
  retainedIsRepeatedSource: Retainedisrepeatedsource;
  retainedVerificationRef: EvidenceReference;
  scope: VersionScope;
  sourceRef: EvidenceReference;
  stabilityRef: EvidenceReference;
}
export interface ProbeEvidence {
  contribution?: Contribution;
  definitionSha256: Definitionsha256;
  durationMs: Durationms;
  inputCaseId: Inputcaseid;
  observedAt: Observedat;
  outputCaseId: Outputcaseid;
  pairedStatuses: Pairedstatuses;
  planRef: EvidenceReference;
  probeId: Probeid;
  relationship: Relationship;
  reportRef: EvidenceReference;
  resultRef: EvidenceReference;
  selectionId: Selectionid;
  sequence: Sequence;
  signature: Signature;
  templateVersion: Templateversion;
}
export interface Pairedstatuses {
  [k: string]: "result" | "error" | "timeout" | "crash";
}
export interface VersionScope {
  baseline: Baseline;
  comparison_version: ComparisonVersion;
  target: Target;
}
export interface Conclusion {
  createdAt: Createdat1;
  evidenceRef: EvidenceReference;
  familyId?: Familyid1;
  familyName?: Familyname;
  familyStatus?: Familystatus1;
  interpretationRef?: EvidenceReference | null;
  observed: Observed;
  reasonCode: Reasoncode1;
  state: State;
  unknowns: Unknowns;
}
export interface ExportManifest {
  classificationEvidenceRef: EvidenceReference;
  createdAt: Createdat2;
  expectationBasis: Expectationbasis;
  files: Files;
  investigationId: Investigationid1;
  regressionTestId: Regressiontestid;
  schemaVersion?: Schemaversion2;
  sourceCaseId: Sourcecaseid;
}
export interface DownloadReference {
  bytes: Bytes1;
  id: Id3;
  key: Key;
  kind: Kind2;
  mediaType: Mediatype1;
  owner: Owner1;
  path: Path1;
  sha256: Sha2561;
}
export interface HistoricalInfluence {
  changed: Changed;
  decisionRef: EvidenceReference;
  pathRefs: Pathrefs1;
  priorInvestigationIds: Priorinvestigationids;
  selectedProbeId: Selectedprobeid;
  withHistory: Withhistory;
  withoutHistory: Withouthistory;
}
export interface InfluenceRank {
  probeId: Probeid1;
  rank: Rank;
  score: Score1;
}
export interface AgentInterpretation {
  family: FamilyExplanation;
  narrative: InvestigationNarrative;
}
export interface FamilyExplanation {
  interpretation: CitedText;
  observed: CitedText;
  proposedName: Proposedname;
  unknown: CitedText;
}
export interface CitedText {
  evidenceIds: Evidenceids;
  text: Text;
}
export interface InvestigationNarrative {
  interpretation: CitedText;
  observed: CitedText;
  unknown: CitedText;
}
export interface MemoryDelta {
  classificationRef: EvidenceReference;
  commitKey: Commitkey;
  costPrecision?: Costprecision;
  entries: Entries;
  exportManifestRef: EvidenceReference;
  investigationId: Investigationid2;
  reason?: Reason1;
  schemaVersion?: Schemaversion3;
  scope: VersionScope;
  state: State1;
}
export interface MemoryEntry {
  after: MemoryStatistics;
  before: MemoryStatistics;
  costMs: Costms;
  edgeId: Edgeid;
  evidenceRefs: Evidencerefs;
  familyId: Familyid2;
  probeId: Probeid2;
  reason: Reason;
  selectionId: Selectionid1;
  successIncrement: Successincrement;
}
export interface MemoryStatistics {
  attempts: Attempts;
  avgCostMs: Avgcostms;
  lastSeenAt: Lastseenat;
  successes: Successes;
}
export interface Decision {
  admission_seconds?: AdmissionSeconds;
  candidates: Candidates1;
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
  sequence?: Sequence1;
  source_snapshot_ref: EvidenceReference;
  terminal_reason?: TerminalReason;
  transformed_case_ref: EvidenceReference | null;
}
export interface RankedCandidate {
  attempts: Attempts1;
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
  rank: Rank1;
  reason: Reason2;
  source: Source1;
  successes: Successes1;
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
export interface EngineSpec {
  commitSha: Commitsha;
  id: Id4;
  imageDigest: Imagedigest;
  imageRef: Imageref;
  label: Label;
  lineage: Lineage;
  repository: Repository;
}
export interface Event {
  at: At;
  data: EventData;
  id: Id5;
  investigationId: Investigationid3;
  phase: Status1;
  sequence: Sequence2;
  summary: Summary;
  type: Type;
}
export interface EventData {
  attemptId?: Attemptid;
  attemptOrdinal?: Attemptordinal;
  childId?: Childid;
  currentCaseId?: Currentcaseid;
  probeSequence: Probesequence;
  references?: References1;
  revision: Revision2;
  status: Status1;
}
export interface EvidencePage {
  items: Items;
  nextCursor: Nextcursor1;
  revision: Revision3;
}
export interface EvidenceItem {
  decision?: Decision1;
  kind: Kind3;
  observations?: PairedSummary | null;
  query?: Query2;
  references: References2;
  sequence: Sequence3;
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
  status: Status2;
}
export interface Snapshot {
  agent: AgentSummary | null;
  budget: Budget;
  cancelRequestedAt: Cancelrequestedat;
  capabilities: Capabilities;
  conclusion: Conclusion | null;
  createdAt: Createdat3;
  deadlineAt: Deadlineat;
  engines: Engines;
  evidence: Evidence;
  exportsReady: Exportsready;
  fingerprintId: Fingerprintid;
  finishedAt: Finishedat;
  id: Id6;
  lastEventSequence: Lasteventsequence;
  memoryState: Memorystate;
  pairId: Pairid1;
  phase: Status4;
  phaseAttempt: Phaseattempt;
  probeSequence: Probesequence1;
  reduction: ReductionSummary | null;
  revision: Revision4;
  schemaVersion: Schemaversion4;
  seedEvidenceId: Seedevidenceid;
  startedAt: Startedat;
  status: Status5;
  terminalReason: Reason3 | null;
  title: Title1;
  updatedAt: Updatedat1;
  workspaceId: Workspaceid;
}
export interface AgentSummary {
  calls: Calls1;
  mode: Mode1;
  model: Model1;
  reasonCode: Reasoncode2;
  status: Status3;
}
export interface Budget {
  chargedBytes: Chargedbytes;
  consideredAttempts: Consideredattempts;
  maxArtifactBytes: Maxartifactbytes;
  maxEvents: Maxevents;
  maxProbes: Maxprobes;
  maxSeconds: Maxseconds;
  reducerCandidates: Reducercandidates;
  reservedCandidates: Reservedcandidates;
  reservedProbes: Reservedprobes;
  stabilityChecks: Stabilitychecks;
}
export interface Capabilities {
  classifying: Classifying;
  exporting: Exporting;
  reducing: Reducing;
}
export interface ReductionSummary {
  acceptedCount: Acceptedcount;
  consideredCount: Consideredcount;
  currentCaseId: Currentcaseid1;
  currentCaseRef: EvidenceReference;
  currentSize: CaseSize;
  finalCaseRef: EvidenceReference | null;
  originalSize: CaseSize;
  rejectedCount: Rejectedcount;
  reservedCandidates: Reservedcandidates1;
  source: ReductionSource;
  sourceSize: CaseSize;
  state: State2;
  stopReason: Stopreason;
  verificationFailures: Verificationfailures;
}
export interface CaseSize {
  executableBytes: Executablebytes;
  queryTokens: Querytokens;
  setupStatements: Setupstatements;
  setupTokens: Setuptokens;
}
export interface ReductionSource {
  engines: Engines1;
  reducerVersion: Reducerversion;
  referenceDivergence: Divergence;
  sourceCaseId: Sourcecaseid1;
  sourceCaseRef: EvidenceReference;
  sourceEvidenceId: Sourceevidenceid;
  sourceKind: Sourcekind;
  sourceProbeSequence: Sourceprobesequence;
  stabilityEvidenceId: Stabilityevidenceid;
  stable: Stable;
}
export interface Divergence {
  baselineObservationDigest: Baselineobservationdigest;
  changedDimensions: Changeddimensions;
  comparisonVersion: Comparisonversion;
  kind: Kind4;
  signature: Signature1;
  targetObservationDigest: Targetobservationdigest;
}
export interface Reason3 {
  code: Code;
  message: Message;
}
export interface EnginePair {
  baselineId: Baselineid;
  id: Id7;
  label: Label1;
  targetId: Targetid;
}
export interface ReductionPage {
  attempts: Attempts2;
  case: ReductionCaseView | null;
  nextCursor: Nextcursor2;
  revision: Revision5;
  sourceCase: ReductionCaseView | null;
  sourceObservations: PairedSummary | null;
  stabilityObservations: PairedSummary | null;
  summary: ReductionSummary | null;
}
export interface ReductionAttemptView {
  attempt: ReductionAttempt;
  candidate: ReductionCaseView | null;
  observations: PairedSummary | null;
  parent: ReductionCaseView | null;
}
export interface ReductionAttempt {
  afterSize: CaseSize | null;
  artifactRefs: Artifactrefs;
  beforeSize: CaseSize;
  candidateCaseId: Candidatecaseid;
  candidatePayloadSha256: Candidatepayloadsha256;
  candidateRef: EvidenceReference;
  change: ReductionChange;
  createdAt: Createdat4;
  id: Id8;
  observedDivergence: Divergence | null;
  ordinal: Ordinal;
  parentCaseId: Parentcaseid;
  phase: Phase;
  reason: Reason4;
  resolvedAt: Resolvedat;
  state: State3;
  transformId: Transformid;
  verificationEvidenceId: Verificationevidenceid;
}
export interface ReductionChange {
  description: Description1;
  end: End1;
  originalTextSha256: Originaltextsha256;
  setupIndex: Setupindex;
  start: Start1;
}
export interface ReductionCaseView {
  caseId: Caseid;
  caseRef: EvidenceReference;
  nextSetupCursor: Nextsetupcursor;
  query: Query3;
  setup: Setup1;
  setupTotal: Setuptotal;
}
export interface ReductionSuggestion {
  query: Query4;
  reason: CitedText;
}
export interface RunReport {
  artifacts: Artifacts;
  caseContentHash: Casecontenthash;
  divergence?: Divergence | null;
  failure?: Failure1 | null;
  finishedAt: Finishedat1;
  observations?: PairedObservation | null;
  oracleAssessment?: Oracleassessment;
  outcome: Outcome1;
  pairId: Pairid2;
  runId: Runid;
  startedAt: Startedat1;
}
export interface ArtifactRef {
  bytes: Bytes2;
  id: Id9;
  kind: Kind5;
  mediaType: Mediatype2;
  path: Path2;
  sha256: Sha2562;
}
export interface Failure1 {
  code: Code1;
  engineRole?: Enginerole;
  message: Message1;
  stage: Stage1;
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
  status: Status7;
  timing: Timing;
}
export interface EngineError {
  category: Category;
  detail: Detail1;
  normalizedCode?: Normalizedcode;
}
export interface CheckObservation {
  name: Name1;
  status: Status6;
  value: Value;
}
export interface Result {
  columns: Columns2;
  ordered: Ordered;
  rows: Rows2;
}
export interface Timing {
  durationMs: Durationms1;
}
