# Platform worker protocol v1

Java owns organization/project authorization, task state, attempt issuance, fencing tokens,
event sequence acceptance and settlement. Workers own analysis and emit observations.
The legacy HTTP/file runner is unchanged until the platform coordinator is integrated.

`v1/task.json` and `v1/succeeded.json` are shared Java/Python conformance fixtures.
Unknown fields/versions, coerced integer strings, unpinned commits and invalid counters
are rejected. Wire dates carry a timezone. No model credentials, host paths or arbitrary
commands are included; trusted repository/policy resolution is a separate worker capability.

- `task_id` identifies one logical task. `attempt` increases for each execution retry.
- `fencing_token` is a monotonically increasing coordinator-issued lease version. The
  receiver must compare it atomically with persisted task state; parsing alone cannot fence.
- `event_id` is the deduplication key. `(task_id, attempt, sequence)` is unique and ordered
  within an attempt. Missing/out-of-order events require retry/reconciliation, not silent loss.
- Repeated IDs with a different body are conflicts, not successful duplicates.
- `result_sha256` is mandatory only for success. Validate referenced stored artifact bytes
  before publishing a report; a supplied digest alone is not proof of a correct result.
- Usage values are nonnegative signed 64-bit integers with an overflow-checked sum.
- Requeue is coordinator-only and must increment attempt/fencing before dispatch. A broker
  acknowledgment does not finish a task; a heartbeat does not independently authorize it.
- Cancellation is a request until acknowledged. A concurrent success/failure may finish
  first. Terminal states cannot reopen; idempotent terminal replay cannot change its data.

Task lifecycle: `QUEUED -> DISPATCHED -> RUNNING -> SUCCEEDED/FAILED`.
Queued tasks can cancel directly; dispatched/running tasks enter `CANCEL_REQUESTED`.
The state enum describes legal edges; transaction predicates and durable uniqueness are
implemented by the coordinator, not by this contract module.
