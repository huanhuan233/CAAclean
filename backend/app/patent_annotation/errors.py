class PatentAnnotationError(Exception):
    """A stable, user-safe patent annotation failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
