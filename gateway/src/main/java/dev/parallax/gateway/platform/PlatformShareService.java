package dev.parallax.gateway.platform;

import java.security.SecureRandom;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.UUID;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.task.TaskState;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Secure, revocable share links for successful report artifacts.
 *
 * The raw token is returned only at creation. The database stores only its
 * SHA-256 hash, so a database read cannot reconstruct a working URL. Expiry,
 * revocation and optional maximum-use accounting are checked atomically on
 * every access; no cache is used, so revocation is immediate.
 */
@Service
public class PlatformShareService {

    public record CreateRequest(Integer expiresInSeconds, Integer maxAccesses) { }
    public record CreatedShare(String id, String token, String path, Instant createdAt,
                               Instant expiresAt, Integer maxAccesses) { }
    public record ShareView(String id, String projectId, String taskId, String createdBy,
                            Instant createdAt, Instant expiresAt, Instant revokedAt,
                            Integer maxAccesses, long accessCount, Instant lastAccessedAt) { }
    public record AccessResult(String content, String sha256) { }

    private record ShareRow(String id, String projectId, String taskId, String createdBy,
                            Instant createdAt, Instant expiresAt, Instant revokedAt,
                            Integer maxAccesses, long accessCount, Instant lastAccessedAt) { }

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int TOKEN_BYTES = 16;
    private static final String TOKEN_PATTERN = "[A-Za-z0-9_-]{22}";
    private static final int MAX_TOKEN_ATTEMPTS = 3;

    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final PlatformTaskService tasks;
    private final PlatformArtifactService artifacts;
    private final PlatformShareStore store;
    private final ParallaxProperties properties;
    private final PlatformMetrics metrics;

    public PlatformShareService(JdbcTemplate jdbc, PlatformIdentityService identity, PlatformTaskService tasks,
            PlatformArtifactService artifacts, PlatformShareStore store, ParallaxProperties properties,
            PlatformMetrics metrics) {
        this.jdbc = jdbc;
        this.identity = identity;
        this.tasks = tasks;
        this.artifacts = artifacts;
        this.store = store;
        this.properties = properties;
        this.metrics = metrics;
    }

    public CreatedShare create(String actor, String projectId, String taskId, CreateRequest request) {
        identity.project(actor, projectId, ProjectRole.REVIEWER);
        artifacts.requireShareable(actor, projectId, taskId);
        var share = properties.getShare();
        int expiresIn = request == null || request.expiresInSeconds() == null
                ? share.getDefaultExpirySeconds() : request.expiresInSeconds();
        if (expiresIn < 60 || expiresIn > share.getMaxExpirySeconds()) {
            throw ApiException.badRequest("Share expiry must be between 60 and "
                    + share.getMaxExpirySeconds() + " seconds");
        }
        Integer maxAccesses = request == null ? null : request.maxAccesses();
        if (maxAccesses != null && (maxAccesses < 1 || maxAccesses > share.getMaxAccesses())) {
            throw ApiException.badRequest("Share max accesses must be between 1 and "
                    + share.getMaxAccesses());
        }
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        Instant expiresAt = now.plusSeconds(expiresIn);
        for (int attempt = 0; attempt < MAX_TOKEN_ATTEMPTS; attempt++) {
            String token = newToken();
            String hash = PlatformTaskService.hash(token);
            String id = UUID.randomUUID().toString();
            if (store.insert(new PlatformShareStore.NewShare(id, projectId, taskId, hash, actor,
                    now, expiresAt, maxAccesses))) {
                metrics.shareAction("create");
                return new CreatedShare(id, token, "/api/v1/platform/shares/" + token,
                        now, expiresAt, maxAccesses);
            }
        }
        throw ApiException.serverError("Could not allocate a unique share token");
    }

    public CursorPage<ShareView> list(String actor, String projectId, String taskId,
            String after, int limit) {
        tasks.get(actor, projectId, taskId);
        CursorPage.validate(after, limit);
        var rows = jdbc.query("SELECT id,project_id,task_id,created_by,created_at,expires_at,"
                        + "revoked_at,max_accesses,access_count,last_accessed_at "
                        + "FROM platform_share_link WHERE project_id=? AND task_id=? AND id>? "
                        + "ORDER BY id LIMIT ?",
                (rs, n) -> view(rs), projectId, taskId, after, limit + 1);
        return CursorPage.of(rows, limit, ShareView::id);
    }

    @Transactional
    public ShareView revoke(String actor, String projectId, String taskId, String shareId) {
        var project = identity.project(actor, projectId, ProjectRole.VIEWER);
        var role = identity.requireRole(actor, project.organizationId(), ProjectRole.VIEWER);
        var rows = jdbc.query("SELECT id,project_id,task_id,created_by,created_at,expires_at,"
                        + "revoked_at,max_accesses,access_count,last_accessed_at "
                        + "FROM platform_share_link WHERE id=? AND project_id=? AND task_id=? FOR UPDATE",
                (rs, n) -> row(rs), shareId, projectId, taskId);
        if (rows.isEmpty()) throw unavailable();
        ShareRow share = rows.getFirst();
        if (!share.createdBy.equals(actor) && !role.permits(ProjectRole.MAINTAINER)) {
            metrics.shareAction("denied");
            throw new ApiException(HttpStatus.FORBIDDEN, "Only the creator or a maintainer can revoke this share");
        }
        if (share.revokedAt == null) {
            Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
            jdbc.update("UPDATE platform_share_link SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                    Timestamp.from(now), shareId);
            identity.audit(actor, "SHARE_REVOKED", shareId);
            metrics.shareAction("revoke");
            share = jdbc.queryForObject("SELECT id,project_id,task_id,created_by,created_at,expires_at,"
                            + "revoked_at,max_accesses,access_count,last_accessed_at "
                            + "FROM platform_share_link WHERE id=?",
                    (rs, n) -> row(rs), shareId);
        }
        return view(share);
    }

    @Transactional
    public AccessResult access(String token) {
        if (token == null || !token.matches(TOKEN_PATTERN)) {
            metrics.shareAction("denied");
            throw unavailable();
        }
        var rows = jdbc.query("SELECT id,project_id,task_id,created_by,created_at,expires_at,"
                        + "revoked_at,max_accesses,access_count,last_accessed_at "
                        + "FROM platform_share_link WHERE token_hash=?",
                (rs, n) -> row(rs), PlatformTaskService.hash(token));
        if (rows.isEmpty()) {
            metrics.shareAction("denied");
            throw unavailable();
        }
        ShareRow share = rows.getFirst();
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        int updated = jdbc.update("UPDATE platform_share_link SET access_count=access_count+1,"
                        + "last_accessed_at=? WHERE id=? AND revoked_at IS NULL AND expires_at>? "
                        + "AND (max_accesses IS NULL OR access_count<max_accesses)",
                Timestamp.from(now), share.id(), Timestamp.from(now));
        if (updated != 1) {
            metrics.shareAction("denied");
            throw unavailable();
        }
        var task = tasks.current(share.taskId(), false);
        if (task.state() != TaskState.SUCCEEDED || task.resultSha256() == null) {
            throw unavailable();
        }
        var artifacts = jdbc.query("SELECT content,sha256 FROM platform_task_artifact "
                        + "WHERE task_id=? AND attempt=? AND fencing_token=? AND sha256=?",
                (rs, n) -> new String[]{rs.getString(1), rs.getString(2)},
                task.id(), task.attempt(), task.fencingToken(), task.resultSha256());
        if (artifacts.isEmpty()) throw unavailable();
        String[] artifact = artifacts.getFirst();
        if (!PlatformTaskService.hash(artifact[0]).equals(artifact[1])) {
            throw ApiException.serverError("Shared artifact integrity check failed");
        }
        metrics.shareAction("access");
        return new AccessResult(artifact[0], artifact[1]);
    }

    private static String newToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static ShareView view(ResultSet rs) throws SQLException {
        return view(row(rs));
    }

    private static ShareView view(ShareRow row) {
        return new ShareView(row.id(), row.projectId(), row.taskId(), row.createdBy(),
                row.createdAt(), row.expiresAt(), row.revokedAt(), row.maxAccesses(),
                row.accessCount(), row.lastAccessedAt());
    }

    private static ShareRow row(ResultSet rs) throws SQLException {
        Timestamp revoked = rs.getTimestamp("revoked_at");
        Timestamp last = rs.getTimestamp("last_accessed_at");
        return new ShareRow(rs.getString("id"), rs.getString("project_id"), rs.getString("task_id"),
                rs.getString("created_by"), rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("expires_at").toInstant(), revoked == null ? null : revoked.toInstant(),
                rs.getObject("max_accesses", Integer.class), rs.getLong("access_count"),
                last == null ? null : last.toInstant());
    }

    private static ApiException unavailable() {
        // Deliberately indistinguishable across unknown, expired, revoked and exhausted tokens.
        return new ApiException(HttpStatus.NOT_FOUND, "Share link is unavailable");
    }
}
