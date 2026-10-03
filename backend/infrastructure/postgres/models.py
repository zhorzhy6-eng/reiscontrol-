"""SQLAlchemy Core metadata for the approved PostgreSQL 16 schema."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()


def uid(name: str, *, primary: bool = False, foreign: str | None = None, nullable=False):
    """Construct a UUID column from the database schema."""
    args = (ForeignKey(foreign),) if foreign else ()
    return Column(name, UUID(as_uuid=True), *args, primary_key=primary, nullable=nullable)


def code(name: str, *, primary: bool = False, foreign: str | None = None, nullable=False):
    """Construct a text code column."""
    args = (ForeignKey(foreign),) if foreign else ()
    return Column(name, Text, *args, primary_key=primary, nullable=nullable)


def stamp(name: str, *, nullable=False):
    """Construct a time-zone-aware timestamp column."""
    return Column(name, DateTime(timezone=True), nullable=nullable)


users = Table(
    "users",
    metadata,
    uid("id", primary=True),
    code("phone"),
    code("password_hash"),
    code("role"),
    Column("is_active", Boolean, nullable=False),
    stamp("created_at"),
    stamp("updated_at"),
    UniqueConstraint("phone", name="uq_users_phone"),
)
driver_profiles = Table(
    "driver_profiles",
    metadata,
    uid("user_id", primary=True, foreign="users.id"),
    code("full_name"),
    code("license_number"),
    Column("license_expires_at", Date, nullable=False),
    stamp("created_at"),
)
devices = Table(
    "devices",
    metadata,
    uid("id", primary=True),
    uid("user_id", foreign="users.id"),
    code("platform"),
    code("os_version", nullable=True),
    code("app_version"),
    code("push_token", nullable=True),
    code("push_provider", nullable=True),
    stamp("last_seen_at", nullable=True),
    stamp("created_at"),
    Index("ix_devices_user_platform", "user_id", "platform"),
)
refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    uid("id", primary=True),
    uid("user_id", foreign="users.id"),
    uid("device_id", foreign="devices.id"),
    code("token_hash"),
    stamp("expires_at"),
    stamp("revoked_at", nullable=True),
    Index("ix_refresh_tokens_user", "user_id"),
    Index("ix_refresh_tokens_hash", "token_hash", unique=True),
)
access_scopes = Table(
    "access_scopes",
    metadata,
    uid("id", primary=True),
    uid("user_id", foreign="users.id"),
    code("scope_type"),
    code("scope_id"),
    stamp("created_at"),
    Index("ix_access_scopes_user_type", "user_id", "scope_type"),
)
user_consents = Table(
    "user_consents",
    metadata,
    uid("id", primary=True),
    uid("user_id", foreign="users.id"),
    code("consent_type"),
    code("policy_version"),
    code("platform"),
    stamp("accepted_at"),
    stamp("revoked_at", nullable=True),
    code("ip"),
    Index("ix_user_consents_user_type", "user_id", "consent_type"),
)

cargo_types = Table("cargo_types", metadata, code("code", primary=True), code("name"))
trip_types = Table("trip_types", metadata, code("code", primary=True), code("name"))
point_types = Table("point_types", metadata, code("code", primary=True), code("name"))
clients = Table(
    "clients", metadata, uid("id", primary=True), code("name"), code("inn"), code("contact")
)
orders = Table(
    "orders",
    metadata,
    uid("id", primary=True),
    uid("client_id", foreign="clients.id"),
    code("cargo_type_code", foreign="cargo_types.code"),
    code("trip_type_code", foreign="trip_types.code"),
    code("status"),
    uid("created_by", foreign="users.id"),
    stamp("created_at"),
    stamp("updated_at"),
)
trips = Table(
    "trips",
    metadata,
    uid("id", primary=True),
    uid("order_id", foreign="orders.id"),
    code("status"),
    Column(
        "config_snapshot_id",
        UUID(as_uuid=True),
        ForeignKey("config_snapshots.id", use_alter=True, name="fk_trips_snapshot"),
        nullable=True,
    ),
    stamp("started_at", nullable=True),
    stamp("closed_at", nullable=True),
    code("track_number", nullable=True),
    stamp("created_at"),
    stamp("updated_at"),
)
trip_participants = Table(
    "trip_participants",
    metadata,
    uid("id", primary=True),
    uid("trip_id", foreign="trips.id"),
    uid("user_id", foreign="users.id"),
    code("role"),
    stamp("from_at"),
    stamp("to_at", nullable=True),
)
trip_points = Table(
    "trip_points",
    metadata,
    uid("id", primary=True),
    uid("trip_id", foreign="trips.id"),
    code("point_type_code", foreign="point_types.code"),
    Column("order_index", Integer, nullable=False),
    code("address"),
    Column("lat", Numeric(9, 6), nullable=True),
    Column("lon", Numeric(9, 6), nullable=True),
    stamp("planned_at", nullable=True),
    stamp("created_at"),
)
cargo_units = Table(
    "cargo_units",
    metadata,
    uid("id", primary=True),
    uid("trip_id", foreign="trips.id"),
    code("vin"),
    code("make"),
    code("model"),
    code("position_in_truck", nullable=True),
    Column("order_index", Integer, nullable=False),
    stamp("created_at"),
)

event_types = Table(
    "event_types",
    metadata,
    code("code", primary=True),
    code("primitive"),
    code("title"),
    Column("order", Integer, nullable=False),
    Column("min_app_version", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False),
)
event_payload_schemas = Table(
    "event_payload_schemas",
    metadata,
    code("event_type_code", primary=True, foreign="event_types.code"),
    Column("schema_version", Integer, primary_key=True),
    Column("json_schema", JSONB, nullable=False),
    stamp("created_at"),
)
events = Table(
    "events",
    metadata,
    uid("id", primary=True),
    uid("client_event_id"),
    uid("device_id", foreign="devices.id"),
    uid("trip_id", foreign="trips.id"),
    uid("point_id", foreign="trip_points.id", nullable=True),
    uid("cargo_unit_id", foreign="cargo_units.id", nullable=True),
    code("event_type_code", foreign="event_types.code"),
    Column("payload_jsonb", JSONB, nullable=False),
    Column("payload_schema_version", Integer, nullable=False),
    stamp("device_time_utc", nullable=True),
    Column("device_tz_offset_min", Integer, nullable=True),
    Column("elapsed_realtime_ms", BigInteger, nullable=True),
    stamp("server_time_utc"),
    Column("clock_skew_ms", Integer, nullable=True),
    code("time_trust"),
    Column("lat", Numeric(9, 6), nullable=True),
    Column("lon", Numeric(9, 6), nullable=True),
    Column("accuracy_m", Integer, nullable=True),
    code("location_source", nullable=True),
    code("state"),
    uid("corrects_event_id", foreign="events.id", nullable=True),
    uid("created_by", foreign="users.id"),
    code("app_version"),
    code("platform"),
    stamp("created_at"),
    UniqueConstraint("client_event_id", "device_id", name="uq_events_client_device"),
    Index("ix_events_trip_created", "trip_id", "created_at"),
    Index("ix_events_trip_type", "trip_id", "event_type_code"),
)

checklist_templates = Table(
    "checklist_templates",
    metadata,
    uid("id", primary=True),
    code("name"),
    code("cargo_type_code", foreign="cargo_types.code"),
    code("trip_type_code", foreign="trip_types.code"),
    uid("client_id", foreign="clients.id"),
    Column("is_active", Boolean, nullable=False),
    stamp("created_at"),
)
checklist_versions = Table(
    "checklist_versions",
    metadata,
    uid("id", primary=True),
    uid("template_id", foreign="checklist_templates.id"),
    Column("version", Integer, nullable=False),
    code("status"),
    stamp("published_at", nullable=True),
    uid("published_by", foreign="users.id", nullable=True),
    Index("ix_checklist_versions_template_version", "template_id", "version"),
)
checklist_steps = Table(
    "checklist_steps",
    metadata,
    uid("id", primary=True),
    uid("version_id", foreign="checklist_versions.id"),
    code("code"),
    code("type"),
    code("title"),
    Column("required", Boolean, nullable=False),
    Column("order", Integer, nullable=False),
    code("scope"),
    code("hint_icon", nullable=True),
)
document_types = Table(
    "document_types",
    metadata,
    code("code", primary=True),
    code("name"),
    Column("required", Boolean, nullable=False),
)
completion_policies = Table(
    "completion_policies",
    metadata,
    uid("id", primary=True),
    uid("version_id", foreign="checklist_versions.id"),
    Column("rules_json", JSONB, nullable=False),
)
config_snapshots = Table(
    "config_snapshots",
    metadata,
    uid("id", primary=True),
    uid("trip_id", foreign="trips.id"),
    uid("version_id", foreign="checklist_versions.id"),
    Column("snapshot_json", JSONB, nullable=False),
    stamp("created_at"),
    Index("ix_config_snapshots_trip", "trip_id"),
)

attachment_kinds = Table("attachment_kinds", metadata, code("code", primary=True), code("name"))
attachments = Table(
    "attachments",
    metadata,
    uid("id", primary=True),
    code("owner_type"),
    uid("owner_id"),
    code("kind", foreign="attachment_kinds.code"),
    code("storage_key"),
    code("mime"),
    Column("size", BigInteger, nullable=False),
    code("sha256", nullable=True),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("watermark_meta", JSONB, nullable=True),
    code("source"),
    uid("version_of", foreign="attachments.id", nullable=True),
    code("state"),
    code("platform"),
    stamp("created_at"),
    Index("ix_attachments_owner", "owner_type", "owner_id"),
    Index("ix_attachments_sha256", "sha256"),
)
attachment_versions = Table(
    "attachment_versions",
    metadata,
    uid("id", primary=True),
    uid("attachment_id", foreign="attachments.id"),
    Column("version", Integer, nullable=False),
    code("storage_key"),
    stamp("created_at"),
)
derived_assets = Table(
    "derived_assets",
    metadata,
    uid("id", primary=True),
    uid("attachment_id", foreign="attachments.id"),
    code("kind"),
    code("storage_key"),
    stamp("created_at"),
)

location_tracks = Table(
    "location_tracks",
    metadata,
    uid("id", primary=True),
    uid("device_id", foreign="devices.id"),
    uid("user_id", foreign="users.id"),
    uid("trip_id", foreign="trips.id", nullable=True),
    Column("lat", Numeric(9, 6), nullable=False),
    Column("lon", Numeric(9, 6), nullable=False),
    Column("accuracy_m", Integer, nullable=False),
    Column("speed_mps", Numeric, nullable=True),
    Column("bearing_deg", Numeric, nullable=True),
    code("location_source"),
    stamp("recorded_at"),
    stamp("received_at"),
    Index("ix_tracks_device_recorded", "device_id", "recorded_at"),
    Index("ix_tracks_trip_recorded", "trip_id", "recorded_at"),
)
outbox = Table(
    "outbox",
    metadata,
    uid("id", primary=True),
    uid("event_id", foreign="events.id"),
    Column("payload", JSONB, nullable=False),
    code("status"),
    Column("retries", Integer, nullable=False),
    stamp("next_attempt_at"),
    stamp("created_at"),
    Index("ix_outbox_status_next", "status", "next_attempt_at"),
)
inbox = Table(
    "inbox",
    metadata,
    uid("id", primary=True),
    code("source"),
    Column("payload", JSONB, nullable=False),
    stamp("received_at"),
)
notification_templates = Table(
    "notification_templates",
    metadata,
    code("code", primary=True),
    code("channel"),
    code("template"),
)
notification_channels = Table(
    "notification_channels",
    metadata,
    code("code", primary=True),
    Column("enabled", Boolean, nullable=False),
)
notification_log = Table(
    "notification_log",
    metadata,
    uid("id", primary=True),
    code("template_code"),
    code("recipient"),
    code("status"),
    stamp("sent_at", nullable=True),
    code("error", nullable=True),
)
integration_jobs = Table(
    "integration_jobs",
    metadata,
    uid("id", primary=True),
    code("integration"),
    Column("payload", JSONB, nullable=False),
    code("status"),
    stamp("created_at"),
)

feature_flags = Table(
    "feature_flags",
    metadata,
    code("code", primary=True),
    Column("enabled", Boolean, nullable=False),
    Column("rollout_percent", Integer, nullable=False),
)
app_releases = Table(
    "app_releases",
    metadata,
    code("platform", primary=True),
    code("channel", primary=True),
    Column("version_code", Integer, primary_key=True),
    code("version_name"),
    Column("min_supported", Integer, nullable=False),
    Column("rollout_percent", Integer, nullable=False),
    code("download_url"),
    code("sha256"),
    code("release_notes"),
    Column("is_mandatory", Boolean, nullable=False),
    stamp("released_at"),
    Index("ix_app_releases_platform_channel_released", "platform", "channel", "released_at"),
)
audit_log = Table(
    "audit_log",
    metadata,
    uid("id", primary=True),
    uid("user_id", foreign="users.id"),
    code("action"),
    code("entity_type"),
    uid("entity_id"),
    Column("payload", JSONB, nullable=False),
    code("platform"),
    stamp("created_at"),
    Index("ix_audit_user_created", "user_id", "created_at"),
    Index("ix_audit_entity", "entity_type", "entity_id"),
)
sync_cursors = Table(
    "sync_cursors",
    metadata,
    uid("device_id", primary=True),
    stamp("last_sync_at"),
    uid("last_event_id", nullable=True),
)
export_jobs = Table(
    "export_jobs",
    metadata,
    uid("id", primary=True),
    uid("trip_id", foreign="trips.id"),
    code("status"),
    code("storage_key", nullable=True),
    stamp("created_at"),
)
