package dev.parallax.gateway.proxy;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import dev.parallax.gateway.common.TraceFilter;

import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;

import jakarta.servlet.http.HttpServletRequest;

/**
 * 统一入口：把白名单内的请求原样转发给上游编排服务。
 *
 */
@RestController
public class ProxyController {

    /** 与 `parallax/service/app.py` 的端点一一对应。改上游路由时必须同步改这里。 */
    private static final Pattern ALLOWED = Pattern.compile(
            "^/(health|ready)$"
                    + "|^/api/v1/meta$"
                    + "|^/api/v1/audits(/[A-Za-z0-9_-]{1,64})?(/(events|result|report))?$");

    private final UpstreamClient upstream;

    public ProxyController(UpstreamClient upstream) {
        this.upstream = upstream;
    }

    @GetMapping({"/health", "/ready", "/api/v1/meta", "/api/v1/audits", "/api/v1/audits/**"})
    public ResponseEntity<StreamingResponseBody> forwardGet(HttpServletRequest request) {
        return forward(request, false, null);
    }

    @PostMapping("/api/v1/audits")
    public ResponseEntity<StreamingResponseBody> forwardPost(
            HttpServletRequest request, @RequestBody(required = false) byte[] body) {
        return forward(request, true, body);
    }

    private ResponseEntity<StreamingResponseBody> forward(
            HttpServletRequest request, boolean nonIdempotent, byte[] body) {
        String path = request.getRequestURI();
        if (!ALLOWED.matcher(path).matches()) {
            return json(HttpStatus.NOT_FOUND, "{\"success\":false,\"error\":\"接口不存在\"}");
        }

        Map<String, String> headers = new HashMap<>();
        headers.put(TraceFilter.TRACE_HEADER, TraceFilter.currentTraceId());
        String lastEventId = request.getHeader("Last-Event-ID");
        if (lastEventId != null && !lastEventId.isBlank()) {
            headers.put("Last-Event-ID", lastEventId);
        }

        try {
            UpstreamResponse response = nonIdempotent
                    ? upstream.sendNonIdempotent(request.getMethod(), path, request.getQueryString(), headers, body)
                    : upstream.sendIdempotent(request.getMethod(), path, request.getQueryString(), headers);
            return stream(response);
        } catch (CallNotPermittedException ex) {
            // 熔断打开：明确告诉调用方"不是你的问题，稍后重试"，而不是伪装成上游 500
            return json(HttpStatus.SERVICE_UNAVAILABLE,
                    "{\"success\":false,\"error\":\"编排服务暂时不可用（熔断保护中），请稍后重试\"}");
        } catch (IOException ex) {
            return json(HttpStatus.BAD_GATEWAY, "{\"success\":false,\"error\":\"编排服务连接失败，请稍后重试\"}");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return json(HttpStatus.SERVICE_UNAVAILABLE, "{\"success\":false,\"error\":\"请求被中断\"}");
        }
    }

    /** 原样透传状态码与 Content-Type；响应体不缓冲、不聚合。 */
    private ResponseEntity<StreamingResponseBody> stream(UpstreamResponse response) {
        String contentType = response.headers().firstValue("Content-Type")
                .orElse(MediaType.APPLICATION_JSON_VALUE);
        return ResponseEntity.status(response.status())
                .contentType(MediaType.parseMediaType(contentType))
                .cacheControl(CacheControl.noCache())
                // 关掉 nginx 缓冲，否则 SSE 会被攒起来一起发
                .header("X-Accel-Buffering", "no")
                .body(out -> {
                    try (InputStream in = response.body()) {
                        in.transferTo(out);
                        out.flush();
                    }
                });
    }

    private ResponseEntity<StreamingResponseBody> json(HttpStatus status, String payload) {
        return ResponseEntity.status(status)
                .contentType(MediaType.APPLICATION_JSON)
                .body(out -> {
                    out.write(payload.getBytes(StandardCharsets.UTF_8));
                    out.flush();
                });
    }

    /** 供文档与测试引用，避免白名单正则被改坏时无人察觉。 */
    public static List<String> allowedPatterns() {
        return List.of(ALLOWED.pattern());
    }
}
