CREATE TABLE platform_share_link (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    max_accesses INTEGER,
    access_count BIGINT NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_platform_share_token UNIQUE (token_hash),
    CONSTRAINT ck_platform_share_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_platform_share_max CHECK (max_accesses IS NULL OR max_accesses > 0),
    CONSTRAINT ck_platform_share_count CHECK (access_count >= 0),
    FOREIGN KEY (task_id) REFERENCES platform_task(id)
);
CREATE INDEX idx_platform_share_task ON platform_share_link(project_id, task_id, id);
