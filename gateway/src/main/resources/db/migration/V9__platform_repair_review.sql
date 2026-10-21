ALTER TABLE platform_task ADD CONSTRAINT uq_platform_task_project_id UNIQUE (project_id,id);

CREATE TABLE platform_repair_review (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL REFERENCES platform_task(id),
    project_id VARCHAR(36) NOT NULL,
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    source_commit_sha VARCHAR(64) NOT NULL,
    patch_sha256 VARCHAR(64) NOT NULL,
    patch_content TEXT NOT NULL,
    test_command VARCHAR(1000) NOT NULL,
    approval_digest VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL CHECK (status IN ('AWAITING_APPROVAL','APPROVED','REJECTED','VERIFYING','PASSED','FAILED')),
    approved_by VARCHAR(36) REFERENCES platform_user(id),
    approved_at TIMESTAMP WITH TIME ZONE,
    verification_id VARCHAR(120),
    verification_sha256 VARCHAR(64),
    verification_detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_repair_review_digest UNIQUE (task_id,approval_digest),
    FOREIGN KEY (project_id,task_id) REFERENCES platform_task(project_id,id)
);
CREATE INDEX idx_platform_repair_review_project ON platform_repair_review(project_id,created_at,id);
