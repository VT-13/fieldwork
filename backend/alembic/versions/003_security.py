"""Add personal operator sessions and encrypted integration state. No credentials imported."""
from alembic import op
import sqlalchemy as sa
revision='003'
down_revision='002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('operator_sessions',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('operator_id',sa.String(40),nullable=False),sa.Column('auth_version',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('revoked_at',sa.DateTime(timezone=True)),sa.CheckConstraint("operator_id = 'personal'",name='session_personal_operator'))
    op.create_index('ix_operator_sessions_expires_at','operator_sessions',['expires_at'])
    op.create_table('integrations',sa.Column('id',sa.String(40),primary_key=True),sa.Column('operator_id',sa.String(40),nullable=False),sa.Column('email',sa.String(320),nullable=False),sa.Column('status',sa.String(40),nullable=False),sa.Column('generation',sa.Integer,nullable=False),sa.Column('encrypted_tokens',sa.Text,nullable=False),sa.Column('scopes',sa.JSON,nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("operator_id = 'personal'",name='integration_personal_operator'),sa.CheckConstraint("status in ('connected','disconnected','reconnect_required','identity_mismatch')",name='integration_status'))
    op.create_table('oauth_grants',sa.Column('state_hash',sa.String(64),primary_key=True),sa.Column('session_hash',sa.String(64),sa.ForeignKey('operator_sessions.token_hash'),nullable=False),sa.Column('verifier_ciphertext',sa.Text,nullable=False),sa.Column('expected_email',sa.String(320),nullable=False),sa.Column('generation',sa.Integer,nullable=False),sa.Column('requested_scopes',sa.JSON,nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed_at',sa.DateTime(timezone=True)))
    op.create_index('ix_oauth_grants_expires_at','oauth_grants',['expires_at'])
    op.create_table('rate_buckets',sa.Column('key',sa.String(64),primary_key=True),sa.Column('window_start',sa.DateTime(timezone=True),nullable=False),sa.Column('count',sa.Integer,nullable=False))

def downgrade():
    raise RuntimeError('Security-state rollback requires a verified backup; never discard integration revocation state')
