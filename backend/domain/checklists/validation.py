"""Check required steps using the trip's configuration snapshot."""

from collections.abc import Iterable, Mapping

from backend.domain.errors import IncompleteChecklistError


def missing_required_steps(
    steps: Iterable[Mapping[str, object]], completed_codes: Iterable[str]
) -> tuple[str, ...]:
    """Return missing required step codes in snapshot order."""
    completed = set(completed_codes)
    return tuple(
        str(step["code"])
        for step in sorted(steps, key=lambda item: int(item["order"]))
        if step.get("required") is True and step["code"] not in completed
    )


def validate_required_steps(
    steps: Iterable[Mapping[str, object]], completed_codes: Iterable[str]
) -> None:
    """Require every mandatory step before an event is completed."""
    missing = missing_required_steps(steps, completed_codes)
    if missing:
        raise IncompleteChecklistError(missing)
