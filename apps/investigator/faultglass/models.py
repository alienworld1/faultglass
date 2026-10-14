from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from .cypher import readonly, statement
from .jsonio import loads

Text = Annotated[str, StringConstraints(min_length=1)]
Category = Literal[
    "PARSE", "SEMANTIC", "TYPE", "CONSTRAINT", "RUNTIME", "TIMEOUT", "CRASH", "UNKNOWN"
]
Hash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpectedResult(Contract):
    columns: list[str]
    rows: list[list[JsonValue]]

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Provide one value per result column.")
        return self


class Expectation(Contract):
    kind: Literal[
        "baseline_matches_expected", "explicit_result", "explicit_error", "none"
    ]
    value: ExpectedResult | None = None
    errorCategory: Category | None = None

    @model_validator(mode="after")
    def fields_match(self):
        if (self.kind == "explicit_result") != (self.value is not None):
            raise ValueError("Provide an expected result only for explicit_result.")
        if (self.kind == "explicit_error") != (self.errorCategory is not None):
            raise ValueError("Provide an error category only for explicit_error.")
        return self


class StateCheck(Contract):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ]
    query: Text
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    _statement = field_validator("query")(readonly)


class ObservationSpec(Contract):
    compareResult: bool
    ordering: Literal["auto", "ordered", "unordered"]
    postconditions: list[StateCheck] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def supported(self):
        names = [check.name for check in self.postconditions]
        if len(set(names)) != len(names):
            raise ValueError("Give each state check a unique name.")
        if self.ordering == "auto":
            raise ValueError("Choose ordered or unordered comparison for this query.")
        return self


class Metadata(Contract):
    source: Annotated[str, StringConstraints(max_length=4000)] | None = None
    notes: Annotated[str, StringConstraints(max_length=4000)] | None = None


class FaultCase(Contract):
    schemaVersion: Literal[1]
    id: str | None = None
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    description: Annotated[str, StringConstraints(max_length=4000)] | None = None
    setup: list[str] = Field(max_length=32)
    query: Text
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    observation: ObservationSpec
    expectation: Expectation | None = None
    metadata: Metadata | None = None
    _query = field_validator("query")(statement)

    @field_validator("schemaVersion", mode="before")
    @classmethod
    def version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Use case version 1.")
        return value

    @field_validator("setup")
    @classmethod
    def setup_statements(cls, value):
        return [statement(query) for query in value]

    @model_validator(mode="after")
    def applicable_oracle(self):
        if (
            not self.observation.compareResult
            and self.expectation
            and self.expectation.kind == "explicit_result"
        ):
            raise ValueError(
                "Enable result comparison to use an explicit result expectation."
            )
        return self


def read_case(data):
    if len(data) > 262144:
        raise ValueError("Keep the case within 256 KiB.")
    return FaultCase.model_validate(loads(data))


class EngineSpec(Contract):
    id: Text
    label: Text
    repository: Literal["FalkorDB/FalkorDB"]
    commitSha: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")]
    lineage: Literal["legacy-c", "rust"]
    imageRef: Text
    imageDigest: Annotated[str, StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def immutable(self):
        if not self.imageRef.endswith("@" + self.imageDigest):
            raise ValueError("Use the approved immutable image reference.")
        return self


class EnginePair(Contract):
    id: Text
    label: Text
    baselineId: Text
    targetId: Text


class RunLimits(Contract):
    startupSeconds: Annotated[int, Field(gt=0, le=20)] = 20
    querySeconds: Annotated[int, Field(gt=0, le=5)] = 5
    pairSeconds: Annotated[int, Field(gt=0, le=60)] = 60
    cleanupSeconds: Annotated[int, Field(gt=0, le=10)] = 10
    rows: Annotated[int, Field(gt=0, le=1000)] = 1000
    outputBytes: Annotated[int, Field(gt=0, le=1048576)] = 1048576
    logBytes: Annotated[int, Field(gt=0, le=262144)] = 262144
    artifactBytes: Annotated[int, Field(gt=0, le=8388608)] = 8388608


class EngineError(Contract):
    category: Category
    normalizedCode: Text | None = None
    detail: Annotated[str, StringConstraints(max_length=16384)]


class Result(ExpectedResult):
    ordered: bool


class CheckObservation(Contract):
    name: Text
    status: Literal["result", "error"]
    value: Result | EngineError

    @model_validator(mode="after")
    def shape(self):
        if (self.status == "result") != isinstance(self.value, Result):
            raise ValueError("State check status must match its value.")
        return self


class Timing(Contract):
    durationMs: Annotated[float, Field(ge=0)]


class EngineObservation(Contract):
    engineVersionId: Text
    status: Literal["result", "error", "timeout", "crash"]
    result: Result | None = None
    error: EngineError | None = None
    postconditions: list[CheckObservation] = Field(default_factory=list)
    timing: Timing

    @model_validator(mode="after")
    def shape(self):
        if (self.status == "result") != (self.result is not None) or (
            self.status != "result"
        ) != (self.error is not None):
            raise ValueError("Engine status must match its observation.")
        if (
            self.status in ("timeout", "crash")
            and self.error.category != self.status.upper()
        ):
            raise ValueError("Engine status must match its error category.")
        return self


class PairedObservation(Contract):
    baseline: EngineObservation
    target: EngineObservation


class Divergence(Contract):
    kind: Literal["status", "error", "result", "postcondition", "mixed"]
    signature: Hash
    baselineObservationDigest: Hash
    targetObservationDigest: Hash
    changedDimensions: list[str]
    comparisonVersion: Text


class ArtifactRef(Contract):
    id: Text
    kind: Text
    path: Text
    mediaType: Text
    sha256: Hash
    bytes: Annotated[int, Field(ge=0)]


class Failure(Contract):
    code: Text
    stage: Text
    message: Text
    engineRole: Literal["baseline", "target"] | None = None


class RunReport(Contract):
    runId: Text
    pairId: Text
    caseContentHash: Hash
    outcome: Literal["reproduced", "not_reproduced", "failed"]
    observations: PairedObservation | None = None
    divergence: Divergence | None = None
    oracleAssessment: (
        dict[str, Literal["match", "mismatch", "not_evaluated"]] | None
    ) = None
    failure: Failure | None = None
    startedAt: Text
    finishedAt: Text
    artifacts: list[ArtifactRef]

    @model_validator(mode="after")
    def completed_shape(self):
        if self.outcome == "failed":
            if self.failure is None or self.divergence is not None:
                raise ValueError(
                    "Failed comparisons require a cause and cannot claim a divergence."
                )
        elif (
            self.observations is None
            or self.failure is not None
            or (self.outcome == "reproduced") != (self.divergence is not None)
        ):
            raise ValueError("Comparison outcome must match its complete evidence.")
        return self
