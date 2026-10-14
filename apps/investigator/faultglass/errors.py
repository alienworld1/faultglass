class ExecutionFailure(Exception):
    def __init__(self, code, stage, message, role=None):
        super().__init__(message)
        self.code, self.stage, self.message, self.role = code, stage, message, role


class DeadlineExceeded(Exception):
    pass
