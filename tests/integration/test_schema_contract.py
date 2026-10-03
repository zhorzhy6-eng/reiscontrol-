"""Check the frozen migration against the SQLAlchemy schema contract."""

import json
import re
from pathlib import Path

import yaml
import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.infrastructure.postgres.models import metadata
from backend.migrations.guards import require_destructive_downgrade


def test_initial_migration_contains_all_approved_tables():
    path = Path("backend/migrations/versions/0001_init.statements.json")
    statements = json.loads(path.read_text(encoding="utf-8"))
    for table_name in metadata.tables:
        assert any(sql.startswith(f"CREATE TABLE {table_name} ") for sql in statements)
    assert len(metadata.tables) == 41


def test_event_idempotency_and_append_only_are_database_constraints():
    statements = json.loads(
        Path("backend/migrations/versions/0001_init.statements.json").read_text(encoding="utf-8")
    )
    event_ddl = next(sql for sql in statements if sql.startswith("CREATE TABLE events "))
    assert "UNIQUE (client_event_id, device_id)" in event_ddl
    assert any("events_append_only BEFORE UPDATE OR DELETE" in sql for sql in statements)
    assert not any("PARTITION BY" in sql for sql in statements)


def test_app_release_key_is_platform_channel_version():
    releases = metadata.tables["app_releases"]
    assert [column.name for column in releases.primary_key] == [
        "platform",
        "channel",
        "version_code",
    ]


def test_snapshot_configuration_and_telegram_subscription_are_migrated():
    statements = json.loads(
        Path("backend/migrations/versions/0001_init.statements.json").read_text(encoding="utf-8")
    )
    versions = next(sql for sql in statements if sql.startswith("CREATE TABLE checklist_versions "))
    steps = next(sql for sql in statements if sql.startswith("CREATE TABLE checklist_steps "))
    subscriptions = next(
        sql for sql in statements if sql.startswith("CREATE TABLE telegram_subscriptions ")
    )
    snapshots = next(sql for sql in statements if sql.startswith("CREATE TABLE config_snapshots "))
    attachments = next(sql for sql in statements if sql.startswith("CREATE TABLE attachments "))
    assert "primitive_configs JSONB NOT NULL" in versions
    assert "event_type_code TEXT NOT NULL" in steps
    assert "FOREIGN KEY(event_type_code) REFERENCES event_types (code)" in steps
    assert "PRIMARY KEY (id)" in subscriptions
    assert any("ix_checklist_steps_version_event_type" in sql for sql in statements)
    assert any("ix_telegram_subscriptions_user" in sql for sql in statements)
    assert "CONSTRAINT uq_config_snapshots_trip UNIQUE (trip_id)" in snapshots
    assert "trip_id UUID" in attachments


def test_attachment_trip_context_and_event_replay_contract():
    contract = yaml.safe_load(Path("docs/05-api/openapi.yaml").read_text(encoding="utf-8"))
    request = contract["paths"]["/attachments:init"]["post"]["requestBody"]
    properties = request["content"]["application/json"]["schema"]["properties"]
    assert "trip_id" in properties
    responses = contract["paths"]["/events"]["post"]["responses"]
    assert "идентичного повтора" in responses["200"]["description"]
    assert "другого содержимого" in responses["409"]["description"]


def test_notification_delivery_expands_log_without_rewriting_events():
    migration = Path("backend/migrations/versions/0002_notification_delivery.py").read_text(
        encoding="utf-8"
    )
    assert "ADD COLUMN IF NOT EXISTS event_id UUID" in migration
    assert "UNIQUE (event_id, recipient)" in migration
    assert "UPDATE events" not in migration


def test_frozen_initial_ddl_matches_sqlalchemy_metadata():
    statements = json.loads(
        Path("backend/migrations/versions/0001_init.statements.json").read_text(encoding="utf-8")
    )

    def normalized(sql):
        return re.sub(r"\s+", " ", sql).strip().rstrip(";")

    frozen = {
        normalized(sql)
        for sql in statements
        if sql.startswith(("CREATE TABLE", "CREATE INDEX", "CREATE UNIQUE INDEX"))
    }
    generated = {
        normalized(str(CreateTable(table).compile(dialect=postgresql.dialect())))
        for table in metadata.tables.values()
    }
    generated.update(
        normalized(str(CreateIndex(index).compile(dialect=postgresql.dialect())))
        for table in metadata.tables.values()
        for index in table.indexes
    )
    assert frozen == generated
    assert len(metadata.tables) == 41
    assert all(
        fk.column.table.name in metadata.tables
        for table in metadata.tables.values()
        for fk in table.foreign_keys
    )
    assert not any("PARTITION BY" in sql for sql in statements)

    positions = {
        sql.split(" ", 3)[2]: position
        for position, sql in enumerate(statements)
        if sql.startswith("CREATE TABLE ")
    }
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target != table.name and not fk.constraint.use_alter:
                assert positions[target] < positions[table.name]


def test_approved_keys_and_indexes_are_present():
    tables = metadata.tables
    assert [column.name for column in tables["telegram_subscriptions"].primary_key] == ["id"]
    assert [column.name for column in tables["app_releases"].primary_key] == [
        "platform",
        "channel",
        "version_code",
    ]
    assert "primitive_configs" in tables["checklist_versions"].c
    assert "event_type_code" in tables["checklist_steps"].c
    assert "owner_id" in tables["attachments"].c
    assert "trip_id" in tables["attachments"].c
    assert "event_id" in tables["notification_log"].c
    assert any(
        [column.name for column in index.columns] == ["client_track_id", "device_id"]
        and index.unique
        for index in tables["location_tracks"].indexes
    )
    assert any(
        [column.name for column in constraint.columns] == ["client_event_id", "device_id"]
        for constraint in tables["events"].constraints
        if isinstance(constraint, UniqueConstraint)
    )


def test_destructive_downgrade_requires_explicit_flag(monkeypatch):
    monkeypatch.delenv("REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE", raising=False)
    with pytest.raises(RuntimeError):
        require_destructive_downgrade()
    monkeypatch.setenv("REISCONTROL_ALLOW_DESTRUCTIVE_DOWNGRADE", "1")
    require_destructive_downgrade()


def test_approved_event_types_are_seeded_as_data():
    values = yaml.safe_load(Path("config/event-types/stage1.yaml").read_text(encoding="utf-8"))
    assert {item["code"]: item["primitive"] for item in values["event_types"]} == {
        "LOADING": "photo_set",
        "UNLOADING": "photo_set",
        "ARRIVAL": "geo_only",
        "DEPARTURE": "geo_only",
        "PARKING": "geo_only",
    }
