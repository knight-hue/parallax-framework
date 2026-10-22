package dev.parallax.gateway.platform;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

class PlatformMetricsTest {

    @Test
    void countersUseBoundedTagsAndArePreregistered() {
        var registry = new SimpleMeterRegistry();
        var metrics = new PlatformMetrics(registry);

        assertThat(registry.get(PlatformMetrics.TASK_TRANSITION).tag("state", "QUEUED")
                .counter().count()).isZero();
        assertThat(registry.get(PlatformMetrics.CACHE_OUTCOME).tag("outcome", "fallback")
                .counter().count()).isZero();

        metrics.taskTransition("QUEUED");
        metrics.workerEvent("STARTED", true);
        metrics.repairAction("verify", "passed");
        metrics.cache("hit");

        assertThat(registry.get(PlatformMetrics.TASK_TRANSITION).tag("state", "QUEUED")
                .counter().count()).isEqualTo(1);
        assertThat(registry.get(PlatformMetrics.WORKER_EVENT).tag("kind", "STARTED")
                .tag("accepted", "true").counter().count()).isEqualTo(1);
        assertThat(registry.get(PlatformMetrics.REPAIR_ACTION).tag("action", "verify")
                .tag("outcome", "passed").counter().count()).isEqualTo(1);
        assertThat(registry.get(PlatformMetrics.CACHE_OUTCOME).tag("outcome", "hit")
                .counter().count()).isEqualTo(1);
    }
}
