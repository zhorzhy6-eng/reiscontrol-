"""Exercise the stage-1 flow against disposable PostgreSQL and real MinIO."""

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.apps.api.main import app, get_services
from backend.apps.worker.outbox import OutboxWorker
from backend.infrastructure.postgres import models as db
from backend.infrastructure.postgres.outbox import PostgresOutboxRepository
from backend.infrastructure.postgres.seed import seed_stage1


def _uuid7() -> UUID:
    """Create a valid time-ordered test fact ID on Python 3.12 and newer."""
    timestamp_ms = int(time.time() * 1000)
    value = (
        (timestamp_ms << 80)
        | (0x7 << 76)
        | (secrets.randbits(12) << 64)
        | (0b10 << 62)
        | secrets.randbits(62)
    )
    return UUID(int=value)


def test_smoke_fact_ids_are_uuid7() -> None:
    """Keep the local generator usable with the API's UUIDv7 requirement."""
    assert _uuid7().version == 7


def _seed_trip(database_url: str) -> tuple[UUID, UUID, UUID, UUID, str, str]:
    now = datetime.now(timezone.utc)
    driver_id, logistician_id, client_id = uuid4(), uuid4(), uuid4()
    order_id, trip_id, cargo_id = uuid4(), uuid4(), uuid4()
    suffix = uuid4().hex[:10]
    phone_suffix = int(uuid4()) % 10**10
    driver_phone = f"+7000{phone_suffix:010d}"
    logistician_phone = f"+7111{phone_suffix:010d}"
    password_hash = PasswordHasher().hash("stage1-smoke-password")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(insert(db.cargo_types).values(code=f"cars_{suffix}", name="Cars"))
        connection.execute(insert(db.trip_types).values(code=f"direct_{suffix}", name="Direct"))
        connection.execute(insert(db.point_types).values(code=f"loading_{suffix}", name="Loading"))
        for user_id, phone, role in (
            (driver_id, driver_phone, "driver"),
            (logistician_id, logistician_phone, "logistician"),
        ):
            connection.execute(
                insert(db.users).values(
                    id=user_id,
                    phone=phone,
                    password_hash=password_hash,
                    role=role,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        connection.execute(
            insert(db.clients).values(
                id=client_id, name="Stage 1 smoke", inn=suffix, contact="test"
            )
        )
        connection.execute(
            insert(db.orders).values(
                id=order_id,
                client_id=client_id,
                cargo_type_code=f"cars_{suffix}",
                trip_type_code=f"direct_{suffix}",
                status="assigned",
                created_by=logistician_id,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(db.trips).values(
                id=trip_id,
                order_id=order_id,
                status="assigned",
                config_snapshot_id=None,
                started_at=None,
                closed_at=None,
                track_number=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(db.trip_participants).values(
                id=uuid4(),
                trip_id=trip_id,
                user_id=driver_id,
                role="driver",
                from_at=now - timedelta(minutes=1),
                to_at=None,
            )
        )
        connection.execute(
            insert(db.access_scopes).values(
                id=uuid4(),
                user_id=logistician_id,
                scope_type="client",
                scope_id=str(client_id),
                created_at=now,
            )
        )
        connection.execute(
            insert(db.cargo_units).values(
                id=cargo_id,
                trip_id=trip_id,
                vin=f"VIN{suffix}",
                make="Test",
                model="Car",
                position_in_truck=None,
                order_index=1,
                created_at=now,
            )
        )
    engine.dispose()
    seed_stage1(database_url)
    return driver_id, logistician_id, trip_id, cargo_id, driver_phone, logistician_phone


def _login(client: TestClient, phone: str, platform: str) -> dict[str, str]:
    device_id = str(uuid4())
    headers = {
        "X-Device-Id": device_id,
        "X-Platform": platform,
        "X-App-Version": "1.0",
    }
    response = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={
            "phone": phone,
            "password": "stage1-smoke-password",
            "device": {"device_id": device_id, "platform": platform, "app_version": "1.0"},
        },
    )
    assert response.status_code == 200, response.text
    return {**headers, "Authorization": f"Bearer {response.json()['access_token']}"}


def test_stage1_live_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify storage, configuration, scoped reads and idempotency on real services."""
    database_url = os.getenv("STAGE1_E2E_DATABASE_URL")
    if not database_url:
        pytest.skip("Set STAGE1_E2E_DATABASE_URL for a migrated disposable database")
    database_name = make_url(database_url).database
    if not database_name or not database_name.endswith("_test"):
        pytest.fail("STAGE1_E2E_DATABASE_URL must target a disposable *_test database")
    for key in ("OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_REGION"):
        if not os.getenv(key):
            pytest.fail(f"{key} is required for the live MinIO test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", "stage1-smoke-only-secret-at-least-32-chars")
    get_services.cache_clear()
    driver_id, logistician_id, trip_id, cargo_id, driver_phone, logistician_phone = _seed_trip(
        database_url
    )
    engine = create_engine(database_url)
    try:
        with TestClient(app) as client:
            driver = _login(client, driver_phone, "android")
            logistician = _login(client, logistician_phone, "web")
            chat_id = f"stage1-test-{uuid4().hex}"
            with engine.begin() as connection:
                connection.execute(
                    insert(db.telegram_subscriptions).values(
                        id=uuid4(),
                        user_id=logistician_id,
                        chat_id=chat_id,
                        enabled=True,
                        created_at=datetime.now(timezone.utc),
                    )
                )
            for consent_type in ("pd", "geo", "tracking"):
                response = client.post(
                    "/api/v1/me/consents",
                    headers=driver,
                    json={"consent_type": consent_type, "policy_version": "1.0"},
                )
                assert response.status_code == 201, response.text
            assert any(
                row["trip_id"] == str(trip_id)
                for row in client.get("/api/v1/orders", headers=driver).json()
            )
            start = client.post(f"/api/v1/trips/{trip_id}/start", headers=driver)
            assert start.status_code == 200, start.text
            snapshot_id = start.json()["config_snapshot_id"]
            snapshot = client.get(f"/api/v1/config/snapshots/{snapshot_id}", headers=driver)
            assert snapshot.status_code == 200, snapshot.text
            loading = next(
                item for item in snapshot.json()["event_types"] if item["code"] == "LOADING"
            )
            assert [step["code"] for step in loading["steps"]] == [
                "front_3_4",
                "rear_3_4",
                "vin_plate",
            ]
            event_id = _uuid7()
            photo_bytes = b"\xff\xd8\xff\xe0stage1-smoke\xff\xd9"
            digest = hashlib.sha256(photo_bytes).hexdigest()
            photos = []
            for step_code, source in (
                ("front_3_4", "camera"),
                ("rear_3_4", "gallery"),
                ("vin_plate", "camera"),
            ):
                init = client.post(
                    "/api/v1/attachments:init",
                    headers=driver,
                    json={
                        "owner_type": "event",
                        "owner_id": str(event_id),
                        "trip_id": str(trip_id),
                        "kind": "photo",
                        "mime": "image/jpeg",
                        "size": len(photo_bytes),
                        "source": source,
                    },
                )
                assert init.status_code == 200, init.text
                attachment_id = init.json()["attachment_id"]
                uploaded = httpx.put(
                    init.json()["upload_url"],
                    content=photo_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=20,
                )
                assert uploaded.status_code == 200, uploaded.text
                committed = client.post(
                    f"/api/v1/attachments/{attachment_id}:commit",
                    headers=driver,
                    json={
                        "sha256": digest,
                        "size": len(photo_bytes),
                        "width": 1,
                        "height": 1,
                        "watermark_meta": {"applied": True},
                    },
                )
                assert committed.status_code == 200, committed.text
                photos.append(
                    {"step_code": step_code, "attachment_id": attachment_id, "source": source}
                )
            event_body = {
                "client_event_id": str(event_id),
                "device_id": driver["X-Device-Id"],
                "trip_id": str(trip_id),
                "cargo_unit_id": str(cargo_id),
                "event_type_code": "LOADING",
                "payload_schema_version": 1,
                "payload": {"photos": photos},
                "device_time_utc": datetime.now(timezone.utc).isoformat(),
                "lat": 55.75,
                "lon": 37.62,
                "accuracy_m": 10,
                "location_source": "platform",
            }
            event_headers = {**driver, "Idempotency-Key": str(event_id)}
            first = client.post("/api/v1/events", headers=event_headers, json=event_body)
            repeat = client.post("/api/v1/events", headers=event_headers, json=event_body)
            assert first.status_code == repeat.status_code == 200, first.text
            assert first.json()["id"] == repeat.json()["id"]
            conflict = client.post(
                "/api/v1/events",
                headers=event_headers,
                json={**event_body, "lat": 55.76},
            )
            assert conflict.status_code == 409, conflict.text
            timeline = client.get(f"/api/v1/trips/{trip_id}/events", headers=logistician)
            assert timeline.status_code == 200, timeline.text
            assert len(timeline.json()) == 1
            assert len(timeline.json()[0]["attachments"]) == 3

            class CapturingTelegram:
                def __init__(self) -> None:
                    self.sent: list[tuple[str, str]] = []

                def send_message(self, recipient: str, message: str) -> None:
                    self.sent.append((recipient, message))

            telegram = CapturingTelegram()
            worker = OutboxWorker(PostgresOutboxRepository(sessionmaker(engine)), telegram)
            assert worker.run_once()
            assert len(telegram.sent) == 1
            assert telegram.sent[0][0] == chat_id
            assert "LOADING" in telegram.sent[0][1]
            track = {
                "client_track_id": str(_uuid7()),
                "trip_id": str(trip_id),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "lat": 55.75,
                "lon": 37.62,
                "accuracy_m": 10,
                "location_source": "platform",
            }
            track_body = {"tracks": [track]}
            assert (
                client.post("/api/v1/location/tracks", headers=driver, json=track_body).status_code
                == 202
            )
            assert (
                client.post("/api/v1/location/tracks", headers=driver, json=track_body).status_code
                == 202
            )
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(db.events)
                        .where(db.events.c.client_event_id == event_id)
                    )
                    == 1
                )
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(db.location_tracks)
                        .where(
                            db.location_tracks.c.client_track_id == UUID(track["client_track_id"])
                        )
                    )
                    == 1
                )
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(db.outbox)
                        .where(db.outbox.c.event_id == UUID(first.json()["id"]))
                    )
                    == 1
                )
                assert (
                    connection.scalar(
                        select(db.outbox.c.status).where(
                            db.outbox.c.event_id == UUID(first.json()["id"])
                        )
                    )
                    == "sent"
                )
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(db.notification_log)
                        .where(db.notification_log.c.event_id == UUID(first.json()["id"]))
                    )
                    == 1
                )
                assert (
                    connection.scalar(
                        select(db.user_consents.c.id).where(
                            db.user_consents.c.user_id == driver_id,
                            db.user_consents.c.consent_type == "tracking",
                        )
                    )
                    is not None
                )
    finally:
        engine.dispose()
        get_services.cache_clear()
