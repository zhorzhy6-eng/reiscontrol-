"""In-process HTTP contract tests for the walking-skeleton routes."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.application.auth import AuthUser
from backend.application.ports import StoredEvent
from backend.apps.api.main import app, get_services
from backend.domain.trips import Trip
from backend.infrastructure.security import Hs256Tokens

CLIENT_EVENT_ID = UUID("0199c6d4-33ef-7c45-9bd2-6d443f8142e1")


class FakeAuth:
    def __init__(self):
        self.user = AuthUser(uuid4(), "+70000000000", "hash", "driver", True)
        self.device_id = None
        self.token_hash = None
        self.expires_at = None

    def get_by_phone(self, phone):
        return self.user if phone == self.user.phone else None

    def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None

    def register_device(self, user_id, device_id, platform, app_version):
        self.device_id = device_id

    def save_refresh(self, user_id, device_id, token_hash, expires_at):
        self.token_hash = token_hash
        self.expires_at = expires_at

    def find_refresh_user(self, token_hash, now):
        if token_hash == self.token_hash and now < self.expires_at:
            return self.user.id, self.device_id
        return None


class FakePasswords:
    def verify(self, password_hash, password):
        return password == "valid-password"


class FakeUsers:
    def can_access_trip(self, user_id, trip_id):
        return True

    def can_operate_trip(self, user_id, trip_id):
        return True


class FakeTrips:
    def __init__(self):
        self.trip = Trip(uuid4(), uuid4(), uuid4(), "in_progress")

    def get(self, trip_id):
        return self.trip if trip_id == self.trip.id else None

    def save(self, trip):
        self.trip = trip


class FakeSnapshots:
    def freeze_for_trip(self, trip):
        return uuid4()


class FakeCompletion:
    def validate(self, trip):
        return None


class FakeDiagnostics:
    def __init__(self):
        self.queued = []

    def queue(self, **kwargs):
        self.queued.append(kwargs)


class FakeConfiguration:
    def validate(self, event, config_snapshot_id):
        return None


class FakeEvents:
    def __init__(self):
        self.saved = None
        self.insert_count = 0

    def get_by_client_key(self, client_event_id, device_id):
        return self.saved

    def save_once_with_notification(self, event, *, user_id, app_version, platform):
        self.insert_count += 1
        self.saved = StoredEvent(uuid4(), event)
        return self.saved


class FakeReads:
    def __init__(self, trip_id):
        self.trip_id = trip_id

    def orders_for_user(self, user_id):
        return [
            {
                "id": uuid4(),
                "client_name": "Клиент",
                "cargo_type_code": "cars",
                "status": "assigned",
                "created_at": datetime.now(timezone.utc),
                "trip_id": self.trip_id,
            }
        ]

    def events_for_trip(self, trip_id):
        return [{"id": uuid4(), "trip_id": trip_id, "state": "accepted", "attachments": []}]

    def trip(self, trip_id):
        return {"id": trip_id, "status": "in_progress"}

    def trips_for_user(self, user_id):
        return [self.trip(self.trip_id)]


class FakeConsents:
    def __init__(self):
        self.items = []

    def list_for_user(self, user_id):
        return self.items

    def accept(self, *, user_id, consent_type, policy_version, platform, ip):
        record = {
            "consent_type": consent_type,
            "policy_version": policy_version,
            "accepted_at": datetime.now(timezone.utc),
            "revoked_at": None,
        }
        self.items.append(record)
        return record


class FakeTracks:
    def __init__(self):
        self.items = []

    def append_batch(self, *, user_id, device_id, tracks, can_operate_trip):
        self.items.extend(tracks)

    def for_trip(self, trip_id):
        return self.items


class FakeAttachments:
    def __init__(self):
        self.attachment_id = uuid4()

    def init_event_upload(self, **kwargs):
        self.init_context = kwargs
        return {
            "attachment_id": self.attachment_id,
            "upload_url": "https://storage.example/upload",
            "expires_at": datetime.now(timezone.utc),
        }

    def commit_event_upload(self, **kwargs):
        self.commit_context = kwargs
        return {"attachment_id": self.attachment_id, "state": "stored"}

    def download_url(self, attachment_id, trip_id):
        return "https://storage.example/read"


def test_event_post_is_authenticated_and_idempotent():
    auth = FakeAuth()
    events = FakeEvents()
    trips = FakeTrips()
    tokens = Hs256Tokens("a" * 32)
    services = SimpleNamespace(
        auth=auth,
        passwords=FakePasswords(),
        tokens=tokens,
        events=events,
        trips=trips,
        users=FakeUsers(),
        configuration=FakeConfiguration(),
        reads=FakeReads(trips.trip.id),
        consents=FakeConsents(),
        tracks=FakeTracks(),
        attachments=FakeAttachments(),
        snapshots=FakeSnapshots(),
        completion=FakeCompletion(),
        diagnostics=FakeDiagnostics(),
    )
    app.dependency_overrides[get_services] = lambda: services
    try:
        client = TestClient(app)
        device_id = uuid4()
        headers = {
            "X-App-Version": "1.0.0",
            "X-Platform": "android",
            "X-Device-Id": str(device_id),
            "X-Trace-Id": str(CLIENT_EVENT_ID),
        }
        login_response = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={
                "phone": auth.user.phone,
                "password": "valid-password",
                "device": {
                    "device_id": str(device_id),
                    "platform": "android",
                    "app_version": "1.0.0",
                },
            },
        )
        assert login_response.status_code == 200
        headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"
        headers["Idempotency-Key"] = str(CLIENT_EVENT_ID)
        body = {
            "client_event_id": str(CLIENT_EVENT_ID),
            "device_id": str(device_id),
            "trip_id": str(trips.trip.id),
            "event_type_code": "CONFIGURED_TYPE",
            "payload": {"value": "arrived"},
            "payload_schema_version": 1,
            "device_time_utc": datetime.now(timezone.utc).isoformat(),
            "device_tz_offset_min": 180,
            "elapsed_realtime_ms": 1234,
        }
        first = client.post("/api/v1/events", headers=headers, json=body)
        again = client.post("/api/v1/events", headers=headers, json=body)
        assert first.status_code == 200
        assert again.status_code == 200
        assert first.json()["id"] == again.json()["id"]
        assert first.json()["state"] == "accepted"
        assert events.insert_count == 1
        conflict = client.post(
            "/api/v1/events", headers=headers, json={**body, "payload": {"value": "changed"}}
        )
        assert conflict.status_code == 409
        orders = client.get("/api/v1/orders", headers=headers)
        assert orders.status_code == 200
        timeline = client.get(f"/api/v1/trips/{trips.trip.id}/events", headers=headers)
        assert timeline.status_code == 200
        assert timeline.json()[0]["state"] == "accepted"
        sync = client.post(
            "/api/v1/sync",
            headers=headers,
            json={
                "device_time_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_realtime_ms": 1234,
            },
        )
        assert sync.status_code == 200
        assert sync.json()["clock_skew_ms"] is not None
        assert len(sync.json()["trips"]) == 1
        consent = client.post(
            "/api/v1/me/consents",
            headers=headers,
            json={"consent_type": "geo", "policy_version": "1"},
        )
        assert consent.status_code == 201
        assert client.get("/api/v1/me/consents", headers=headers).json()[0]["consent_type"] == "geo"
        track = client.post(
            "/api/v1/location/tracks",
            headers=headers,
            json={
                "tracks": [
                    {
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "lat": 55.75,
                        "lon": 37.62,
                        "accuracy_m": 10,
                        "location_source": "platform",
                        "trip_id": str(trips.trip.id),
                    }
                ]
            },
        )
        assert track.status_code == 202
        assert len(client.get(f"/api/v1/trips/{trips.trip.id}/tracks", headers=headers).json()) == 1
        init_body = {
            "owner_type": "event",
            "owner_id": str(CLIENT_EVENT_ID),
            "trip_id": str(trips.trip.id),
            "kind": "photo",
            "mime": "image/jpeg",
            "size": 12,
            "source": "gallery",
        }
        init = client.post("/api/v1/attachments:init", headers=headers, json=init_body)
        assert init.status_code == 200
        assert services.attachments.init_context["trip_id"] == trips.trip.id
        missing_trip = client.post(
            "/api/v1/attachments:init",
            headers=headers,
            json={key: value for key, value in init_body.items() if key != "trip_id"},
        )
        assert missing_trip.status_code == 422
        commit = client.post(
            f"/api/v1/attachments/{init.json()['attachment_id']}:commit",
            headers=headers,
            json={"sha256": "a" * 64, "size": 12},
        )
        assert commit.status_code == 200
        assert commit.json()["state"] == "stored"
        completed = client.post(
            f"/api/v1/trips/{trips.trip.id}/complete",
            headers=headers,
            json={"track_number": "TR-123"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "pending_logistician"
        diagnostic = client.post(
            "/api/v1/logs",
            headers=headers,
            json={
                "level": "error",
                "message": "sync.failed",
                "context": {"status_code": 503, "phone": "+79990000000"},
            },
        )
        assert diagnostic.status_code == 204
        assert services.diagnostics.queued[0]["context"] == {"status_code": 503}
        assert (
            client.post(
                "/api/v1/logs",
                headers=headers,
                json={"level": "error", "message": "Call +79990000000"},
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.clear()


def test_missing_client_headers_return_structured_error():
    response = TestClient(app).get("/api/v1/me")
    assert response.status_code == 400
    assert set(response.json()) == {"error", "trace_id"}


def test_trip_start_freezes_config_before_accepting_events():
    auth, trips = FakeAuth(), FakeTrips()
    trips.trip = Trip(trips.trip.id, trips.trip.order_id, None, "assigned")
    services = SimpleNamespace(
        auth=auth,
        passwords=FakePasswords(),
        tokens=Hs256Tokens("a" * 32),
        trips=trips,
        users=FakeUsers(),
        snapshots=FakeSnapshots(),
    )
    app.dependency_overrides[get_services] = lambda: services
    try:
        client = TestClient(app)
        device_id = uuid4()
        headers = {
            "X-App-Version": "1.0.0",
            "X-Platform": "android",
            "X-Device-Id": str(device_id),
        }
        login_response = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={
                "phone": auth.user.phone,
                "password": "valid-password",
                "device": {
                    "device_id": str(device_id),
                    "platform": "android",
                    "app_version": "1.0.0",
                },
            },
        )
        headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"
        response = client.post(f"/api/v1/trips/{trips.trip.id}/start", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"
        assert response.json()["config_snapshot_id"] == str(trips.trip.config_snapshot_id)
    finally:
        app.dependency_overrides.clear()
