package dev.parallax.gateway.task;

import java.time.Instant;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;

public record WorkerEvent(
        @JsonProperty("schema_version") int schemaVersion,
        @JsonProperty("event_id") String eventId,
        @JsonProperty("task_id") String taskId,
        int attempt,
        @JsonProperty("fencing_token") long fencingToken,
        long sequence,
        Kind kind,
        @JsonProperty("occurred_at") Instant occurredAt,
        @JsonProperty("result_sha256") String resultSha256,
        @JsonProperty(value = "prompt_tokens", required = true) long promptTokens,
        @JsonProperty(value = "completion_tokens", required = true) long completionTokens) {

    public enum Kind { STARTED, PROGRESS, SUCCEEDED, FAILED, CANCELED }

    public WorkerEvent {
        if (schemaVersion != 1) throw new IllegalArgumentException("Unsupported event schema version");
        WorkerTask.requireId(eventId); WorkerTask.requireId(taskId);
        if (attempt < 1 || fencingToken < 1 || sequence < 1 || promptTokens < 0 || completionTokens < 0) {
            throw new IllegalArgumentException("Invalid event counters");
        }
        Math.addExact(promptTokens, completionTokens);
        Objects.requireNonNull(kind, "kind");
        Objects.requireNonNull(occurredAt, "occurred_at");
        if (kind == Kind.SUCCEEDED) {
            if (resultSha256 == null || !resultSha256.matches("[0-9a-f]{64}")) {
                throw new IllegalArgumentException("Successful result requires a SHA-256 digest");
            }
        } else if (resultSha256 != null) {
            throw new IllegalArgumentException("Only successful events contain result_sha256");
        }
    }

    public void requireCurrent(WorkerTask task) {
        if (!taskId.equals(task.taskId()) || attempt != task.attempt() || fencingToken != task.fencingToken()) {
            throw new IllegalStateException("Stale or unrelated worker event");
        }
    }
}
