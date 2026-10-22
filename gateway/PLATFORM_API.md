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

## Platform tasks and token reservations

System ADMIN tokens configure an organization token limit with
`PUT /api/v1/platform/budgets/{organizationId}`: `{tokenLimit:1000000}`.
Limits are cumulative, not an implicit daily reset; used/reserved tokens cannot be
erased by lowering the limit. New organizations have no execution allowance until
an administrator grants it. Tenant roles cannot grant their own budget.

Members read `GET /api/v1/platform/organizations/{id}/budget`. Administrators inspect
`GET /api/v1/platform/budgets/{id}/reconciliation`: compares account counters against
unsettled tasks and immutable reservation/settlement ledger entries under an account
lock. It reports mismatches without silently modifying accounting history.

Under `/api/v1/platform/projects/{projectId}/tasks`:

- POST (REVIEWER) requires `Idempotency-Key` (1..64 letters/digits/underscore/hyphen),
  body `{repositoryId,policyVersion,commitSha,tokenBudget}`. SHA is a fixed full lowercase
  40/64 digit Git object ID. Repository and policy must belong to that project; budget
  cannot exceed the frozen policy. The policy determines the deadline.
- The key is scoped to project + submitting user. Same input replays the original task
  even after cancellation/exhaustion; different input returns 409. It never restarts a
  canceled task. Exhaustion returns 429.
- Reservation, task, RESERVE ledger, dispatch Outbox and access audit commit together.
  Organization account row locking and conditional update enforce capacity across DB
  connections; unique keys protect retries. Composite foreign keys enforce resource
  associations independently of Java checks.
- GET collection uses seek pagination; GET `/{id}` requires VIEWER. POST `/{id}/cancel`
  allows the submitting REVIEWER or a MAINTAINER. Queued cancellation settles at zero,
  refunds once and supersedes pending dispatch messages. Dispatched/running cancellation
  records CANCEL_REQUESTED and a cancel Outbox; a result racing cancellation may win.

This module durably queues work; broker publication and Python execution integration are
separate steps. The legacy audit entry point remains independent until worker integration
and the workbench are switched. Budget invariants are enforced in MySQL, not Redis.

## Worker coordination and durable event replay

`POST /api/v1/internal/platform/events` accepts the strict shared v1 WorkerEvent contract
with `X-Internal-Token`. Missing configuration returns 503; missing/wrong token returns
401. This ingress must stay on a private network. A tenant JWT does not authorize it.

- The platform grants execution only after accepting STARTED for a currently dispatched,
  leased attempt. Workers must wait for this acknowledgement before spending/model I/O.
- Event ID duplicates with identical canonical content are acknowledged without changes.
  ID reuse with different content, stale attempts/fences, gaps, terminal reopen and late
  heartbeats are rejected. Usage is cumulative and monotonic within the token reservation.
- Inbox/event insert, state update and final budget settlement are one transaction.
  Task/account locks serialize related work; READ COMMITTED for ingress avoids absent-key
  gap locking between unrelated tenants. All hard limits remain enforced by the database.
- STARTED/PROGRESS renew a server-clock lease (default 120 seconds, bounded by deadline).
  CANCEL_REQUESTED heartbeats do not extend that cancellation lease. A successful final
  result may race cancellation; whichever terminal transition commits is authoritative.
- Coordinator recovery retries only DISPATCHED work with no accepted STARTED, increasing
  attempt/fence (default maximum 3). Exhausted unclaimed work refunds; QUEUED deadlines
  cancel/refund. Running workers lost after a grant charge the full reservation
  conservatively with `WORKER_LOST_USAGE_UNCERTAIN`; reported token counters remain the
  last observation. This is an uncertainty charge, not a measured provider invoice. No
  automatic restart spends a fresh full budget while the old worker may still be alive.
- With the opt-in dispatch runtime enabled, bounded background scans call recovery and
  expose metrics. See DISPATCH_OPERATIONS.md; Python platform integration and real
  broker/multi-instance acceptance remain pending.

`GET /api/v1/platform/projects/{projectId}/tasks/{taskId}/events?after=0&limit=50`
checks live project membership and returns `{items,nextCursor}`. Cursor is the database
event ID (not worker sequence); events include system transitions and accepted worker
receipts, survive restart and remain ordered across attempt changes. Use the last returned
ID for future polling; a null nextCursor only means the current page reaches today's end.
No process-local queue is the source of platform progress. SSE/workbench integration is
still pending. Successful completion requires a stored artifact with matching task,
attempt, fence and SHA-256; an absent artifact cannot advance state or settle budget.

`POST /api/v1/internal/platform/execution-snapshot` uses the same mandatory private
credential and strict v1 WorkerTask. It validates the authoritative contract, active
dispatch lease, repository allowlist and policy integrity, returning `{task,clone_url,
policy_json,policy_sha256,cancel_requested}`. A stale contract/lease is 409; terminal
or expired work is 410. A lookup is not an execution grant: STARTED must still be
persisted and acknowledged before model or source I/O. Python's local delivery journal
and fixed-origin client implement retry foundations. The worker runs the evidence engine
after STARTED and uploads its report before sending SUCCEEDED; real cross-process
acceptance remains pending.

## Immutable result artifacts

`POST /api/v1/internal/platform/artifacts` requires the private internal credential and
body `{task_id,attempt,fencing_token,artifact_id,sha256,content}`. UTF-8 content is limited
to 2,000,000 bytes and its digest is verified. Only the current running/cancel-requested
attempt with an active lease/deadline may upload. Repeated content for the same attempt
returns the stored artifact with the same microsecond creation timestamp. Conflicting
artifact IDs return 409. Python validates the returned execution binding and content.

`GET /api/v1/platform/projects/{projectId}/tasks/{taskId}/result` requires live project
VIEWER membership and successful completion. It returns the bound artifact and verifies
stored content against the successful digest; corruption returns 409. Revoked members
and other projects cannot retrieve it. This is bounded database report storage; an S3
backend, patch lifecycle and approval integration are separate pending modules.

## Repair review and isolated verification

`POST /api/v1/platform/projects/{projectId}/tasks/{taskId}/repairs` requires a live
REVIEWER and a `SUCCEEDED` task. The body is
`{sourceCommitSha,patchSha256,patchContent,testCommand}`. The source commit must equal
the task snapshot and the patch digest is recalculated from the supplied UTF-8 bytes.
The response contains an immutable `approvalDigest`, which also binds the successful
report digest and test command. Repeating the same proposal is idempotent.

`POST .../repairs/{reviewId}/approve` requires a MAINTAINER and the exact approval
digest. It records approval only; it does not claim a regression passed. The isolated
executor submits its result through the private
`POST /api/v1/internal/platform/repair-verifications?projectId=...&taskId=...&reviewId=...`
endpoint with `X-Internal-Token`. Its body contains the approval digest, a verification
ID, SHA-256 of the JSON evidence and the evidence itself. The gateway checks that the
evidence names the exact review/task/commit/patch/command, proves a marked baseline
failure and a zero exit regression, and makes the terminal receipt idempotent. Public
users can read a proposal or page proposals with current project membership; they
cannot submit a verification receipt.

## Cache behavior

Policy-version reads may use a Redis/Redisson read-through cache when
`PARALLAX_CACHE_REDIS_URL` (or the rate-limit Redis URL) is configured. The gateway
checks live project membership before every policy lookup, so a cached value never
authorizes a request. Cache entries are immutable policy snapshots with a bounded TTL;
database rows remain authoritative for policy integrity and all task, quota, artifact,
and approval decisions; cached policy JSON is also schema- and digest-checked before use. A Redis timeout, lock timeout, malformed value, or unavailable
server falls back to MySQL. A short Redisson rebuild lease reduces a thundering herd,
but it is not used as a correctness lock or as a replacement for database constraints.
