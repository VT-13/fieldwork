-- Historical 001 schema snapshot only. Canonical current schema is Alembic001→003; see app/models.py and docs/MIGRATION_PLAN.md.
-- Fieldwork initial PostgreSQL schema. Managed through Alembic.


CREATE TABLE cache (
	key VARCHAR(64) NOT NULL, 
	value JSON NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;

CREATE TABLE companies (
	id VARCHAR(36) NOT NULL, 
	domain VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	website TEXT NOT NULL, 
	industry VARCHAR(100) NOT NULL, 
	distance_miles FLOAT, 
	description TEXT NOT NULL, 
	source TEXT NOT NULL, 
	research JSON NOT NULL, 
	score INTEGER NOT NULL, 
	score_factors JSON NOT NULL, 
	stage VARCHAR(40) NOT NULL, 
	demo BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	researched_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (domain)
)

;
CREATE INDEX ix_companies_stage ON companies (stage);

CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	payload JSON NOT NULL, 
	dedupe_key VARCHAR(255) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	error TEXT NOT NULL, 
	result JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (dedupe_key)
)

;
CREATE INDEX ix_jobs_status ON jobs (status);

CREATE TABLE profiles (
	id INTEGER NOT NULL, 
	data JSON NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE state (
	key VARCHAR(100) NOT NULL, 
	value JSON NOT NULL, 
	PRIMARY KEY (key)
)

;

CREATE TABLE suppressions (
	email VARCHAR(320) NOT NULL, 
	reason VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (email)
)

;

CREATE TABLE contacts (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	source TEXT NOT NULL, 
	validation VARCHAR(40) NOT NULL, 
	validated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	UNIQUE (email)
)

;
CREATE INDEX ix_contacts_company_id ON contacts (company_id);

CREATE TABLE events (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	source_id VARCHAR(255) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	UNIQUE (source_id)
)

;
CREATE INDEX ix_events_company_id ON events (company_id);

CREATE TABLE evidence (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	url TEXT NOT NULL, 
	quote TEXT NOT NULL, 
	fact TEXT NOT NULL, 
	category VARCHAR(60) NOT NULL, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id)
)

;
CREATE INDEX ix_evidence_company_id ON evidence (company_id);

CREATE TABLE usage (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36), 
	service VARCHAR(80) NOT NULL, 
	reserved_usd FLOAT NOT NULL, 
	tokens INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id)
)

;
CREATE INDEX ix_usage_created_at ON usage (created_at);
CREATE INDEX ix_usage_company_id ON usage (company_id);

CREATE TABLE outreach (
	id VARCHAR(36) NOT NULL, 
	company_id VARCHAR(36) NOT NULL, 
	contact_id VARCHAR(36) NOT NULL, 
	sequence INTEGER NOT NULL, 
	subject VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	evidence_ids JSON NOT NULL, 
	review JSON NOT NULL, 
	strategy VARCHAR(80) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	provider_id TEXT NOT NULL, 
	thread_id TEXT NOT NULL, 
	message_id VARCHAR(255) NOT NULL, 
	attempts INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (company_id, sequence), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(contact_id) REFERENCES contacts (id)
)

;
CREATE INDEX ix_outreach_status ON outreach (status);
CREATE INDEX ix_outreach_company_id ON outreach (company_id);
CREATE INDEX outreach_due ON outreach (status, due_at);
