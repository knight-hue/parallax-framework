package dev.parallax.gateway.platform;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Appends participate in the caller's task transaction. No independent commit or in-memory bus. */
@Component
public class PlatformEventStore {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    public PlatformEventStore(JdbcTemplate jdbc,ObjectMapper mapper) { this.jdbc=jdbc;this.mapper=mapper; }
    void system(PlatformTaskService.Task task,String kind,Object detail,Instant at) {
        try { insert(UUID.randomUUID().toString(),task,null,kind,mapper.writeValueAsString(detail),at); }
        catch(com.fasterxml.jackson.core.JsonProcessingException ex) { throw new IllegalStateException(ex); }
    }
    void insert(String id,PlatformTaskService.Task task,Long sequence,String kind,String payload,Instant now) {
        jdbc.update("INSERT INTO platform_task_event (event_id,task_id,attempt,fencing_token,sequence_number,kind,payload,payload_sha256,received_at) VALUES (?,?,?,?,?,?,?,?,?)",
                id,task.id(),task.attempt(),task.fencingToken(),sequence,kind,payload,PlatformTaskService.hash(payload),Timestamp.from(now));
    }
}
