package dev.parallax.gateway.platform;

public enum ProjectRole {
    VIEWER, REVIEWER, MAINTAINER, OWNER;

    public boolean permits(ProjectRole required) {
        return ordinal() >= required.ordinal();
    }
}
