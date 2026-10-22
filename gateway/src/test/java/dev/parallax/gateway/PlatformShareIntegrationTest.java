package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;

import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.platform.PlatformArtifactService;
import dev.parallax.gateway.platform.PlatformCatalogService;
import dev.parallax.gateway.platform.PlatformIdentityService;
import dev.parallax.gateway.platform.PlatformShareService;
import dev.parallax.gateway.platform.PlatformTaskService;
import dev.parallax.gateway.platform.ProjectRole;
import dev.parallax.gateway.task.WorkerEvent;

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
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "parallax.gateway.require-auth=true",
        "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef",
        "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformShareIntegrationTest {

    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired dev.parallax.gateway.platform.PlatformWorkerCoordinator coordinator;
    @Autowired PlatformArtifactService artifacts;
    @Autowired PlatformShareService shares;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;

    private record Fixture(String user, String org, String project, String task) { }

    private Fixture fixture(boolean succeed, String content) {
        var user = identity.provision("test", "share-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "team");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://github.com/team/api");
        var policy = catalog.publish(user.id(), project.id(),
                new PlatformCatalogService.PolicyConfig(4, 2, 3, 2, true, 1000L, 3600));
        tasks.configureBudget("test-admin", org.id(), 1000);
        var task = tasks.submit(user.id(), project.id(), "share-request",
                new PlatformTaskService.Submission(repository.id(), policy.id(), "a".repeat(40), 100));
        if (succeed) {
            assertThat(coordinator.prepareDispatch(task.id(), 1, 1)).isTrue();
            coordinator.receive(event(task, 1, WorkerEvent.Kind.STARTED, 0, 0, null));
            String sha = sha256(content);
            artifacts.put(new PlatformArtifactService.Upload(task.id(), task.attempt(), task.fencingToken(),
                    UUID.randomUUID().toString(), sha, content));
            coordinator.receive(event(task, 2, WorkerEvent.Kind.SUCCEEDED, 10, 5, sha));
        }
        return new Fixture(user.id(), org.id(), project.id(), task.id());
    }

    private WorkerEvent event(PlatformTaskService.Task task, long sequence, WorkerEvent.Kind kind,
            long prompt, long completion, String resultSha) {
        return new WorkerEvent(1, UUID.randomUUID().toString(), task.id(), task.attempt(),
                task.fencingToken(), sequence, kind, Instant.now(), resultSha, prompt, completion);
    }

    private HttpHeaders auth(String userId) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(jwt.issueUserToken(userId, "test"));
        headers.setContentType(MediaType.APPLICATION_JSON);
        return headers;
    }

    private String base(Fixture fixture) {
        return "/api/v1/platform/projects/" + fixture.project + "/tasks/" + fixture.task;
    }

    private static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private ResponseEntity<Map> createShare(String userId, Fixture fixture, int expiresIn, Integer maxAccesses) {
        Map<String, Object> body = new HashMap<>();
        body.put("expiresInSeconds", expiresIn);
        if (maxAccesses != null) body.put("maxAccesses", maxAccesses);
        return rest.exchange(base(fixture) + "/shares", HttpMethod.POST,
                new HttpEntity<>(body, auth(userId)), Map.class);
    }

    private ResponseEntity<Map> listShares(Fixture fixture) {
        return rest.exchange(base(fixture) + "/shares", HttpMethod.GET,
                new HttpEntity<>(auth(fixture.user)), Map.class);
    }

    private ResponseEntity<Map> revoke(Fixture fixture, String shareId) {
        return rest.exchange(base(fixture) + "/shares/" + shareId, HttpMethod.DELETE,
                new HttpEntity<>(auth(fixture.user)), Map.class);
    }

    @Test
    void createsHashedTokenAndServesReportWithoutJwt() {
        String content = "{\"summary\":\"ok\"}";
        var fixture = fixture(true, content);
        var created = createShare(fixture.user, fixture, 3600, 2);

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        String id = (String) created.getBody().get("id");
        String token = (String) created.getBody().get("token");
        assertThat(token).matches("[A-Za-z0-9_-]{22}");
        assertThat(jdbc.queryForObject("SELECT token_hash FROM platform_share_link WHERE id=?",
                String.class, id)).isEqualTo(sha256(token)).isNotEqualTo(token);

        var first = rest.getForEntity("/api/v1/platform/shares/" + token, String.class);
        assertThat(first.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(first.getBody()).isEqualTo(content);
        assertThat(first.getHeaders().getFirst(HttpHeaders.CACHE_CONTROL)).contains("no-store");
        assertThat(first.getHeaders().getFirst("Referrer-Policy")).isEqualTo("no-referrer");

        var listed = listShares(fixture);
        assertThat(listed.getStatusCode()).isEqualTo(HttpStatus.OK);
        @SuppressWarnings("unchecked")
        var items = (List<Map<String, Object>>) listed.getBody().get("items");
        assertThat(items).hasSize(1);
        assertThat(((Number) items.getFirst().get("accessCount")).longValue()).isEqualTo(1);

        assertThat(rest.getForEntity("/api/v1/platform/shares/" + token, String.class).getStatusCode())
                .isEqualTo(HttpStatus.OK);
        assertThat(rest.getForEntity("/api/v1/platform/shares/" + token, String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(rest.getForEntity("/api/v1/platform/shares/" + "x".repeat(22), String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void expiredAndRevokedTokensAreUnavailableImmediately() {
        var fixture = fixture(true, "{\"summary\":\"ok\"}");

        var expiring = createShare(fixture.user, fixture, 60, null);
        String expiringId = (String) expiring.getBody().get("id");
        String expiringToken = (String) expiring.getBody().get("token");
        Instant past = Instant.now().minusSeconds(120);
        jdbc.update("UPDATE platform_share_link SET created_at=?, expires_at=? WHERE id=?",
                Timestamp.from(past), Timestamp.from(past.plusSeconds(60)), expiringId);
        assertThat(rest.getForEntity("/api/v1/platform/shares/" + expiringToken, String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);

        var revocable = createShare(fixture.user, fixture, 3600, null);
        String revocableId = (String) revocable.getBody().get("id");
        String revocableToken = (String) revocable.getBody().get("token");
        assertThat(revoke(fixture, revocableId).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(rest.getForEntity("/api/v1/platform/shares/" + revocableToken, String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(revoke(fixture, revocableId).getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void shareCreationRequiresReviewerAndSuccessfulArtifact() {
        var fixture = fixture(true, "{\"summary\":\"ok\"}");
        var viewer = identity.provision("test", "viewer-" + UUID.randomUUID(), "test-password-123");
        identity.addMember(fixture.user, fixture.org, viewer.id(), ProjectRole.VIEWER);
        assertThat(createShare(viewer.id(), fixture, 3600, null).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);

        var other = fixture(true, "{\"summary\":\"other\"}");
        assertThat(createShare(other.user, fixture, 3600, null).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);

        var pending = fixture(false, "");
        assertThat(createShare(pending.user, pending, 3600, null).getStatusCode())
                .isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void concurrentAccessNeverExceedsMaxAccesses() throws Exception {
        var fixture = fixture(true, "{\"summary\":\"ok\"}");
        var created = createShare(fixture.user, fixture, 3600, 5);
        String id = (String) created.getBody().get("id");
        String token = (String) created.getBody().get("token");

        int successes;
        try (var pool = Executors.newFixedThreadPool(10)) {
            var jobs = IntStream.range(0, 10)
                    .mapToObj(i -> (Callable<Boolean>) () -> {
                        try {
                            shares.access(token);
                            return true;
                        } catch (ApiException ex) {
                            return false;
                        }
                    })
                    .toList();
            successes = 0;
            for (var future : pool.invokeAll(jobs)) {
                if (future.get()) successes++;
            }
        }

        assertThat(successes).isEqualTo(5);
        assertThat(jdbc.queryForObject("SELECT access_count FROM platform_share_link WHERE id=?",
                Long.class, id)).isEqualTo(5);
    }
}
