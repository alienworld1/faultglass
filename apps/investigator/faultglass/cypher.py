from typing import ClassVar

from pygments.lexers.graph import CypherLexer
from pygments.token import Comment, Name, String, Whitespace


class BoundaryLexer(CypherLexer):
    tokens: ClassVar[dict] = {
        "root": [
            (r"/\*([^*]|\*(?!/))*\*/", Comment.Multiline),
            (r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", String),
            (r"`(?:``|[^`])*`", Name.Variable),
        ]
        + CypherLexer.tokens["root"],
    }


def tokens(query):
    return [
        (kind, text) for _, kind, text in BoundaryLexer().get_tokens_unprocessed(query)
    ]


def statement(query):
    if not query.strip():
        raise ValueError("Add a query to compare.")
    if len(query.encode()) > 16384:
        raise ValueError("Keep each statement within 16 KiB.")
    parts = tokens(query)
    visible = [
        (kind, text)
        for kind, text in parts
        if kind not in Comment and kind not in Whitespace
    ]
    if any(
        text in ("'", '"', "`")
        for kind, text in visible
        if kind not in String and kind != Name.Variable
    ):
        raise ValueError("Close quoted text before comparing this statement.")
    if any(
        parts[i][1] == "/" and parts[i + 1][1] == "*" for i in range(len(parts) - 1)
    ):
        raise ValueError("Close the block comment before comparing this statement.")
    separators = [
        i
        for i, (kind, text) in enumerate(visible)
        if text == ";" and kind not in String and kind != Name.Variable
    ]
    if separators and separators != [len(visible) - 1]:
        raise ValueError("Use exactly one statement per entry.")
    return query


def readonly(query):
    statement(query)
    parts = [
        (kind, text.upper())
        for kind, text in tokens(query)
        if kind not in Comment and kind not in Whitespace
    ]
    if not parts or parts[0][1] not in (
        "MATCH",
        "OPTIONAL",
        "RETURN",
        "WITH",
        "UNWIND",
    ):
        raise ValueError("Use a supported read-only query for this state check.")
    forbidden = {
        "CREATE",
        "MERGE",
        "SET",
        "DELETE",
        "DETACH",
        "REMOVE",
        "DROP",
        "CALL",
        "LOAD",
        "FOREACH",
    }
    if any(
        text in forbidden and kind not in String and kind != Name.Variable
        for kind, text in parts
    ):
        raise ValueError("Use a supported read-only query for this state check.")
    return query
