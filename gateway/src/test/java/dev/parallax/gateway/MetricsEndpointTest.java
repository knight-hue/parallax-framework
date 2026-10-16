package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

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
 * C4 的验收：`/actuator/prometheus` 上三个业务指标的数值**正确**。
 *
 * 只断言"指标名字存在"是不够的——预注册零值让名字一定存在，
 * 而数值错了（例如把 token 数记成"次数"、把拒绝记到别的标签上）
 * 照样能让名字检查通过。因此这里断言具体数值。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class MetricsEndpointTest {

    private static final String ADMIN_SECRET = "metrics-admin-secret";
    private static final String INTERNAL_TOKEN = "metrics-internal-token";

    private static UpstreamStub upstream;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private QuotaPolicyRepository policies;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("parallax.gateway.upstream-base-url", () -> upstream.baseUrl());
        registry.add("parallax.ratelimit.enabled", () -> "false");
        registry.add("parallax.gateway.admin-secret", () -> ADMIN_SECRET);
        registry.add("parallax.gateway.internal-token", () -> INTERNAL_TOKEN);
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

    private String adminToken() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/auth/token",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("secret", ADMIN_SECRET), headers),
                mapType());
        return (String) response.getBody().get("accessToken");
    }

    private Map<String, Object> createCredential(String name, String policy) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        if (policy != null) {
            body.put("quotaPolicy", policy);
        }
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/credentials", HttpMethod.POST, new HttpEntity<>(body, adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return response.getBody();
    }

    private void submit(String key) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-Key", key);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/audits",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("repo", "/workspace/metrics"), headers),
                mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
    }

    private void complete(String runId, String credentialId, long prompt, long completion) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", INTERNAL_TOKEN);
        rest.exchange(
                "/api/v1/internal/runs/" + runId + "/complete",
                HttpMethod.POST,
                new HttpEntity<>(
                        Map.of(
                                "credentialId", credentialId,
                                "promptTokens", prompt,
                                "completionTokens", completion,
                                "status", "done"),
                        headers),
                mapType());
    }

    /** 抓取 Prometheus 文本并取出某个样本的数值。 */
    private double scrape(String samplePrefix, String... tags) {
        String body = rest.getForObject("/actuator/prometheus", String.class);
        assertThat(body).as("/actuator/prometheus 应可访问").isNotNull();
        for (String line : body.split("\n")) {
            if (line.startsWith("#") || !line.startsWith(samplePrefix)) {
                continue;
            }
            if (!Arrays.stream(tags).allMatch(line::contains)) {
                continue;
            }
            return Double.parseDouble(line.substring(line.lastIndexOf(' ') + 1));
        }
        throw new AssertionError(
                "未找到样本 " + samplePrefix + " " + String.join(", ", tags) + "\n" + body);
    }

    // ---- 指标 ----

    @Test
    void runAndTokenCountersReflectCompletedWork() {
        Map<String, Object> created = createCredential("metrics-a", null);
        String credentialId = (String) created.get("id");
        String key = (String) created.get("apiKey");

        submit(key);
        String runId = jdbc.queryForObject(
                "SELECT run_id FROM audit_run WHERE credential_id = ?", String.class, credentialId);
        complete(runId, credentialId, 1_500, 500);

        assertThat(scrape("parallax_runs_total", "status=\"done\"")).isGreaterThanOrEqualTo(1.0);
        assertThat(scrape("parallax_tokens_total", "credential=\"" + credentialId + "\""))
                .as("token 数应按总量累加，而不是按调用次数")
                .isEqualTo(2_000.0);
    }

    @Test
    void quotaRejectionsAreCountedWithTheirReason() {
        policies.findByName("metrics-tiny")
                .orElseGet(() -> policies.save(new QuotaPolicy("metrics-tiny", 1, 10_000_000L, 100_000_000L)));
        Map<String, Object> created = createCredential("metrics-quota", "metrics-tiny");
        String key = (String) created.get("apiKey");

        submit(key);
        // 第二次会被日运行数挡下
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-Key", key);
        ResponseEntity<Map<String, Object>> rejected = rest.exchange(
                "/api/v1/audits",
                HttpMethod.POST,
                new HttpEntity<>(Map.of("repo", "/workspace/metrics-2"), headers),
                mapType());
        assertThat(rejected.getStatusCode()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);

        assertThat(scrape("parallax_quota_rejections_total", "metric=\"daily_runs\""))
                .as("拒绝计数必须带上原因标签，否则无法区分是次数还是 token 用尽")
                .isGreaterThanOrEqualTo(1.0);
    }

    @Test
    void countersAreVisibleBeforeAnyEventHappens() {
        // 零值预注册：否则"没有曲线"与"还没有事件"在面板上看起来一样
        String body = rest.getForObject("/actuator/prometheus", String.class);
        assertThat(body).contains("parallax_runs_total");
        assertThat(body).contains("parallax_quota_rejections_total");
    }

    @Test
    void rateLimitDegradationMetricIsExposed() {
        String body = rest.getForObject("/actuator/prometheus", String.class);
        assertThat(body)
                .as("「一直在降级」必须能被发现，否则配额会悄悄退化成单实例口径")
                .contains("parallax_ratelimit_degraded_total");
    }
}
