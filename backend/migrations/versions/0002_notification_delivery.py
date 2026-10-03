"""Expand notification log for per-recipient outbox retry tracking."""

from alembic import op

from backend.migrations.guards import require_destructive_downgrade

revision = "0002_notification_delivery"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable event linkage without rewriting existing log rows."""
    op.execute("ALTER TABLE notification_log ADD COLUMN IF NOT EXISTS event_id UUID")
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conrelid = 'notification_log'::regclass AND conname = 'fk_notification_event') "
        "THEN ALTER TABLE notification_log ADD CONSTRAINT fk_notification_event "
        "FOREIGN KEY (event_id) REFERENCES events (id); END IF; END; $$"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conrelid = 'notification_log'::regclass "
        "AND conname = 'uq_notification_event_recipient') "
        "THEN ALTER TABLE notification_log ADD CONSTRAINT uq_notification_event_recipient "
        "UNIQUE (event_id, recipient); END IF; END; $$"
    )


def downgrade() -> None:
    """Reverse this expansion only on explicitly disposable databases."""
    require_destructive_downgrade()
    op.execute(
        "ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS uq_notification_event_recipient"
    )
    op.execute("ALTER TABLE notification_log DROP CONSTRAINT IF EXISTS fk_notification_event")
    op.execute("ALTER TABLE notification_log DROP COLUMN IF EXISTS event_id")
