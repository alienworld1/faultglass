class ContextError(ValueError):
    pass


class ContextUnavailable(ContextError):
    def __init__(self):
        super().__init__(
            "Investigation memory is unavailable. Check the context service and try again."
        )


class SchemaIncompatible(ContextError):
    def __init__(self):
        super().__init__(
            "Investigation memory needs a compatible schema. Check the setup instructions."
        )


class EvidenceIntegrity(ContextError):
    def __init__(self):
        super().__init__(
            "Saved evidence is missing or has changed. Restore the original evidence before trying again."
        )


class IdentityConflict(ContextError):
    def __init__(self):
        super().__init__(
            "Saved context conflicts with this evidence. Keep the original evidence and inspect the conflict."
        )
