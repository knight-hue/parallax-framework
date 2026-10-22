CREATE TABLE platform_share_link (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    task_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6),
    max_accesses INTEGER,
    access_count BIGINT NOT NULL DEFAULT 0,
    last_accessed_at DATETIME(6),
    CONSTRAINT uq_platform_share_token UNIQUE (token_hash),
    CONSTRAINT ck_platform_share_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_platform_share_max CHECK (max_accesses IS NULL OR max_accesses > 0),
    CONSTRAINT ck_platform_share_count CHECK (access_count >= 0),
    FOREIGN KEY (task_id) REFERENCES platform_task(id),
    FOREIGN KEY (created_by) REFERENCES platform_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_share_task ON platform_share_link(project_id, task_id, id);
