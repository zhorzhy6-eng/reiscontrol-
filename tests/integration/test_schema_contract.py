"""Check the frozen migration against the SQLAlchemy schema contract."""

import json
from pathlib import Path

import yaml

from backend.infrastructure.postgres.models import metadata


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
    assert "primitive_configs_jsonb JSONB NOT NULL" in versions
    assert "event_type_code TEXT NOT NULL" in steps
    assert "FOREIGN KEY(event_type_code) REFERENCES event_types (code)" in steps
    assert "PRIMARY KEY (user_id, chat_id)" in subscriptions
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
