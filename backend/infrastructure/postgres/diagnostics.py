"""Queue privacy-filtered client errors for developer-bot delivery."""

from datetime import datetime, timezone
from uuid import uuid4

from backend.infrastructure.postgres import models as db
from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker


class PostgresDiagnosticRepository:
    """Persist retryable developer notifications in the generic integration queue."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def queue(self, *, level: str, message_code: str, trace_id: str, context: dict) -> None:
        """Enqueue only whitelisted codes and numeric context."""
        if level not in ("error", "crash"):
            return
        with self.sessions.begin() as session:
            session.execute(
                insert(db.integration_jobs).values(
                    id=uuid4(),
                    integration="devbot",
                    payload={
                        "level": level,
                        "message_code": message_code,
                        "trace_id": trace_id,
                        "context": context,
                    },
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                )
            )
