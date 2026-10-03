"""Two-phase attachment persistence with trip-scoped authorization."""

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.application.errors import ForbiddenError, NotFoundError
from backend.domain.errors import DomainError
from backend.infrastructure.postgres import models as db
from backend.infrastructure.storage import ObjectStore

UPLOAD_URL_SECONDS = 900
DOWNLOAD_URL_SECONDS = 300
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class PostgresAttachmentRepository:
    """Store event uploads and verify bytes before exposing a committed attachment."""

    def __init__(self, sessions: sessionmaker[Session], store: ObjectStore) -> None:
        self.sessions = sessions
        self.store = store

    def init_event_upload(
        self,
        *,
        client_event_id: UUID,
        trip_id: UUID,
        kind: str,
        mime: str,
        size: int,
        source: str,
        platform: str,
    ) -> dict:
        """Reserve one upload identified by a future client event ID."""
        attachment_id = uuid4()
        staging_key = f"staging/{attachment_id}"
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            known_kind = session.execute(
                select(db.attachment_kinds.c.code).where(db.attachment_kinds.c.code == kind)
            ).scalar_one_or_none()
            if known_kind is None:
                raise DomainError("Unknown attachment kind")
            session.execute(
                insert(db.attachments).values(
                    id=attachment_id,
                    owner_type="event",
                    owner_id=client_event_id,
                    trip_id=trip_id,
                    kind=kind,
                    storage_key=staging_key,
                    mime=mime,
                    size=size,
                    sha256=None,
                    width=None,
                    height=None,
                    watermark_meta=None,
                    source=source,
                    version_of=None,
                    state="init",
                    platform=platform,
                    created_at=now,
                )
            )
        return {
            "attachment_id": attachment_id,
            "upload_url": self.store.presign_put(staging_key, mime, UPLOAD_URL_SECONDS),
            "expires_at": now + timedelta(seconds=UPLOAD_URL_SECONDS),
        }

    def commit_event_upload(
        self,
        *,
        attachment_id: UUID,
        user_id: UUID,
        can_operate_trip,
        sha256: str,
        size: int,
        width: int | None,
        height: int | None,
        watermark_meta: dict | None,
    ) -> dict:
        """Commit copied bytes only when hash, length and trip access agree."""
        if not SHA256_PATTERN.fullmatch(sha256):
            raise DomainError("Invalid SHA-256")
        with self.sessions() as session:
            row = (
                session.execute(select(db.attachments).where(db.attachments.c.id == attachment_id))
                .mappings()
                .one_or_none()
            )
        if row is None or row["owner_type"] != "event" or row["trip_id"] is None:
            raise NotFoundError("Attachment not found")
        if not can_operate_trip(user_id, row["trip_id"]):
            raise ForbiddenError("Trip access denied")
        if row["state"] == "stored":
            if row["sha256"] != sha256.lower() or row["size"] != size:
                raise DomainError("Attachment commit differs from stored bytes")
            return {"attachment_id": attachment_id, "state": "stored"}
        if row["state"] != "init":
            raise DomainError("Attachment cannot be committed")
        final_key = f"attachments/{attachment_id}"
        actual_sha256, actual_size = self.store.commit_copy_and_hash(row["storage_key"], final_key)
        if actual_sha256 != sha256.lower() or actual_size != size or size != row["size"]:
            raise DomainError("Attachment checksum or size mismatch")
        with self.sessions.begin() as session:
            result = session.execute(
                update(db.attachments)
                .where(db.attachments.c.id == attachment_id, db.attachments.c.state == "init")
                .values(
                    storage_key=final_key,
                    sha256=actual_sha256,
                    size=actual_size,
                    width=width,
                    height=height,
                    watermark_meta=watermark_meta,
                    state="stored",
                )
            )
            if result.rowcount == 0:
                raise DomainError("Attachment was committed concurrently")
        return {"attachment_id": attachment_id, "state": "stored"}

    def download_url(self, attachment_id: UUID, trip_id: UUID) -> str:
        """Presign a stored attachment from an already authorized trip timeline."""
        with self.sessions() as session:
            storage_key = session.execute(
                select(db.attachments.c.storage_key).where(
                    db.attachments.c.id == attachment_id,
                    db.attachments.c.trip_id == trip_id,
                    db.attachments.c.state == "stored",
                )
            ).scalar_one_or_none()
        if storage_key is None:
            raise NotFoundError("Attachment not found")
        return self.store.presign_get(storage_key, DOWNLOAD_URL_SECONDS)
