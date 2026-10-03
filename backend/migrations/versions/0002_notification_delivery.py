"""Expand notification log for per-recipient outbox retry tracking."""

from alembic import op

revision = "0002_notification_delivery"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable event linkage without rewriting existing log rows."""
    op.execute("ALTER TABLE notification_log ADD COLUMN event_id UUID")
    op.execute(
        "ALTER TABLE notification_log ADD CONSTRAINT fk_notification_event "
        "FOREIGN KEY (event_id) REFERENCES events (id)"
    )
    op.execute(
        "ALTER TABLE notification_log ADD CONSTRAINT uq_notification_event_recipient "
        "UNIQUE (event_id, recipient)"
    )


def downgrade() -> None:
    """Preserve delivery records; removal needs a separate contract migration."""
    raise RuntimeError("Notification delivery contract rollback requires an explicit plan")
