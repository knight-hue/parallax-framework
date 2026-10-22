package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.Clock;
import java.time.temporal.ChronoUnit;
import com.fasterxml.jackson.annotation.JsonProperty;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.task.TaskState;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Immutable, content-addressed result artifact owned by the authoritative task attempt. */
@Service
public class PlatformArtifactService {
    public record Upload(@JsonProperty("task_id") String taskId, int attempt,
            @JsonProperty("fencing_token") long fencingToken,
            @JsonProperty("artifact_id") String artifactId, String sha256, String content) { }
    public record Artifact(String artifactId, String taskId, int attempt, long fencingToken,
            String sha256, String content, Instant createdAt) { }
    private final JdbcTemplate jdbc;
    private final PlatformTaskService tasks;
    private final Clock clock;
    public PlatformArtifactService(JdbcTemplate jdbc, PlatformTaskService tasks, Clock clock) { this.jdbc=jdbc;this.tasks=tasks;this.clock=clock; }

    @Transactional
    public Artifact put(Upload upload) {
        if(upload==null || upload.taskId()==null || upload.artifactId()==null || upload.sha256()==null || upload.content()==null)
            throw ApiException.badRequest("Artifact fields are required");
        if(upload.artifactId().length()>64 || !upload.artifactId().matches("[A-Za-z0-9_-]{1,64}")
                || !upload.sha256().matches("[0-9a-f]{64}") || upload.content().getBytes(StandardCharsets.UTF_8).length>2_000_000)
            throw ApiException.badRequest("Invalid or oversized artifact");
        if(!PlatformTaskService.hash(upload.content()).equals(upload.sha256())) throw ApiException.badRequest("Artifact digest mismatch");
        var task=tasks.current(upload.taskId(),true);
        if(task.attempt()!=upload.attempt() || task.fencingToken()!=upload.fencingToken()) throw new ApiException(HttpStatus.CONFLICT,"Stale artifact attempt");
        if(task.state()!=TaskState.RUNNING && task.state()!=TaskState.CANCEL_REQUESTED) throw new ApiException(HttpStatus.CONFLICT,"Task is not accepting artifacts");
        Instant now=clock.instant().truncatedTo(ChronoUnit.MICROS);
        if(task.leaseUntil()==null || !task.leaseUntil().isAfter(now) || !task.deadline().isAfter(now))
            throw new ApiException(HttpStatus.CONFLICT,"Artifact lease or deadline expired");
        var existing=jdbc.query("SELECT artifact_id,task_id,attempt,fencing_token,sha256,content,created_at FROM platform_task_artifact WHERE task_id=? AND attempt=? AND sha256=?",
                (rs,n)->artifact(rs),upload.taskId(),upload.attempt(),upload.sha256());
        if(!existing.isEmpty()) return existing.getFirst();
        try {
            jdbc.update("INSERT INTO platform_task_artifact(artifact_id,task_id,attempt,fencing_token,sha256,content,created_at) VALUES (?,?,?,?,?,?,?)",
                    upload.artifactId(),upload.taskId(),upload.attempt(),upload.fencingToken(),upload.sha256(),upload.content(),Timestamp.from(now));
            return new Artifact(upload.artifactId(),upload.taskId(),upload.attempt(),upload.fencingToken(),upload.sha256(),upload.content(),now);
        } catch(DuplicateKeyException ex) { throw new ApiException(HttpStatus.CONFLICT,"Artifact ID already belongs to another result"); }
    }

    public void require(PlatformTaskService.Task task, String sha256) {
        if(sha256==null || jdbc.queryForObject("SELECT COUNT(*) FROM platform_task_artifact WHERE task_id=? AND attempt=? AND fencing_token=? AND sha256=?",
                Integer.class,task.id(),task.attempt(),task.fencingToken(),sha256)!=1)
            throw new ApiException(HttpStatus.CONFLICT,"Successful result has no verified artifact");
    }

    /** Share creation needs a successful, verified artifact but not its full content. */
    public void requireShareable(String actor, String projectId, String taskId) {
        var task = tasks.get(actor, projectId, taskId);
        if (task.state() != TaskState.SUCCEEDED || task.resultSha256() == null)
            throw new ApiException(HttpStatus.CONFLICT, "Task has no shareable successful result");
        require(task, task.resultSha256());
    }

    public Artifact result(String actor, String projectId, String taskId) {
        var task=tasks.get(actor,projectId,taskId);
        if(task.state()!=TaskState.SUCCEEDED || task.resultSha256()==null)
            throw new ApiException(HttpStatus.CONFLICT,"Task has no successful result");
        var rows=jdbc.query("SELECT artifact_id,task_id,attempt,fencing_token,sha256,content,created_at FROM platform_task_artifact WHERE task_id=? AND attempt=? AND fencing_token=? AND sha256=?",
                (rs,n)->artifact(rs),task.id(),task.attempt(),task.fencingToken(),task.resultSha256());
        if(rows.size()!=1 || !PlatformTaskService.hash(rows.getFirst().content()).equals(task.resultSha256()))
            throw new ApiException(HttpStatus.CONFLICT,"Result artifact integrity check failed");
        return rows.getFirst();
    }
    private static Artifact artifact(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new Artifact(rs.getString(1),rs.getString(2),rs.getInt(3),rs.getLong(4),rs.getString(5),rs.getString(6),rs.getTimestamp(7).toInstant());
    }
}
