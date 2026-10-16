package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import dev.parallax.gateway.identity.ApiKeyService;
import dev.parallax.gateway.identity.QuotaPolicy;
import dev.parallax.gateway.identity.QuotaPolicyRepository;
import dev.parallax.gateway.identity.UsageLedgerRepository;
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
 * C1 端到端：建 key → 用它提交审查 → 用量被记账 → 超限被拒 → 吊销后失效。
 *
 * 刻意做成**跨 HTTP 的端到端**而不是直接调 Service：
 * 过滤器链的顺序（API Key → JWT → 配额）本身就是易错点，
 * 只测 Service 会把"配额到底在转发前还是转发后校验"这类问题整个漏掉。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class IdentityIntegrationTest {

    private static final String ADMIN_SECRET = "admin-secret-for-test";
    private static final String INTERNAL_TOKEN = "test-internal-token";

    private static UpstreamStub upstream;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private QuotaPolicyRepository policies;

    @Autowired
    private UsageLedgerRepository ledger;

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
    }

    // ---- HTTP 辅助 ----

    @SuppressWarnings("unchecked")
    private static Class<Map<String, Object>> mapType() {
        return (Class<Map<String, Object>>) (Class<?>) Map.class;
    }

    /** 走 JWT 的管理端点。 */
    private ResponseEntity<Map<String, Object>> asAdmin(HttpMethod method, String path, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(adminToken());
        return rest.exchange(path, method, new HttpEntity<>(body, headers), mapType());
    }

    /** 走 API Key 的集成端点。 */
    private ResponseEntity<Map<String, Object>> withKey(
            HttpMethod method, String path, Object body, String apiKey) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (apiKey != null) {
            headers.set("X-API-Key", apiKey);
        }
        return rest.exchange(path, method, new HttpEntity<>(body, headers), mapType());
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

    private Map<String, Object> createCredential(String name, String policy) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        if (policy != null) {
            body.put("quotaPolicy", policy);
        }
        ResponseEntity<Map<String, Object>> response =
                asAdmin(HttpMethod.POST, "/api/v1/credentials", body);
        assertThat(response.getStatusCode())
                .as("创建凭据失败：%s", response.getBody())
                .isEqualTo(HttpStatus.OK);
        return response.getBody();
    }

    /** 端点返回数组时不能反序列化成 Map，单独走这条路径。 */
    private List<Map<String, Object>> asAdminList(String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(adminToken());
        ResponseEntity<List<Map<String, Object>>> response = rest.exchange(
                path,
                HttpMethod.GET,
                new HttpEntity<>(headers),
                new ParameterizedTypeReference<>() {
                });
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        return response.getBody();
    }

    private String createKey(String name, String policy) {
        return (String) createCredential(name, policy).get("apiKey");
    }

    private String idOf(String name) {
        return jdbc.queryForObject("SELECT id FROM api_credential WHERE name = ?", String.class, name);
    }

    /** 最近一次提交拿到上游 run_id。完成回调必须用它，否则统计会被补建成另一条记录。 */
    private String latestRunIdOf(String credentialId) {
        return jdbc.queryForObject(
                "SELECT run_id FROM audit_run WHERE credential_id = ? AND run_id IS NOT NULL"
                        + " ORDER BY submitted_at DESC LIMIT 1",
                String.class,
                credentialId);
    }

    /**
     * JSON 反序列化到 Map 时，整数会变成 Integer/Long 不等。
     * 断言数值必须比 longValue，直接比对象会因类型不同而假失败。
     */
    private static long longField(Map<String, Object> map, String key) {
        Object value = map.get(key);
        assertThat(value).as("字段 %s 缺失", key).isNotNull();
        return ((Number) value).longValue();
    }

    private ResponseEntity<Map<String, Object>> completeRun(
            String runId, String credentialId, long promptTokens, long completionTokens) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", INTERNAL_TOKEN);
        return rest.exchange(
                "/api/v1/internal/runs/" + runId + "/complete",
                HttpMethod.POST,
                new HttpEntity<>(
                        Map.of(
                                "credentialId", credentialId,
                                "promptTokens", promptTokens,
                                "completionTokens", completionTokens),
                        headers),
                mapType());
    }

    private ResponseEntity<Map<String, Object>> submitAudit(String apiKey) {
        return withKey(HttpMethod.POST, "/api/v1/audits", Map.of("repo", "/tmp/demo"), apiKey);
    }

    // ---- 创建：明文只返回一次 ----

    @Test
    void createdKeyIsReturnedOnceWithPrefixAndQuota() {
        Map<String, Object> created = createCredential("ci-bot", null);

        assertThat(created).containsKeys("id", "apiKey", "keyPrefix", "quota");
        assertThat((String) created.get("apiKey")).startsWith("plx_");
        assertThat((String) created.get("keyPrefix")).startsWith("plx_").endsWith("…");
        assertThat((String) created.get("apiKey"))
                .as("前缀只是给人辨认用的，不构成足够的还原信息")
                .doesNotStartWith((String) created.get("keyPrefix"));
    }

    @Test
    void listEndpointNeverReturnsThePlaintextKey() {
        String plaintext = createKey("lister", null);

        List<Map<String, Object>> rows = asAdminList("/api/v1/credentials");

        assertThat(rows).isNotEmpty();
        for (Map<String, Object> row : rows) {
            assertThat(row).doesNotContainKey("apiKey");
            assertThat(row.toString()).doesNotContain(plaintext);
        }
    }

    /**
     * **C1 的核心安全断言**：`api_credential` 表里查不到任何明文 key。
     *
     * 逐列全表扫描而不是只查 key_hash：只查一列的话，将来有人加一个
     * `key_plain` 列做"内部调试用"，这个测试就检测不到了。
     */
    @Test
    void noPlaintextKeyIsEverPersisted() {
        String plaintext = createKey("forensic", null);
        assertThat(plaintext).isNotBlank();

        List<Map<String, Object>> rows = jdbc.queryForList("SELECT * FROM api_credential");
        assertThat(rows).isNotEmpty();
        for (Map<String, Object> row : rows) {
            for (Map.Entry<String, Object> column : row.entrySet()) {
                assertThat(String.valueOf(column.getValue()))
                        .as("列 %s 中出现了明文 key", column.getKey())
                        .doesNotContain(plaintext);
            }
        }

        String stored = jdbc.queryForObject(
                "SELECT key_hash FROM api_credential WHERE name = 'forensic'", String.class);
        assertThat(stored)
                .as("存的必须是摘要，而不是别的东西")
                .isEqualTo(ApiKeyService.hash(plaintext))
                .hasSize(64);
    }

    // ---- 提交与转发 ----

    @Test
    void submittingWithKeyReachesUpstream() {
        String key = createKey("forwarder", null);

        ResponseEntity<Map<String, Object>> response = submitAudit(key);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(upstream.requests()).hasSize(1);
        assertThat(upstream.requests().get(0).path()).isEqualTo("/api/v1/audits");

        // 提交记录必须与上游 run_id 对上，否则完成回调的统计无处可归
        Long linked = jdbc.queryForObject(
                "SELECT count(*) FROM audit_run WHERE credential_id = ? AND run_id IS NOT NULL",
                Long.class,
                idOf("forwarder"));
        assertThat(linked).isEqualTo(1L);
    }

    /**
     * 额度按**提交**计数，而不是按完成计数。
     *
     * 这条断言的意义：若配额只统计已完成的运行，用户就能在第一次完成之前
     * 并发提交上千次，每次都真实烧掉模型费用——那正是配额要防的事。
     */
    @Test
    void submissionsCountTowardsQuotaEvenBeforeAnyRunCompletes() {
        policies.save(new QuotaPolicy("one-submission", 1, 10_000_000L, 100_000_000L));
        String key = createKey("submit-only", "one-submission");

        assertThat(submitAudit(key).getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(jdbc.queryForObject(
                        "SELECT count(*) FROM usage_ledger WHERE credential_id = ?",
                        Long.class,
                        idOf("submit-only")))
                .as("还没完成任何运行，这个凭据不应有账目")
                .isZero();
        assertThat(submitAudit(key).getStatusCode())
                .as("未完成的提交同样要占额度")
                .isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
    }

    @Test
    void unknownApiKeyDoesNotGrantIdentity() {
        ResponseEntity<Map<String, Object>> response = submitAudit("plx_not-a-real-key");

        // 匿名身份：require-auth=false 时仍会转发，但/usage/me 必须拒绝
        assertThat(withKey(HttpMethod.GET, "/api/v1/usage/me", null, "plx_not-a-real-key").getStatusCode())
                .isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
    }

    // ---- 记账 ----

    @Test
    void completionCallbackWritesLedgerOnceEvenIfDeliveredTwice() {
        String key = createKey("bookkeeper", null);
        String credentialId = idOf("bookkeeper");
        submitAudit(key);

        ResponseEntity<Map<String, Object>> first = completeRun("run-abc", credentialId, 1000, 250);
        ResponseEntity<Map<String, Object>> second = completeRun("run-abc", credentialId, 1000, 250);

        assertThat(first.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(first.getBody()).containsEntry("recorded", true);
        assertThat(second.getBody())
                .as("完成回调可能被重投，第二次必须幂等而不是重复计费")
                .containsEntry("recorded", false);

        assertThat(ledger.findByCredentialIdOrderByOccurredAtDesc(credentialId))
                .singleElement()
                .satisfies(entry -> {
                    assertThat(entry.getTotalTokens()).isEqualTo(1250);
                    assertThat(entry.getPromptTokens()).isEqualTo(1000);
                    assertThat(entry.getCompletionTokens()).isEqualTo(250);
                });
    }

    @Test
    void callbackRejectsWrongInternalToken() {
        createKey("intruder", null);
        String credentialId = idOf("intruder");
        Map<String, Object> body = Map.of(
                "credentialId", credentialId, "promptTokens", 1, "completionTokens", 1);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", "not-the-token");

        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/internal/runs/run-x/complete",
                HttpMethod.POST,
                new HttpEntity<>(body, headers),
                mapType());

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(ledger.existsByRunId("run-x")).isFalse();
    }

    // ---- 超限被拒 ----

    @Test
    void quotaRejectionIsStructuredAndHappensBeforeForwarding() {
        policies.save(new QuotaPolicy("two-runs", 2, 10_000_000L, 100_000_000L));
        String key = createKey("small-quota", "two-runs");

        assertThat(submitAudit(key).getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(submitAudit(key).getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        int forwardedBefore = upstream.requests().size();

        ResponseEntity<Map<String, Object>> rejected = submitAudit(key);

        assertThat(rejected.getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        assertThat(upstream.requests())
                .as("被拒的请求绝不能到达上游——否则用户已经烧掉了模型费用")
                .hasSize(forwardedBefore);

        @SuppressWarnings("unchecked")
        Map<String, Object> quota = (Map<String, Object>) rejected.getBody().get("quota");
        assertThat(quota).containsEntry("metric", "daily_runs");
        assertThat(quota).containsEntry("limit", 2);
        assertThat(((Number) quota.get("used")).longValue()).isEqualTo(2L);
        assertThat(quota.get("resetsAt")).isNotNull();
        assertThat(rejected.getHeaders().getFirst("Retry-After")).isNotNull();
    }

    @Test
    void tokenQuotaAlsoBlocks() {
        policies.save(new QuotaPolicy("tiny-tokens", 100, 1_000L, 100_000L));
        String key = createKey("tiny", "tiny-tokens");
        completeRun("run-tiny", idOf("tiny"), 900, 200);

        ResponseEntity<Map<String, Object>> rejected = submitAudit(key);

        assertThat(rejected.getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        @SuppressWarnings("unchecked")
        Map<String, Object> quota = (Map<String, Object>) rejected.getBody().get("quota");
        assertThat(quota).containsEntry("metric", "daily_tokens");
    }

    // ---- 吊销立即生效 ----

    @Test
    void revokedKeyLosesIdentityOnTheVeryNextRequest() {
        String key = createKey("doomed", null);
        assertThat(submitAudit(key).getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(withKey(HttpMethod.GET, "/api/v1/usage/me", null, key).getStatusCode())
                .isEqualTo(HttpStatus.OK);

        ResponseEntity<Map<String, Object>> revoked =
                asAdmin(HttpMethod.DELETE, "/api/v1/credentials/" + idOf("doomed"), null);

        assertThat(revoked.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(revoked.getBody()).containsEntry("name", "doomed");
        assertThat(revoked.getBody().get("revokedAt")).isNotNull();

        assertThat(withKey(HttpMethod.GET, "/api/v1/usage/me", null, key).getStatusCode())
                .as("吊销必须对下一个请求就生效，不能等到令牌自然过期")
                .isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    // ---- 报表一致性 ----

    @Test
    void usageReportMatchesLedgerSums() {
        String key = createKey("reporter", null);
        String credentialId = idOf("reporter");
        for (int i = 0; i < 3; i++) {
            submitAudit(key);
            completeRun(latestRunIdOf(credentialId), credentialId, 100, 50);
        }

        Map<String, Object> me = withKey(HttpMethod.GET, "/api/v1/usage/me", null, key).getBody();
        assertThat(me).isNotNull();
        @SuppressWarnings("unchecked")
        Map<String, Object> today = (Map<String, Object>) me.get("today");
        assertThat(longField(today, "runs")).isEqualTo(3L);
        assertThat(longField(today, "tokens")).isEqualTo(450L);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows =
                (List<Map<String, Object>>) asAdmin(HttpMethod.GET, "/api/v1/usage", null).getBody().get("rows");
        Map<String, Object> mine = rows.stream()
                .filter(r -> credentialId.equals(r.get("credentialId")))
                .findFirst()
                .orElseThrow();
        assertThat(longField(mine, "runs")).isEqualTo(3L);
        assertThat(longField(mine, "tokens")).isEqualTo(450L);
    }

    @Test
    void fleetViewListsCredentialsWithNoUsageToo() {
        createKey("never-used", null);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows =
                (List<Map<String, Object>>) asAdmin(HttpMethod.GET, "/api/v1/usage", null).getBody().get("rows");

        assertThat(rows)
                .as("只列有用量的凭据会让运营方以为凭据丢了")
                .anySatisfy(row -> {
                    assertThat(row).containsEntry("name", "never-used");
                    assertThat(longField(row, "runs")).isZero();
                });
    }
}
