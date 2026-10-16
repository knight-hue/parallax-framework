package dev.parallax.gateway.proxy;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.TraceFilter;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.runs.RunService;

import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
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
 * 唯一"不原样"的地方是 `POST /api/v1/audits`：它要在转发前后各做一件平台侧的事
 * （记一次提交、回填上游 run_id）。其余端点严格透传，响应体不缓冲、不解析——
 * 尤其是 SSE 事件流，缓冲会让"实时进度"变成"最后一次性出现"。
 */
@RestController
public class ProxyController {

    /** 与 `parallax/service/app.py` 的端点一一对应。改上游路由时必须同步改这里。 */
    private static final Pattern ALLOWED = Pattern.compile(
            "^/(health|ready)$"
                    + "|^/api/v1/meta$"
                    + "|^/api/v1/audits(/[A-Za-z0-9_-]{1,64})?(/(events|result|report))?$");

    /** 提交审查的响应体上限。正常只有几十字节；超过它说明上游返回了意料之外的东西。 */
    private static final int MAX_CAPTURE_BYTES = 64 * 1024;

    private final UpstreamClient upstream;
    private final RunService runService;
    private final ParallaxProperties props;
    private final ObjectMapper mapper;

    public ProxyController(
            UpstreamClient upstream, RunService runService, ParallaxProperties props, ObjectMapper mapper) {
        this.upstream = upstream;
        this.runService = runService;
        this.props = props;
        this.mapper = mapper;
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
        AuthPrincipal principal = currentPrincipal();
        if (principal != null && principal.hasCredential()) {
            headers.put(CredentialHeaders.CREDENTIAL_ID, principal.credentialId());
        }
        String lastEventId = request.getHeader("Last-Event-ID");
        if (lastEventId != null && !lastEventId.isBlank()) {
            headers.put("Last-Event-ID", lastEventId);
        }

        // 提交审查时先落一条 queued：额度按"提交"计数，而不是按"完成"计数
        String submissionId = registerSubmission(nonIdempotent, body);

        try {
            UpstreamResponse response = nonIdempotent
                    ? upstream.sendNonIdempotent(request.getMethod(), path, request.getQueryString(), headers, body)
                    : upstream.sendIdempotent(request.getMethod(), path, request.getQueryString(), headers);
            return stream(response, submissionId, response.status() < 300);
        } catch (CallNotPermittedException ex) {
            // 熔断打开：明确告诉调用方"不是你的问题，稍后重试"，而不是伪装成上游 500
            runService.markFailed(submissionId, "熔断保护中，未转发");
            return json(HttpStatus.SERVICE_UNAVAILABLE,
                    "{\"success\":false,\"error\":\"编排服务暂时不可用（熔断保护中），请稍后重试\"}");
        } catch (IOException ex) {
            runService.markFailed(submissionId, "上游连接失败：" + ex.getMessage());
            return json(HttpStatus.BAD_GATEWAY, "{\"success\":false,\"error\":\"编排服务连接失败，请稍后重试\"}");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            runService.markFailed(submissionId, "请求被中断");
            return json(HttpStatus.SERVICE_UNAVAILABLE, "{\"success\":false,\"error\":\"请求被中断\"}");
        }
    }

    private String registerSubmission(boolean nonIdempotent, byte[] body) {
        if (!nonIdempotent || !props.getIdentity().isEnabled()) {
            return null;
        }
        AuthPrincipal principal = currentPrincipal();
        if (principal == null || !principal.hasCredential()) {
            return null;
        }        return runService.registerSubmission(
                principal.credentialId(), readText(body, "repo"), readText(body, "question"));
    }

    /**
     * 原样透传状态码与 Content-Type，响应体不缓冲、不聚合。
     *
     * 例外：提交审查（captureRunId=true）需要从响应体里拿到 run_id，才能把提交记录
     * 与上游运行对应起来。此时**有界**地缓冲响应体，解析后仍按流返回。
     * 这个端点的响应只有几十字节，且不涉及 SSE。
     */
    private ResponseEntity<StreamingResponseBody> stream(
            UpstreamResponse response, String submissionId, boolean captureRunId) {
        String contentType = response.headers().firstValue("Content-Type")
                .orElse(MediaType.APPLICATION_JSON_VALUE);

        ResponseEntity.BodyBuilder builder = ResponseEntity.status(response.status())
                .contentType(MediaType.parseMediaType(contentType))
                .cacheControl(CacheControl.noCache())
                // 关掉 nginx 缓冲，否则 SSE 会被攒起来一起发
                .header("X-Accel-Buffering", "no");

        if (captureRunId && submissionId != null) {
            byte[] payload = readBounded(response.body());
            runService.attachUpstreamRunId(submissionId, extractRunId(payload));
            return builder.body(out -> {
                out.write(payload);
                out.flush();
            });
        }

        return builder.body(out -> {
            try (InputStream in = response.body()) {
                in.transferTo(out);
                out.flush();
            }
        });
    }

    private byte[] readBounded(InputStream in) {
        try (in) {
            return in.readNBytes(MAX_CAPTURE_BYTES);
        } catch (IOException ex) {
            return new byte[0];
        }
    }

    /** 上游提交成功时返回 `{"run_id": "...", ...}`；拿不到就返回 null。 */
    private String extractRunId(byte[] payload) {
        JsonNode node = parse(payload);
        if (node == null) {
            return null;
        }
        JsonNode runId = node.get("run_id");
        return runId == null || runId.isNull() ? null : runId.asText();
    }

    private String readText(byte[] body, String field) {
        JsonNode node = parse(body);
        if (node == null) {
            return null;
        }
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }

    /**
     * 解析失败一律返回 null 而不是抛异常。
     *
     * 这些解析只服务于"把提交记录和上游运行对上"这件**尽力而为**的事；
     * 让一次本来成功的审查因为记录不上而变成错误响应，是本末倒置。
     */
    private JsonNode parse(byte[] payload) {
        if (payload == null || payload.length == 0) {
            return null;
        }
        try {
            return mapper.readTree(new String(payload, StandardCharsets.UTF_8));
        } catch (IOException ex) {
            return null;
        }
    }

    private AuthPrincipal currentPrincipal() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return null;
        }
        return auth.getPrincipal() instanceof AuthPrincipal principal ? principal : null;
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
