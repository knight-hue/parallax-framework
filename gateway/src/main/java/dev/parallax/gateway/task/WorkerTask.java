package dev.parallax.gateway.task;

import java.time.Instant;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Immutable dispatch contract. Repository/policy references resolve inside a trusted worker. */
public record WorkerTask(
        @JsonProperty("schema_version") int schemaVersion,
        @JsonProperty("task_id") String taskId,
        int attempt,
        @JsonProperty("fencing_token") long fencingToken,
        @JsonProperty("organization_id") String organizationId,
        @JsonProperty("project_id") String projectId,
        @JsonProperty("repository_id") String repositoryId,
        @JsonProperty("commit_sha") String commitSha,
        @JsonProperty("policy_version") String policyVersion,
        @JsonProperty("token_budget") long tokenBudget,
        Instant deadline,
        @JsonProperty("trace_id") String traceId) {

    public WorkerTask {
        if (schemaVersion != 1) throw new IllegalArgumentException("Unsupported task schema version");
        requireId(taskId); requireId(organizationId); requireId(projectId);
        requireId(repositoryId); requireId(policyVersion);
        if (traceId != null) requireId(traceId);
        if (attempt < 1 || fencingToken < 1 || tokenBudget < 1) {
            throw new IllegalArgumentException("Attempt, fencing token and budget must be positive");
        }
        if (commitSha == null || !commitSha.matches("[0-9a-f]{40}|[0-9a-f]{64}")) {
            throw new IllegalArgumentException("A full, lowercase commit SHA is required");
        }
        Objects.requireNonNull(deadline, "deadline");
    }

    public void requireActive(Instant now) {
        if (!deadline.isAfter(now)) throw new IllegalStateException("Task deadline exceeded");
    }

    static void requireId(String value) {
        if (value == null || !value.matches("[A-Za-z0-9_-]{1,64}")) {
            throw new IllegalArgumentException("Invalid protocol identifier");
        }
    }
}
