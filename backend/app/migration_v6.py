"""Frozen schema006 State identity widening, also used for empty-target staging.

No aliases or normalization: the original primary key and JSON remain intact.
The staging helper may run before legacy imports; Alembic still runs 002's
receipt backfill only after every legacy State record has been inserted.
"""
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext

STATE_KEY_LIMIT = 255


def widen_state_key(connection):
    observed = sa.inspect(connection).get_columns('state')
    column = next(c for c in observed if c['name'] == 'key')
    width = getattr(column['type'], 'length', None)
    if width not in (100, STATE_KEY_LIMIT):
        raise ValueError('Unrecognized State identifier schema; reconcile explicitly')
    # SQLite accepts over-width strings. Refuse before any schema006 DDL.
    if connection.scalar(sa.text('SELECT count(*) FROM state WHERE length(key) > 255')):
        raise ValueError('State identifier exceeds schema006 column width; reconcile losslessly')
    if width == STATE_KEY_LIMIT:
        return
    op = Operations(MigrationContext.configure(connection))
    with op.batch_alter_table('state') as batch:
        batch.alter_column('key', existing_type=sa.String(100),
                           type_=sa.String(STATE_KEY_LIMIT), existing_nullable=False)
