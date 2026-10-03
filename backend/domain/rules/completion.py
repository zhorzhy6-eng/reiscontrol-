"""Evaluate the documented completion rule primitives."""

from collections.abc import Iterable, Mapping

from backend.domain.errors import DomainError


def unmet_completion_rules(
    rules: Iterable[Mapping[str, object]],
    *,
    missing_steps: Iterable[str],
    photo_count: int,
    track_number: str | None,
    signature_present: bool,
) -> tuple[str, ...]:
    """Return unmet rule names from the trip's configuration snapshot."""
    missing = tuple(missing_steps)
    unmet: list[str] = []
    for rule in rules:
        rule_type = str(rule.get("rule", ""))
        if rule_type == "all_required_steps_done":
            satisfied = not missing
        elif rule_type == "min_photos":
            minimum = rule.get("count")
            if not isinstance(minimum, int) or minimum < 0:
                raise DomainError("min_photos needs a non-negative integer count")
            satisfied = photo_count >= minimum
        elif rule_type == "require_track_number":
            satisfied = bool(track_number and track_number.strip())
        elif rule_type == "require_signature":
            satisfied = signature_present
        else:
            raise DomainError(f"Unsupported completion rule: {rule_type}")
        if not satisfied:
            unmet.append(rule_type)
    return tuple(unmet)
