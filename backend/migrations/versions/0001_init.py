"""Initial PostgreSQL schema, expanded without partitioning (ADR-0012)."""

import json
from pathlib import Path

from alembic import op

from backend.infrastructure.postgres.models import metadata
from backend.migrations.guards import require_destructive_downgrade

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial tables and indexes, including client track deduplication."""
    sql_path = Path(__file__).with_suffix(".statements.json")
    statements = json.loads(sql_path.read_text(encoding="utf-8"))
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    """Drop only project tables on an explicitly disposable database."""
    require_destructive_downgrade()
    for table in reversed(metadata.sorted_tables):
        op.execute(f'DROP TABLE IF EXISTS "{table.name}" CASCADE')
    op.execute("DROP FUNCTION IF EXISTS reject_fact_mutation()")
