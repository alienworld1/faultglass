from pygments.token import Keyword, Name, Number, String

from .canonicalize import statement_tokens
from .feature_catalog import CATALOG_VERSION
from .jsonio import digest

FINGERPRINT_VERSION = "fingerprint-v1"
CLAUSES = {
    "CALL",
    "YIELD",
    "MATCH",
    "WITH",
    "WHERE",
    "UNWIND",
    "CREATE",
    "MERGE",
    "RETURN",
    "LIMIT",
    "SKIP",
    "UNION",
}
WRITES = {"CREATE", "MERGE", "SET", "DELETE", "REMOVE", "FOREACH"}
AGGREGATES = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "collect",
    "stdev",
    "stdevp",
    "percentilecont",
    "percentiledisc",
}


def syntax(parts, index, text=None):
    if not 0 <= index < len(parts):
        return False
    kind, value = parts[index]
    if kind != str(Keyword):
        return False
    if index and parts[index - 1][1] in (".", ":", "$", "(", "-[", "<-["):
        return False
    if index + 1 < len(parts) and parts[index + 1][1] == ":":
        return False
    return text is None or value.upper() == text


def scan_features(parts):
    features, clauses = set(), []
    texts = [value for _, value in parts]
    relationship = False
    for i, (kind, value) in enumerate(parts):
        upper = value.upper()
        if syntax(parts, i):
            if upper in CLAUSES:
                clause = (
                    "OPTIONAL_MATCH"
                    if upper == "MATCH" and syntax(parts, i - 1, "OPTIONAL")
                    else upper
                )
                features.add(clause)
                clauses.append(clause)
            if upper in WRITES:
                features.add("WRITE_CLAUSE")
            if upper in {"DISTINCT", "NULL"}:
                features.add("NULL_SEMANTICS" if upper == "NULL" else upper)
            if upper == "ORDER" and syntax(parts, i + 1, "BY"):
                features.add("ORDERING")
                clauses.append("ORDER_BY")
            if upper == "AS" and i + 1 < len(parts) and parts[i + 1][0] == str(Name):
                features.add("ALIAS_SCOPE")
        if value in ("-[", "<-["):
            relationship = True
        elif relationship and "]" in value:
            relationship = False
        elif relationship and value == "*":
            features.add("VARIABLE_LENGTH_PATH")
        elif relationship and value == "|":
            features.add("RELATIONSHIP_TYPE_CARDINALITY")
        if (
            kind == str(Name)
            and value.lower() in AGGREGATES
            and texts[i + 1 : i + 2] == ["("]
            and (not i or texts[i - 1] not in (".", ":", "$"))
        ):
            features.add("AGGREGATION")
        if (
            value == "{"
            and i
            and (syntax(parts, i - 1, "CALL") or syntax(parts, i - 1, "EXISTS"))
        ):
            features.add("SUBQUERY")
        if (
            kind == str(Name)
            and texts[i + 1 : i + 3] == ["=", "("]
            and i
            and (syntax(parts, i - 1, "MATCH") or texts[i - 1] == ",")
        ):
            features.add("PATH_VALUE")
        if kind == str(Name) and texts[i + 1 : i + 2] == ["."] and i + 2 < len(parts):
            # Procedure/function names are not property access.
            end = i + 2
            while end + 1 < len(parts) and texts[end + 1] == ".":
                end += 2
            if texts[end + 1 : end + 2] != ["("] and (not i or texts[i - 1] != "$"):
                features.add("PROPERTY_ACCESS")
    return features, clauses


def normalize_simple(parts):
    """Normalize only a single simple pattern binding and its direct references."""
    features, _ = scan_features(parts)
    uncertain = bool(
        features & {"WITH", "YIELD", "UNWIND", "UNION", "SUBQUERY"}
    ) or any(
        v in ("{", "}", "[", "]")
        or (k == str(Keyword) and v.upper() in ("IN", "FOREACH"))
        for k, v in parts
    )
    result = [part.copy() for part in parts]
    reasons = []
    bindings = {}
    if not uncertain:
        active_clause = None
        for i, (kind, value) in enumerate(parts):
            if syntax(parts, i) and value.upper() in CLAUSES:
                active_clause = value.upper()
            if (
                active_clause in ("MATCH", "CREATE", "MERGE")
                and kind == str(Name)
                and i
                and parts[i - 1][1] in ("(", "-[", "<-[")
            ):
                # An opening function parenthesis does not introduce a binding.
                opening = i - 1
                if opening and parts[opening - 1][0] == str(Name):
                    continue
                if i + 1 < len(parts) and parts[i + 1][1] in (
                    ":",
                    ")",
                    "]->",
                    "]-",
                    "*",
                    "|",
                ):
                    bindings.setdefault(value, "v" + str(len(bindings)))
        if any(syntax(parts, i, "AS") for i in range(len(parts))):
            uncertain = True
    if uncertain:
        reasons.append("UNCERTAIN_SCOPE")
    else:
        for i, (kind, value) in enumerate(parts):
            if value in bindings and kind == str(Name):
                previous = parts[i - 1][1] if i else ""
                following = parts[i + 1][1] if i + 1 < len(parts) else ""
                if previous not in (".", ":", "$") and following != "(":
                    result[i] = ["variable", bindings[value]]
        if bindings:
            features.add("ALIAS_SCOPE")
        # Standalone scalar RETURN lists only; preserve aliases and other expressions.
        if (
            parts
            and syntax(parts, 0, "RETURN")
            and all(
                k in (str(Number), str(String))
                or v == ","
                or (k == str(Keyword) and v.upper() in ("NULL", "TRUE", "FALSE"))
                for k, v in parts[1:]
            )
        ):
            seen = {}
            for i, (kind, value) in enumerate(parts[1:], 1):
                if kind in (str(Number), str(String)):
                    literal_class = (
                        "string"
                        if kind == str(String)
                        else "float"
                        if any(c in value.lower() for c in (".", "e"))
                        else "integer"
                    )
                    # Zero is structural; do not merge it with nonzero values.
                    if literal_class != "string" and float(value) == 0:
                        continue
                    key = (literal_class, value)
                    seen.setdefault(key, str(sum(k[0] == literal_class for k in seen)))
                    result[i] = [literal_class, seen[key]]
        elif any(k.startswith("Token.Literal") for k, _ in parts):
            reasons.append("EXACT_LITERAL_CONTEXT")
    for i, (kind, value) in enumerate(result):
        if syntax(parts, i) and not uncertain:
            result[i] = [kind, value.upper()]
    if not parts or not any(
        syntax(parts, i) and v.upper() in CLAUSES for i, (_, v) in enumerate(parts)
    ):
        reasons.append("UNSUPPORTED_STATEMENT")
    return result, features, reasons


def extract_statement(query):
    canonical = statement_tokens(query)
    if "exact" in canonical:
        return canonical, set(), [], ["LEXICAL_FALLBACK"]
    parts = canonical["tokens"]
    shape, features, reasons = normalize_simple(parts)
    _, clauses = scan_features(parts)
    return {"tokens": shape}, features, clauses, reasons


def extract_fingerprint(case):
    statements = [
        *case.setup,
        case.query,
        *(c.query for c in case.observation.postconditions),
    ]
    extracted = [extract_statement(query) for query in statements]
    features = sorted(set().union(*(entry[1] for entry in extracted)))
    reasons = sorted({reason for entry in extracted for reason in entry[3]})
    observation = case.observation.model_dump()
    observation["postconditions"] = [
        {"name": check.name, "parameters": check.parameters}
        for check in case.observation.postconditions
    ]
    shape = {
        "setup": [entry[0] for entry in extracted[: len(case.setup)]],
        "query": extracted[len(case.setup)][0],
        "postconditions": [entry[0] for entry in extracted[len(case.setup) + 1 :]],
        "parameters": case.parameters,
        "observation": observation,
        "expectation": case.expectation.model_dump() if case.expectation else None,
    }
    signature = " ".join(extracted[len(case.setup)][2])
    if not signature or len(signature) > 512:
        signature = "UNSUPPORTED"
    identity = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "normalized_shape": shape,
        "feature_ids": features,
    }
    return {
        "id": digest(identity),
        "version": FINGERPRINT_VERSION,
        "catalog_version": CATALOG_VERSION,
        "normalized_shape": shape,
        "shape_hash": digest(shape),
        "clause_signature": signature,
        "feature_ids": features,
        "analysis_support": "conservative" if reasons else "supported",
        "unsupported_reasons": reasons,
    }
