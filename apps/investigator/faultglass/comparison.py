from .jsonio import digest, encode
from .models import Divergence, Result
from .normalize import VERSION, normalize

COMPARISON_VERSION = "paired-evidence-v1/" + VERSION


def error_key(error):
    return {"category": error.category, "normalizedCode": error.normalizedCode}


def result_key(value):
    rows = value.rows if value.ordered else sorted(value.rows, key=encode)
    return {"columns": value.columns, "rows": rows, "ordered": value.ordered}


def material(observation, spec):
    value = {"status": observation.status}
    if observation.error:
        value["error"] = error_key(observation.error)
    if spec.compareResult and observation.result:
        value["result"] = result_key(observation.result)
    value["postconditions"] = {
        check.name: {
            "status": check.status,
            "value": result_key(check.value)
            if isinstance(check.value, Result)
            else error_key(check.value),
        }
        for check in observation.postconditions
    }
    return value


def compare(pair, engines, spec):
    baseline, target = material(pair.baseline, spec), material(pair.target, spec)
    changed = []
    if baseline["status"] != target["status"]:
        changed.append("status")
    if baseline.get("error") != target.get("error"):
        changed.append("error")
    if baseline.get("result") != target.get("result"):
        for dimension in ("columns", "rows"):
            if baseline.get("result", {}).get(dimension) != target.get(
                "result", {}
            ).get(dimension):
                changed.append("result." + dimension)
    for name in sorted(
        baseline["postconditions"].keys() | target["postconditions"].keys()
    ):
        if baseline["postconditions"].get(name) != target["postconditions"].get(name):
            changed.append("postcondition." + name)
    if not changed:
        return None
    changed = sorted(set(changed))
    kinds = {dimension.split(".")[0] for dimension in changed}
    identity = [
        {
            key: getattr(engine, key)
            for key in ("repository", "commitSha", "lineage", "imageDigest")
        }
        for engine in engines
    ]
    signature = digest(
        {
            "version": COMPARISON_VERSION,
            "engines": identity,
            "configuration": {
                "compareResult": spec.compareResult,
                "ordering": spec.ordering,
                "postconditionNames": [check.name for check in spec.postconditions],
            },
            "changedDimensions": changed,
            "baseline": baseline,
            "target": target,
        }
    )
    return Divergence(
        kind=next(iter(kinds)) if len(kinds) == 1 else "mixed",
        signature=signature,
        baselineObservationDigest=digest(baseline),
        targetObservationDigest=digest(target),
        changedDimensions=changed,
        comparisonVersion=COMPARISON_VERSION,
    )


def assess_oracle(case, pair):
    expected = case.expectation
    if expected is None or expected.kind == "none":
        return {"baseline": "not_evaluated", "target": "not_evaluated"}
    if expected.kind == "baseline_matches_expected":
        reference = material(pair.baseline, case.observation)
        return {
            role: "match"
            if material(getattr(pair, role), case.observation) == reference
            else "mismatch"
            for role in ("baseline", "target")
        }
    assessments = {}
    for role in ("baseline", "target"):
        observed = getattr(pair, role)
        if expected.kind == "explicit_error":
            matches = (
                observed.error is not None
                and observed.error.category == expected.errorCategory
            )
        else:
            reference = Result(
                columns=expected.value.columns,
                rows=[
                    [normalize(value) for value in row] for row in expected.value.rows
                ],
                ordered=case.observation.ordering == "ordered",
            )
            matches = observed.result is not None and result_key(
                observed.result
            ) == result_key(reference)
        assessments[role] = "match" if matches else "mismatch"
    return assessments
