import re

from pydantic import Field, model_validator
from pygments.token import Comment, Keyword, Name, Number, String, Whitespace

from .canonicalize import case_identity
from .cypher import BoundaryLexer
from .execution import validate_parameters
from .jsonio import encode
from .models import Contract, read_case


class SourceEdit(Contract):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    before: str = Field(max_length=16384)
    after: str = Field(min_length=1, max_length=16384)

    @model_validator(mode="after")
    def span(self):
        if self.end < self.start or self.end - self.start != len(self.before):
            raise ValueError("The saved transformation span does not agree.")
        return self


def terminal_span(query):
    parts = [
        (offset, kind, text)
        for offset, kind, text in BoundaryLexer().get_tokens_unprocessed(query)
        if kind not in Comment and kind not in Whitespace
    ]
    if parts and parts[-1][2] == ";":
        parts.pop()
    index = 0

    def take(text=None, identifier=False, literal=False):
        nonlocal index
        if index == len(parts):
            raise ValueError("unsupported_shape")
        offset, kind, value = parts[index]
        if text is not None:
            valid = value.upper() == text and (
                kind in Keyword if text.isalpha() else True
            )
        elif identifier:
            valid = kind in Name and (
                bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value))
                or bool(re.fullmatch(r"`(?:``|[^`])+`", value))
            )
        else:
            valid = literal and (
                kind in String
                or kind in Number
                or value.upper() in ("TRUE", "FALSE", "NULL")
            )
        if not valid:
            raise ValueError("unsupported_shape")
        index += 1
        return offset, value

    try:
        take("CALL")
        take(identifier=True)
        while index < len(parts) and parts[index][2] == ".":
            take(".")
            take(identifier=True)
        take("(")
        if index < len(parts) and parts[index][2] != ")":
            take(literal=True)
            while index < len(parts) and parts[index][2] == ",":
                take(",")
                take(literal=True)
        take(")")
        take("YIELD")
        _, binding = take(identifier=True)
        start, match = take("MATCH")
        take("(")
        take(identifier=True)
        take(")")
        if index != len(parts):
            return None
        return start, start + len(match), binding
    except ValueError:
        return None


def transform(case, definition):
    if not definition.enabled:
        return None, None, "disabled"
    span = terminal_span(case.query)
    if span is None:
        return None, None, "unsupported_shape"
    start, end, binding = span
    if definition.type == "REPLACE_TERMINAL_MATCH_WITH_OPTIONAL":
        replacement = "OPTIONAL MATCH"
    elif definition.type == "INSERT_WITH_BEFORE_TERMINAL_MATCH":
        end = start
        replacement = "WITH " + binding + " "
    else:
        return None, None, "unmet_precondition"
    edit = SourceEdit(
        start=start, end=end, before=case.query[start:end], after=replacement
    )
    try:
        content = case.model_dump()
        content["query"] = case.query[:start] + replacement + case.query[end:]
        output = read_case(encode(content))
        validate_parameters(output)
        if case_identity(output)[0] == case_identity(case)[0]:
            return None, None, "unchanged_output"
        return output, edit, "applicable"
    except ValueError:
        return None, None, "invalid_output"
