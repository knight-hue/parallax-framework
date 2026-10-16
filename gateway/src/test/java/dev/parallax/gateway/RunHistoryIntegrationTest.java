package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import dev.parallax.gateway.identity.QuotaPolicy;
import dev.parallax.gateway.identity.QuotaPolicyRepository;
import dev.parallax.gateway.support.UpstreamStub;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
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
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * C2 端到端：提交 → 落记录 → 完成回调补统计 → 按状态/凭据/时间过滤与分页 → 事件留痕。
 *
 * 其中"服务重启后记录不丢"这条无法用内存库证明——H2 的内存库随进程消失而消失。
 * 那一项由 gateway-it（Testcontainers 真实 PostgreSQL）负责，见
 * `IdentityPostgresIT`。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class RunHistoryIntegrationTest {

    private static final String ADMIN_SECRET = "admin-secret-for-test";
    private static final String INTERNAL_TOKEN = "test-internal-token";

    private static UpstreamStub upstream;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private QuotaPolicyRepository policies;

    /** 明文 key 只在创建响应里出现一次，测试必须自己留住它。 */
    private final Map<String, String> issuedKeys = new ConcurrentHashMap<>();

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("parallax.gateway.upstream-base-url", () -> upstream.baseUrl());
        registry.add("parallax.ratelimit.enabled", () -> "false");
        registry.add("parallax.gateway.require-auth", () -> "false");
        registry.add("parallax.gateway.admin-secret", () -> ADMIN_SECRET);
        registry.add("parallax.jwt.secret", () -> "0123456789abcdef0123456789abcdef");
    }

    @BeforeAll
    static void startUpstream() throws Exception {
        upstream = UpstreamStub.start();
    }

    @AfterAll
    static void stopUpstream() {
        if (upstream != null) {
            upstream.close();
        }
    }

    @BeforeEach
    void reset() {
        upstream.reset();
        upstream.auditsStatus(202);
        // 配额放宽到不可能触发，本类只验证记录与查询。
        // 用 findByName 而不是无条件 save：策略名有唯一约束，
        // 同一个 Spring 上下文里多个测试方法共用同一个内存库。
        if (policies.findByName("history").isEmpty()) {
            policies.save(new QuotaPolicy("history", 1_000, 1_000_000_000L, 10_000_000_000L));
        }
    }

    // ---- 辅助 ----

    @SuppressWarnings("unchecked")
    private static Class<Map<String, Object>> mapType() {
        return (Class<Map<String, Object>>) (Class<?>) Map.class;
    }

    private HttpHeaders adminHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(adminToken());
        return headers;
    }

    @SuppressWarnings("unchecked")
    private String adminToken() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/auth/token",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("secret", ADMIN_SECRET), headers),
                mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return (String) response.getBody().get("accessToken");
    }

    private Map<String, Object> createCredential(String name) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        body.put("quotaPolicy", "history");
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/credentials", HttpMethod.POST, new HttpEntity<>(body, adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        // 明文 key 只在此刻存在，必须马上留住——服务端没有"再查一次"的端点
        issuedKeys.put(name, (String) response.getBody().get("apiKey"));
        return response.getBody();
    }

    private String keyOf(String name) {
        String key = issuedKeys.get(name);
        assertThat(key).as("测试里还没为 %s 签发过凭据", name).isNotNull();
        return key;
    }

    private String submit(String apiKey, String repo) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-Key", apiKey);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/audits", HttpMethod.POST, new HttpEntity<>(Map.of("repo", repo), headers), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        return jdbc.queryForObject(
                "SELECT run_id FROM audit_run WHERE repo_path = ? ORDER BY submitted_at DESC LIMIT 1",
                String.class,
                repo);
    }

    private ResponseEntity<Map<String, Object>> complete(
            String runId, String credentialId, String status, long prompt, long completion, Double elapsed) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", INTERNAL_TOKEN);
        Map<String, Object> body = new HashMap<>();
        body.put("credentialId", credentialId);
        body.put("promptTokens", prompt);
        body.put("completionTokens", completion);
        body.put("status", status);
        body.put("stopReason", "max_rounds_reached");
        body.put("countsJson", "{\"high_confidence\":3,\"pending\":7}");
        if (elapsed != null) {
            body.put("elapsedS", elapsed);
        }
        return rest.exchange(
                "/api/v1/internal/runs/" + runId + "/complete",
                HttpMethod.POST,
                new HttpEntity<>(body, headers),
                mapType());
    }

    private Map<String, Object> runsPage(String query) {
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/runs" + query, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return response.getBody();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> items(Map<String, Object> page) {
        return (List<Map<String, Object>>) page.get("items");
    }

    private static long longField(Map<String, Object> map, String key) {
        Object value = map.get(key);
        assertThat(value).as("字段 %s 缺失", key).isNotNull();
        return ((Number) value).longValue();
    }

    // ---- 记录与统计 ----

    @Test
    void submissionIsRecordedAsQueuedAndLinkedToUpstreamRunId() {
        Map<String, Object> created = createCredential("history-a");
        String key = (String) created.get("apiKey");
        String runId = submit(key, "/workspace/alpha");

        Map<String, Object> detail = rest.exchange(
                        "/api/v1/runs/" + runId, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType())
                .getBody();
        assertThat(detail).isNotNull();
        @SuppressWarnings("unchecked")
        Map<String, Object> run = (Map<String, Object>) detail.get("run");
        assertThat(run).containsEntry("status", "queued");
        assertThat(run).containsEntry("credentialId", created.get("id"));
        assertThat(run).containsEntry("repoPath", "/workspace/alpha");
        assertThat(run.get("runId")).isEqualTo(runId);
    }

    @Test
    void completionCallbackFillsUsageAndStatistics() {
        String credentialId = (String) createCredential("history-b").get("id");
        String runId = submit(keyOf("history-b"), "/workspace/beta");

        ResponseEntity<Map<String, Object>> response = complete(runId, credentialId, "done", 1200, 300, 42.5);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);

        @SuppressWarnings("unchecked")
        Map<String, Object> run = (Map<String, Object>) rest.exchange(
                        "/api/v1/runs/" + runId, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType())
                .getBody()
                .get("run");

        assertThat(run).containsEntry("status", "done");
        assertThat(run).containsEntry("stopReason", "max_rounds_reached");
        assertThat(run.get("countsJson")).asString().contains("high_confidence");
        assertThat((Double) run.get("elapsedS")).isEqualTo(42.5);

        @SuppressWarnings("unchecked")
        Map<String, Object> usage = (Map<String, Object>) run.get("usage");
        assertThat(longField(usage, "promptTokens")).isEqualTo(1200L);
        assertThat(longField(usage, "completionTokens")).isEqualTo(300L);
        assertThat(longField(usage, "totalTokens"))
                .as("总 token 必须由服务端算出，不能信任调用方传来的合计")
                .isEqualTo(1500L);
    }

    @Test
    void tokenTotalsMatchWhatTheCallerReported() {
        String credentialId = (String) createCredential("history-consistency").get("id");
        String runId = submit(keyOf("history-consistency"), "/workspace/gamma");
        complete(runId, credentialId, "done", 7_777, 2_223, null);

        Long stored = jdbc.queryForObject(
                "SELECT total_tokens FROM audit_run WHERE run_id = ?", Long.class, runId);
        assertThat(stored)
                .as("网关存下的 total 必须等于上游 meta.json 里的用量之和")
                .isEqualTo(10_000L);
    }

    // ---- 过滤与分页 ----

    @Test
    void historyCanBeFilteredByStatusCredentialAndTimeRange() {
        String credentialId = (String) createCredential("history-filter").get("id");
        String key = keyOf("history-filter");
        String doneRun = submit(key, "/workspace/done");
        String failedRun = submit(key, "/workspace/failed");
        complete(doneRun, credentialId, "done", 10, 5, null);
        complete(failedRun, credentialId, "failed", 20, 5, null);

        assertThat(items(runsPage("?status=done"))).anySatisfy(
                item -> assertThat(itRunId(item)).isEqualTo(doneRun));
        assertThat(items(runsPage("?status=done")))
                .noneSatisfy(item -> assertThat(itRunId(item)).isEqualTo(failedRun));
        assertThat(items(runsPage("?status=failed")))
                .singleElement()
                .satisfies(item -> assertThat(itRunId(item)).isEqualTo(failedRun));

        assertThat(items(runsPage("?credentialId=" + credentialId)))
                .hasSize(2);

        // 未来时间窗口内应当什么都查不到
        assertThat(items(runsPage("?since=2999-01-01T00:00:00Z"))).isEmpty();
        assertThat(items(runsPage("?until=2000-01-01T00:00:00Z"))).isEmpty();
    }

    @Test
    void historyRejectsUnknownStatusInsteadOfReturningEmpty() {
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/runs?status=whatever", HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType());
        assertThat(response.getStatusCode())
                .as("拼错的状态返回空列表会让人以为没有数据，而不是自己拼错了")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void paginationIsCappedSoOneRequestCannotDrainMemory() {
        String key = keyOf((String) createCredential("history-page").get("name"));
        String credentialId = idOf("history-page");
        for (int i = 0; i < 3; i++) {
            submit(key, "/workspace/page-" + i);
        }

        Map<String, Object> page = runsPage("?size=1&page=1&credentialId=" + credentialId);
        assertThat(longField(page, "totalElements")).isGreaterThanOrEqualTo(3L);

        Map<String, Object> capped = runsPage("?size=100000");
        assertThat(longField(capped, "size")).isEqualTo(200L);
    }

    // ---- 可见性 ----

    @Test
    void credentialHolderOnlySeesItsOwnRuns() {
        String mine = (String) createCredential("history-mine").get("id");
        String other = (String) createCredential("history-other").get("id");
        submit(keyOf("history-mine"), "/workspace/mine");
        submit(keyOf("history-other"), "/workspace/other");

        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", keyOf("history-mine"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) rest.exchange(
                        "/api/v1/runs?credentialId=" + other,
                        HttpMethod.GET,
                        new HttpEntity<>(headers),
                        mapType())
                .getBody()
                .get("items");

        assertThat(rows)
                .as("即使显式传了别人的 credentialId，也只能看到自己的")
                .isNotEmpty()
                .allSatisfy(row -> assertThat(row).containsEntry("credentialId", mine));
    }

    @Test
    void unknownRunIsNotFound() {
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/runs/does-not-exist", HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    // ---- 事件留痕 ----

    @Test
    void lifecycleEventsAreJournaled() {
        String credentialId = (String) createCredential("history-events").get("id");
        String runId = submit(keyOf("history-events"), "/workspace/events");
        complete(runId, credentialId, "done", 1, 1, null);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> events = (List<Map<String, Object>>) rest.exchange(
                        "/api/v1/runs/" + runId, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType())
                .getBody()
                .get("events");

        assertThat(events).extracting(e -> e.get("type")).containsExactly("submitted", "completed");
        assertThat(events.get(1).get("detail")).asString().contains("2 tokens").contains(runId);
    }

    @Test
    void failedCompletionIsJournaledAsFailed() {
        String credentialId = (String) createCredential("history-failed-event").get("id");
        String runId = submit(keyOf("history-failed-event"), "/workspace/fail");
        complete(runId, credentialId, "failed", 1, 1, null);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> events = (List<Map<String, Object>>) rest.exchange(
                        "/api/v1/runs/" + runId, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType())
                .getBody()
                .get("events");
        assertThat(events).extracting(e -> e.get("type")).contains("failed");
    }

    @Test
    void runDetailPointsAtUpstreamEndpointsInsteadOfDuplicatingThem() {
        String runId = submit(keyOf((String) createCredential("history-links").get("name")), "/workspace/links");

        @SuppressWarnings("unchecked")
        Map<String, Object> upstreamLinks = (Map<String, Object>) rest.exchange(
                        "/api/v1/runs/" + runId, HttpMethod.GET, new HttpEntity<>(adminHeaders()), mapType())
                .getBody()
                .get("upstream");

        assertThat(upstreamLinks).containsEntry("eventsUrl", "/api/v1/audits/" + runId + "/events");
        assertThat(upstreamLinks).containsEntry("reportUrl", "/api/v1/audits/" + runId + "/report");
    }

    // ---- 工具 ----

    private String idOf(String name) {
        return jdbc.queryForObject("SELECT id FROM api_credential WHERE name = ?", String.class, name);
    }

    private static String itRunId(Map<String, Object> item) {
        Object runId = item.get("runId");
        return runId == null ? null : String.valueOf(runId);
    }
}
