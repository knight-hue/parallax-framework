-- MySQL baseline: UTC DATETIME(6), explicit FK constraints, deterministic collation.
CREATE TABLE platform_user (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE platform_organization (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    created_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE platform_membership (
    organization_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('OWNER', 'MAINTAINER', 'REVIEWER', 'VIEWER')),
    PRIMARY KEY (organization_id, user_id),
    FOREIGN KEY (organization_id) REFERENCES platform_organization(id),
    FOREIGN KEY (user_id) REFERENCES platform_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_member_user ON platform_membership(user_id, organization_id);

CREATE TABLE platform_project (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_platform_project_name UNIQUE (organization_id, name),
    FOREIGN KEY (organization_id) REFERENCES platform_organization(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE platform_access_audit (
    id VARCHAR(36) PRIMARY KEY,
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(48) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
CREATE INDEX idx_platform_access_resource ON platform_access_audit(resource_id, at);
