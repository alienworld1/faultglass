REQUIRED_MESSAGES = {
    "query": "Add a query to compare.",
    "title": "Give this case a name.",
    "setup": "Provide setup statements, or an empty list.",
    "schemaVersion": "Use case version 1.",
    "observation": "Choose what to compare and how to order rows.",
    "compareResult": "Choose whether to compare results.",
    "ordering": "Choose ordered or unordered comparison.",
}


def case_error(item):
    field = ".".join(map(str, item["loc"]))
    if item["type"] == "missing":
        message = REQUIRED_MESSAGES.get(
            str(item["loc"][-1]), "Add this field to your case."
        )
    elif item["type"] == "extra_forbidden":
        message = "Remove this unsupported field."
    else:
        message = item["msg"].removeprefix("Value error, ")
    return field + ": " + message
