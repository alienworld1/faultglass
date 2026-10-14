from .runner_profile import PROFILE


def executable_envelope(case, limits):
    return {
        "setup": case.setup,
        "query": case.query,
        "parameters": case.parameters,
        "postconditions": [
            check.model_dump() for check in case.observation.postconditions
        ],
        "limits": limits.model_dump(),
        "profile": PROFILE,
    }
