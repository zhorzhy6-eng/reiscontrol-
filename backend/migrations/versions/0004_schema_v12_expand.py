"""Expand existing databases toward the approved schema v1.2."""

from alembic import op

from backend.migrations.guards import require_destructive_downgrade

revision = "0004_schema_v12_expand"
down_revision = "0003_track_client_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Copy configuration values and assign subscription IDs before contract."""
    op.execute("ALTER TABLE checklist_versions ADD COLUMN IF NOT EXISTS primitive_configs JSONB")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'checklist_versions' "
        "AND column_name = 'primitive_configs_jsonb') "
        "THEN UPDATE checklist_versions SET primitive_configs = primitive_configs_jsonb "
        "WHERE primitive_configs IS NULL; END IF; END; $$"
    )
    op.execute("ALTER TABLE telegram_subscriptions ADD COLUMN IF NOT EXISTS id UUID")
    op.execute("UPDATE telegram_subscriptions SET id = gen_random_uuid() WHERE id IS NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_telegram_subscriptions_user "
        "ON telegram_subscriptions (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_checklist_steps_version_event_type "
        "ON checklist_steps (version_id, event_type_code)"
    )


def downgrade() -> None:
    """Reverse expansion only on an explicitly disposable database."""
    require_destructive_downgrade()
    op.execute("DROP INDEX IF EXISTS ix_checklist_steps_version_event_type")
    op.execute("DROP INDEX IF EXISTS ix_telegram_subscriptions_user")
    op.execute("ALTER TABLE telegram_subscriptions DROP COLUMN IF EXISTS id")
    op.execute("ALTER TABLE checklist_versions DROP COLUMN IF EXISTS primitive_configs")
