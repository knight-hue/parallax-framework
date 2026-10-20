CREATE TABLE platform_repository (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    name VARCHAR(120) NOT NULL,
    clone_url VARCHAR(1024) NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (project_id) REFERENCES platform_project(id),
    FOREIGN KEY (created_by) REFERENCES platform_user(id),
    CONSTRAINT uq_platform_repository_name UNIQUE (project_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_repository_project ON platform_repository(project_id, id);

CREATE TABLE platform_policy_version (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    config_json VARCHAR(4000) NOT NULL,
    config_sha256 VARCHAR(64) NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (project_id) REFERENCES platform_project(id),
    FOREIGN KEY (created_by) REFERENCES platform_user(id),
    CONSTRAINT uq_platform_policy_version UNIQUE (project_id, version_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_policy_project ON platform_policy_version(project_id, id);
