-- Documentation of additive 003→004 only; run Alembic, not this file.

-- Precondition: schema003. No live database has been migrated.

ALTER TABLE evidence ADD COLUMN source_kind VARCHAR(30) NOT NULL DEFAULT 'unknown';

ALTER TABLE evidence ADD COLUMN confidence VARCHAR(30) NOT NULL DEFAULT 'unknown';

ALTER TABLE evidence ADD COLUMN content_hash VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE evidence ADD COLUMN verified_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE usage ADD COLUMN details JSON NOT NULL DEFAULT '{}';

CREATE TABLE candidates (
	id VARCHAR(36) NOT NULL,
	domain VARCHAR(255) NOT NULL,
	name VARCHAR(255) NOT NULL,
	website TEXT NOT NULL,
	industry VARCHAR(100) NOT NULL,
	distance_miles FLOAT,
	status VARCHAR(30) NOT NULL,
	company_id VARCHAR(36),
	observations JSON NOT NULL,
	contexts JSON NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (domain),
	FOREIGN KEY(company_id) REFERENCES companies (id)
);

CREATE TABLE contact_observations (
	id VARCHAR(36) NOT NULL,
	company_id VARCHAR(36) NOT NULL,
	contact_id VARCHAR(36) NOT NULL,
	field VARCHAR(40) NOT NULL,
	value TEXT NOT NULL,
	provider VARCHAR(30) NOT NULL,
	external_id VARCHAR(255) NOT NULL,
	source_url TEXT NOT NULL,
	confidence VARCHAR(30) NOT NULL,
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	verified_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(company_id) REFERENCES companies (id),
	FOREIGN KEY(contact_id) REFERENCES contacts (id)
);

CREATE INDEX ix_contact_observations_company_id ON contact_observations (company_id);

CREATE INDEX ix_contact_observations_contact_id ON contact_observations (contact_id);

CREATE TABLE student_facts (
	id VARCHAR(64) NOT NULL,
	profile_id INTEGER NOT NULL,
	profile_hash VARCHAR(64) NOT NULL,
	field VARCHAR(40) NOT NULL,
	text TEXT NOT NULL,
	verified_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(profile_id) REFERENCES profiles (id)
);

CREATE INDEX ix_student_facts_profile_hash ON student_facts (profile_hash);

CREATE TABLE generations (
	id VARCHAR(36) NOT NULL,
	company_id VARCHAR(36) NOT NULL,
	outreach_id VARCHAR(36),
	job_id VARCHAR(36),
	prompt_version VARCHAR(100) NOT NULL,
	provider VARCHAR(40) NOT NULL,
	model VARCHAR(80) NOT NULL,
	settings JSON NOT NULL,
	input_hash VARCHAR(64) NOT NULL,
	evidence_ids JSON NOT NULL,
	student_fact_ids JSON NOT NULL,
	subject VARCHAR(200) NOT NULL,
	body TEXT NOT NULL,
	review JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(company_id) REFERENCES companies (id),
	FOREIGN KEY(outreach_id) REFERENCES outreach (id),
	FOREIGN KEY(job_id) REFERENCES jobs (id)
);

CREATE INDEX ix_generations_company_id ON generations (company_id);

CREATE INDEX ix_generations_input_hash ON generations (input_hash);

CREATE INDEX ix_generations_outreach_id ON generations (outreach_id);
