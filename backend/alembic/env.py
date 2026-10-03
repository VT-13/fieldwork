from alembic import context
from app.db import Base, engine
from app import models
config=context.config
if context.is_offline_mode():
    from app.config import settings
    context.configure(url=settings().database_url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    def migrate(conn):
        context.configure(connection=conn,target_metadata=Base.metadata)
        with context.begin_transaction():context.run_migrations()
    supplied=config.attributes.get('connection')
    if supplied is not None:migrate(supplied)
    else:
        with engine.connect() as conn:migrate(conn)
