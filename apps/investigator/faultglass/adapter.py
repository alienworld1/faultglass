from .models import EngineError
from .normalize import result


def classify_error(detail):
    category = "UNKNOWN"
    if detail.startswith("Query cannot conclude with MATCH"):
        category = "SEMANTIC"
    return EngineError(category=category, detail=detail[:16384])


def validate_scalar(cell):
    if not isinstance(cell, list) or len(cell) != 2 or type(cell[0]) is not int:
        raise ValueError("The engine returned an ambiguous typed value.")
    kind, value = cell
    if kind not in range(1, 11):
        raise ValueError("This engine value type is not supported.")
    if kind == 6:
        for inner in value:
            validate_scalar(inner)
    elif kind == 10:
        keys = value[::2]
        if (
            len(value) % 2
            or any(type(key) is not str for key in keys)
            or len(set(keys)) != len(keys)
        ):
            raise ValueError("The engine returned ambiguous map keys.")
        for inner in value[1::2]:
            validate_scalar(inner)
    elif kind in (7, 8):
        properties = value[4] if kind == 7 else value[2]
        if len({prop[0] for prop in properties}) != len(properties):
            raise ValueError("The engine returned ambiguous graph properties.")
        for prop in properties:
            validate_scalar(prop[1:])
    elif kind == 9:
        for inner in value:
            validate_scalar(inner)
    elif kind == 4 and value not in ("true", "false"):
        raise ValueError("The engine returned an ambiguous boolean.")
    elif kind == 3 and not (type(value) is int or type(value) is str):
        raise ValueError("The engine integer lost precision in transport.")
    elif kind == 2 and type(value) is not str:
        raise ValueError("The engine string representation is ambiguous.")


def decode_result(graph, raw, ordered, limits):
    from falkordb.query_result import QueryResult

    if not isinstance(raw, list) or len(raw) not in (1, 3):
        raise ValueError("The engine returned an incomplete observation.")
    if len(raw) == 3:
        if len(raw[1]) > limits.rows:
            raise ValueError("The output exceeded the comparison limit.")
        for row in raw[1]:
            for cell in row:
                validate_scalar(cell)
    parsed = QueryResult(graph, raw)
    return result(
        [column[1] for column in parsed.header], parsed.result_set, ordered, limits
    )


def checked_result(graph, raw, ordered, limits):
    try:
        return decode_result(graph, raw, ordered, limits)
    except (TypeError, IndexError, KeyError, OverflowError, RecursionError) as error:
        raise ValueError(
            "The engine returned an ambiguous or unsupported observation."
        ) from error


def query(graph, transport, text, parameters, ordered, limits, read_only=False):
    command = "GRAPH.RO_QUERY" if read_only else "GRAPH.QUERY"
    raw = transport.command(
        command,
        graph.name,
        (graph._build_params_header(parameters) if parameters else "") + text,
        "--compact",
        "timeout",
        limits.querySeconds * 1000,
    )
    return checked_result(graph, raw, ordered, limits)
