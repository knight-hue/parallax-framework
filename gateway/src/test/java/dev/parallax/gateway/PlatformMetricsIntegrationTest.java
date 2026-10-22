package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;

import dev.parallax.gateway.platform.PlatformCatalogService;
import dev.parallax.gateway.platform.PlatformIdentityService;
import dev.parallax.gateway.platform.PlatformMetrics;
import dev.parallax.gateway.platform.PlatformTaskService;

import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class PlatformMetricsIntegrationTest {

    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired MeterRegistry registry;

    @Test
    void taskAndOutboxSignalsAreExposed() {
        var user = identity.provision("test", "metrics-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "team");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://github.com/team/api");
        var policy = catalog.publish(user.id(), project.id(),
                new PlatformCatalogService.PolicyConfig(4, 2, 3, 2, true, 1000L, 3600));
        tasks.configureBudget("test-admin", org.id(), 1000);

        var task = tasks.submit(user.id(), project.id(), "metrics-request",
                new PlatformTaskService.Submission(repository.id(), policy.id(), "a".repeat(40), 100));

        assertThat(registry.get(PlatformMetrics.TASK_TRANSITION).tag("state", "QUEUED")
                .counter().count()).isGreaterThanOrEqualTo(1);
        assertThat(registry.get("parallax.outbox.pending").gauge()).isNotNull();
        assertThat(registry.get("parallax.outbox.inflight").gauge()).isNotNull();
        assertThat(registry.get("parallax.outbox.oldest.age.seconds").gauge()).isNotNull();

        tasks.cancel(user.id(), project.id(), task.id());
        assertThat(registry.get(PlatformMetrics.TASK_TRANSITION).tag("state", "CANCELED")
                .counter().count()).isGreaterThanOrEqualTo(1);
    }
}
