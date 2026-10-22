package dev.parallax.gateway.platform;

import java.util.List;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * Bounded-cardinality platform signals intended for diagnosis and alerting.
 *
 * Tags deliberately use only finite sets (state, event kind, action, cache
 * outcome). Project, repository and delivery ids are never tags, because they
 * would explode Prometheus time-series cardinality.
 */
@Component
public class PlatformMetrics {

    public static final String TASK_TRANSITION = "parallax.platform.task.transition";
    public static final String WORKER_EVENT = "parallax.platform.worker.event";
    public static final String REPAIR_ACTION = "parallax.platform.repair.action";
    public static final String CACHE_OUTCOME = "parallax.policy.cache";

    private final MeterRegistry registry;

    public PlatformMetrics(MeterRegistry registry) {
        this.registry = registry;
        for (String state : List.of("QUEUED", "DISPATCHED", "RUNNING", "CANCEL_REQUESTED",
                "SUCCEEDED", "FAILED", "CANCELED")) {
            Counter.builder(TASK_TRANSITION).tag("state", state).register(registry);
        }
        for (String kind : List.of("STARTED", "PROGRESS", "SUCCEEDED", "FAILED", "CANCELED")) {
            Counter.builder(WORKER_EVENT).tag("kind", kind).tag("accepted", "true").register(registry);
            Counter.builder(WORKER_EVENT).tag("kind", kind).tag("accepted", "false").register(registry);
        }
        for (String action : List.of("propose", "approve", "verify")) {
            for (String outcome : List.of("accepted", "rejected", "passed", "failed")) {
                Counter.builder(REPAIR_ACTION).tag("action", action).tag("outcome", outcome).register(registry);
            }
        }
        for (String outcome : List.of("hit", "miss", "rebuild", "invalid", "fallback", "bypass", "write_error")) {
            Counter.builder(CACHE_OUTCOME).tag("outcome", outcome).register(registry);
        }
    }

    public void taskTransition(String state) {
        Counter.builder(TASK_TRANSITION).tag("state", state).register(registry).increment();
    }

    public void workerEvent(String kind, boolean accepted) {
        Counter.builder(WORKER_EVENT).tag("kind", kind).tag("accepted", Boolean.toString(accepted))
                .register(registry).increment();
    }

    public void repairAction(String action, String outcome) {
        Counter.builder(REPAIR_ACTION).tag("action", action).tag("outcome", outcome)
                .register(registry).increment();
    }

    public void cache(String outcome) {
        Counter.builder(CACHE_OUTCOME).tag("outcome", outcome).register(registry).increment();
    }
}
