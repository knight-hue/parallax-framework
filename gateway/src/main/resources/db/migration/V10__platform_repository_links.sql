CREATE TABLE platform_repository_link (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    repository_id VARCHAR(36) NOT NULL,
    provider VARCHAR(16) NOT NULL CHECK (provider IN ('GITHUB','GITLAB')),
    external_id VARCHAR(120) NOT NULL,
    token_budget BIGINT NOT NULL CHECK (token_budget BETWEEN 1 AND 10000000),
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_repository_link_external UNIQUE (provider, external_id),
    CONSTRAINT uq_platform_repository_link_target UNIQUE (project_id, repository_id, provider),
    FOREIGN KEY (project_id, repository_id) REFERENCES platform_repository(project_id, id)
);

CREATE TABLE platform_webhook_delivery (
    id VARCHAR(36) PRIMARY KEY,
    provider VARCHAR(16) NOT NULL,
    delivery_id VARCHAR(64) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    repository_id VARCHAR(36) NOT NULL,
    pull_request_number INTEGER NOT NULL CHECK (pull_request_number > 0),
    task_id VARCHAR(36) NOT NULL REFERENCES platform_task(id),
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    FOREIGN KEY (project_id, repository_id) REFERENCES platform_repository(project_id, id)
);
CREATE INDEX idx_platform_webhook_delivery ON platform_webhook_delivery(provider, delivery_id, received_at);

INSERT INTO platform_user (id, username, password_hash, disabled, created_at)
SELECT seed.id, seed.username, seed.password_hash, seed.disabled, seed.created_at FROM (
    SELECT '00000000-0000-0000-0000-000000000001' AS id, 'system.webhook' AS username,
           '$2a$12$UvDJ85QYd0eDXys4USt7.OvPmm79FmgODJjBzvWl97bgcXRd17wAe' AS password_hash,
           TRUE AS disabled, CURRENT_TIMESTAMP AS created_at
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM platform_user WHERE username = 'system.webhook');
