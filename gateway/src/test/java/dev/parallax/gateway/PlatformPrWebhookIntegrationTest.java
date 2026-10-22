package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicLong;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.platform.PlatformCatalogService;
import dev.parallax.gateway.platform.PlatformIdentityService;
import dev.parallax.gateway.platform.PlatformPrService;
import dev.parallax.gateway.platform.PlatformTaskService;
import dev.parallax.gateway.platform.ProjectRole;
import dev.parallax.gateway.task.TaskState;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "parallax.gateway.require-auth=true",
        "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef",
        "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformPrWebhookIntegrationTest {

    private static final String WEBHOOK_SECRET = "test-github-webhook-secret";
    private static final AtomicLong EXTERNAL_IDS =
            new AtomicLong(10_000 + ThreadLocalRandom.current().nextInt(100_000));

    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformPrService pr;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    @Autowired ObjectMapper mapper;

    private record Fixture(String user, String org, String project, String repository, String policy, String externalId) { }

    private Fixture fixture() {
        var user = identity.provision("test", "pr-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "team");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://github.com/team/api");
        var policy = catalog.publish(user.id(), project.id(),
                new PlatformCatalogService.PolicyConfig(4, 2, 3, 2, true, 1000L, 3600));
        tasks.configureBudget("test-admin", org.id(), 1000);
        return new Fixture(user.id(), org.id(), project.id(), repository.id(), policy.id(),
                Long.toString(EXTERNAL_IDS.incrementAndGet()));
    }

    private String payload(String action, long repositoryId, String cloneUrl, String headSha) throws Exception {
        return mapper.writeValueAsString(Map.of(
                "action", action,
                "repository", Map.of("id", repositoryId, "clone_url", cloneUrl),
                "pull_request", Map.of("number", 42, "head", Map.of("sha", headSha))));
    }

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() { };

    private ResponseEntity<Map<String, Object>> webhook(String deliveryId, String event, String body, String signature)
            throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (event != null) headers.set("X-GitHub-Event", event);
        if (deliveryId != null) headers.set("X-GitHub-Delivery", deliveryId);
        if (signature != null) headers.set("X-Hub-Signature-256", signature);
        return rest.exchange("/api/v1/platform/webhooks/github", HttpMethod.POST,
                new HttpEntity<>(body, headers), MAP_TYPE);
    }

    private ResponseEntity<Map<String, Object>> signedWebhook(String deliveryId, String event, String body) throws Exception {
        return webhook(deliveryId, event, body, signature(body));
    }

    private static String signature(String body) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(WEBHOOK_SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return "sha256=" + HexFormat.of().formatHex(mac.doFinal(body.getBytes(StandardCharsets.UTF_8)));
    }

    private ResponseEntity<Map<String, Object>> linkRequest(String token, Fixture fixture, String externalId) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        headers.setContentType(MediaType.APPLICATION_JSON);
        return rest.exchange(
                "/api/v1/platform/projects/" + fixture.project + "/repositories/" + fixture.repository + "/links",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("provider", "GITHUB", "externalId", externalId, "tokenBudget", 100L), headers),
                MAP_TYPE);
    }

    @Test
    void signedWebhookCreatesTaskWithFixedCommitAndAudit() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITHUB", fixture.externalId, 100L));
        String head = "a".repeat(40);
        String delivery = UUID.randomUUID().toString();

        var response = signedWebhook(delivery, "pull_request",
                payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", head));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(response.getBody()).containsEntry("accepted", true);
        assertThat(response.getBody()).containsEntry("commitSha", head);
        String taskId = (String) response.getBody().get("taskId");
        var task = tasks.get(fixture.user, fixture.project, taskId);
        assertThat(task.commitSha()).isEqualTo(head);
        assertThat(task.repositoryId()).isEqualTo(fixture.repository);
        assertThat(task.policyVersion()).isEqualTo(fixture.policy);
        assertThat(task.createdBy()).isEqualTo(PlatformPrService.SYSTEM_USER_ID);
        assertThat(task.state()).isEqualTo(TaskState.QUEUED);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_webhook_delivery WHERE provider='GITHUB' AND delivery_id=?",
                Integer.class, delivery)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE action='GITHUB_PR_TASK_CREATED' AND resource_id=?",
                Integer.class, taskId)).isEqualTo(1);
    }

    @Test
    void duplicateDeliveryReturnsTheSameTaskWithoutConsumingBudgetTwice() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITHUB", fixture.externalId, 100L));
        String body = payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", "b".repeat(40));
        String delivery = UUID.randomUUID().toString();

        var first = signedWebhook(delivery, "pull_request", body);
        var second = signedWebhook(delivery, "pull_request", body);

        assertThat(first.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(second.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(second.getBody().get("taskId")).isEqualTo(first.getBody().get("taskId"));
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_task WHERE project_id=?",
                Integer.class, fixture.project)).isEqualTo(1);
        assertThat(tasks.budget(fixture.user, fixture.org).reservedTokens()).isEqualTo(100);
    }

    @Test
    void invalidSignatureAndUnlinkedRepositoryAreRejected() throws Exception {
        var fixture = fixture();
        String body = payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", "c".repeat(40));

        var invalid = webhook(UUID.randomUUID().toString(), "pull_request", body, "sha256=deadbeef");
        assertThat(invalid.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);

        var unlinked = signedWebhook(UUID.randomUUID().toString(), "pull_request", body);
        assertThat(unlinked.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_task WHERE project_id=?",
                Integer.class, fixture.project)).isZero();
    }

    @Test
    void cloneUrlMismatchAndReusedDeliveryWithDifferentContentAreRejected() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITHUB", fixture.externalId, 100L));
        String delivery = UUID.randomUUID().toString();

        var mismatch = signedWebhook(delivery, "pull_request",
                payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/other.git", "d".repeat(40)));
        assertThat(mismatch.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);

        var accepted = signedWebhook(delivery, "pull_request",
                payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", "e".repeat(40)));
        assertThat(accepted.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);

        var reused = signedWebhook(delivery, "pull_request",
                payload("opened", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", "f".repeat(40)));
        assertThat(reused.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void nonTriggeringActionIsIgnoredWithoutCreatingATask() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITHUB", fixture.externalId, 100L));

        var ignored = signedWebhook(UUID.randomUUID().toString(), "pull_request",
                payload("closed", Long.parseLong(fixture.externalId), "https://github.com/team/api.git", "1".repeat(40)));

        assertThat(ignored.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(ignored.getBody()).containsEntry("accepted", false);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_task WHERE project_id=?",
                Integer.class, fixture.project)).isZero();
    }

    @Test
    void linkRequiresMaintainerAndRejectsDuplicateBindings() {
        var fixture = fixture();
        var viewer = identity.provision("test", "viewer-" + UUID.randomUUID(), "test-password-123");
        identity.addMember(fixture.user, fixture.org, viewer.id(), ProjectRole.VIEWER);

        var forbidden = linkRequest(jwt.issueUserToken(viewer.id(), "viewer"), fixture, fixture.externalId);
        assertThat(forbidden.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);

        var owner = linkRequest(jwt.issueUserToken(fixture.user, "owner"), fixture, fixture.externalId);
        assertThat(owner.getStatusCode()).isEqualTo(HttpStatus.OK);

        var duplicate = linkRequest(jwt.issueUserToken(fixture.user, "owner"), fixture, fixture.externalId);
        assertThat(duplicate.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }
}
