package dev.parallax.gateway.support;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

/**
 * 上游编排服务的测试替身：一个真实监听的 HTTP 服务。
 *
 * 不用 mock 框架：网关与编排服务之间出问题的地方几乎都在 HTTP 层
 * （分块传输、状态码透传、异步超时），mock 掉 HTTP 等于把最可能坏的那层换成永不坏的实现。
 *
 * 每次请求的记录都留下，测试可以断言"网关确实转发了"而不是只断言状态码。
 */
public final class UpstreamStub implements AutoCloseable {

    public record Received(String method, String path, String body) {
    }

    private final HttpServer server;
    private final List<Received> requests = new CopyOnWriteArrayList<>();
    private final AtomicInteger runIdSeq = new AtomicInteger();
    private volatile int auditsStatus = 202;

    private UpstreamStub(HttpServer server) {
        this.server = server;
    }

    public static UpstreamStub start() throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        UpstreamStub stub = new UpstreamStub(server);
        server.createContext("/health", ex -> stub.respond(ex, 200, "{\"status\":\"ok\"}"));
        server.createContext("/api/v1/meta", ex -> stub.respond(ex, 200, "{\"version\":\"test\"}"));
        server.createContext("/api/v1/audits", stub::handleAudits);
        server.setExecutor(null);
        server.start();
        return stub;
    }

    public String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    public List<Received> requests() {
        return List.copyOf(requests);
    }

    public void reset() {
        requests.clear();
    }

    /** 让上游在提交审查时返回指定状态码，用于验证网关透传而不改写。 */
    public void auditsStatus(int status) {
        this.auditsStatus = status;
    }

    private void handleAudits(HttpExchange exchange) throws IOException {
        String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        requests.add(new Received(exchange.getRequestMethod(), exchange.getRequestURI().getPath(), body));

        if (exchange.getRequestURI().getPath().endsWith("/result")) {
            respond(exchange, 200, "{\"result\":\"ok\"}");
            return;
        }
        if ("POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            respond(exchange, auditsStatus, "{\"run_id\":\"run-stub-" + runIdSeq.incrementAndGet() + "\"}");
            return;
        }
        respond(exchange, 200, "{\"total\":0,\"runs\":[]}");
    }

    private void respond(HttpExchange exchange, int status, String payload) throws IOException {
        byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
