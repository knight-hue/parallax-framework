ALTER TABLE platform_task ADD COLUMN recovery_reason VARCHAR(120);
CREATE INDEX idx_platform_task_budget_reconcile ON platform_task(organization_id,settled,id);
CREATE TABLE platform_task_event (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id VARCHAR(64) NOT NULL UNIQUE,
    task_id VARCHAR(36) NOT NULL,
    attempt INTEGER NOT NULL,
    fencing_token BIGINT NOT NULL,
    sequence_number BIGINT,
    kind VARCHAR(48) NOT NULL,
    payload VARCHAR(8000) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    received_at DATETIME(6) NOT NULL,
    FOREIGN KEY (task_id) REFERENCES platform_task(id),
    CONSTRAINT uq_platform_worker_sequence UNIQUE (task_id,attempt,sequence_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_task_event_replay ON platform_task_event(task_id,id);
