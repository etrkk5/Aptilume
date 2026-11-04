"""Add scoped exports and persisted development plans to existing application DBs."""

from alembic import op
from app.models import ExportScope, DevelopmentAction

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    ExportScope.__table__.create(op.get_bind(), checkfirst=True)
    DevelopmentAction.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError(
        "Restore an operator-created backup; destructive downgrade is unsupported."
    )
