package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HexFormat;
import java.util.UUID;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.common.TraceFilter;
import dev.parallax.gateway.task.TaskState;
import dev.parallax.gateway.task.WorkerTask;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Authoritative platform submissions. No network/model work is performed in a DB transaction. */
@Service
public class PlatformTaskService {
    public record Submission(String repositoryId, String policyVersion, String commitSha, long tokenBudget) { }
    public record Budget(String organizationId, long tokenLimit, long reservedTokens, long usedTokens) {
        @com.fasterxml.jackson.annotation.JsonProperty("availableTokens")
        public long availableTokens() { return tokenLimit-reservedTokens-usedTokens; }
    }
    public record Reconciliation(Budget account, long expectedReserved, long expectedUsed, long invalidLedgerTasks, boolean consistent) { }
    public record Task(String id, String organizationId, String projectId, String repositoryId, String policyVersion,
                       String createdBy, String commitSha, long tokenBudget, Instant deadline, TaskState state,
                       int attempt, long fencingToken, long lastSequence, long promptTokens, long completionTokens,
                       boolean settled, Instant leaseUntil, String resultSha256, Instant createdAt, String recoveryReason) {
        public WorkerTask dispatch() {
            return new WorkerTask(1,id,attempt,fencingToken,organizationId,projectId,repositoryId,commitSha,policyVersion,tokenBudget,deadline,null);
        }
    }
    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final PlatformCatalogService catalog;
    private final ObjectMapper mapper;
    private final PlatformEventStore events;
    private final PlatformMetrics metrics;

    public PlatformTaskService(JdbcTemplate jdbc, PlatformIdentityService identity, PlatformCatalogService catalog, ObjectMapper mapper, PlatformEventStore events, PlatformMetrics metrics) {
        this.jdbc=jdbc; this.identity=identity; this.catalog=catalog; this.mapper=mapper;this.events=events;this.metrics=metrics;
    }

    @Transactional
    public Budget configureBudget(String administrator, String organizationId, long limit) {
        if (limit < 0 || limit > 1_000_000_000_000L) throw ApiException.badRequest("Budget limit must be 0..1000000000000");
        var org=jdbc.queryForList("SELECT id FROM platform_organization WHERE id=? FOR UPDATE",String.class,organizationId);
        if(org.isEmpty()) throw notFound();
        var accounts=jdbc.query("SELECT organization_id,token_limit,reserved_tokens,used_tokens FROM platform_budget_account WHERE organization_id=? FOR UPDATE",
                (rs,n)->budget(rs),organizationId);
        if(accounts.isEmpty()) {
            jdbc.update("INSERT INTO platform_budget_account (organization_id,token_limit,reserved_tokens,used_tokens,updated_at) VALUES (?,?,0,0,?)",organizationId,limit,now());
        } else {
            Budget old=accounts.getFirst();
            if(limit < old.usedTokens+old.reservedTokens) throw conflict("Budget is below used and reserved tokens");
            jdbc.update("UPDATE platform_budget_account SET token_limit=?,updated_at=? WHERE organization_id=?",limit,now(),organizationId);
        }
        identity.audit(administrator,"BUDGET_CONFIGURED",organizationId);
        return new Budget(organizationId,limit,accounts.isEmpty()?0:accounts.getFirst().reservedTokens,accounts.isEmpty()?0:accounts.getFirst().usedTokens);
    }

    public Budget budget(String actor, String organizationId) {
        identity.requireRole(actor,organizationId,ProjectRole.VIEWER);
        return jdbc.query("SELECT organization_id,token_limit,reserved_tokens,used_tokens FROM platform_budget_account WHERE organization_id=?",
                (rs,n)->budget(rs),organizationId).stream().findFirst().orElse(new Budget(organizationId,0,0,0));
    }

    @Transactional
    public Reconciliation reconcile(String organizationId) {
        Budget account=lockBudget(organizationId);
        // All submission/settlement writes hold this account lock; this snapshot is stable.
        long reserved=jdbc.queryForObject("SELECT COALESCE(SUM(token_budget),0) FROM platform_task WHERE organization_id=? AND settled=FALSE",Long.class,organizationId);
        long used=jdbc.queryForObject("SELECT COALESCE(SUM(tokens),0) FROM platform_budget_ledger WHERE organization_id=? AND kind='SETTLE'",Long.class,organizationId);
        long invalid=jdbc.queryForObject("SELECT COUNT(*) FROM platform_task t WHERE t.organization_id=? AND (NOT EXISTS (SELECT 1 FROM platform_budget_ledger r WHERE r.task_id=t.id AND r.kind='RESERVE' AND r.tokens=t.token_budget AND r.organization_id=t.organization_id) OR (t.settled=TRUE AND NOT EXISTS (SELECT 1 FROM platform_budget_ledger s WHERE s.task_id=t.id AND s.kind='SETTLE' AND s.organization_id=t.organization_id AND s.tokens<=t.token_budget)) OR (t.settled=FALSE AND EXISTS (SELECT 1 FROM platform_budget_ledger s WHERE s.task_id=t.id AND s.kind='SETTLE')))",Long.class,organizationId);
        return new Reconciliation(account,reserved,used,invalid,account.reservedTokens==reserved && account.usedTokens==used && invalid==0);
    }

    @Transactional
    public Task submit(String actor, String projectId, String requestKey, Submission request) {
        var project=identity.project(actor,projectId,ProjectRole.REVIEWER);
        if(requestKey==null || !requestKey.matches("[A-Za-z0-9_-]{1,64}")) throw ApiException.badRequest("A valid Idempotency-Key is required");
        if(request==null || request.commitSha==null || !request.commitSha.matches("[0-9a-f]{40}|[0-9a-f]{64}")) throw ApiException.badRequest("A fixed full lowercase commit SHA is required");
        catalog.repository(actor,projectId,request.repositoryId);
        var policy=catalog.policy(actor,projectId,request.policyVersion);
        policy.config().validate();
        if(request.tokenBudget < 1 || request.tokenBudget > policy.config().maxTokenBudget()) throw ApiException.badRequest("Token budget exceeds policy");
        lockBudget(project.organizationId());
        String hash=hash(json(request));
        // Use a current read: authorization above may have opened an older RR snapshot.
        var existing=jdbc.query("SELECT * FROM platform_task WHERE project_id=? AND created_by=? AND request_key=? FOR UPDATE",
                (rs,n)->new Object[]{task(rs),rs.getString("request_sha256")},projectId,actor,requestKey);
        if(!existing.isEmpty()) {
            if(!hash.equals(existing.getFirst()[1])) throw conflict("Idempotency-Key was already used for different input");
            return (Task)existing.getFirst()[0];
        }
        int reserved=jdbc.update("UPDATE platform_budget_account SET reserved_tokens=reserved_tokens+?,updated_at=? WHERE organization_id=? AND token_limit-used_tokens-reserved_tokens>=?",
                request.tokenBudget,now(),project.organizationId(),request.tokenBudget);
        if(reserved!=1) throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,"Organization token budget exhausted");
        String id=UUID.randomUUID().toString();
        Instant created=Instant.now().truncatedTo(java.time.temporal.ChronoUnit.MICROS), deadline=created.plusSeconds(policy.config().deadlineSeconds());
        jdbc.update("INSERT INTO platform_task (id,organization_id,project_id,repository_id,policy_version,created_by,request_key,request_sha256,commit_sha,token_budget,deadline,state,attempt,fencing_token,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,'QUEUED',1,1,?,?)",
                id,project.organizationId(),projectId,request.repositoryId,request.policyVersion,actor,requestKey,hash,request.commitSha,request.tokenBudget,Timestamp.from(deadline),Timestamp.from(created),Timestamp.from(created));
        ledger(project.organizationId(),id,"RESERVE",request.tokenBudget);
        WorkerTask dispatch=new WorkerTask(1,id,1,1,project.organizationId(),projectId,request.repositoryId,request.commitSha,request.policyVersion,request.tokenBudget,deadline,TraceFilter.currentTraceId());
        outbox(id,1,"DISPATCH",json(dispatch));
        identity.audit(actor,"TASK_SUBMITTED",id);
        var task=current(id,false);
        events.system(task,"QUEUED",java.util.Map.of("state","QUEUED"),created);
        metrics.taskTransition(task.state().name());
        return task;
    }

    public Task get(String actor, String projectId, String id) {
        identity.project(actor,projectId,ProjectRole.VIEWER);
        Task task=current(id,false);
        if(!task.projectId.equals(projectId)) throw notFound();
        return task;
    }

    public CursorPage<Task> tasks(String actor, String projectId, String after, int limit) {
        identity.project(actor,projectId,ProjectRole.VIEWER);
        CursorPage.validate(after,limit);
        return CursorPage.of(jdbc.query("SELECT * FROM platform_task WHERE project_id=? AND id>? ORDER BY id LIMIT ?",
                (rs,n)->task(rs),projectId,after,limit+1),limit,Task::id);
    }

    @Transactional
    public Task cancel(String actor, String projectId, String id) {
        Task visible=get(actor,projectId,id);
        identity.project(actor,projectId,visible.createdBy.equals(actor)?ProjectRole.REVIEWER:ProjectRole.MAINTAINER);
        lockBudget(visible.organizationId);
        Task task=current(id,true);
        if(task.state.terminal()) return task;
        if(task.state==TaskState.CANCEL_REQUESTED) return task;
        if(task.state!=TaskState.QUEUED) {
            jdbc.update("UPDATE platform_task SET state='CANCEL_REQUESTED',updated_at=? WHERE id=?",now(),id);
            outbox(id,task.attempt,"CANCEL",json(task.dispatch()));
            identity.audit(actor,"TASK_CANCEL_REQUESTED",id);
            var canceled=current(id,true);
            events.system(canceled,"CANCEL_REQUESTED",java.util.Map.of("state","CANCEL_REQUESTED"),Instant.now());
            metrics.taskTransition(canceled.state().name());
            return canceled;
        }
        jdbc.update("UPDATE platform_task SET state='CANCELED',fencing_token=fencing_token+1,updated_at=? WHERE id=?",now(),id);
        settle(task,0);
        jdbc.update("UPDATE platform_outbox SET status='SUPERSEDED',claim_token=NULL,claim_until=NULL WHERE task_id=? AND status<>'PUBLISHED'",id);
        identity.audit(actor,"TASK_CANCELED",id);
        var canceled=current(id,true);
        events.system(canceled,"CANCELED",java.util.Map.of("state","CANCELED"),Instant.now());
        metrics.taskTransition(canceled.state().name());
        return canceled;
    }

    Budget lockBudget(String organizationId) {
        return jdbc.query("SELECT organization_id,token_limit,reserved_tokens,used_tokens FROM platform_budget_account WHERE organization_id=? FOR UPDATE",
                (rs,n)->budget(rs),organizationId).stream().findFirst().orElseThrow(()->new ApiException(HttpStatus.TOO_MANY_REQUESTS,"Organization token budget is not configured"));
    }

    Task current(String id, boolean lock) {
        return jdbc.query("SELECT * FROM platform_task WHERE id=?"+(lock?" FOR UPDATE":""),(rs,n)->task(rs),id)
                .stream().findFirst().orElseThrow(PlatformTaskService::notFound);
    }

    // Caller holds budget then task locks. Unique ledger keys make repeated settlement impossible.
    void settle(Task task, long used) {
        if(task.settled) return;
        if(used<0 || used>task.tokenBudget) throw new IllegalArgumentException("Settlement exceeds reservation");
        if(jdbc.update("UPDATE platform_task SET settled=TRUE WHERE id=? AND settled=FALSE",task.id)!=1) throw new IllegalStateException("Settlement race");
        if(jdbc.update("UPDATE platform_budget_account SET reserved_tokens=reserved_tokens-?,used_tokens=used_tokens+?,updated_at=? WHERE organization_id=? AND reserved_tokens>=?",
                task.tokenBudget,used,now(),task.organizationId,task.tokenBudget)!=1) throw new IllegalStateException("Reservation invariant violated");
        ledger(task.organizationId,task.id,"SETTLE",used);
    }

    void outbox(String taskId, int attempt, String kind, String payload) {
        jdbc.update("INSERT INTO platform_outbox (id,task_id,attempt,kind,payload,status,available_at,created_at) VALUES (?,?,?,?,?,'PENDING',?,?)",
                UUID.randomUUID().toString(),taskId,attempt,kind,payload,now(),now());
    }
    private void ledger(String org, String task, String kind, long tokens) {
        jdbc.update("INSERT INTO platform_budget_ledger (id,organization_id,task_id,kind,tokens,at) VALUES (?,?,?,?,?,?)",UUID.randomUUID().toString(),org,task,kind,tokens,now());
    }
    String json(Object value) {
        try { return mapper.writeValueAsString(value); }
        catch(com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException("JSON serialization failed",ex); }
    }
    static String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch(java.security.NoSuchAlgorithmException ex) { throw new IllegalStateException(ex); }
    }
    private static Budget budget(ResultSet rs) throws SQLException { return new Budget(rs.getString(1),rs.getLong(2),rs.getLong(3),rs.getLong(4)); }
    private static Task task(ResultSet rs) throws SQLException {
        Timestamp lease=rs.getTimestamp("lease_until");
        return new Task(rs.getString("id"),rs.getString("organization_id"),rs.getString("project_id"),rs.getString("repository_id"),rs.getString("policy_version"),rs.getString("created_by"),rs.getString("commit_sha"),rs.getLong("token_budget"),rs.getTimestamp("deadline").toInstant(),TaskState.valueOf(rs.getString("state")),rs.getInt("attempt"),rs.getLong("fencing_token"),rs.getLong("last_sequence"),rs.getLong("prompt_tokens"),rs.getLong("completion_tokens"),rs.getBoolean("settled"),lease==null?null:lease.toInstant(),rs.getString("result_sha256"),rs.getTimestamp("created_at").toInstant(),rs.getString("recovery_reason"));
    }
    private static Timestamp now() { return Timestamp.from(Instant.now()); }
    private static ApiException conflict(String message) { return new ApiException(HttpStatus.CONFLICT,message); }
    private static ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND,"Resource not found"); }
}
