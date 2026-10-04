"""Preserve exact legacy self-test identifiers; widen State keys losslessly."""
from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    from app.migration_v6 import widen_state_key
    widen_state_key(op.get_bind())


def downgrade():
    raise RuntimeError('State identity rollback is unsafe; restore a verified backup with senders stopped')
