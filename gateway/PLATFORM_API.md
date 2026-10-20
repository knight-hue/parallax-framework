# Platform identity API

This module adds project ownership boundaries without changing legacy audit ownership.
Schema is managed by Flyway; PostgreSQL/H2 migrations remain the current baseline until
the MySQL runtime is verified. Organization members currently inherit their role for all
projects in that organization; per-project membership overrides are not implemented.

1. An existing system administrator provisions a user with `POST /api/v1/platform/users`
   (`username`, `password`). Public self-registration is not enabled.
2. `POST /api/v1/auth/login` returns a user access token. Passwords have a minimum length
   of 12 characters and a maximum of 72 UTF-8 bytes, with BCrypt cost 12 storage.
3. A user creates/lists their organizations at `/api/v1/platform/organizations`.
4. Organization owners add/list/remove members at
   `/api/v1/platform/organizations/{id}/members[/{userId}]`.
5. Owners/maintainers create projects; members list them at
   `/api/v1/platform/organizations/{id}/projects` and read
   `/api/v1/platform/projects/{id}`.

Roles are OWNER > MAINTAINER > REVIEWER > VIEWER. Ownership transfer is not exposed;
membership mutation cannot remove or demote the owner. This ordering is enforced in
Java code and role values are constrained in the database. Resource creation and audit
events commit in the same transaction. Credentials and access tokens redact toString.

System administrators disable users with `DELETE /api/v1/platform/users/{id}`. The user
record and audit history are retained; disabled users cannot log in or reuse access tokens.
Membership is checked on every resource access, so a still-valid JWT does not retain a
removed membership. `/api/v1/platform/me` returns the current active user.

Tenant JWTs are denied access to legacy routes until those routes enforce project
ownership. Existing administrator JWTs/API keys keep their old endpoints; a legacy
administrator token alone cannot masquerade as a platform user. Later modules must
apply the same resource checks to tasks, events, reports, artifacts and approvals.

This is an identity foundation, not a claim of a completed platform. Password recovery,
organization ownership transfer, per-project overrides, SSO and a management UI are
not implemented. Current lists are unpaginated and need bounded pagination before
large-scale rollout. Existing rate limiting remains in force; production diagnostics must
not log HTTP credential bodies or Authorization headers.
