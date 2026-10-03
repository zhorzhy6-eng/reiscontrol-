"""Contract old configuration and subscription keys after expansion."""

from alembic import op

from backend.migrations.guards import require_destructive_downgrade

revision = "0005_schema_v12_contract"
down_revision = "0004_schema_v12_expand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove the old column and switch subscriptions to the source-schema PK."""
    op.execute("ALTER TABLE checklist_versions ALTER COLUMN primitive_configs SET NOT NULL")
    op.execute("ALTER TABLE checklist_versions DROP COLUMN IF EXISTS primitive_configs_jsonb")
    op.execute("ALTER TABLE telegram_subscriptions ALTER COLUMN id SET NOT NULL")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conrelid = 'telegram_subscriptions'::regclass "
        "AND conname = 'telegram_subscriptions_pkey' "
        "AND pg_get_constraintdef(oid) = 'PRIMARY KEY (user_id, chat_id)') "
        "THEN ALTER TABLE telegram_subscriptions DROP CONSTRAINT telegram_subscriptions_pkey; "
        "ALTER TABLE telegram_subscriptions ADD CONSTRAINT telegram_subscriptions_pkey "
        "PRIMARY KEY (id); END IF; END; $$"
    )


def downgrade() -> None:
    """Restore prior columns and key only on an explicitly disposable database."""
    require_destructive_downgrade()
    op.execute(
        "ALTER TABLE checklist_versions ADD COLUMN IF NOT EXISTS primitive_configs_jsonb JSONB"
    )
    op.execute(
        "UPDATE checklist_versions SET primitive_configs_jsonb = primitive_configs "
        "WHERE primitive_configs_jsonb IS NULL"
    )
    op.execute("ALTER TABLE checklist_versions ALTER COLUMN primitive_configs_jsonb SET NOT NULL")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conrelid = 'telegram_subscriptions'::regclass "
        "AND conname = 'telegram_subscriptions_pkey' "
        "AND pg_get_constraintdef(oid) = 'PRIMARY KEY (id)') "
        "THEN ALTER TABLE telegram_subscriptions DROP CONSTRAINT telegram_subscriptions_pkey; "
        "ALTER TABLE telegram_subscriptions ADD CONSTRAINT telegram_subscriptions_pkey "
        "PRIMARY KEY (user_id, chat_id); END IF; END; $$"
    )
