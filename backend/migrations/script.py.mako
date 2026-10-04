"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from alembic import op
import sqlalchemy as sa

from backend.migrations.guards import require_destructive_downgrade
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade the schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade only when explicitly allowed for a disposable database."""
    require_destructive_downgrade()
    ${downgrades if downgrades else "pass"}
