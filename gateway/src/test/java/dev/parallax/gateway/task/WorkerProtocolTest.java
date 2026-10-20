package dev.parallax.gateway.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class WorkerProtocolTest {
    private String fixture(String name) throws IOException {
        Path root = Path.of(System.getProperty("basedir", ".")).toAbsolutePath();
        if (!Files.exists(root.resolve("contracts"))) root = root.getParent();
        return Files.readString(root.resolve("contracts/worker/v1/" + name + ".json"));
    }

    @Test
    void consumesSameWireFixturesAsPython() throws Exception {
        var task = WorkerProtocol.readTask(fixture("task"));
        var event = WorkerProtocol.readEvent(fixture("succeeded"));
        event.requireCurrent(task);
        assertThat(task.tokenBudget()).isEqualTo(10000);
        assertThat(event.promptTokens() + event.completionTokens()).isEqualTo(120);
        task.requireActive(Instant.parse("2026-10-20T00:00:00Z"));
        assertThatThrownBy(() -> task.requireActive(task.deadline()))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void rejectsOldAttemptsEvenIfTaskIdMatches() throws Exception {
        String json = fixture("succeeded");
        var task = WorkerProtocol.readTask(fixture("task"));
        var oldAttempt = WorkerProtocol.readEvent(json.replace("\"attempt\": 2", "\"attempt\": 1"));
        var oldFence = WorkerProtocol.readEvent(json.replace("\"fencing_token\": 7", "\"fencing_token\": 6"));
        assertThatThrownBy(() -> oldAttempt.requireCurrent(task)).isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> oldFence.requireCurrent(task)).isInstanceOf(IllegalStateException.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "\"attempt\": 0", "\"attempt\": 2.5", "\"attempt\": \"2\"", "\"attempt\": null"
    })
    void rejectsInvalidWireNumbers(String replacement) throws Exception {
        String json = fixture("task").replace("\"attempt\": 2", replacement);
        assertThatThrownBy(() -> WorkerProtocol.readTask(json)).isInstanceOf(IOException.class);
    }

    @Test
    void rejectsUnknownFieldsVersionsAndTrailingObjects() throws Exception {
        String json = fixture("task");
        assertThatThrownBy(() -> WorkerProtocol.readTask(json.replace("{", "{\"api_key\":\"forbidden\",")))
                .isInstanceOf(IOException.class);
        assertThatThrownBy(() -> WorkerProtocol.readTask(json.replace("\"schema_version\": 1", "\"schema_version\": 2")))
                .isInstanceOf(IOException.class);
        assertThatThrownBy(() -> WorkerProtocol.readTask(json + "{}" )).isInstanceOf(IOException.class);
    }

    @Test
    void resultRequiresDigestAndCannotOverflowUsage() throws Exception {
        String json = fixture("succeeded");
        assertThatThrownBy(() -> WorkerProtocol.readEvent(json.replace("\"SUCCEEDED\"", "\"PROGRESS\"")))
                .isInstanceOf(IOException.class);
        assertThatThrownBy(() -> WorkerProtocol.readEvent(json.replace("\"kind\": \"SUCCEEDED\"", "\"kind\": 2")))
                .isInstanceOf(IOException.class);
        assertThatThrownBy(() -> WorkerProtocol.readEvent(json.replace("\"prompt_tokens\": 100", "\"prompt_tokens\": 9223372036854775807")))
                .isInstanceOf(IOException.class);
        assertThatThrownBy(() -> WorkerProtocol.readEvent(json.replace("\"prompt_tokens\": 100,", "")))
                .isInstanceOf(IOException.class);
    }

    @Test
    void lifecyclePreservesTerminalsAndAllowsCancellationRace() {
        assertThat(TaskState.QUEUED.transitionTo(TaskState.DISPATCHED)
                .transitionTo(TaskState.RUNNING).transitionTo(TaskState.CANCEL_REQUESTED)
                .transitionTo(TaskState.SUCCEEDED)).isEqualTo(TaskState.SUCCEEDED);
        assertThat(TaskState.RUNNING.transitionTo(TaskState.QUEUED)).isEqualTo(TaskState.QUEUED);
        assertThat(TaskState.CANCEL_REQUESTED.transitionTo(TaskState.CANCELED)).isEqualTo(TaskState.CANCELED);
        for (TaskState terminal : new TaskState[]{TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELED}) {
            assertThat(terminal.terminal()).isTrue();
            assertThat(terminal.transitionTo(terminal)).isEqualTo(terminal);
            assertThatThrownBy(() -> terminal.transitionTo(TaskState.RUNNING)).isInstanceOf(IllegalStateException.class);
        }
        assertThatThrownBy(() -> TaskState.QUEUED.transitionTo(TaskState.SUCCEEDED))
                .isInstanceOf(IllegalStateException.class);
    }
}
