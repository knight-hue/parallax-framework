package dev.parallax.gateway.proxy;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.common.TraceFilter;
import dev.parallax.gateway.config.ParallaxProperties;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;

/**
 * 转发到上游编排服务。
 *
 * 三条容易踩的坑，都在这里一次性处理掉：
 *
 * 1. **必须强制 HTTP/1.1。** JDK 的 HttpClient 对明文 HTTP 会尝试 h2c 升级，
 *    而上游（FastAPI/uvicorn）不监听 upgrade，连接会被直接断开，
 *    报错形如 "header parser received no bytes"——看起来像上游崩了，其实是协议协商失败。
 *
 * 2. **重试必须区分幂等性。** 见上。
 *
 * 3. **响应体不做缓冲。** 拿到响应头就返回，响应体交给调用方流式消费。
 *    否则 SSE 会被攒成一整块，工作台的"实时进度"就变成了"最后一次性出现"。
 */
@Service
public class UpstreamClient {

    private static final Logger log = LoggerFactory.getLogger(UpstreamClient.class);

    private final ParallaxProperties props;
    private final HttpClient httpClient;

    public UpstreamClient(ParallaxProperties props) {
        this.props = props;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.getGateway().connectTimeout())
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    /** 幂等请求（GET / HEAD）：允许在连接阶段失败后重试。 */
    @CircuitBreaker(name = "upstream")
    @Retry(name = "upstreamRead")
    public UpstreamResponse sendIdempotent(String method, String path, String query, Map<String, String> headers)
            throws IOException, InterruptedException {
        return send(method, path, query, headers, null);
    }

    /** 非幂等请求（POST）：熔断保护仍生效，但**不重试**。 */
    @CircuitBreaker(name = "upstream")
    public UpstreamResponse sendNonIdempotent(
            String method, String path, String query, Map<String, String> headers, byte[] body)
            throws IOException, InterruptedException {
        return send(method, path, query, headers, body);
    }

    private UpstreamResponse send(String method, String path, String query, Map<String, String> headers, byte[] body)
            throws IOException, InterruptedException {
        String baseUrl = props.getGateway().getUpstreamBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            throw ApiException.serverError("上游地址未配置（PARALLAX_UPSTREAM_URL）");
        }
        String url = trimTrailingSlash(baseUrl) + path + (query == null || query.isBlank() ? "" : "?" + query);

        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(url))
                .timeout(props.getGateway().readTimeout())
                .header("Accept", "text/event-stream, application/json");

        String traceId = headers.get(TraceFilter.TRACE_HEADER);
        if (traceId != null && !traceId.isBlank()) {
            builder.header(TraceFilter.TRACE_HEADER, traceId);
        }
        String internalToken = props.getGateway().getInternalToken();
        if (internalToken != null && !internalToken.isBlank()) {
            builder.header("X-Internal-Token", internalToken);
        }
        // SSE 断线重连要靠这个头补发缺口事件，丢了它前端就会静默漏事件
        String lastEventId = headers.get("Last-Event-ID");
        if (lastEventId != null && !lastEventId.isBlank()) {
            builder.header("Last-Event-ID", lastEventId);
        }

        HttpRequest.BodyPublisher publisher = body == null
                ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofByteArray(body);
        if (body != null) {
            builder.header("Content-Type", "application/json");
        }
        builder.method(method, publisher);

        HttpResponse<InputStream> response =
                httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofInputStream());
        log.debug("转发 {} {} -> {}", method, path, response.statusCode());
        return new UpstreamResponse(response.statusCode(), response.headers(), response.body());
    }

    private String trimTrailingSlash(String value) {
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    /** 探活用：只关心上游是否可达。 */
    public boolean upstreamReachable() {
        try {
            HttpResponse<Void> response = httpClient.send(
                    HttpRequest.newBuilder(URI.create(trimTrailingSlash(props.getGateway().getUpstreamBaseUrl()) + "/health"))
                            .timeout(Duration.ofMillis(props.getGateway().getConnectTimeoutMs()))
                            .GET()
                            .build(),
                    HttpResponse.BodyHandlers.discarding());
            return response.statusCode() < 500;
        } catch (IOException | InterruptedException ex) {
            if (ex instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            return false;
        }
    }
}
