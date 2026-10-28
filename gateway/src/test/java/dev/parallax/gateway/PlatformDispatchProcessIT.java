package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;

import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.TaskState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * Full dispatch chain: Outbox -> real RabbitMQ -> Java consumer -> real Python worker process.
 *
 * <p>Two different worker processes serve the same fixed endpoint, and the second worker is also the
 * only thing alive when a dead-lettered dispatch has to be recovered by attempt/fence.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
    "parallax.jwt.secret=0123456789abcdef0123456789abcdef",
    "parallax.gateway.admin-secret=platform-test-admin",
    "parallax.dispatch.enabled=true",
    "parallax.gateway.internal-token=test-internal-token",
    "parallax.worker.lease-seconds=15",
    "parallax.dispatch.publish-delay-ms=200",
    "parallax.dispatch.recovery-delay-ms=500"
})
@ActiveProfiles("test")
@EnabledIfSystemProperty(named = "parallax.test.rabbit", matches = "true")
@EnabledIfSystemProperty(named = "parallax.test.python", matches = ".+")
class PlatformDispatchProcessIT {
    private static final int WORKER_PORT = freePort();

    @DynamicPropertySource
    static void dispatchProperties(DynamicPropertyRegistry registry) {
        registry.add("parallax.dispatch.rabbit-uri", () -> {
            String uri = System.getenv("PARALLAX_TEST_RABBIT_URI");
            return uri == null || uri.isBlank() ? "amqp://nobody:nothing@127.0.0.1:1/%2f" : uri;
        });
        registry.add("parallax.dispatch.worker-url", () -> "http://127.0.0.1:" + WORKER_PORT);
    }

    @LocalServerPort int gatewayPort;
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformArtifactService artifacts;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper mapper;
    @TempDir Path temporary;
    private final HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(2)).build();

    private record Fixture(String user, String org, String project, PlatformTaskService.Task task) {}

    private Fixture submit() {
        var user = identity.provision("test", "dispatch-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "team");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://github.com/team/api");
        var policy = catalog.publish(user.id(), project.id(),
                new PlatformCatalogService.PolicyConfig(2, 2, 1, 2, false, 1000, 600));
        tasks.configureBudget("test", org.id(), 10_000);
        var task = tasks.submit(user.id(), project.id(), "request-" + UUID.randomUUID(),
                new PlatformTaskService.Submission(repository.id(), policy.id(), "a".repeat(40), 1000));
        return new Fixture(user.id(), org.id(), project.id(), task);
    }

    private Process startWorker() throws Exception {
        Path repo = Path.of("").toAbsolutePath().getParent();
        var builder = new ProcessBuilder(System.getProperty("parallax.test.python"),
                repo.resolve("backend/tests/platform_process_fixture.py").toString(), temporary.toString(),
                "http://127.0.0.1:" + gatewayPort, Integer.toString(WORKER_PORT));
        builder.directory(repo.resolve("backend").toFile());
        builder.environment().put("PYTHONPATH", repo.resolve("backend").toString());
        for (String key : new String[]{"OPENAI_API_KEY", "PARALLAX_LLM_API_KEY", "OPENAI_BASE_URL",
                "PARALLAX_LLM_BASE_URL"}) {
            builder.environment().remove(key);
        }
        return builder.redirectErrorStream(true)
                .redirectOutput(ProcessBuilder.Redirect.appendTo(temporary.resolve("worker.log").toFile()))
                .start();
    }

    private void ready(Process process) throws Exception {
        await(() -> {
            assertThat(process.isAlive())
                    .as("Python worker must stay alive; see %s", temporary.resolve("worker.log")).isTrue();
            try {
                var response = http.send(HttpRequest.newBuilder(
                                URI.create("http://127.0.0.1:" + WORKER_PORT + "/health"))
                        .timeout(Duration.ofSeconds(1)).GET().build(), HttpResponse.BodyHandlers.discarding());
                return response.statusCode() == 200;
            } catch (Exception ex) {
                return false;
            }
        }, 25);
    }

    private static void await(BooleanSupplier condition, int seconds) throws Exception {
        long end = System.nanoTime() + Duration.ofSeconds(seconds).toNanos();
        while (System.nanoTime() < end) {
            if (condition.getAsBoolean()) return;
            Thread.sleep(50);
        }
        assertThat(condition.getAsBoolean()).as("Condition must converge within %s seconds", seconds).isTrue();
    }

    private PlatformTaskService.Task current(Fixture f) {
        return tasks.get(f.user, f.project, f.task.id());
    }

    private static void stop(Process process) throws Exception {
        process.destroy();
        if (!process.waitFor(10, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            assertThat(process.waitFor(10, TimeUnit.SECONDS)).isTrue();
        }
    }

    private static int freePort() {
        try (var socket = new ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) {
            return socket.getLocalPort();
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    private int settlements(String taskId) {
        return jdbc.queryForObject(
                "SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=? AND kind='SETTLE'",
                Integer.class, taskId);
    }

    @Test
    void brokerDeliveryReachesARealWorkerAndASecondProcessServesTheNextTask() throws Exception {
        Process worker = startWorker();
        try {
            ready(worker);
            var first = submit();
            await(() -> current(first).state() == TaskState.SUCCEEDED, 90);
            assertThat(current(first).attempt()).isEqualTo(1);
            assertThat(settlements(first.task.id())).isEqualTo(1);
            assertThat(tasks.budget(first.user, first.org))
                    .isEqualTo(new PlatformTaskService.Budget(first.org, 10_000, 0, 10));
            assertThat(tasks.reconcile(first.org).consistent()).isTrue();
            assertThat(artifacts.result(first.user, first.project, first.task.id()).content())
                    .contains("Demo.java", "Empty array access");

            // A different operating-system process must be able to serve the same fixed endpoint.
            stop(worker);
            worker = startWorker();
            ready(worker);
            var second = submit();
            await(() -> current(second).state() == TaskState.SUCCEEDED, 90);
            assertThat(settlements(second.task.id())).isEqualTo(1);
            assertThat(tasks.reconcile(second.org).consistent()).isTrue();
        } finally {
            if (worker.isAlive()) stop(worker);
        }
    }

    @Test
    void aDeadLetteredDispatchIsRecoveredByTheNextWorkerProcess() throws Exception {
        Process worker = null;
        try {
            // No worker is listening yet, so every broker delivery is refused and lands in the dead-letter queue.
            var task = submit();
            await(() -> current(task).state() == TaskState.DISPATCHED, 30);
            await(() -> current(task).attempt() >= 2, 90);
            assertThat(current(task).fencingToken()).isGreaterThan(1);
            assertThat(settlements(task.task.id())).isZero();

            worker = startWorker();
            ready(worker);
            await(() -> current(task).state() == TaskState.SUCCEEDED, 120);
            assertThat(current(task).attempt()).isGreaterThanOrEqualTo(1);
            assertThat(settlements(task.task.id())).isEqualTo(1);
            assertThat(tasks.reconcile(task.org).consistent()).isTrue();
        } finally {
            if (worker != null && worker.isAlive()) stop(worker);
            if (java.nio.file.Files.exists(temporary.resolve("worker.log"))) {
                java.nio.file.Files.copy(temporary.resolve("worker.log"),
                        Path.of("target/platform-dispatch-process.log"),
                        java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
        }
    }
}
