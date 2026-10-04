"""Additive evidence/candidate/generation provenance; historical records stay unknown."""
from alembic import op
import sqlalchemy as sa
revision='004'
down_revision='003'
branch_labels=None
depends_on=None

def upgrade():
    for name,type,default,nullable in [('source_kind',sa.String(30),'unknown',False),('confidence',sa.String(30),'unknown',False),('content_hash',sa.String(64),'',False),('verified_at',sa.DateTime(timezone=True),None,True)]:
        op.add_column('evidence',sa.Column(name,type,nullable=nullable,server_default=default))
    op.add_column('usage',sa.Column('details',sa.JSON,nullable=False,server_default='{}'))
    from app.migration_v4 import metadata
    metadata.create_all(op.get_bind(),tables=[metadata.tables[n] for n in ('candidates','contact_observations','student_facts','generations')])

def downgrade():
    raise RuntimeError('Intelligence history rollback requires a verified backup; never discard claim provenance')
