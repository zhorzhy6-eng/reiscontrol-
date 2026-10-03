"""Version-1 payload validation for config-driven event types."""

from uuid import uuid4

import pytest

from backend.domain.errors import DomainError, IncompleteChecklistError
from backend.domain.events import validate_payload_v1


def test_photo_set_checks_snapshot_steps_and_gallery():
    attachment = uuid4()
    config = {
        "steps": [{"code": "front", "required": True, "min_photos": 1, "max_photos": 2}],
        "camera": {"allow_gallery": True},
    }
    payload = {
        "photos": [{"step_code": "front", "attachment_id": str(attachment), "source": "gallery"}]
    }
    assert validate_payload_v1("photo_set", payload, config) == (attachment,)
    with pytest.raises(DomainError, match="Gallery"):
        validate_payload_v1("photo_set", payload, config, gallery_enabled=False)
    with pytest.raises(IncompleteChecklistError):
        validate_payload_v1("photo_set", {"photos": []}, config)


def test_document_set_supports_multipage_and_requires_documents():
    config = {"documents": [{"code": "ttn", "required": True, "pages": "multi"}]}
    attachments = (uuid4(), uuid4())
    payload = {
        "documents": [
            {"document_code": "ttn", "attachment_id": str(attachment)} for attachment in attachments
        ]
    }
    assert validate_payload_v1("document_set", payload, config) == attachments
    with pytest.raises(IncompleteChecklistError):
        validate_payload_v1("document_set", {"documents": []}, config)


@pytest.mark.parametrize(
    ("primitive", "payload", "config"),
    [
        ("text", {"value": "T-123"}, {"required": True, "max_length": 20}),
        ("number", {"value": 123}, {"min": 0, "decimal": False}),
        ("confirm", {"value": True}, {}),
        ("geo_only", {"point_id": str(uuid4())}, {}),
        ("signature", {"attachment_id": str(uuid4()), "full_name": "Иван Иванов"}, {}),
    ],
)
def test_simple_primitive_shapes(primitive, payload, config):
    validate_payload_v1(primitive, payload, config)


def test_payload_rejects_unapproved_fields():
    with pytest.raises(DomainError, match="fields"):
        validate_payload_v1("confirm", {"value": True, "reason": "why"}, {})
