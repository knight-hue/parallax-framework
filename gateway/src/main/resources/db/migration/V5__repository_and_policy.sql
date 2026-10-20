CREATE TABLE platform_repository (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES platform_project(id),
    name VARCHAR(120) NOT NULL,
    clone_url VARCHAR(1024) NOT NULL,
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_repository_name UNIQUE (project_id, name)
);
CREATE INDEX idx_platform_repository_project ON platform_repository(project_id, id);

CREATE TABLE platform_policy_version (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES platform_project(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    config_json VARCHAR(4000) NOT NULL,
    config_sha256 VARCHAR(64) NOT NULL,
    created_by VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_policy_version UNIQUE (project_id, version_number)
);
CREATE INDEX idx_platform_policy_project ON platform_policy_version(project_id, id);
