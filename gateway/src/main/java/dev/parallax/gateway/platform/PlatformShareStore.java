package dev.parallax.gateway.platform;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * Inserts share links in their own transaction so a token-hash collision can be
 * retried without poisoning the caller's transaction (PostgreSQL aborts a
 * transaction after a unique-key violation).
 */
@Component
public class PlatformShareStore {

    public record NewShare(String id, String projectId, String taskId, String tokenHash,
                           String createdBy, Instant createdAt, Instant expiresAt, Integer maxAccesses) { }

    private final JdbcTemplate jdbc;

    public PlatformShareStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public boolean insert(NewShare share) {
        try {
            jdbc.update("INSERT INTO platform_share_link "
                            + "(id,project_id,task_id,token_hash,created_by,created_at,expires_at,max_accesses,access_count) "
                            + "VALUES (?,?,?,?,?,?,?,?,0)",
                    share.id(), share.projectId(), share.taskId(), share.tokenHash(), share.createdBy(),
                    Timestamp.from(share.createdAt()), Timestamp.from(share.expiresAt()), share.maxAccesses());
            jdbc.update("INSERT INTO platform_access_audit (id, actor, action, resource_id, at) VALUES (?,?,?,?,?)",
                    UUID.randomUUID().toString(), share.createdBy(), "SHARE_CREATED", share.id(),
                    Timestamp.from(share.createdAt()));
            return true;
        } catch (DuplicateKeyException ex) {
            return false;
        }
    }
}
