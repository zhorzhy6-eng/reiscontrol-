"""Version-one HTTP API for authentication, trips and event submission."""

import logging
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.application.auth import AuthenticationError, login, refresh_access
from backend.application.errors import ForbiddenError, IdempotencyConflictError, NotFoundError
from backend.application.events import submit_event
from backend.application.trips import complete_trip_for_user, start_trip_for_user
from backend.apps.api.logging_config import configure_json_logging
from backend.domain.errors import DomainError
from backend.domain.events import create_event, transition_event
from backend.infrastructure.postgres.attachments import PostgresAttachmentRepository
from backend.infrastructure.postgres.auth_repository import PostgresAuthRepository
from backend.infrastructure.postgres.completion import PostgresTripCompletionPolicy
from backend.infrastructure.postgres.consents import PostgresConsentRepository
from backend.infrastructure.postgres.diagnostics import PostgresDiagnosticRepository
from backend.infrastructure.postgres.read_repository import PostgresReadRepository
from backend.infrastructure.postgres.repositories import (
    PostgresEventConfiguration,
    PostgresEventRepository,
    PostgresTripRepository,
    PostgresUserRepository,
)
from backend.infrastructure.postgres.snapshots import PostgresConfigSnapshotRepository
from backend.infrastructure.postgres.tracks import PostgresTrackRepository
from backend.infrastructure.security import Argon2Passwords, Hs256Tokens
from backend.infrastructure.storage import S3ObjectStore, StorageError

logger = logging.getLogger(__name__)
TRACE_PATTERN = re.compile(r"^(?:[0-9a-fA-F-]{36}|tr_[A-Za-z0-9_-]{8,64})$")
SAFE_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z.+_-]{1,32}$")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Enable structured JSON logs for the process."""
    configure_json_logging(service="api", level=os.getenv("LOG_LEVEL", "INFO"))
    yield


app = FastAPI(title="ReisControl API", version="1.1.0", lifespan=lifespan)


@dataclass(slots=True)
class Services:
    """Request-independent adapters; replaceable in tests."""

    auth: PostgresAuthRepository
    events: PostgresEventRepository
    trips: PostgresTripRepository
    users: PostgresUserRepository
    configuration: PostgresEventConfiguration
    reads: PostgresReadRepository
    consents: PostgresConsentRepository
    tracks: PostgresTrackRepository
    passwords: Argon2Passwords
    tokens: Hs256Tokens
    attachments: PostgresAttachmentRepository
    snapshots: PostgresConfigSnapshotRepository
    completion: PostgresTripCompletionPolicy
    diagnostics: PostgresDiagnosticRepository


@lru_cache(maxsize=1)
def get_services() -> Services:
    """Build adapters from environment-provided secrets and database URL."""
    database_url = os.environ["DATABASE_URL"]
    jwt_secret = os.environ["JWT_SECRET"]
    sessions = sessionmaker(create_engine(database_url), expire_on_commit=False)
    store = S3ObjectStore(
        endpoint_url=os.environ["OBJECT_STORAGE_ENDPOINT"],
        bucket=os.environ["OBJECT_STORAGE_BUCKET"],
        region=os.environ["OBJECT_STORAGE_REGION"],
    )
    return Services(
        auth=PostgresAuthRepository(sessions),
        events=PostgresEventRepository(sessions),
        trips=PostgresTripRepository(sessions),
        users=PostgresUserRepository(sessions),
        configuration=PostgresEventConfiguration(sessions),
        reads=PostgresReadRepository(sessions),
        consents=PostgresConsentRepository(sessions),
        tracks=PostgresTrackRepository(sessions),
        passwords=Argon2Passwords(),
        tokens=Hs256Tokens(jwt_secret),
        attachments=PostgresAttachmentRepository(sessions, store),
        snapshots=PostgresConfigSnapshotRepository(sessions),
        completion=PostgresTripCompletionPolicy(sessions),
        diagnostics=PostgresDiagnosticRepository(sessions),
    )


class DeviceInput(BaseModel):
    """Device identity supplied at login."""

    device_id: UUID
    platform: Literal["android", "ios", "web"]
    app_version: str
    os_version: str | None = None


class LoginInput(BaseModel):
    """Phone/password login body."""

    phone: str
    password: str
    device: DeviceInput


class RefreshInput(BaseModel):
    """Opaque refresh-token body."""

    refresh_token: str


class ConsentInput(BaseModel):
    """Explicit acceptance of a policy version."""

    consent_type: Literal["pd", "geo", "tracking"]
    policy_version: str


class EventInput(BaseModel):
    """Client fact as described by the shared OpenAPI contract."""

    model_config = ConfigDict(extra="ignore")

    client_event_id: UUID
    device_id: UUID
    trip_id: UUID
    point_id: UUID | None = None
    cargo_unit_id: UUID | None = None
    event_type_code: str
    payload: dict[str, Any]
    payload_schema_version: int = Field(default=1, ge=1)
    device_time_utc: datetime | None = None
    device_tz_offset_min: int | None = None
    elapsed_realtime_ms: int | None = None
    lat: float | None = None
    lon: float | None = None
    accuracy_m: int | None = None
    location_source: Literal["gms", "hms", "platform", "ios"] | None = None
    corrects_event_id: UUID | None = None


class SyncInput(BaseModel):
    """Pull request with an optional current device-clock sample."""

    last_sync_at: datetime | None = None
    cursor: str | None = None
    device_time_utc: datetime | None = None
    elapsed_realtime_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def paired_clock_sample(self):
        """Require both wall and monotonic clocks when sampling time."""
        if (self.device_time_utc is None) != (self.elapsed_realtime_ms is None):
            raise ValueError("Both device clock fields are required")
        return self


class TrackInput(BaseModel):
    """One periodic location sample."""

    recorded_at: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: int = Field(ge=0)
    speed_mps: float | None = None
    bearing_deg: float | None = None
    location_source: Literal["gms", "hms", "platform", "ios"]
    trip_id: UUID


class TracksInput(BaseModel):
    """Batch of periodic location samples."""

    tracks: list[TrackInput]


class CompleteTripInput(BaseModel):
    """Driver-supplied transport document number."""

    track_number: str = Field(min_length=1)


class AttachmentInitInput(BaseModel):
    """Reserve a future event attachment in an authorized trip."""

    owner_type: Literal["event", "point", "trip", "document"]
    owner_id: UUID
    trip_id: UUID | None = None
    kind: Literal["photo", "document", "pdf", "signature", "scan"]
    mime: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    source: Literal["camera", "gallery"]


class AttachmentCommitInput(BaseModel):
    """Expected checksum and metadata of already uploaded bytes."""

    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    size: int = Field(gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    watermark_meta: dict[str, Any] | None = None


class ClientLogContext(BaseModel):
    """Only identifiers and counts safe for structured diagnostics."""

    model_config = ConfigDict(extra="ignore")

    event_type_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,50}$")
    attachments_count: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    status_code: int | None = Field(default=None, ge=100, le=599)


class ClientLogInput(BaseModel):
    """Machine-readable error codes keep free-form personal data out of logs."""

    level: Literal["info", "warning", "error", "crash"]
    message: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    context: ClientLogContext = Field(default_factory=ClientLogContext)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Require version/platform/device headers and log safe request metadata."""
    supplied_trace = request.headers.get("X-Trace-Id", "")
    trace_id = supplied_trace if TRACE_PATTERN.fullmatch(supplied_trace) else str(uuid4())
    request.state.trace_id = trace_id
    if request.url.path != "/health":
        required = ("X-App-Version", "X-Platform", "X-Device-Id")
        missing = [name for name in required if not request.headers.get(name)]
        if missing:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required client headers", "trace_id": trace_id},
                headers={"X-Trace-Id": trace_id},
            )
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    logger.info(
        "HTTP request completed",
        extra={
            "trace_id": trace_id,
            "app_version": (
                request.headers.get("X-App-Version")
                if SAFE_VERSION_PATTERN.fullmatch(request.headers.get("X-App-Version", ""))
                else "unknown"
            ),
            "platform": (
                request.headers.get("X-Platform")
                if request.headers.get("X-Platform") in ("android", "ios", "web")
                else "unknown"
            ),
            "context": {
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000),
            },
        },
    )
    return response


@app.exception_handler(DomainError)
async def domain_error(request: Request, error: DomainError):
    """Map business validation to structured 422 responses."""
    return JSONResponse(
        status_code=422,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(ForbiddenError)
async def forbidden_error(request: Request, error: ForbiddenError):
    """Map trip authorization failures to structured 403 responses."""
    return JSONResponse(
        status_code=403,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(NotFoundError)
async def not_found_error(request: Request, error: NotFoundError):
    """Map missing objects to structured 404 responses."""
    return JSONResponse(
        status_code=404,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(IdempotencyConflictError)
async def idempotency_error(request: Request, error: IdempotencyConflictError):
    """Reject reuse of a client key for different facts."""
    return JSONResponse(
        status_code=409,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(AuthenticationError)
async def authentication_error(request: Request, error: AuthenticationError):
    """Return an opaque authentication failure without credential details."""
    return JSONResponse(
        status_code=401,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, _error: RequestValidationError):
    """Hide input values while preserving the shared error shape."""
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid request", "trace_id": request.state.trace_id},
    )


@app.exception_handler(ValueError)
async def value_error(request: Request, error: ValueError):
    """Map invalid state transitions to a structured client error."""
    return JSONResponse(
        status_code=422,
        content={"error": str(error), "trace_id": request.state.trace_id},
    )


@app.exception_handler(StorageError)
async def storage_error(request: Request, _error: StorageError):
    """Keep provider details out of the response and mark failures retryable."""
    logger.error("Object Storage unavailable", extra={"trace_id": request.state.trace_id})
    return JSONResponse(
        status_code=503,
        content={"error": "Object Storage unavailable", "trace_id": request.state.trace_id},
    )


def current_user(request: Request, services: Services = Depends(get_services)) -> UUID:
    """Validate bearer JWT, device binding and active account."""
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        claims = services.tokens.decode(authorization.removeprefix("Bearer "))
        device_id = UUID(request.headers["X-Device-Id"])
        if claims["device_id"] != str(device_id):
            raise AuthenticationError("Invalid device binding")
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as error:
        raise AuthenticationError("Invalid access token") from error
    user = services.auth.get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid access token")
    return user_id


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException):
    """Keep framework errors in the shared structured shape."""
    return JSONResponse(
        status_code=error.status_code,
        content={"error": str(error.detail), "trace_id": request.state.trace_id},
    )


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Allow infrastructure to check API liveness."""
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login_route(
    body: LoginInput, request: Request, services: Services = Depends(get_services)
) -> dict:
    """Authenticate a client and return short-lived access credentials."""
    if (
        str(body.device.device_id) != request.headers["X-Device-Id"]
        or body.device.platform != request.headers["X-Platform"]
        or body.device.app_version != request.headers["X-App-Version"]
    ):
        raise AuthenticationError("Device headers do not match login body")
    result = login(
        phone=body.phone,
        password=body.password,
        device_id=body.device.device_id,
        platform=body.device.platform,
        app_version=body.device.app_version,
        repository=services.auth,
        passwords=services.passwords,
        tokens=services.tokens,
    )
    return {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "user": {
            "id": result.user.id,
            "phone": result.user.phone,
            "role": result.user.role,
            "full_name": result.user.full_name,
        },
    }


@app.post("/api/v1/auth/refresh")
def refresh_route(body: RefreshInput, services: Services = Depends(get_services)) -> dict:
    """Issue a new access token from a stored refresh-token hash."""
    access_token, expires_in = refresh_access(
        body.refresh_token, repository=services.auth, tokens=services.tokens
    )
    return {"access_token": access_token, "expires_in": expires_in}


@app.get("/api/v1/me")
def me_route(
    user_id: UUID = Depends(current_user), services: Services = Depends(get_services)
) -> dict:
    """Return the authenticated profile."""
    user = services.auth.get_by_id(user_id)
    return {"id": user.id, "phone": user.phone, "role": user.role, "full_name": user.full_name}


@app.get("/api/v1/me/consents")
def consents_route(
    user_id: UUID = Depends(current_user), services: Services = Depends(get_services)
) -> list[dict]:
    """Return the user's recorded consents."""
    return services.consents.list_for_user(user_id)


@app.post("/api/v1/me/consents", status_code=201)
def accept_consent_route(
    body: ConsentInput,
    request: Request,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Idempotently accept one policy version."""
    return services.consents.accept(
        user_id=user_id,
        consent_type=body.consent_type,
        policy_version=body.policy_version,
        platform=request.headers["X-Platform"],
        ip=request.client.host if request.client else "",
    )


@app.get("/api/v1/orders")
def orders_route(
    user_id: UUID = Depends(current_user), services: Services = Depends(get_services)
) -> list[dict]:
    """Return orders visible to the driver or scoped logistician."""
    return [
        {
            "id": row["id"],
            "client_name": row["client_name"],
            "cargo_type": row["cargo_type_code"],
            "status": row["status"],
            "created_at": row["created_at"],
            "trip_id": row["trip_id"],
        }
        for row in services.reads.orders_for_user(user_id)
    ]


@app.get("/api/v1/trips/{trip_id}")
def trip_route(
    trip_id: UUID,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Return one scoped trip with its route points and cargo units."""
    if not services.users.can_access_trip(user_id, trip_id):
        raise ForbiddenError("Trip access denied")
    trip = services.reads.trip(trip_id)
    if trip is None:
        raise NotFoundError("Trip not found")
    return trip


@app.post("/api/v1/trips/{trip_id}/start")
def start_trip_route(
    trip_id: UUID,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Start an assigned trip with its published checklist frozen to a snapshot."""
    started = start_trip_for_user(
        trip_id,
        user_id=user_id,
        started_at=datetime.now(timezone.utc),
        trips=services.trips,
        users=services.users,
        snapshots=services.snapshots,
    )
    return {
        "id": started.id,
        "order_id": started.order_id,
        "status": started.status,
        "config_snapshot_id": started.config_snapshot_id,
        "started_at": started.started_at,
    }


@app.post("/api/v1/trips/{trip_id}/complete")
def complete_trip_route(
    trip_id: UUID,
    body: CompleteTripInput,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Submit a trip for logistician confirmation after snapshot rules pass."""
    completed = complete_trip_for_user(
        trip_id,
        user_id=user_id,
        track_number=body.track_number,
        trips=services.trips,
        users=services.users,
        policy=services.completion,
    )
    return {
        "id": completed.id,
        "order_id": completed.order_id,
        "status": completed.status,
        "config_snapshot_id": completed.config_snapshot_id,
        "track_number": completed.track_number,
    }


@app.get("/api/v1/trips/{trip_id}/events")
def trip_events_route(
    trip_id: UUID,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> list[dict]:
    """Return the accepted event timeline for the web cabin and mobile client."""
    if not services.users.can_access_trip(user_id, trip_id):
        raise ForbiddenError("Trip access denied")
    timeline = services.reads.events_for_trip(trip_id)
    for event in timeline:
        for attachment in event["attachments"]:
            if attachment["state"] == "stored":
                attachment["download_url"] = services.attachments.download_url(
                    attachment["id"], trip_id
                )
    return timeline


@app.get("/api/v1/config/snapshots/{snapshot_id}")
def config_snapshot_route(
    snapshot_id: UUID,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Return the immutable configuration attached to an authorized trip."""
    snapshot = services.reads.config_snapshot(snapshot_id)
    if snapshot is None:
        raise NotFoundError("Snapshot not found")
    trip_id = UUID(str(snapshot["trip_id"]))
    if not services.users.can_access_trip(user_id, trip_id):
        raise ForbiddenError("Trip access denied")
    return snapshot


@app.post("/api/v1/sync")
def sync_route(
    body: SyncInput,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Pull current trip projections and estimate clock offset at request time."""
    server_now = datetime.now(timezone.utc)
    clock_skew_ms = None
    if body.device_time_utc is not None:
        if body.device_time_utc.utcoffset() != timezone.utc.utcoffset(None):
            raise DomainError("device_time_utc must be UTC")
        clock_skew_ms = round((server_now - body.device_time_utc).total_seconds() * 1000)
    return {
        "server_time": server_now,
        "clock_skew_ms": clock_skew_ms,
        "trips": services.reads.trips_for_user(user_id),
        "next_cursor": None,
    }


@app.get("/api/v1/app/releases/latest")
def latest_release_route(
    current_version: int,
    platform: str,
    channel: str,
    services: Services = Depends(get_services),
) -> dict:
    """Return server-configured release metadata for one distribution channel."""
    release = services.reads.latest_release(platform, channel)
    if release is None:
        raise NotFoundError("Release not found")
    return {
        "version_code": release["version_code"],
        "version_name": release["version_name"],
        "min_supported": release["min_supported"],
        "download_url": release["download_url"],
        "sha256": release["sha256"],
        "mandatory": release["is_mandatory"],
        "release_notes": release["release_notes"],
    }


@app.post("/api/v1/location/tracks", status_code=202)
def post_tracks_route(
    body: TracksInput,
    request: Request,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Append samples only while the driver has tracking consent and an active trip."""
    services.tracks.append_batch(
        user_id=user_id,
        device_id=UUID(request.headers["X-Device-Id"]),
        tracks=[track.model_dump() for track in body.tracks],
        can_operate_trip=services.users.can_operate_trip,
    )
    return {"accepted": len(body.tracks)}


@app.get("/api/v1/trips/{trip_id}/tracks")
def trip_tracks_route(
    trip_id: UUID,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> list[dict]:
    """Read track points for a user with access to the trip."""
    if not services.users.can_access_trip(user_id, trip_id):
        raise ForbiddenError("Trip access denied")
    return services.tracks.for_trip(trip_id)


@app.post("/api/v1/attachments:init")
def attachment_init_route(
    body: AttachmentInitInput,
    request: Request,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Authorize a driver and reserve an upload for a future event fact."""
    if body.owner_type != "event":
        raise DomainError("Only event attachments are available in stage 1")
    if body.trip_id is None:
        raise DomainError("trip_id is required for event attachments")
    if not services.users.can_operate_trip(user_id, body.trip_id):
        raise ForbiddenError("Trip access denied")
    trip = services.trips.get(body.trip_id)
    if trip is None or trip.status != "in_progress":
        raise DomainError("Trip is not in progress")
    return services.attachments.init_event_upload(
        client_event_id=body.owner_id,
        trip_id=body.trip_id,
        kind=body.kind,
        mime=body.mime,
        size=body.size,
        source=body.source,
        platform=request.headers["X-Platform"],
    )


@app.post("/api/v1/attachments/{attachment_id}:commit")
def attachment_commit_route(
    attachment_id: UUID,
    body: AttachmentCommitInput,
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Verify copied Object Storage bytes and mark the attachment stored."""
    return services.attachments.commit_event_upload(
        attachment_id=attachment_id,
        user_id=user_id,
        can_operate_trip=services.users.can_operate_trip,
        **body.model_dump(),
    )


@app.post("/api/v1/logs", status_code=204)
def client_logs_route(
    body: ClientLogInput,
    request: Request,
    _user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> Response:
    """Record a safe client diagnostic and queue errors for the developer bot."""
    context = body.context.model_dump(exclude_none=True)
    log_level = (
        logging.ERROR
        if body.level in ("error", "crash")
        else (logging.WARNING if body.level == "warning" else logging.INFO)
    )
    logger.log(
        log_level,
        body.message,
        extra={"trace_id": request.state.trace_id, "context": context},
    )
    services.diagnostics.queue(
        level=body.level,
        message_code=body.message,
        trace_id=request.state.trace_id,
        context=context,
    )
    return Response(status_code=204)


@app.post("/api/v1/events")
def post_event(
    body: EventInput,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user_id: UUID = Depends(current_user),
    services: Services = Depends(get_services),
) -> dict:
    """Accept one completed fact and atomically enqueue its notification."""
    if idempotency_key != str(body.client_event_id):
        raise DomainError("Idempotency-Key must equal client_event_id")
    if str(body.device_id) != request.headers["X-Device-Id"]:
        raise AuthenticationError("Invalid device binding")
    event = create_event(**body.model_dump())
    complete = transition_event(event, "complete")
    stored = submit_event(
        complete,
        user_id=user_id,
        received_at_utc=datetime.now(timezone.utc),
        trace_id=request.state.trace_id,
        app_version=request.headers["X-App-Version"],
        platform=request.headers["X-Platform"],
        events=services.events,
        trips=services.trips,
        users=services.users,
        configuration=services.configuration,
    )
    return {
        "id": stored.id,
        "state": stored.event.state,
        "server_time_utc": stored.event.server_time_utc,
        "rejection_reason": stored.event.rejection_reason,
    }
