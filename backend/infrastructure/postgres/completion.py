"""Snapshot-driven completion checks over accepted immutable events."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.errors import DomainError, IncompleteChecklistError
from backend.domain.rules.completion import unmet_completion_rules
from backend.domain.trips import Trip
from backend.infrastructure.postgres import models as db


def missing_event_requirements(
    snapshot: dict, cargo_ids: list, accepted: set[tuple]
) -> tuple[str, ...]:
    """Require an accepted event for every mandatory event and cargo unit."""
    missing = []
    for event_type in snapshot.get("event_types", []):
        if not any(step.get("required") for step in event_type.get("steps", [])):
            continue
        code = event_type["code"]
        if event_type.get("scope") == "per_cargo_unit":
            for cargo_id in cargo_ids:
                if (code, cargo_id) not in accepted:
                    missing.append(f"{code}:{cargo_id}")
        elif (code, None) not in accepted:
            missing.append(code)
    return tuple(missing)


class PostgresTripCompletionPolicy:
    """Read the trip's frozen rules and accepted facts before closure."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def validate(self, trip: Trip) -> None:
        """Reject a trip whose frozen mandatory checklist is incomplete."""
        if trip.config_snapshot_id is None:
            raise DomainError("Trip has no configuration snapshot")
        with self.sessions() as session:
            snapshot = session.execute(
                select(db.config_snapshots.c.snapshot_json).where(
                    db.config_snapshots.c.id == trip.config_snapshot_id,
                    db.config_snapshots.c.trip_id == trip.id,
                )
            ).scalar_one_or_none()
            if snapshot is None:
                raise DomainError("Trip configuration snapshot is unavailable")
            cargo_ids = (
                session.execute(
                    select(db.cargo_units.c.id).where(db.cargo_units.c.trip_id == trip.id)
                )
                .scalars()
                .all()
            )
            events = session.execute(
                select(
                    db.events.c.event_type_code,
                    db.events.c.cargo_unit_id,
                    db.events.c.payload_jsonb,
                ).where(db.events.c.trip_id == trip.id, db.events.c.state == "accepted")
            ).all()
        accepted = {(event.event_type_code, event.cargo_unit_id) for event in events}
        missing = missing_event_requirements(snapshot, cargo_ids, accepted)
        photo_count = sum(
            len(event.payload_jsonb.get("photos", []))
            for event in events
            if isinstance(event.payload_jsonb, dict)
        )
        signature_present = any(
            event_type.get("primitive") == "signature"
            and any(event.event_type_code == event_type["code"] for event in events)
            for event_type in snapshot.get("event_types", [])
        )
        unmet = unmet_completion_rules(
            snapshot.get("completion_rules", []),
            missing_steps=missing,
            photo_count=photo_count,
            track_number=trip.track_number,
            signature_present=signature_present,
        )
        if missing or unmet:
            raise IncompleteChecklistError((*missing, *unmet))
