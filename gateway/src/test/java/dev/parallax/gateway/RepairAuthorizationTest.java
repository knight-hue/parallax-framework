package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import com.sun.net.httpserver.HttpServer;
import dev.parallax.gateway.auth.JwtService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class RepairAuthorizationTest {
    private static HttpServer upstream;
    private static final AtomicReference<String> operator = new AtomicReference<>();
    @Autowired private TestRestTemplate rest;
    @Autowired private JwtService jwt;

    @BeforeAll
    static void start() throws Exception {
        upstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        upstream.createContext("/api/v1/audits", exchange -> {
            operator.set(exchange.getRequestHeaders().getFirst("X-Parallax-Operator"));
            exchange.getRequestBody().readAllBytes();
            byte[] body = "{}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(201, body.length);
            try (var out = exchange.getResponseBody()) { out.write(body); }
        });
        upstream.start();
    }

    @AfterAll
    static void stop() { if (upstream != null) upstream.stop(0); }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("parallax.gateway.upstream-base-url", () -> "http://127.0.0.1:" + upstream.getAddress().getPort());
        registry.add("parallax.gateway.require-auth", () -> "true");
        registry.add("parallax.identity.enabled", () -> "false");
        registry.add("parallax.ratelimit.enabled", () -> "false");
        registry.add("parallax.jwt.secret", () -> "test-repair-secret-32-bytes-minimum");
    }

    private ResponseEntity<String> propose(String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (token != null) headers.setBearerAuth(token);
        return rest.postForEntity("/api/v1/audits/run1/repairs", new HttpEntity<>(Map.of("claim_id", "c1"), headers), String.class);
    }

    @Test
    void anonymousCannotGenerateRepair() { assertThat(propose(null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED); }

    @Test
    void ordinaryReaderCannotGenerateRepair() {
        assertThat(propose(jwt.issueAccessToken("reader", "USER")).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void administratorCanGenerateAndIdentitySurvivesHttpHeaders() {
        assertThat(propose(jwt.issueAccessToken("操作员 甲", "ADMIN")).getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(java.net.URLDecoder.decode(operator.get(), StandardCharsets.UTF_8)).isEqualTo("操作员 甲");
    }
}
