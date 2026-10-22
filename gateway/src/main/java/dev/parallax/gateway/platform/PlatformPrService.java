package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Signed GitHub pull-request ingress bound to an explicit project repository.
 *
 * A webhook is never allowed to name its own clone URL or policy. The repository
 * id in the payload must resolve to a registered link, the payload clone URL must
 * match the registered repository, and the task always uses the latest immutable
 * policy for that project. The delivery id provides task-level idempotency.
 */
@Service
public class PlatformPrService {

    /** Disabled account created by V10; it cannot log in and only submits bound webhook tasks. */
    public static final String SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001";
    private static final String GITHUB = "GITHUB";
    private static final String GITLAB = "GITLAB";
    private static final Set<String> GITHUB_ACTIONS = Set.of("opened", "reopened", "synchronize");
    /** GitLab 的 MR 事件用 open/reopen/update，语义与 GitHub 对应。 */
    private static final Set<String> GITLAB_ACTIONS = Set.of("open", "reopen", "update");

    public record LinkRequest(String provider, String externalId, Long tokenBudget) { }
    public record Link(String id, String projectId, String repositoryId, String provider,
                       String externalId, long tokenBudget, String createdBy, Instant createdAt) { }
    public record DeliveryResult(boolean accepted, String reason, String taskId, String status,
                                 String commitSha) { }

    private record Linked(String id, String projectId, String organizationId, String repositoryId,
                          String provider, String externalId, long tokenBudget) { }
    private record PriorDelivery(String taskId, String payloadSha256) { }

    private final JdbcTemplate jdbc;
    private final PlatformIdentityService identity;
    private final PlatformCatalogService catalog;
    private final PlatformTaskService tasks;
    private final ObjectMapper mapper;
    private final ParallaxProperties properties;

    public PlatformPrService(JdbcTemplate jdbc, PlatformIdentityService identity,
            PlatformCatalogService catalog, PlatformTaskService tasks, ObjectMapper mapper,
            ParallaxProperties properties) {
        this.jdbc = jdbc;
        this.identity = identity;
        this.catalog = catalog;
        this.tasks = tasks;
        this.mapper = mapper;
        this.properties = properties;
    }

    @Transactional
    public Link link(String actor, String projectId, String repositoryId, LinkRequest request) {
        var project = identity.project(actor, projectId, ProjectRole.MAINTAINER);
        catalog.repository(actor, projectId, repositoryId);
        if (request == null || request.provider() == null) throw ApiException.badRequest("Provider is required");
        String provider = request.provider().strip().toUpperCase(Locale.ROOT);
        if (!GITHUB.equals(provider) && !GITLAB.equals(provider)) {
            throw ApiException.badRequest("Only GitHub or GitLab repository links are supported");
        }
        String externalId = request.externalId() == null ? "" : request.externalId().strip();
        if (!externalId.matches("[0-9]{1,120}")) {
            throw ApiException.badRequest("Repository id must be numeric");
        }
        var policy = catalog.latestPolicyForAutomation(projectId);
        long maximum = policy.config().maxTokenBudget();
        long budget = request.tokenBudget() == null ? maximum : request.tokenBudget();
        if (budget < 1 || budget > maximum) {
            throw ApiException.badRequest("Token budget exceeds the latest policy");
        }
        identity.ensureWebhookReviewer(project.organizationId(), SYSTEM_USER_ID);
        String id = UUID.randomUUID().toString();
        Instant now = Instant.now();
        try {
            jdbc.update("INSERT INTO platform_repository_link "
                            + "(id,project_id,repository_id,provider,external_id,token_budget,created_by,created_at) "
                            + "VALUES (?,?,?,?,?,?,?,?)",
                    id, projectId, repositoryId, provider, externalId, budget, actor, Timestamp.from(now));
        } catch (DuplicateKeyException ex) {
            throw new ApiException(HttpStatus.CONFLICT, "Repository or external id is already linked");
        }
        identity.audit(actor, "REPOSITORY_LINKED", id);
        return new Link(id, projectId, repositoryId, provider, externalId, budget, actor, now);
    }

    public CursorPage<Link> links(String actor, String projectId, String repositoryId, String after, int limit) {
        identity.project(actor, projectId, ProjectRole.VIEWER);
        CursorPage.validate(after, limit);
        var rows = jdbc.query("SELECT id,project_id,repository_id,provider,external_id,token_budget,created_by,created_at "
                        + "FROM platform_repository_link WHERE project_id=? AND repository_id=? AND id>? ORDER BY id LIMIT ?",
                (rs, n) -> link(rs), projectId, repositoryId, after, limit + 1);
        return CursorPage.of(rows, limit, Link::id);
    }

    @Transactional
    public DeliveryResult githubWebhook(String signature, String event, String deliveryId, String body) {
        String secret = properties.getWebhooks().getGithubSecret();
        if (secret == null || secret.isBlank()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "GitHub webhook is not enabled");
        }
        requireBody(body);
        if (!validSignature(secret, body, signature)) {
            throw ApiException.unauthorized("Webhook signature is invalid");
        }
        if (!"pull_request".equals(event)) {
            return new DeliveryResult(false, "event type does not trigger review", null, null, null);
        }
        requireDeliveryId(deliveryId, "X-GitHub-Delivery");
        JsonNode payload = parse(body);
        String action = payload.path("action").asText("");
        if (!GITHUB_ACTIONS.contains(action)) {
            return new DeliveryResult(false, "pull request action does not trigger review", null, null, null);
        }
        JsonNode repository = payload.path("repository");
        JsonNode pull = payload.path("pull_request");
        return accept(GITHUB, deliveryId, repository.path("id").asText(""), repository.path("clone_url").asText(""),
                pull.path("number").asInt(0), pull.path("head").path("sha").asText(""),
                PlatformTaskService.hash(body), "GITHUB_PR_TASK_CREATED", "gh-",
                "GitHub repository is not linked to a Parallax project");
    }

    /**
     * GitLab merge-request ingress. GitLab authenticates with a shared token header instead of an
     * HMAC body signature, so the token is compared in constant time before the payload is read.
     */
    @Transactional
    public DeliveryResult gitlabWebhook(String token, String event, String deliveryId, String body) {
        String secret = properties.getWebhooks().getGitlabSecret();
        if (secret == null || secret.isBlank()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "GitLab webhook is not enabled");
        }
        requireBody(body);
        if (token == null || !constantTimeEquals(secret, token)) {
            throw ApiException.unauthorized("Webhook token is invalid");
        }
        if (!"Merge Request Hook".equals(event)) {
            return new DeliveryResult(false, "event type does not trigger review", null, null, null);
        }
        requireDeliveryId(deliveryId, "X-Gitlab-Event-UUID");
        JsonNode payload = parse(body);
        if (!"merge_request".equals(payload.path("object_kind").asText(""))) {
            return new DeliveryResult(false, "object kind does not trigger review", null, null, null);
        }
        JsonNode attributes = payload.path("object_attributes");
        String action = attributes.path("action").asText("");
        if (!GITLAB_ACTIONS.contains(action)) {
            return new DeliveryResult(false, "merge request action does not trigger review", null, null, null);
        }
        JsonNode project = payload.path("project");
        return accept(GITLAB, deliveryId, project.path("id").asText(""), project.path("git_http_url").asText(""),
                attributes.path("iid").asInt(0), attributes.path("last_commit").path("id").asText(""),
                PlatformTaskService.hash(body), "GITLAB_MR_TASK_CREATED", "gl-",
                "GitLab project is not linked to a Parallax project");
    }

    /** Shared acceptance path: both providers only differ in authentication and payload naming. */
    private DeliveryResult accept(String provider, String deliveryId, String externalId, String cloneUrl,
                                  int pullRequestNumber, String headSha, String bodyDigest, String auditAction,
                                  String requestKeyPrefix, String notLinkedMessage) {
        if (!externalId.matches("[0-9]{1,120}")) {
            throw ApiException.badRequest("Webhook is missing a numeric repository id");
        }
        if (pullRequestNumber < 1) {
            throw ApiException.badRequest("Webhook is missing a pull-request number");
        }
        if (!headSha.matches("[0-9a-fA-F]{40}|[0-9a-fA-F]{64}")) {
            throw ApiException.badRequest("Webhook must contain a fixed pull-request head commit");
        }
        String normalizedHead = headSha.toLowerCase(Locale.ROOT);

        var links = jdbc.query("SELECT l.id,l.project_id,p.organization_id,l.repository_id,l.provider,l.external_id,l.token_budget "
                        + "FROM platform_repository_link l JOIN platform_project p ON p.id=l.project_id "
                        + "WHERE l.provider=? AND l.external_id=?",
                (rs, n) -> new Linked(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getLong(7)), provider, externalId);
        Linked link = links.stream().findFirst().orElseThrow(() ->
                new ApiException(HttpStatus.NOT_FOUND, notLinkedMessage));

        String registered = jdbc.queryForObject(
                "SELECT clone_url FROM platform_repository WHERE project_id=? AND id=?",
                String.class, link.projectId(), link.repositoryId());
        if (!normalizeClone(registered).equals(normalizeClone(cloneUrl))) {
            throw new ApiException(HttpStatus.CONFLICT, "Webhook repository does not match the linked repository");
        }

        identity.ensureWebhookReviewer(link.organizationId(), SYSTEM_USER_ID);
        String digest = bodyDigest;
        var prior = jdbc.query("SELECT task_id,payload_sha256 FROM platform_webhook_delivery "
                        + "WHERE provider=? AND delivery_id=? ORDER BY received_at DESC LIMIT 1",
                (rs, n) -> new PriorDelivery(rs.getString(1), rs.getString(2)), provider, deliveryId);
        if (!prior.isEmpty()) {
            PriorDelivery previous = prior.getFirst();
            if (!previous.payloadSha256().equals(digest)) {
                throw new ApiException(HttpStatus.CONFLICT, "Delivery id was reused with different content");
            }
            var task = tasks.get(SYSTEM_USER_ID, link.projectId(), previous.taskId());
            return new DeliveryResult(true, "duplicate delivery", task.id(), task.state().name(), task.commitSha());
        }

        var policy = catalog.latestPolicyForAutomation(link.projectId());
        if (link.tokenBudget() > policy.config().maxTokenBudget()) {
            throw new ApiException(HttpStatus.CONFLICT, "Linked token budget exceeds the current policy");
        }
        var task = tasks.submit(SYSTEM_USER_ID, link.projectId(), requestKeyPrefix + deliveryId,
                new PlatformTaskService.Submission(link.repositoryId(), policy.id(), normalizedHead, link.tokenBudget()));
        jdbc.update("INSERT INTO platform_webhook_delivery "
                        + "(id,provider,delivery_id,payload_sha256,project_id,repository_id,pull_request_number,task_id,received_at) "
                        + "VALUES (?,?,?,?,?,?,?,?,?)",
                UUID.randomUUID().toString(), provider, deliveryId, digest, link.projectId(),
                link.repositoryId(), pullRequestNumber, task.id(), Timestamp.from(Instant.now()));
        identity.audit(SYSTEM_USER_ID, auditAction, task.id());
        return new DeliveryResult(true, "accepted", task.id(), task.state().name(), task.commitSha());
    }

    private void requireBody(String body) {
        if (body == null || body.getBytes(StandardCharsets.UTF_8).length > properties.getWebhooks().getMaxBodyBytes()) {
            throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "Webhook body is missing or too large");
        }
    }

    private static void requireDeliveryId(String deliveryId, String header) {
        if (deliveryId == null || !deliveryId.matches("[A-Za-z0-9_-]{1,64}")) {
            throw ApiException.badRequest("A valid " + header + " header is required");
        }
    }

    private static boolean constantTimeEquals(String expected, String provided) {
        return MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),
                provided.getBytes(StandardCharsets.UTF_8));
    }

    private JsonNode parse(String body) {
        try {
            return mapper.readTree(body);
        } catch (JsonProcessingException ex) {
            throw ApiException.badRequest("Webhook payload is not valid JSON");
        }
    }

    private static boolean validSignature(String secret, String body, String signature) {
        if (signature == null || !signature.startsWith("sha256=")) return false;
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] expected = mac.doFinal(body.getBytes(StandardCharsets.UTF_8));
            byte[] supplied = HexFormat.of().parseHex(signature.substring("sha256=".length()));
            return MessageDigest.isEqual(expected, supplied);
        } catch (Exception ex) {
            return false;
        }
    }

    private static String normalizeClone(String value) {
        String normalized = value == null ? "" : value.strip().toLowerCase(Locale.ROOT);
        if (normalized.endsWith(".git")) normalized = normalized.substring(0, normalized.length() - 4);
        if (normalized.endsWith("/")) normalized = normalized.substring(0, normalized.length() - 1);
        return normalized;
    }

    private static Link link(ResultSet rs) throws SQLException {
        return new Link(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                rs.getString(5), rs.getLong(6), rs.getString(7), rs.getTimestamp(8).toInstant());
    }
}
