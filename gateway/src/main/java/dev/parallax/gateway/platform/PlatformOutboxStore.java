package dev.parallax.gateway.platform;

import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PlatformOutboxStore {
    public record Claim(String id,String taskId,int attempt,String kind,String payload,String claimToken,int publishAttempts) { }
    private final JdbcTemplate jdbc;
    private final Clock clock;
    public PlatformOutboxStore(JdbcTemplate jdbc,Clock clock) { this.jdbc=jdbc;this.clock=clock; }

    /** Only holds an outbox lock. No task/budget lock or broker I/O in this transaction. */
    // Avoid next-key gap locks on the mutable status index while competing claimers
    // skip locked rows. Each selected row still carries an exclusive record lock.
    @Transactional(isolation=org.springframework.transaction.annotation.Isolation.READ_COMMITTED)
    public Optional<Claim> claim() {
        Instant now=clock.instant();
        var rows=jdbc.query("SELECT id,task_id,attempt,kind,payload,publish_attempts FROM platform_outbox WHERE (status='PENDING' AND available_at<=?) OR (status='IN_FLIGHT' AND claim_until<=?) ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
                (rs,n)->new Claim(rs.getString(1),rs.getString(2),rs.getInt(3),rs.getString(4),rs.getString(5),UUID.randomUUID().toString(),Math.addExact(rs.getInt(6),1)),Timestamp.from(now),Timestamp.from(now));
        if(rows.isEmpty()) return Optional.empty();
        var claim=rows.getFirst();
        jdbc.update("UPDATE platform_outbox SET status='IN_FLIGHT',claim_token=?,claim_until=?,publish_attempts=? WHERE id=?",
                claim.claimToken,Timestamp.from(now.plusSeconds(30)),claim.publishAttempts,claim.id);
        return Optional.of(claim);
    }
    public boolean owned(Claim c) {
        return jdbc.queryForObject("SELECT COUNT(*) FROM platform_outbox WHERE id=? AND status='IN_FLIGHT' AND claim_token=? AND claim_until>?",Integer.class,c.id,c.claimToken,Timestamp.from(clock.instant()))==1;
    }
    @Transactional
    public boolean complete(Claim c,boolean published) {
        return jdbc.update("UPDATE platform_outbox SET status=?,published_at=?,claim_token=NULL,claim_until=NULL WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",
                published?"PUBLISHED":"SUPERSEDED",published?Timestamp.from(clock.instant()):null,c.id,c.claimToken)==1;
    }
    @Transactional
    public boolean retry(Claim c) {
        long delay=Math.min(60,1L<<Math.min(c.publishAttempts,6));
        return jdbc.update("UPDATE platform_outbox SET status='PENDING',available_at=?,claim_token=NULL,claim_until=NULL WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",
                Timestamp.from(clock.instant().plusSeconds(delay)),c.id,c.claimToken)==1;
    }
}
