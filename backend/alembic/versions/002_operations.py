"""Shared operation/attempt ledger; additive, preserves all legacy operational data."""
from alembic import op
revision='002'
down_revision='001'
branch_labels=None
depends_on=None

def upgrade():
    from app.migration_v2 import upgrade
    upgrade(op.get_bind())

def downgrade():
    # Dropping accepted/uncertain evidence would make duplicate sends possible.
    raise RuntimeError('Ledger downgrade is unsafe. Restore a verified pre-migration backup with all senders stopped.')
