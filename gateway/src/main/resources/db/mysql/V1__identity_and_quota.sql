-- MySQL baseline: UTC DATETIME(6), explicit FK constraints, deterministic collation.
CREATE TABLE quota_policy (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(64)  NOT NULL UNIQUE,
    daily_run_limit     INTEGER      NOT NULL,
    daily_token_limit   BIGINT       NOT NULL,
    monthly_token_limit BIGINT       NOT NULL,
    created_at          DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE api_credential (
    id              VARCHAR(36) PRIMARY KEY,
    name            VARCHAR(80) NOT NULL,
    key_hash        VARCHAR(64) NOT NULL UNIQUE,
    key_prefix      VARCHAR(16) NOT NULL,
    role            VARCHAR(16) NOT NULL,
    quota_policy_id BIGINT      NOT NULL,
    created_at      DATETIME(6) NOT NULL,
    revoked_at      DATETIME(6),
    last_used_at    DATETIME(6),
    FOREIGN KEY (quota_policy_id) REFERENCES quota_policy(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE INDEX idx_api_credential_hash ON api_credential (key_hash);

CREATE TABLE usage_ledger (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    credential_id VARCHAR(36) NOT NULL,
    run_id            VARCHAR(64) NOT NULL,
    occurred_at       DATETIME(6) NOT NULL,
    prompt_tokens     BIGINT      NOT NULL,
    completion_tokens BIGINT      NOT NULL,
    total_tokens      BIGINT      NOT NULL,
    trace_id          VARCHAR(64),
    CONSTRAINT uq_usage_run UNIQUE (run_id),
    FOREIGN KEY (credential_id) REFERENCES api_credential(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE INDEX idx_usage_credential_time ON usage_ledger (credential_id, occurred_at);

INSERT INTO quota_policy (name, daily_run_limit, daily_token_limit, monthly_token_limit, created_at)
VALUES ('default', 20, 2000000, 20000000, CURRENT_TIMESTAMP);
