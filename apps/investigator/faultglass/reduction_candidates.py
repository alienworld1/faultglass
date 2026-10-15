import re

from pygments.token import Comment, Keyword, Name, Number, String, Whitespace

from .canonicalize import case_identity
from .cypher import BoundaryLexer
from .execution import validate_parameters
from .investigation_planning import digest_bytes
from .jsonio import encode
from .models import read_case
from .reduction_models import CaseSize, ReductionChange


def significant(query):
    parts = [
        (i, k, t)
        for i, k, t in BoundaryLexer().get_tokens_unprocessed(query)
        if k not in Comment and k not in Whitespace
    ]
    if parts and parts[-1][2] == ";":
        parts.pop()
    return parts


def case_size(case):
    return CaseSize(
        queryTokens=len(significant(case.query)),
        setupStatements=len(case.setup),
        setupTokens=sum(len(significant(q)) for q in case.setup),
        executableBytes=sum(len(q.encode()) for q in [case.query, *case.setup]),
    )


def smaller(before, after):
    keys = ("queryTokens", "setupStatements", "setupTokens")
    return all(getattr(after, k) <= getattr(before, k) for k in keys) and any(
        getattr(after, k) < getattr(before, k) for k in keys
    )


def validate_candidate(parent, data):
    candidate = read_case(data)
    validate_parameters(candidate)
    if any(
        v != candidate.model_dump()[k]
        for k, v in parent.model_dump().items()
        if k not in {"query", "setup"}
    ):
        raise ValueError("This change would alter how the case is checked.")
    if case_identity(parent)[0] == case_identity(candidate)[0] or not smaller(
        case_size(parent), case_size(candidate)
    ):
        raise ValueError("The case is not smaller.")
    return candidate


def query_cuts(query):
    parts, index = significant(query), 0

    def take(text=None, identifier=False, literal=False):
        nonlocal index
        offset, kind, value = parts[index]
        if text is not None:
            valid = value.upper() == text and (
                kind in Keyword if text.isalpha() else True
            )
        elif identifier:
            valid = kind in Name and bool(
                re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*|`(?:``|[^`])+`", value)
            )
        else:
            valid = literal and (
                kind in String
                or kind in Number
                or value.upper() in {"TRUE", "FALSE", "NULL"}
            )
        if not valid:
            raise ValueError()
        index += 1
        return offset, value

    try:
        take("CALL")
        take(identifier=True)
        while parts[index][2] == ".":
            take(".")
            take(identifier=True)
        take("(")
        if parts[index][2] != ")":
            take(literal=True)
            while parts[index][2] == ",":
                take(",")
                take(literal=True)
        take(")")
        take("YIELD")
        _, binding = take(identifier=True)
        cuts = []
        if parts[index][2].upper() == "WITH":
            start, _ = take("WITH")
            end, value = take(identifier=True)
            if value != binding:
                return []
            cuts.append(
                (
                    "remove-with-v1",
                    start,
                    end + len(value),
                    "Removed the pass-through WITH clause",
                )
            )
        start = parts[index][0]
        if parts[index][2].upper() == "OPTIONAL":
            offset, value = take("OPTIONAL")
            cuts.append(
                ("remove-optional-v1", offset, offset + len(value), "Removed OPTIONAL")
            )
        take("MATCH")
        take("(")
        take(identifier=True)
        end, value = take(")")
        if index != len(parts):
            return []
        cuts.append(
            (
                "remove-match-v1",
                start,
                end + len(value),
                "Removed the terminal MATCH clause",
            )
        )
        return cuts
    except (IndexError, ValueError):
        return []


def candidates(case):
    for transform, start, end, description in query_cuts(case.query):
        content = case.model_dump()
        content["query"] = case.query[:start] + case.query[end:]
        yield (
            "query",
            transform,
            encode(content),
            ReductionChange(
                start=start,
                end=end,
                originalTextSha256=digest_bytes(case.query[start:end].encode()),
                description=description,
            ),
        )
    for index, query in enumerate(case.setup):
        content = case.model_dump()
        content["setup"] = [q for i, q in enumerate(case.setup) if i != index]
        yield (
            "fixture",
            "remove-setup-v1",
            encode(content),
            ReductionChange(
                setupIndex=index,
                originalTextSha256=digest_bytes(query.encode()),
                description=f"Removed setup statement {index + 1}",
            ),
        )
