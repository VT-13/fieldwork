"""Initial schema, frozen SQL artifact generated alongside this migration."""
from alembic import op
import sqlalchemy as sa
revision='001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    # Initial schema snapshot; future migrations must use explicit op changes.
    from app.migration_v1 import metadata
    metadata.create_all(op.get_bind())

def downgrade():
    from app.migration_v1 import metadata
    metadata.drop_all(op.get_bind())
