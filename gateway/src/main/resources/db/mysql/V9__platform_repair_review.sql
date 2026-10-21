ALTER TABLE platform_task ADD CONSTRAINT uq_platform_task_project_id UNIQUE (project_id,id);

CREATE TABLE platform_repair_review (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    source_commit_sha VARCHAR(64) NOT NULL,
    patch_sha256 VARCHAR(64) NOT NULL,
    patch_content MEDIUMTEXT NOT NULL,
    test_command VARCHAR(1000) NOT NULL,
    approval_digest VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL,
    approved_by VARCHAR(36),
    approved_at DATETIME(6),
    verification_id VARCHAR(120),
    verification_sha256 VARCHAR(64),
    verification_detail TEXT,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_platform_repair_review_digest UNIQUE (task_id,approval_digest),
    FOREIGN KEY (task_id) REFERENCES platform_task(id),
    FOREIGN KEY (project_id,task_id) REFERENCES platform_task(project_id,id),
    FOREIGN KEY (created_by) REFERENCES platform_user(id),
    FOREIGN KEY (approved_by) REFERENCES platform_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_repair_review_project ON platform_repair_review(project_id,created_at,id);
