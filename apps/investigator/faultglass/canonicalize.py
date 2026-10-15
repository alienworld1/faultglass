from pygments.token import Comment, Error, Whitespace

from .cypher import tokens
from .jsonio import digest

CANONICALIZATION_VERSION = "case-v1"


def statement_tokens(query):
    parts = tokens(query)
    if any(kind in Error for kind, _ in parts):
        return {"exact": query}
    visible = [
        [str(kind), text]
        for kind, text in parts
        if kind not in Comment and kind not in Whitespace
    ]
    if visible and visible[-1][1] == ";":
        visible.pop()
    return {"tokens": visible}


def canonical_payload(case):
    observation = case.observation.model_dump()
    observation["postconditions"] = [
        {**check.model_dump(), "query": statement_tokens(check.query)}
        for check in case.observation.postconditions
    ]
    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "schema_version": case.schemaVersion,
        "case_content": {
            "setup": [statement_tokens(query) for query in case.setup],
            "query": statement_tokens(case.query),
            "parameters": case.parameters,
            "observation": observation,
            "expectation": case.expectation.model_dump() if case.expectation else None,
        },
    }


def case_identity(case):
    payload = canonical_payload(case)
    return digest(payload), payload
