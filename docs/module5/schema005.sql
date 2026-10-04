-- Documentation only: frozen Alembic005 is the migration authority.
-- Additive PostgreSQL shape; no historical values/linkage are inferred.
ALTER TABLE jobs ADD COLUMN available_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE jobs ADD COLUMN owner_token VARCHAR(36) DEFAULT '' NOT NULL;
ALTER TABLE jobs ADD COLUMN lease_until TIMESTAMP WITH TIME ZONE;
CREATE INDEX ix_jobs_available_at ON jobs (available_at);
ALTER TABLE events ADD COLUMN contact_id VARCHAR(36);
ALTER TABLE events ADD CONSTRAINT events_contact_id_fk FOREIGN KEY (contact_id) REFERENCES contacts(id);
ALTER TABLE events ADD COLUMN outreach_id VARCHAR(36);
ALTER TABLE events ADD CONSTRAINT events_outreach_id_fk FOREIGN KEY (outreach_id) REFERENCES outreach(id);
ALTER TABLE events ADD COLUMN campaign_id VARCHAR(40) DEFAULT 'personal' NOT NULL;
