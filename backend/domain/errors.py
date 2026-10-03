"""Errors raised by business rules, independent of transport and persistence."""


class DomainError(ValueError):
    """A business invariant was violated."""


class InvalidTransitionError(DomainError):
    """The requested state transition is not allowed."""


class IncompleteChecklistError(DomainError):
    """Required steps in the trip's configuration snapshot are unfinished."""

    def __init__(self, missing_steps: tuple[str, ...]) -> None:
        self.missing_steps = missing_steps
        super().__init__("Required checklist steps are unfinished")
