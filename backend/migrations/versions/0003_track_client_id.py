"""Expand existing location tracks for client-generated idempotency keys."""

from alembic import op

from backend.migrations.guards import require_destructive_downgrade

revision = "0003_track_client_id"
down_revision = "0002_notification_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep historical rows nullable while requiring UUIDv7 at the API boundary."""
    op.execute("ALTER TABLE location_tracks ADD COLUMN IF NOT EXISTS client_track_id UUID")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tracks_client_device "
        "ON location_tracks (client_track_id, device_id)"
    )


def downgrade() -> None:
    """Remove track identities only on an explicitly disposable database."""
    require_destructive_downgrade()
    op.execute("DROP INDEX IF EXISTS uq_tracks_client_device")
    op.execute("ALTER TABLE location_tracks DROP COLUMN IF EXISTS client_track_id")
