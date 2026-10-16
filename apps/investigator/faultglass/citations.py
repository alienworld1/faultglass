from .llm_provider import ProviderFailure


def reference_context(context):
    references = {
        f"r{index}": identity
        for index, identity in enumerate(dict.fromkeys(context["evidenceIds"]), 1)
    }
    return {
        **context,
        "evidenceIds": list(references),
        "evidenceReferences": references,
    }


def resolve_citations(model, references):
    def resolve(value):
        if isinstance(value, dict):
            return {
                key: [references[identity] for identity in item]
                if key == "evidenceIds"
                else resolve(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return value

    try:
        return type(model).model_validate(resolve(model.model_dump()))
    except KeyError:
        raise ProviderFailure("invalid_citation") from None
