"""Add immutable answer-quality cases for HR review."""

from alembic import op
from app.models import QualityIssue, RunPolicy

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    QualityIssue.__table__.create(op.get_bind(), checkfirst=True)
    RunPolicy.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError(
        "Restore an operator-created backup; destructive downgrade is unsupported."
    )
