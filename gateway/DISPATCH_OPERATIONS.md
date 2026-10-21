# Reliable platform dispatch

This runtime is opt-in. Keep `PARALLAX_DISPATCH_ENABLED=false` until the platform
Python Worker endpoints and the broker are accepted together. The legacy audit runner is independent.

Set these through the deployment secret/config provider (never commit credentials):

- `PARALLAX_DISPATCH_ENABLED=true`
- `PARALLAX_RABBIT_URI`: explicit AMQP/AMQPS URI with credentials and vhost. Use a
  dedicated vhost and least-privilege account. AMQPS checks server certificates and hostname.
- `PARALLAX_PLATFORM_WORKER_URL`: fixed private HTTP(S) Worker base URL. Redirects
  are disabled; it is never taken from task input.
- `PARALLAX_GATEWAY_INTERNAL_TOKEN`: same nonempty internal secret on Java and Worker.

On Python set `PARALLAX_PLATFORM_URL` to the fixed Java origin and
`PARALLAX_PLATFORM_SOURCE_HOSTS` to a JSON array of exact allowed source hosts.
`PARALLAX_PLATFORM_HEARTBEAT_SECONDS` defaults to 20 (must be shorter than the Java
lease, allowing for network delays); `PARALLAX_PLATFORM_REPLAY_SECONDS` defaults to 5.
The application starts receipt replay automatically and stops executions on shutdown.
Heartbeats currently report zero until final cumulative usage is known. Interrupted
provider work never receives an invented zero-cost terminal refund: Java lease
recovery conservatively charges the reservation and records uncertain usage.

The runtime declares durable direct exchange `parallax.dispatch.v1`, separate quorum
task/cancel queues, and a quorum dead-letter queue. Requires RabbitMQ 4.1+ with quorum
at-least-once dead-letter support. Task/cancel queues reject publishing beyond 10,000
messages; publisher nacks leave the Outbox retryable. Do not silently change arguments
of an existing queue: provision compatible topology before enabling this runtime.
For availability across broker-node failure, deploy a properly sized RabbitMQ cluster;
a single local broker only verifies delivery behavior.

## Guarantees and limits

1. The database Outbox commits with task/reservation. Claiming uses a short READ
   COMMITTED transaction, row locks with SKIP LOCKED, a random claim token and 30-second
   expiry. Broker I/O happens after commit. Expired claim owners cannot overwrite a
   newer owner's decision. READ COMMITTED avoids MySQL next-key locks while mutating
   the status index; true MySQL contention is covered by the opt-in verifier.
2. Messages are persistent, mandatory and confirmed with a bounded wait. PUBLISHED
   means RabbitMQ confirmed routable delivery, not that the engine finished. Lost
   confirms/process crashes can deliver duplicates; STARTED fencing and Worker dedup
   are necessary. Publication retries back off to 60 seconds without refunding work.
3. A two-thread scheduler publishes at most 10 messages per batch and scans at most
   100 expired tasks per recovery batch. Defaults: publication delay 500 ms, recovery
   delay 5 seconds. Recovery retains the coordinator's conservative charging rules.
4. Consumers use manual acknowledgements and prefetch 1, with 2..4 concurrent consumers.
   Worker 2xx / safe stale-or-duplicate 409 / expired 410 are acknowledged. Network,
   429 and 5xx failures requeue. Contract errors and permanent 4xx reject to DLQ.
   Quorum delivery limit 10 bounds repeated requeues; this is bounded redelivery,
   not unlimited delayed retry. The current HTTP bridge assumes 409 has no pending
   work requiring delivery; Worker implementations must preserve that contract.
5. At-least-once dead lettering with reject-publish retains messages when the DLQ
   cannot accept them. Monitor storage and DLQ, not just task completion. A DLQ
   entry is not a successful task: lease/deadline recovery remains authoritative.

Observe `parallax.outbox.*`, `parallax.dispatch.delivery` and `parallax.worker.*`
Micrometer counters, pending age, queue depth, dead-letter age and uncertain-usage
recoveries. After correcting a Worker/configuration error, inspect task state and
current attempt before an operator republishes a dead letter. Never blindly rerun a
started task or edit settled accounting history. Late events remain fenced.

## Isolated verification without image downloads

`RabbitDispatchTransportTest` verifies confirms, nacks, mandatory returns and timeouts
with a mocked broker. `WorkerHttpBridgeTest` uses a real loopback HTTP server and
mocked AMQP channels. Neither proves real RabbitMQ delivery.

When a RabbitMQ 4.1+ image is already cached, run from repository root:

```powershell
backend/.venv/Scripts/python.exe gateway/tools/verify_cached_rabbit.py --image rabbitmq:4.1-management --maven .toolchain/maven/bin/mvn.cmd --java-home .toolchain/jdk --out gateway/target/rabbit-acceptance
```

The tool inspects the cache first, starts only its own temporary container with
`--pull=never`, random credentials and a loopback random port, runs three opt-in
broker tests (persistent confirmation, channel-loss redelivery, reject-to-DLQ),
and removes only its own container. No existing broker is used or changed. Exit 2
means the Docker engine/image is unavailable; it is not a passing acceptance.
RabbitMQ production topology, cluster failover and capacity still need target-
environment evidence.
