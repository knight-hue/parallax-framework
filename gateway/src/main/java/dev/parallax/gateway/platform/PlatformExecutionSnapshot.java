package dev.parallax.gateway.platform;

import java.time.Clock;
import com.fasterxml.jackson.annotation.JsonProperty;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.task.TaskState;
import dev.parallax.gateway.task.WorkerTask;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** A snapshot lookup never grants execution. STARTED remains the only execution grant. */
@Service
public class PlatformExecutionSnapshot {
    public record Snapshot(WorkerTask task,
            @JsonProperty("clone_url") String cloneUrl,
            @JsonProperty("policy_json") String policyJson,
            @JsonProperty("policy_sha256") String policySha256,
            @JsonProperty("cancel_requested") boolean cancelRequested) { }
    private final PlatformTaskService tasks;
    private final PlatformCatalogService catalog;
    private final Clock clock;
    public PlatformExecutionSnapshot(PlatformTaskService tasks,PlatformCatalogService catalog,Clock clock) {
        this.tasks=tasks;this.catalog=catalog;this.clock=clock;
    }
    @Transactional(isolation=org.springframework.transaction.annotation.Isolation.READ_COMMITTED)
    public Snapshot resolve(WorkerTask requested) {
        var visible=tasks.current(requested.taskId(),false);
        tasks.lockBudget(visible.organizationId());
        var current=tasks.current(requested.taskId(),true);
        var expected=current.dispatch();
        // MySQL stores microseconds; old queued payloads may carry nanoseconds. Trace is diagnostic.
        if(requested.attempt()!=expected.attempt() || requested.fencingToken()!=expected.fencingToken()
                || !requested.organizationId().equals(expected.organizationId()) || !requested.projectId().equals(expected.projectId())
                || !requested.repositoryId().equals(expected.repositoryId()) || !requested.policyVersion().equals(expected.policyVersion())
                || !requested.commitSha().equals(expected.commitSha()) || requested.tokenBudget()!=expected.tokenBudget()
                || java.time.Duration.between(requested.deadline(),expected.deadline()).abs().compareTo(java.time.Duration.ofNanos(1000))>0) {
            throw new ApiException(HttpStatus.CONFLICT,"Execution contract differs from the authoritative task");
        }
        if(current.state().terminal() || !current.deadline().isAfter(clock.instant())) throw new ApiException(HttpStatus.GONE,"Task is no longer executable");
        if(current.state()==TaskState.QUEUED || current.leaseUntil()==null || !current.leaseUntil().isAfter(clock.instant())) {
            throw new ApiException(HttpStatus.CONFLICT,"Task has no active dispatch lease");
        }
        var config=catalog.executionPolicy(current.projectId(),current.repositoryId(),current.policyVersion());
        return new Snapshot(requested,config.cloneUrl(),config.policyJson(),config.policySha256(),current.state()==TaskState.CANCEL_REQUESTED);
    }
}
