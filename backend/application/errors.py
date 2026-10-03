"""Use-case errors translated by the API boundary."""


class NotFoundError(LookupError):
    """A requested object is absent."""


class ForbiddenError(PermissionError):
    """The user cannot access the requested trip."""


class IdempotencyConflictError(ValueError):
    """A client key was reused for a different event."""
