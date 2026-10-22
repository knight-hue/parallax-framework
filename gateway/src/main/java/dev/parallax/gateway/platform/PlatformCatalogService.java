package dev.parallax.gateway.platform;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.common.ApiException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PlatformCatalogService {
    public record Repository(String id, String projectId, String name, String cloneUrl) { }
    public record PolicyConfig(int readers, int redundancy, int maxRounds, int minIndependentSupport,
                               boolean falsifierEnabled, long maxTokenBudget, int deadlineSeconds) {
        public void validate() {
            if (readers < 2 || readers > 16 || redundancy < 1 || redundancy > readers
                    || maxRounds < 1 || maxRounds > 8 || minIndependentSupport < 1 || minIndependentSupport > readers
                    || maxTokenBudget < 1 || maxTokenBudget > 10_000_000 || deadlineSeconds < 60 || deadlineSeconds > 86400) {
                throw ApiException.badRequest("Policy parameters exceed supported bounds");
            }
        }
    }
    public record Policy(String id, String projectId, int versionNumber, PolicyConfig config, String configSha256) { }
    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final ObjectMapper mapper;
    private final PlatformPolicyCache policyCache;
    private final Set<String> allowedHosts;

    public PlatformCatalogService(JdbcTemplate jdbc, PlatformIdentityService identity, ObjectMapper mapper,
            PlatformPolicyCache policyCache,
            @Value("${parallax.repositories.allowed-hosts:github.com,gitlab.com,gitee.com}") String allowedHosts) {
        this.jdbc = jdbc; this.identity = identity; this.mapper = mapper; this.policyCache = policyCache;
        this.allowedHosts = Arrays.stream(allowedHosts.split(",")).map(String::strip)
                .map(s -> s.toLowerCase(Locale.ROOT)).filter(s -> !s.isEmpty()).collect(Collectors.toUnmodifiableSet());
    }

    @Transactional
    public Repository register(String actor, String projectId, String name, String cloneUrl) {
        identity.project(actor, projectId, ProjectRole.MAINTAINER);
        if (name == null || name.isBlank() || name.length() > 120) throw ApiException.badRequest("Invalid repository name");
        String canonical = canonicalUrl(cloneUrl);
        String id = UUID.randomUUID().toString();
        try {
            jdbc.update("INSERT INTO platform_repository (id,project_id,name,clone_url,created_by,created_at) VALUES (?,?,?,?,?,?)",
                    id, projectId, name.strip(), canonical, actor, Timestamp.from(Instant.now()));
        } catch (DuplicateKeyException ex) { throw new ApiException(HttpStatus.CONFLICT, "Repository name already exists"); }
        identity.audit(actor, "REPOSITORY_REGISTERED", id);
        return new Repository(id, projectId, name.strip(), canonical);
    }

    public Repository repository(String actor, String projectId, String id) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        return jdbc.query("SELECT id,project_id,name,clone_url FROM platform_repository WHERE id=? AND project_id=?",
                (rs,n) -> repository(rs), id, projectId).stream().findFirst().orElseThrow(PlatformCatalogService::notFound);
    }

    public CursorPage<Repository> repositories(String actor, String projectId, String after, int limit) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        CursorPage.validate(after, limit);
        var rows = jdbc.query("SELECT id,project_id,name,clone_url FROM platform_repository WHERE project_id=? AND id>? ORDER BY id LIMIT ?",
                (rs,n) -> repository(rs), projectId, after, limit + 1);
        return CursorPage.of(rows, limit, Repository::id);
    }

    @Transactional
    public Policy publish(String actor, String projectId, PolicyConfig config) {
        identity.project(actor, projectId, ProjectRole.MAINTAINER);
        if (config == null) throw ApiException.badRequest("Policy config is required");
        config.validate();
        // Serialize publishers across instances. The unique key is an additional invariant.
        jdbc.queryForObject("SELECT id FROM platform_project WHERE id=? FOR UPDATE", String.class, projectId);
        // A locking read sees the newest committed row under MySQL REPEATABLE READ;
        // a plain MAX read could reuse the authorization query's older snapshot.
        var latest = jdbc.queryForList("SELECT version_number FROM platform_policy_version WHERE project_id=? ORDER BY version_number DESC LIMIT 1 FOR UPDATE", Integer.class, projectId);
        int version = Math.addExact(latest.isEmpty() ? 0 : latest.getFirst(), 1);
        String id = UUID.randomUUID().toString();
        String json = json(config), hash = digest(json);
        jdbc.update("INSERT INTO platform_policy_version (id,project_id,version_number,config_json,config_sha256,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                id, projectId, version, json, hash, actor, Timestamp.from(Instant.now()));
        identity.audit(actor, "POLICY_PUBLISHED", id);
        return new Policy(id, projectId, version, config, hash);
    }

    public Policy policy(String actor, String projectId, String id) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        return policyCache.get(projectId, id, () -> jdbc.query(
                "SELECT id,project_id,version_number,config_json,config_sha256 FROM platform_policy_version WHERE project_id=? AND id=?",
                (rs,n) -> policy(rs), projectId, id).stream().findFirst().orElseThrow(PlatformCatalogService::notFound));
    }

    /**
     * Latest immutable policy for a project-level automation binding.
     *
     * The caller must already have established the binding (for example a signed
     * repository webhook). This method intentionally does not accept an actor and
     * must not be exposed as a user-facing read endpoint.
     */
    Policy latestPolicyForAutomation(String projectId) {
        return jdbc.query(
                "SELECT id,project_id,version_number,config_json,config_sha256 FROM platform_policy_version WHERE project_id=? ORDER BY version_number DESC LIMIT 1",
                (rs,n) -> policy(rs), projectId).stream().findFirst().orElseThrow(PlatformCatalogService::notFound);
    }

    /** Only called after the internal worker boundary checks the authoritative task. */
    ExecutionPolicy executionPolicy(String projectId,String repositoryId,String policyId) {
        String url=jdbc.queryForList("SELECT clone_url FROM platform_repository WHERE project_id=? AND id=?",String.class,projectId,repositoryId)
                .stream().findFirst().orElseThrow(PlatformCatalogService::notFound);
        canonicalUrl(url);
        var rows=jdbc.query("SELECT id,project_id,version_number,config_json,config_sha256 FROM platform_policy_version WHERE project_id=? AND id=?",
                (rs,n)->{ var policy=policy(rs);policy.config().validate();return new ExecutionPolicy(url,rs.getString(4),policy.configSha256()); },projectId,policyId);
        return rows.stream().findFirst().orElseThrow(PlatformCatalogService::notFound);
    }
    record ExecutionPolicy(String cloneUrl,String policyJson,String policySha256) { }

    public CursorPage<Policy> policies(String actor, String projectId, String after, int limit) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        CursorPage.validate(after, limit);
        var rows = jdbc.query("SELECT id,project_id,version_number,config_json,config_sha256 FROM platform_policy_version WHERE project_id=? AND id>? ORDER BY id LIMIT ?",
                (rs,n) -> policy(rs), projectId, after, limit + 1);
        return CursorPage.of(rows, limit, Policy::id);
    }

    private String canonicalUrl(String input) {
        try {
            if (input == null || input.length() > 1024) throw new IllegalArgumentException();
            URI uri = URI.create(input);
            String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(Locale.ROOT);
            String path = uri.getRawPath();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || !allowedHosts.contains(host)
                    || uri.getRawUserInfo() != null || uri.getPort() != -1 || uri.getRawQuery() != null || uri.getRawFragment() != null
                    || path == null || !path.matches("/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")
                    || Arrays.stream(path.split("/")).anyMatch(p -> p.equals(".") || p.equals(".."))) throw new IllegalArgumentException();
            return "https://" + host + path;
        } catch (IllegalArgumentException ex) { throw ApiException.badRequest("Repository requires an approved HTTPS host and clean repository path"); }
    }

    private Repository repository(ResultSet rs) throws SQLException {
        return new Repository(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4));
    }
    private Policy policy(ResultSet rs) throws SQLException {
        String json = rs.getString(4), hash = rs.getString(5);
        if (!digest(json).equals(hash)) throw ApiException.serverError("Policy integrity check failed");
        try { return new Policy(rs.getString(1), rs.getString(2), rs.getInt(3), mapper.readValue(json, PolicyConfig.class), hash); }
        catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw ApiException.serverError("Stored policy is invalid"); }
    }
    private String json(PolicyConfig config) {
        try { return mapper.writeValueAsString(config); }
        catch (com.fasterxml.jackson.core.JsonProcessingException ex) { throw ApiException.serverError("Could not serialize policy"); }
    }
    private static String digest(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (java.security.NoSuchAlgorithmException ex) { throw new IllegalStateException(ex); }
    }
    private static ApiException notFound() { return new ApiException(HttpStatus.NOT_FOUND, "Resource not found"); }
}
