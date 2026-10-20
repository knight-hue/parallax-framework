ALTER TABLE platform_project ADD CONSTRAINT uq_platform_project_org_id UNIQUE (organization_id,id);
ALTER TABLE platform_repository ADD CONSTRAINT uq_platform_repository_project_id UNIQUE (project_id,id);
ALTER TABLE platform_policy_version ADD CONSTRAINT uq_platform_policy_project_id UNIQUE (project_id,id);

CREATE TABLE platform_budget_account (
    organization_id VARCHAR(36) PRIMARY KEY REFERENCES platform_organization(id),
    token_limit BIGINT NOT NULL CHECK (token_limit BETWEEN 0 AND 1000000000000),
    reserved_tokens BIGINT NOT NULL DEFAULT 0 CHECK (reserved_tokens >= 0),
    used_tokens BIGINT NOT NULL DEFAULT 0 CHECK (used_tokens >= 0),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT ck_platform_budget_available CHECK (used_tokens <= token_limit AND reserved_tokens <= token_limit-used_tokens)
);

CREATE TABLE platform_task (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL REFERENCES platform_budget_account(organization_id),
    project_id VARCHAR(36) NOT NULL,
    repository_id VARCHAR(36) NOT NULL,
    policy_version VARCHAR(36) NOT NULL,
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    request_key VARCHAR(64) NOT NULL,
    request_sha256 VARCHAR(64) NOT NULL,
    commit_sha VARCHAR(64) NOT NULL,
    token_budget BIGINT NOT NULL CHECK (token_budget BETWEEN 1 AND 10000000),
    deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    state VARCHAR(24) NOT NULL CHECK (state IN ('QUEUED','DISPATCHED','RUNNING','CANCEL_REQUESTED','SUCCEEDED','FAILED','CANCELED')),
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    fencing_token BIGINT NOT NULL CHECK (fencing_token > 0),
    last_sequence BIGINT NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    prompt_tokens BIGINT NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    completion_tokens BIGINT NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
    settled BOOLEAN NOT NULL DEFAULT FALSE,
    lease_until TIMESTAMP WITH TIME ZONE,
    result_sha256 VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_task_request UNIQUE (project_id,created_by,request_key),
    FOREIGN KEY (organization_id,project_id) REFERENCES platform_project(organization_id,id),
    FOREIGN KEY (project_id,repository_id) REFERENCES platform_repository(project_id,id),
    FOREIGN KEY (project_id,policy_version) REFERENCES platform_policy_version(project_id,id),
    CONSTRAINT ck_platform_task_usage CHECK (prompt_tokens <= token_budget AND completion_tokens <= token_budget-prompt_tokens)
);
CREATE INDEX idx_platform_task_project ON platform_task(project_id,id);
CREATE INDEX idx_platform_task_recovery ON platform_task(state,lease_until,id);

CREATE TABLE platform_budget_ledger (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL REFERENCES platform_budget_account(organization_id),
    task_id VARCHAR(36) NOT NULL REFERENCES platform_task(id),
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('RESERVE','SETTLE')),
    tokens BIGINT NOT NULL CHECK (tokens >= 0),
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_budget_entry UNIQUE (task_id,kind)
);
CREATE INDEX idx_platform_budget_ledger_org ON platform_budget_ledger(organization_id,id);

CREATE TABLE platform_outbox (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES platform_task(id),
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('DISPATCH','CANCEL')),
    payload VARCHAR(4000) NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('PENDING','IN_FLIGHT','PUBLISHED','SUPERSEDED')),
    available_at TIMESTAMP WITH TIME ZONE NOT NULL,
    claim_token VARCHAR(36),
    claim_until TIMESTAMP WITH TIME ZONE,
    publish_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_platform_outbox_attempt UNIQUE (task_id,attempt,kind)
);
CREATE INDEX idx_platform_outbox_pending ON platform_outbox(status,available_at,id);
