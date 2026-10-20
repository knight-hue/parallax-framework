# Platform identity API

This module adds project ownership boundaries without changing legacy audit ownership.
Schema is managed by Flyway with MySQL as the default runtime and a legacy PostgreSQL
profile for migration/regression. Organization members currently inherit their role for all
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
not implemented. All platform collection endpoints use bounded UUID seek pagination:
`?after=<nextCursor>&limit=50` (1..100), returning `{items,nextCursor}`. A null cursor
means the end of the collection. Existing rate limiting remains in force; production diagnostics must
not log HTTP credential bodies or Authorization headers.

## Repositories and immutable policies

Under `/api/v1/platform/projects/{projectId}`:

- `POST /repositories` accepts `{name,cloneUrl}` (MAINTAINER); GET lists or GET
  `/repositories/{id}` reads (VIEWER). Names are unique within a project.
- Clone URLs require HTTPS on operator-approved exact hosts, without credentials,
  ports, query strings, fragments, path traversal or percent encoding. Defaults are
  github.com/gitlab.com/gitee.com; override `parallax.repositories.allowed-hosts`.
  This registry does not perform a network fetch. Worker checkout must separately
  enforce DNS/redirect/egress restrictions and map repository IDs, never client paths.
- `POST /policies` publishes a new version (MAINTAINER), GET lists or GET `/policies/{id}`
  reads (VIEWER). No update/delete endpoint exists. Each task will bind the policy ID,
  not a mutable "latest" alias. SHA-256 detects stored configuration changes.
- Policy config: `{readers:4,redundancy:2,maxRounds:3,minIndependentSupport:2,
  falsifierEnabled:true,maxTokenBudget:100000,deadlineSeconds:3600}`.
  Limits: readers 2..16, redundancy/support 1..readers, rounds 1..8, token budget
  1..10,000,000, deadline 60..86,400 seconds. These are platform-side bounds;
  worker application of the snapshot belongs to the execution integration module.
- Version numbers are serialized by a project row lock and a locking latest-version
  read, including under MySQL REPEATABLE READ. Configuration and access audit commit
  together. All resources check membership and project association at each access.
