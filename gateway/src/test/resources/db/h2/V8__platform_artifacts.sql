CREATE TABLE platform_task_artifact (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    artifact_id VARCHAR(64) NOT NULL UNIQUE,
    task_id VARCHAR(36) NOT NULL,
    attempt INTEGER NOT NULL,
    fencing_token BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    FOREIGN KEY (task_id) REFERENCES platform_task(id),
    CONSTRAINT uq_platform_artifact_attempt UNIQUE (task_id,attempt,sha256)
);
CREATE INDEX idx_platform_task_artifact_task ON platform_task_artifact(task_id,created_at);
