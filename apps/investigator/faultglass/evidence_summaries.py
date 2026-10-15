from typing import Literal

from pydantic import Field

from .models import Contract


class ObservationSummary(Contract):
    engineVersionId: str
    status: Literal["result", "error", "timeout", "crash"]
    rowCount: int | None
    columns: list[str] = Field(max_length=32)
    errorCategory: str | None
    detail: str | None = Field(max_length=256)


class PairedSummary(Contract):
    baseline: ObservationSummary
    target: ObservationSummary


def summarize(report):
    if not report.observations:
        return None
    values = {}
    for role in ("baseline", "target"):
        observed = getattr(report.observations, role)
        values[role] = ObservationSummary(
            engineVersionId=observed.engineVersionId,
            status=observed.status,
            rowCount=len(observed.result.rows) if observed.result else None,
            columns=[c[:160] for c in observed.result.columns[:32]]
            if observed.result
            else [],
            errorCategory=observed.error.category if observed.error else None,
            detail=observed.error.detail[:256] if observed.error else None,
        )
    return PairedSummary(**values)
