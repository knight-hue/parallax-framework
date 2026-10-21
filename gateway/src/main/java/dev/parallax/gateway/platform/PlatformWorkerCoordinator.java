package dev.parallax.gateway.platform;

import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.task.TaskState;
import dev.parallax.gateway.task.WorkerEvent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** DB authority for worker leases, inbox, ordered events and exactly-once budget settlement. */
@Service
public class PlatformWorkerCoordinator {
    public record Acknowledgement(boolean accepted, boolean cancelRequested, PlatformTaskService.Task task) { }
    public record Event(long id, String kind, JsonNode payload, Instant receivedAt) { }
    public record Events(List<Event> items, Long nextCursor) { }
    private final JdbcTemplate jdbc;
    private final PlatformTaskService tasks;
    private final ObjectMapper mapper;
    private final Clock clock;
    private final int leaseSeconds;
    private final int maxAttempts;
    private final PlatformEventStore store;
    private final PlatformArtifactService artifacts;

    public PlatformWorkerCoordinator(JdbcTemplate jdbc, PlatformTaskService tasks, ObjectMapper mapper, Clock clock, PlatformEventStore store, PlatformArtifactService artifacts,
            @Value("${parallax.worker.lease-seconds:120}") int leaseSeconds,
            @Value("${parallax.worker.max-attempts:3}") int maxAttempts) {
        if(leaseSeconds<10 || leaseSeconds>3600 || maxAttempts<1 || maxAttempts>10) throw new IllegalArgumentException("Invalid worker lease/retry configuration");
        this.jdbc=jdbc;this.tasks=tasks;this.mapper=mapper;this.clock=clock;this.store=store;this.artifacts=artifacts;this.leaseSeconds=leaseSeconds;this.maxAttempts=maxAttempts;
    }

    @Transactional(isolation=org.springframework.transaction.annotation.Isolation.READ_COMMITTED)
    public Acknowledgement receive(WorkerEvent event) {
        var visible=tasks.current(event.taskId(),false);
        tasks.lockBudget(visible.organizationId());
        var task=tasks.current(event.taskId(),true);
        String payload=tasks.json(event), digest=PlatformTaskService.hash(payload);
        // The task lock serializes its duplicates. READ COMMITTED sees that prior commit
        // without locking an absent unique-key gap across unrelated organizations.
        var prior=jdbc.queryForList("SELECT payload_sha256 FROM platform_task_event WHERE event_id=?",String.class,event.eventId());
        if(!prior.isEmpty()) {
            if(!prior.getFirst().equals(digest)) throw conflict("Event ID was reused with different data");
            return ack(false,task);
        }
        try { event.requireCurrent(task.dispatch()); }
        catch(IllegalStateException ex) { throw conflict("Stale worker attempt or fencing token"); }
        Instant now=clock.instant();
        if(task.state().terminal()) throw conflict("Task is terminal");
        if(!task.deadline().isAfter(now) || task.leaseUntil()==null || !task.leaseUntil().isAfter(now)) throw conflict("Worker lease or deadline expired");
        if(event.occurredAt().isAfter(now.plusSeconds(60))) throw ApiException.badRequest("Worker clock is too far in the future");
        if(event.sequence()!=task.lastSequence()+1) throw conflict("Worker event sequence is not contiguous");
        long total=Math.addExact(event.promptTokens(),event.completionTokens());
        if(event.promptTokens()<task.promptTokens() || event.completionTokens()<task.completionTokens() || total>task.tokenBudget()) {
            throw ApiException.badRequest("Usage must be cumulative, monotonic and within the reservation");
        }
        if(task.lastSequence()==0 && event.kind()!=WorkerEvent.Kind.STARTED) {
            if((event.kind()!=WorkerEvent.Kind.FAILED && event.kind()!=WorkerEvent.Kind.CANCELED) || total!=0) {
                throw conflict("A worker must claim STARTED before progress, success or spending");
            }
        }
        TaskState next=switch(event.kind()) {
            case STARTED -> {
                if(task.state()!=TaskState.DISPATCHED || total!=0) throw conflict("STARTED must claim a dispatched task before spending");
                yield TaskState.RUNNING;
            }
            case PROGRESS -> {
                if(task.state()!=TaskState.RUNNING && task.state()!=TaskState.CANCEL_REQUESTED) throw conflict("Task is not running");
                yield task.state();
            }
            case SUCCEEDED -> {
                if(task.state()!=TaskState.RUNNING && task.state()!=TaskState.CANCEL_REQUESTED) throw conflict("Task was not started");
                artifacts.require(task,event.resultSha256());
                yield TaskState.SUCCEEDED;
            }
            case FAILED -> {
                if(task.state()==TaskState.DISPATCHED && total!=0) throw conflict("Unclaimed work cannot report spending");
                yield TaskState.FAILED;
            }
            case CANCELED -> {
                if(task.state()!=TaskState.CANCEL_REQUESTED) throw conflict("Cancellation was not requested");
                yield TaskState.CANCELED;
            }
        };
        task.state().transitionTo(next);
        Instant lease=task.state()==TaskState.CANCEL_REQUESTED ? task.leaseUntil() : lease(now,task.deadline());
        jdbc.update("UPDATE platform_task SET state=?,last_sequence=?,prompt_tokens=?,completion_tokens=?,result_sha256=?,lease_until=?,updated_at=? WHERE id=?",
                next.name(),event.sequence(),event.promptTokens(),event.completionTokens(),event.resultSha256(),next.terminal()?null:Timestamp.from(lease),Timestamp.from(now),task.id());
        insertEvent(event.eventId(),task,event.sequence(),event.kind().name(),payload,now);
        if(next.terminal()) {
            tasks.settle(task,total);
            supersede(task.id());
        }
        return ack(true,tasks.current(task.id(),true));
    }

    /** Called by the outbox publisher before any broker I/O. Worker STARTED is the execution grant. */
    @Transactional
    public boolean prepareDispatch(String taskId, int attempt, long fencingToken) {
        var visible=tasks.current(taskId,false);tasks.lockBudget(visible.organizationId());
        var task=tasks.current(taskId,true);
        if(task.attempt()!=attempt || task.fencingToken()!=fencingToken || task.state().terminal() || !task.deadline().isAfter(clock.instant())) return false;
        if(task.state()==TaskState.DISPATCHED) return task.leaseUntil()!=null && task.leaseUntil().isAfter(clock.instant());
        if(task.state()!=TaskState.QUEUED) return false;
        Instant now=clock.instant();
        jdbc.update("UPDATE platform_task SET state='DISPATCHED',lease_until=?,updated_at=? WHERE id=?",Timestamp.from(lease(now,task.deadline())),Timestamp.from(now),task.id());
        systemEvent(task,"DISPATCHED",Map.of("attempt",attempt,"fencing_token",fencingToken),now);
        return true;
    }

    /** Recovery is conservative: only work without an accepted STARTED can be retried for free. */
    @Transactional
    public boolean recover(String taskId) {
        var visible=tasks.current(taskId,false);tasks.lockBudget(visible.organizationId());
        var task=tasks.current(taskId,true);
        if(task.state().terminal()) return false;
        Instant now=clock.instant();
        boolean expired=!task.deadline().isAfter(now);
        boolean lost=task.leaseUntil()!=null && !task.leaseUntil().isAfter(now);
        if(!expired && !lost) return false;
        if(!expired && task.state()==TaskState.DISPATCHED && task.attempt()<maxAttempts) {
            supersede(task.id());
            jdbc.update("UPDATE platform_task SET state='QUEUED',attempt=attempt+1,fencing_token=fencing_token+1,last_sequence=0,lease_until=NULL,recovery_reason='UNCLAIMED_DISPATCH_RETRY',updated_at=? WHERE id=?",Timestamp.from(now),task.id());
            var retry=tasks.current(task.id(),true);
            tasks.outbox(task.id(),retry.attempt(),"DISPATCH",tasks.json(retry.dispatch()));
            systemEvent(retry,"REQUEUED",Map.of("reason","UNCLAIMED_DISPATCH_RETRY"),now);
            return true;
        }
        boolean unclaimed=task.state()==TaskState.QUEUED || task.state()==TaskState.DISPATCHED
                || (task.state()==TaskState.CANCEL_REQUESTED && task.lastSequence()==0);
        TaskState terminal=task.state()==TaskState.QUEUED?TaskState.CANCELED:TaskState.FAILED;
        String reason=unclaimed?(expired?"DEADLINE_BEFORE_START":"DISPATCH_ATTEMPTS_EXHAUSTED"):"WORKER_LOST_USAGE_UNCERTAIN";
        jdbc.update("UPDATE platform_task SET state=?,fencing_token=fencing_token+1,lease_until=NULL,recovery_reason=?,updated_at=? WHERE id=?",terminal.name(),reason,Timestamp.from(now),task.id());
        tasks.settle(task,unclaimed?0:task.tokenBudget());
        supersede(task.id());
        systemEvent(tasks.current(task.id(),true),"RECOVERED_TERMINAL",Map.of("reason",reason,"charged_tokens",unclaimed?0:task.tokenBudget()),now);
        return true;
    }

    public List<String> recoveryCandidates(int limit) {
        if(limit<1 || limit>100) throw new IllegalArgumentException("Recovery batch must be 1..100");
        Timestamp now=Timestamp.from(clock.instant());
        return jdbc.queryForList("SELECT id FROM platform_task WHERE state IN ('QUEUED','DISPATCHED','RUNNING','CANCEL_REQUESTED') AND (deadline<=? OR lease_until<=?) ORDER BY id LIMIT ?",String.class,now,now,limit);
    }

    public Events events(String actor,String projectId,String taskId,long after,int limit) {
        tasks.get(actor,projectId,taskId);
        if(after<0 || limit<1 || limit>100) throw ApiException.badRequest("Invalid event cursor or limit");
        var rows=jdbc.query("SELECT id,kind,payload,received_at FROM platform_task_event WHERE task_id=? AND id>? ORDER BY id LIMIT ?",
                (rs,n)->new Event(rs.getLong(1),rs.getString(2),parse(rs.getString(3)),rs.getTimestamp(4).toInstant()),taskId,after,limit+1);
        boolean more=rows.size()>limit;
        var items=List.copyOf(rows.subList(0,Math.min(rows.size(),limit)));
        return new Events(items,more?items.getLast().id:null);
    }

    void systemEvent(PlatformTaskService.Task task,String kind,Object detail,Instant now) {
        store.system(task,kind,detail,now);
    }
    private void insertEvent(String id,PlatformTaskService.Task task,Long sequence,String kind,String payload,Instant now) {
        try {
            store.insert(id,task,sequence,kind,payload,now);
        } catch(DuplicateKeyException ex) { throw conflict("Event ID or sequence already exists"); }
    }
    private void supersede(String id) {
        jdbc.update("UPDATE platform_outbox SET status='SUPERSEDED',claim_token=NULL,claim_until=NULL WHERE task_id=? AND status<>'PUBLISHED'",id);
    }
    private JsonNode parse(String json) {
        try { return mapper.readTree(json); }
        catch(com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException("Invalid stored event",ex); }
    }
    private Instant lease(Instant now,Instant deadline) { Instant end=now.plusSeconds(leaseSeconds);return end.isBefore(deadline)?end:deadline; }
    private static Acknowledgement ack(boolean accepted,PlatformTaskService.Task task) { return new Acknowledgement(accepted,task.state()==TaskState.CANCEL_REQUESTED,task); }
    private static ApiException conflict(String message) { return new ApiException(HttpStatus.CONFLICT,message); }
}
