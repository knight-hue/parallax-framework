CREATE TABLE platform_user (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE platform_organization (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE platform_membership (
    organization_id VARCHAR(36) NOT NULL REFERENCES platform_organization(id),
    user_id VARCHAR(36) NOT NULL REFERENCES platform_user(id),
    role VARCHAR(16) NOT NULL CHECK (role IN ('OWNER', 'MAINTAINER', 'REVIEWER', 'VIEWER')),
    PRIMARY KEY (organization_id, user_id)
);
CREATE INDEX idx_platform_member_user ON platform_membership(user_id, organization_id);

CREATE TABLE platform_project (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL REFERENCES platform_organization(id),
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_platform_project_name UNIQUE (organization_id, name)
);

CREATE TABLE platform_access_audit (
    id VARCHAR(36) PRIMARY KEY,
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(48) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX idx_platform_access_resource ON platform_access_audit(resource_id, at);
