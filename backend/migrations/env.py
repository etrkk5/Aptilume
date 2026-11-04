from alembic import context
from app.models import Base

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    from app.store import Store
    from app.config import Settings

    connection = Store(Settings.from_env()).engine.connect()
context.configure(
    connection=connection, target_metadata=Base.metadata, compare_type=True
)
with context.begin_transaction():
    context.run_migrations()
