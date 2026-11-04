"""Initial Aptilume schema, including role profiles and immutable results."""

from alembic import op
from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError(
        "Destructive downgrade is unsupported. Restore an operator-created backup instead."
    )
