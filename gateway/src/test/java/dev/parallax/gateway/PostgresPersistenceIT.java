package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import dev.parallax.gateway.identity.ApiKeyService;
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
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * **真实 PostgreSQL** 上的集成测试。
 *
 * ## 为什么必须有这一层
 *
 * 默认测试档跑的是 H2 的 PostgreSQL 兼容模式。它有价值（迁移脚本每次都真的被执行、
 * 没有 Docker 的机器也能跑完整套测试），但它**不能替代真实 PostgreSQL**：
 * 类型推导、`coalesce(sum(...))` 的返回类型、时区往返、Criteria 生成的 SQL，
 * 这些都只有真库才能证伪。本类就是为这些差异存在的。
 *
 * ## 为什么"重启后不丢"可以在这里被证明
 *
 * 证据不是"再启动一次 Spring 上下文"（那既慢又只证明了一件事），
 * 而是**绕开应用连接池与 Hibernate，用一条独立 JDBC 连接直接读库**：
 * 读得到就说明数据在数据库里，而不是在 Hibernate 的一级缓存或内存里。
 * 内存库做不到这一点（进程结束即消失），这才是"持久"的实质。
 *
 * 没有 Docker 时整类自动跳过（`disabledWithoutDocker`），不让它成为本地开发的阻塞项。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers(disabledWithoutDocker = true)
class PostgresPersistenceIT {

    private static final String ADMIN_SECRET = "admin-secret-for-it";
    private static final String INTERNAL_TOKEN = "it-internal-token";

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine")
            .withDatabaseName("parallax")
            .withUsername("parallax")
            .withPassword("parallax");

    private static UpstreamStub upstream;

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private JdbcTemplate jdbc;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "validate");
        registry.add("parallax.gateway.upstream-base-url", () -> upstream.baseUrl());
        registry.add("parallax.ratelimit.enabled", () -> "false");
        registry.add("parallax.gateway.admin-secret", () -> ADMIN_SECRET);
        registry.add("parallax.gateway.internal-token", () -> INTERNAL_TOKEN);
        registry.add("parallax.jwt.secret", () -> "0123456789abcdef0123456789abcdef");
        registry.add("parallax.identity.enabled", () -> "true");
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

    private String createKey(String name) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/credentials", HttpMethod.POST, new HttpEntity<>(body, adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return (String) response.getBody().get("apiKey");
    }

    private String submit(String key, String repo) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-Key", key);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/audits", HttpMethod.POST, new HttpEntity<>(Map.of("repo", repo), headers), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        return jdbc.queryForObject(
                "SELECT run_id FROM audit_run WHERE repo_path = ?", String.class, repo);
    }

    private void complete(String runId, String credentialId, long prompt, long completion) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Internal-Token", INTERNAL_TOKEN);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
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
        assertThat(response.getStatusCode()).as("%s", response.getBody()).isEqualTo(HttpStatus.OK);
    }

    /**
     * 绕开应用连接池与 Hibernate 的直接读：证明数据在库里。
     *
     * ⚠️ 只提供 `long` 与 `String` 两个变体，不写通用的 `<T> read(Class<T>)`。
     * 起因是一个真实报错：PostgreSQL 的 `count(*)` 返回 **int8**，而
     * `ResultSet.getObject(1, Integer.class)` 在 PG 驱动上直接抛
     * "conversion to class java.lang.Integer from int8 not supported"。
     * 泛型化的辅助方法会诱导调用方随手写 `Integer.class`，而这个错误
     * 只有真库才会暴露——H2 与"想当然"都不会。
     */
    private long readLongDirectly(String sql) throws Exception {
        try (Connection connection = openDirectConnection();
                Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            assertThat(resultSet.next()).as("查询无结果：%s", sql).isTrue();
            return resultSet.getLong(1);
        }
    }

    private String readStringDirectly(String sql) throws Exception {
        try (Connection connection = openDirectConnection();
                Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            assertThat(resultSet.next()).as("查询无结果：%s", sql).isTrue();
            return resultSet.getString(1);
        }
    }

    private Connection openDirectConnection() throws Exception {
        return DriverManager.getConnection(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
    }

    // ---- 迁移与表结构 ----

    @Test
    void flywayMigrationsApplyCleanlyOnRealPostgres() throws Exception {
        for (String table : List.of(
                "quota_policy", "api_credential", "usage_ledger", "audit_run", "audit_event")) {
            long count = readLongDirectly(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = '" + table + "'");
            assertThat(count).as("真实 PostgreSQL 上缺少表 %s", table).isEqualTo(1L);
        }
        assertThat(readLongDirectly("SELECT count(*) FROM flyway_schema_history"))
                .as("三个迁移都应当已应用")
                .isGreaterThanOrEqualTo(3L);
    }

    // ---- 持久化 ----

    @Test
    void credentialAndRunSurviveOutsideTheApplicationsOwnSession() throws Exception {
        String key = createKey("it-persistence");
        String credentialId = jdbc.queryForObject(
                "SELECT id FROM api_credential WHERE name = 'it-persistence'", String.class);
        String runId = submit(key, "/workspace/it-persist");
        complete(runId, credentialId, 900, 100);

        // 独立连接读到 => 数据确实在数据库里，不是 Hibernate 一级缓存
        assertThat(readLongDirectly(
                        "SELECT count(*) FROM api_credential WHERE name = 'it-persistence'"))
                .isEqualTo(1L);
        assertThat(readLongDirectly(
                        "SELECT total_tokens FROM audit_run WHERE run_id = '" + runId + "'"))
                .as("真实 PG 上 total_tokens 必须是整数而不是字符串或数值对象")
                .isEqualTo(1_000L);
        assertThat(readLongDirectly(
                        "SELECT sum(total_tokens) FROM usage_ledger WHERE credential_id = '"
                                + credentialId + "'"))
                .isEqualTo(1_000L);
    }

    /** 这一条专治 H2 与 PG 的差异：`coalesce(sum(bigint), 0)` 在 PG 上返回 numeric。 */
    @Test
    void tokenAggregationOverEmptyWindowReturnsZeroNotNull() {
        String credentialId = (String) createCredentialResponse("it-empty").get("id");
        Map<String, Object> me = rest.exchange(
                        "/api/v1/usage/me",
                        HttpMethod.GET,
                        new HttpEntity<>(apiKeyHeaders("it-empty")),
                        mapType())
                .getBody();
        assertThat(me).isNotNull();
        @SuppressWarnings("unchecked")
        Map<String, Object> today = (Map<String, Object>) me.get("today");
        assertThat(((Number) today.get("tokens")).longValue())
                .as("没有账目时应当是 0，而不是 null 或异常")
                .isZero();
        assertThat(credentialId).isNotBlank();
    }

    @Test
    void timestampWithTimeZoneRoundTripsOnRealPostgres() {
        String key = createKey("it-tz");
        String credentialId = jdbc.queryForObject(
                "SELECT id FROM api_credential WHERE name = 'it-tz'", String.class);
        String runId = submit(key, "/workspace/it-tz");
        complete(runId, credentialId, 10, 5);

        Map<String, Object> page = rest.exchange(
                        "/api/v1/runs?credentialId=" + credentialId,
                        HttpMethod.GET,
                        new HttpEntity<>(adminHeaders()),
                        mapType())
                .getBody();
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) page.get("items");
        assertThat(items)
                .as("提交时间必须能往返；PG 的 timestamptz 与 Instant 映射出错时这里会是空")
                .hasSize(1);
        assertThat(items.get(0).get("submittedAt")).asString().contains("T");
        assertThat(items.get(0).get("finishedAt")).isNotNull();
    }

    @Test
    void plaintextKeyIsAbsentFromTheRealDatabase() throws Exception {
        String plaintext = createKey("it-forensics");

        try (Connection connection = openDirectConnection();
                Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery("SELECT * FROM api_credential")) {
            while (resultSet.next()) {
                for (int column = 1; column <= resultSet.getMetaData().getColumnCount(); column++) {
                    Object value = resultSet.getObject(column);
                    assertThat(String.valueOf(value))
                            .as("列 %s 中出现了明文 key", resultSet.getMetaData().getColumnName(column))
                            .doesNotContain(plaintext);
                }
            }
        }
        assertThat(readStringDirectly(
                        "SELECT key_hash FROM api_credential WHERE name = 'it-forensics'"))
                .isEqualTo(ApiKeyService.hash(plaintext));
    }

    // ---- 工具 ----

    private Map<String, Object> createCredentialResponse(String name) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        ResponseEntity<Map<String, Object>> response = rest.exchange(
                "/api/v1/credentials", HttpMethod.POST, new HttpEntity<>(body, adminHeaders()), mapType());
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        issuedKeys.put(name, (String) response.getBody().get("apiKey"));
        return response.getBody();
    }

    private final Map<String, String> issuedKeys = new HashMap<>();

    private HttpHeaders apiKeyHeaders(String name) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", issuedKeys.get(name));
        return headers;
    }
}
