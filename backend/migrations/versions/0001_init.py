"""Initial PostgreSQL schema, expanded without partitioning (ADR-0012)."""

import json
from pathlib import Path

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tables, indexes, and append-only guards from frozen schema v1.1."""
    sql_path = Path(__file__).with_suffix(".statements.json")
    statements = json.loads(sql_path.read_text(encoding="utf-8"))
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    """Preserve production facts: initial schema rollback requires an explicit plan."""
    raise RuntimeError("Initial schema downgrade is intentionally disabled")
