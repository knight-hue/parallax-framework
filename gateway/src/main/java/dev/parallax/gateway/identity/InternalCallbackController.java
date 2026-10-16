package dev.parallax.gateway.identity;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.common.TraceFilter;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.runs.RunService;
import dev.parallax.gateway.runs.RunStatus;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

/**
 * 编排服务的完成回调：一次运行结束后把用量写进账本。
 *
 * **为什么需要这个端点**：配额要在**提交前**校验，而真实 token 用量只有跑完才知道。
 * 两者只能靠"提交时记一笔待运行、完成时补记用量"衔接。把用量写在 Python 侧的
 * `meta.json` 里而不回传，网关的账本就会长期停留在 0——报表和实际对不上。
 *
 * 安全：用 `X-Internal-Token` 与网关共享的密钥校验。这个端点**不能**对公网开放，
 * 否则任何人都能伪造用量记录去"帮别人"耗尽额度，或者把自己的额度洗干净。
 */
@RestController
public class InternalCallbackController {

    private static final Logger log = LoggerFactory.getLogger(InternalCallbackController.class);

    private final QuotaService quota;
    private final ApiKeyService apiKeys;
    private final RunService runService;
    private final ParallaxProperties props;

    public InternalCallbackController(
            QuotaService quota, ApiKeyService apiKeys, RunService runService, ParallaxProperties props) {
        this.quota = quota;
        this.apiKeys = apiKeys;
        this.runService = runService;
        this.props = props;
    }

    public record CompletionRequest(
            @NotBlank String credentialId,
            @Min(0) long promptTokens,
            @Min(0) long completionTokens,
            String status,
            Double elapsedS,
            String stopReason,
            String countsJson,
            String traceId) {

        /** 省略 status 时按"正常完成"处理：多数调用方只关心用量。 */
        String resolvedStatus() {
            return status == null || status.isBlank() ? RunStatus.DONE : status;
        }
    }

    public record CompletionResponse(
            String runId, boolean recorded, String credentialId, String status, Instant occurredAt) {
    }

    @PostMapping("/api/v1/internal/runs/{runId}/complete")
    public CompletionResponse complete(
            @PathVariable String runId,
            @RequestHeader(value = "X-Internal-Token", required = false) String internalToken,
            @RequestBody @Valid CompletionRequest request) {

        requireInternalToken(internalToken);
        if (!props.getIdentity().isEnabled()) {
            throw new ApiException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未启用身份与配额（PARALLAX_IDENTITY_ENABLED=false），不接受完成回调");
        }
        // 显式校验而不是交给外键去报错：外键冲突会变成 500，
        // 而这里明明是调用方传错了 id，应该是 400。
        if (apiKeys.list().stream().noneMatch(c -> c.getId().equals(request.credentialId()))) {
            throw ApiException.badRequest("凭据不存在：" + request.credentialId());
        }

        // trace 优先用调用方显式传入的；缺失时沿用本次请求的网关 traceId，
        // 这样即使 Python 侧还没升级，两端日志也能靠这一层的 trace 串起来
        String traceId = request.traceId() == null || request.traceId().isBlank()
                ? TraceFilter.currentTraceId()
                : request.traceId();

        // 先补运行记录与统计（这一步必须做，无论账本是否已记过），再写账本
        String status = RunService.requireKnownStatus(request.resolvedStatus());
        runService.complete(
                runId,
                request.credentialId(),
                status,
                request.promptTokens(),
                request.completionTokens(),
                request.elapsedS(),
                request.countsJson(),
                request.stopReason());

        boolean recorded = quota.record(
                request.credentialId(), runId, request.promptTokens(), request.completionTokens(), traceId);

        if (!recorded) {
            // 不是错误：完成回调本来就可能被重投。记 INFO 而不是 WARN，
            // 否则正常的幂等重试会被当成异常刷屏。
            log.info("完成回调重复投递，已忽略记账 run_id={} credential={}", runId, request.credentialId());
        } else {
            log.info(
                    "用量已记账 run_id={} credential={} tokens={} trace={}",
                    runId,
                    request.credentialId(),
                    request.promptTokens() + request.completionTokens(),
                    traceId);
        }
        return new CompletionResponse(runId, recorded, request.credentialId(), status, Instant.now());
    }

    /** 定长比较，避免用 equals 泄漏逐字节的时序信息。 */
    private void requireInternalToken(String provided) {
        String expected = props.getGateway().getInternalToken();
        if (expected == null || expected.isBlank()) {
            throw new ApiException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未配置 PARALLAX_GATEWAY_INTERNAL_TOKEN，完成回调不可用");
        }
        if (provided == null
                || !MessageDigest.isEqual(
                        expected.getBytes(StandardCharsets.UTF_8),
                        provided.trim().getBytes(StandardCharsets.UTF_8))) {
            throw ApiException.unauthorized("内部令牌不正确");
        }
    }
}
