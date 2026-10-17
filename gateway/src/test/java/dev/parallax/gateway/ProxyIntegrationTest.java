package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * 转发链路的端到端测试，上游用一个真实的 HTTP 服务桩。
 *
 * 为什么不 mock 上游：这条链路上出问题的地方几乎都在 HTTP 层——
 * 协议版本协商、分块传输、请求头的透传、异步超时。
 * mock 掉 HTTP 就等于把最可能坏的那一层换成了"永不坏的实现"。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class ProxyIntegrationTest {

    private static HttpServer upstream;
    private static int upstreamPort;

    /** 记录上游收到的请求头，用来断言透传是否真的发生了。 */
    private static final Map<String, String> lastHeaders = new ConcurrentHashMap<>();
    private static final List<String> receivedPaths = new CopyOnWriteArrayList<>();

    @LocalServerPort
    private int gatewayPort;

    @Autowired
    private TestRestTemplate rest;

    @BeforeAll
    static void startUpstream() throws IOException {
        upstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        upstreamPort = upstream.getAddress().getPort();

        upstream.createContext("/health", exchange -> respondJson(exchange, 200, "{\"status\":\"ok\"}"));

        upstream.createContext("/api/v1/meta", exchange -> respondJson(exchange, 200, "{\"version\":\"0.1.0\"}"));

        upstream.createContext("/api/v1/audits", ProxyIntegrationTest::handleAudits);

        upstream.setExecutor(null);
        upstream.start();
    }

    @AfterAll
    static void stopUpstream() {
        if (upstream != null) {
            upstream.stop(0);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("parallax.gateway.upstream-base-url", () -> "http://127.0.0.1:" + upstreamPort);
        registry.add("parallax.gateway.require-auth", () -> "false");
        // 关掉限流：这个测试要连续发多次请求，不该被令牌桶干扰
        registry.add("parallax.ratelimit.enabled", () -> "false");
    }

    private static void handleAudits(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        receivedPaths.add(path);
        exchange.getRequestHeaders().forEach((name, values) -> {
            if (!values.isEmpty()) {
                lastHeaders.put(name.toLowerCase(), values.get(0));
            }
        });

        if (path.endsWith("/events")) {
            // 分块发送：先发一个事件，停顿后再发一个——用来证明网关没有把它攒成一整块
            exchange.getResponseHeaders().add("Content-Type", "text/event-stream; charset=utf-8");
            exchange.sendResponseHeaders(200, 0);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write("id: 1\nevent: queued\ndata: {\"n\":1}\n\n".getBytes(StandardCharsets.UTF_8));
                out.flush();
                pause(150);
                out.write("id: 2\nevent: done\ndata: {\"n\":2}\n\n".getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
            return;
        }

        if ("POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            byte[] body = exchange.getRequestBody().readAllBytes();
            // 回显收到的请求体：证明网关把 POST body 原样送到了上游
            respondJson(exchange, 202, "{\"run_id\":\"abc\",\"echo\":" + new String(body, StandardCharsets.UTF_8) + "}");
            return;
        }
        respondJson(exchange, 200, "{\"total\":0,\"runs\":[]}");
    }

    private static void respondJson(HttpExchange exchange, int status, String payload) throws IOException {
        byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    private static void pause(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    private String url(String path) {
        return "http://127.0.0.1:" + gatewayPort + path;
    }

    @Test
    void forwardsGetAndPreservesStatusAndBody() {
        ResponseEntity<String> response = rest.getForEntity(url("/health"), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("status").contains("ok");
    }

    @Test
    void forwardsQueryString() {
        ResponseEntity<String> response = rest.getForEntity(url("/api/v1/audits?limit=7"), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("runs");
    }

    @Test
    void forwardsPostBodyAndUpstreamStatus() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<String> response = rest.exchange(
                url("/api/v1/audits"),
                HttpMethod.POST,
                new HttpEntity<>("{\"repo_path\":\"/tmp/repo\",\"readers\":3}", headers),
                String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(response.getBody()).contains("run_id").contains("/tmp/repo");
    }

    @Test
    void forwardsCancelDelete() {
        ResponseEntity<String> response = rest.exchange(
                url("/api/v1/audits/abc"), HttpMethod.DELETE, HttpEntity.EMPTY, String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(receivedPaths).contains("/api/v1/audits/abc");
    }

    @Test
    void forwardsLastEventIdHeaderForSseReplay() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Last-Event-ID", "42");
        headers.setAccept(List.of(MediaType.TEXT_EVENT_STREAM));

        ResponseEntity<String> response = rest.exchange(
                url("/api/v1/audits/abc/events"), HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getHeaders().getContentType()).isNotNull();
        assertThat(response.getHeaders().getContentType().toString()).contains("text/event-stream");
        // 丢了 Last-Event-ID，前端重连时会静默漏掉中间事件
        assertThat(lastHeaders.get("last-event-id")).isEqualTo("42");
        assertThat(response.getBody()).contains("event: queued").contains("event: done");
    }

    @Test
    void stampsTraceIdOnEveryResponse() {
        ResponseEntity<String> response = rest.getForEntity(url("/api/v1/meta"), String.class);

        assertThat(response.getHeaders().getFirst("X-Trace-Id")).isNotBlank();
    }

    @Test
    void refusesPathsOutsideTheWhitelist() {
        // 这个路径会被 /api/v1/audits/** 的映射接住，但不在白名单里。
        // 没有白名单的话它就真的被转发到上游了——网关会变成一个开放代理。
        //
        // 显式不让这条连接被复用。背景：本用例在 CI 上偶发
        // `HTTP/1.1 header parser received no bytes`，本地从未复现。
        // 根因不是白名单判断错了，而是 HttpURLConnection 的连接池复用了服务端
        // 已关闭的空闲连接——前一个用例是 SSE 流，那类响应必然是 close-delimited，
        // 服务端发完就关连接，而客户端并不知道。
        // 生产侧的对应修法是给小 JSON 响应补 Content-Length
        // （见 ProxyController#json 的说明）；这里再显式禁掉复用，
        // 让"白名单是否生效"不再受连接时序影响。
        HttpHeaders headers = new HttpHeaders();
        headers.set(HttpHeaders.CONNECTION, "close");
        ResponseEntity<String> response = rest.exchange(
                url("/api/v1/audits/abc/bogus"), HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(receivedPaths).doesNotContain("/api/v1/audits/abc/bogus");
    }
}
