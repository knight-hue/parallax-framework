package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicLong;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.platform.PlatformCatalogService;
import dev.parallax.gateway.platform.PlatformIdentityService;
import dev.parallax.gateway.platform.PlatformPrService;
import dev.parallax.gateway.platform.PlatformTaskService;
import dev.parallax.gateway.platform.ProjectRole;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "parallax.gateway.require-auth=true",
        "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef",
        "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformGitLabWebhookIntegrationTest {

    private static final String GITLAB_TOKEN = "test-gitlab-webhook-token";
    private static final AtomicLong EXTERNAL_IDS =
            new AtomicLong(500_000 + ThreadLocalRandom.current().nextInt(100_000));
    private static final ParameterizedTypeReference<java.util.Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() { };

    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformPrService pr;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    @Autowired ObjectMapper mapper;

    private record Fixture(String user, String project, String repository, String externalId) { }

    private Fixture fixture() {
        var user = identity.provision("test", "gl-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "team");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://gitlab.com/team/api");
        catalog.publish(user.id(), project.id(), new PlatformCatalogService.PolicyConfig(4, 2, 3, 2, true, 1000L, 3600));
        tasks.configureBudget("test-admin", org.id(), 1000);
        return new Fixture(user.id(), project.id(), repository.id(), Long.toString(EXTERNAL_IDS.incrementAndGet()));
    }

    private String payload(String action, long projectId, String cloneUrl, String headSha) throws Exception {
        return mapper.writeValueAsString(java.util.Map.of(
                "object_kind", "merge_request",
                "project", java.util.Map.of("id", projectId, "git_http_url", cloneUrl),
                "object_attributes", java.util.Map.of(
                        "iid", 7, "action", action, "last_commit", java.util.Map.of("id", headSha))));
    }

    private ResponseEntity<java.util.Map<String, Object>> webhook(String token, String event, String delivery, String body) {
        var headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (event != null) headers.set("X-Gitlab-Event", event);
        if (delivery != null) headers.set("X-Gitlab-Event-UUID", delivery);
        if (token != null) headers.set("X-Gitlab-Token", token);
        return rest.exchange("/api/v1/platform/webhooks/gitlab", HttpMethod.POST,
                new HttpEntity<>(body, headers), MAP_TYPE);
    }

    @Test
    void mergeRequestHookCreatesTaskAndIsIdempotent() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITLAB", fixture.externalId, 100L));
        String head = "b".repeat(40);
        String delivery = UUID.randomUUID().toString();
        String body = payload("open", Long.parseLong(fixture.externalId), "https://gitlab.com/team/api.git", head);

        var response = webhook(GITLAB_TOKEN, "Merge Request Hook", delivery, body);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(response.getBody()).containsEntry("accepted", true).containsEntry("commitSha", head);
        String taskId = (String) response.getBody().get("taskId");
        assertThat(tasks.get(fixture.user, fixture.project, taskId).commitSha()).isEqualTo(head);
        assertThat(jdbc.queryForObject(
                "SELECT COUNT(*) FROM platform_webhook_delivery WHERE provider='GITLAB' AND delivery_id=?",
                Integer.class, delivery)).isEqualTo(1);

        var replay = webhook(GITLAB_TOKEN, "Merge Request Hook", delivery, body);
        assertThat(replay.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(replay.getBody()).containsEntry("accepted", true).containsEntry("taskId", taskId);
        assertThat(replay.getBody()).containsEntry("reason", "duplicate delivery");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_task WHERE project_id=?",
                Integer.class, fixture.project)).isEqualTo(1);
    }

    @Test
    void wrongTokenIsRejectedAndOtherEventsAreIgnored() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITLAB", fixture.externalId, 100L));
        String body = payload("open", Long.parseLong(fixture.externalId), "https://gitlab.com/team/api.git", "c".repeat(40));

        assertThat(webhook("wrong-token", "Merge Request Hook", UUID.randomUUID().toString(), body).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(webhook(null, "Merge Request Hook", UUID.randomUUID().toString(), body).getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);

        var ignored = webhook(GITLAB_TOKEN, "Push Hook", UUID.randomUUID().toString(), body);
        assertThat(ignored.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(ignored.getBody()).containsEntry("accepted", false);
    }

    @Test
    void cloneUrlMustMatchTheLinkedRepository() throws Exception {
        var fixture = fixture();
        pr.link(fixture.user, fixture.project, fixture.repository,
                new PlatformPrService.LinkRequest("GITLAB", fixture.externalId, 100L));
        String body = payload("open", Long.parseLong(fixture.externalId), "https://gitlab.com/other/repo.git", "d".repeat(40));

        assertThat(webhook(GITLAB_TOKEN, "Merge Request Hook", UUID.randomUUID().toString(), body).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
    }
}
