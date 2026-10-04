-- Documentation only: Alembic006 and app/migration_v6.py are authoritative.
-- PostgreSQL: retain exact key/value, primary key and all history.
ALTER TABLE state ALTER COLUMN key TYPE VARCHAR(255);
-- SQLite: the Alembic batch operation rebuilds only the State table declaration.
-- Never manually stamp006 or execute this fragment on the installed database.
