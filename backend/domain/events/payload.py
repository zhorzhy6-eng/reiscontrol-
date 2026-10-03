"""Validate the approved version-1 payload for each configured primitive."""

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from backend.domain.errors import DomainError, IncompleteChecklistError


def validate_payload_v1(
    primitive: str,
    payload: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    gallery_enabled: bool = True,
) -> tuple[UUID, ...]:
    """Validate a payload against its trip snapshot and return attachment IDs."""
    if primitive == "photo_set":
        return _validate_photos(payload, config, gallery_enabled)
    if primitive == "document_set":
        return _validate_documents(payload, config)
    if primitive == "text":
        _require_keys(payload, {"value"})
        value = payload["value"]
        if not isinstance(value, str):
            raise DomainError("Text value must be a string")
        if config.get("required") and not value.strip():
            raise DomainError("Text value is required")
        if len(value) < int(config.get("min_length", 0)):
            raise DomainError("Text value is too short")
        if len(value) > int(config.get("max_length", 500)):
            raise DomainError("Text value is too long")
        pattern = config.get("pattern")
        if pattern and re.fullmatch(str(pattern), value) is None:
            raise DomainError("Text value does not match its pattern")
        return ()
    if primitive == "number":
        _require_keys(payload, {"value"})
        value = payload["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainError("Number value must be numeric")
        if not config.get("decimal", False) and not float(value).is_integer():
            raise DomainError("Number value must be an integer")
        if "min" in config and value < config["min"]:
            raise DomainError("Number value is below minimum")
        if "max" in config and value > config["max"]:
            raise DomainError("Number value exceeds maximum")
        return ()
    if primitive == "confirm":
        _require_keys(payload, {"value"})
        if payload["value"] is not True:
            raise DomainError("Confirmation must be true")
        return ()
    if primitive == "geo_only":
        _require_keys(payload, {"point_id"})
        _as_uuid(payload["point_id"])
        return ()
    if primitive == "signature":
        expected = {"attachment_id"}
        if config.get("require_full_name", True):
            expected.add("full_name")
        elif "full_name" in payload:
            expected.add("full_name")
        _require_keys(payload, expected)
        if "full_name" in payload and not str(payload["full_name"]).strip():
            raise DomainError("Signer name is empty")
        return (_as_uuid(payload["attachment_id"]),)
    raise DomainError(f"Unsupported primitive: {primitive}")


def _validate_photos(
    payload: Mapping[str, Any], config: Mapping[str, Any], gallery_enabled: bool
) -> tuple[UUID, ...]:
    _require_keys(payload, {"photos"})
    photos = payload["photos"]
    if not isinstance(photos, list):
        raise DomainError("photos must be an array")
    steps = {str(step["code"]): step for step in config.get("steps", [])}
    counts: Counter[str] = Counter()
    attachments: list[UUID] = []
    allow_gallery = config.get("camera", {}).get("allow_gallery", True) and gallery_enabled
    for photo in photos:
        if not isinstance(photo, dict):
            raise DomainError("photo must be an object")
        _require_keys(photo, {"step_code", "attachment_id", "source"})
        step_code = photo["step_code"]
        if step_code not in steps:
            raise DomainError("Unknown photo step")
        if photo["source"] not in ("camera", "gallery"):
            raise DomainError("Invalid photo source")
        if photo["source"] == "gallery" and not allow_gallery:
            raise DomainError("Gallery is disabled")
        counts[step_code] += 1
        attachments.append(_as_uuid(photo["attachment_id"]))
    missing = tuple(
        code
        for code, step in steps.items()
        if step.get("required", False) and counts[code] < int(step.get("min_photos", 1))
    )
    if missing:
        raise IncompleteChecklistError(missing)
    for step_code, count in counts.items():
        if count > int(steps[step_code].get("max_photos", 1)):
            raise DomainError("Too many photos for step")
    _require_distinct(attachments)
    return tuple(attachments)


def _validate_documents(payload: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[UUID, ...]:
    _require_keys(payload, {"documents"})
    documents = payload["documents"]
    if not isinstance(documents, list):
        raise DomainError("documents must be an array")
    definitions = {str(item["code"]): item for item in config.get("documents", [])}
    counts: Counter[str] = Counter()
    attachments: list[UUID] = []
    for document in documents:
        if not isinstance(document, dict):
            raise DomainError("document must be an object")
        _require_keys(document, {"document_code", "attachment_id"})
        document_code = document["document_code"]
        if document_code not in definitions:
            raise DomainError("Unknown document code")
        counts[document_code] += 1
        attachments.append(_as_uuid(document["attachment_id"]))
    missing = tuple(
        code
        for code, definition in definitions.items()
        if definition.get("required") and not counts[code]
    )
    if missing:
        raise IncompleteChecklistError(missing)
    for document_code, count in counts.items():
        if count > 1 and definitions[document_code].get("pages", "single") == "single":
            raise DomainError("Single-page document has multiple attachments")
    _require_distinct(attachments)
    return tuple(attachments)


def _require_keys(payload: Mapping[str, Any], expected: set[str]) -> None:
    if set(payload) != expected:
        raise DomainError("Invalid payload fields")


def _as_uuid(value: Any) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise DomainError("Invalid attachment or point ID") from error


def _require_distinct(attachments: list[UUID]) -> None:
    if len(attachments) != len(set(attachments)):
        raise DomainError("Attachment ID is repeated")
