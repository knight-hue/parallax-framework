package dev.parallax.gateway.runs;

import java.time.Instant;
import java.util.List;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 运行历史。
 *
 * 可见性按主体分档，且**在服务端强制**，不靠调用方自觉：
 * - ADMIN 可查全部，可按任意凭据过滤；
 * - 凭据持有者只能查自己的——即使它在 URL 里传了别人的 credentialId，
 *   也会被改写成自己的。接受参数而不是直接拒绝，是因为"越权查询"和"没查到"
 *   对外应当看起来一样，不给出"存在这个凭据"的旁证。
 */
@RestController
@RequestMapping("/api/v1/runs")
public class RunController {

    private final RunQueryService queries;
    private final ParallaxProperties props;

    public RunController(RunQueryService queries, ParallaxProperties props) {
        this.queries = queries;
        this.props = props;
    }

    public record UsageView(Long promptTokens, Long completionTokens, Long totalTokens) {
    }

    public record RunView(
            String id,
            String runId,
            String credentialId,
            String repoPath,
            String question,
            String status,
            Instant submittedAt,
            Instant finishedAt,
            Double elapsedS,
            String traceId,
            UsageView usage,
            String countsJson,
            String stopReason,
            String error) {
    }

    public record EventView(String type, Instant at, String detail, String traceId) {
    }

    /** 上游的编排细节仍在上游，这里只给出取用它们的地址，不复制一份事实。 */
    public record UpstreamLinks(String runUrl, String eventsUrl, String resultUrl, String reportUrl) {
    }

    public record RunDetail(RunView run, List<EventView> events, UpstreamLinks upstream) {
    }

    public record PageView<T>(List<T> items, int page, int size, long totalElements, int totalPages) {
    }

    @GetMapping
    public PageView<RunView> list(
            @AuthenticationPrincipal AuthPrincipal principal,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String credentialId,
            @RequestParam(required = false) Instant since,
            @RequestParam(required = false) Instant until,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {

        require();
        String scoped = scopedCredentialId(principal, credentialId);
        if (status != null && !status.isBlank() && !RunStatus.isKnown(status)) {
            throw ApiException.badRequest("未知的运行状态：" + status);
        }

        Page<AuditRun> found = queries.search(
                new RunQueryService.Filter(status, scoped, since, until), page, size);
        return new PageView<>(
                found.getContent().stream().map(RunController::toView).toList(),
                found.getNumber(),
                found.getSize(),
                found.getTotalElements(),
                found.getTotalPages());
    }

    @GetMapping("/{runId}")
    public RunDetail detail(@AuthenticationPrincipal AuthPrincipal principal, @PathVariable String runId) {
        require();
        AuditRun run = queries
                .findByRunId(runId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "未找到运行：" + runId));

        if (!isAdmin(principal) && !run.getCredentialId().equals(credentialIdOf(principal))) {
            // 用 404 而不是 403：403 会告诉对方"这个 run 存在，只是不给你看"
            throw new ApiException(HttpStatus.NOT_FOUND, "未找到运行：" + runId);
        }

        List<EventView> events = queries.eventsOf(run.getId()).stream()
                .map(e -> new EventView(e.getEventType(), e.getAt(), e.getDetail(), e.getTraceId()))
                .toList();
        return new RunDetail(toView(run), events, linksOf(runId));
    }

    private void require() {
        if (!props.getIdentity().isEnabled()) {
            throw new ApiException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未启用身份与配额（PARALLAX_IDENTITY_ENABLED=false），运行历史不可用");
        }
    }

    /** 非 ADMIN 只能看自己的：把请求里的 credentialId 直接改写掉，不做"先查再判"。 */
    private String scopedCredentialId(AuthPrincipal principal, String requested) {
        if (isAdmin(principal)) {
            return requested;
        }
        String mine = credentialIdOf(principal);
        if (mine == null) {
            throw ApiException.unauthorized("该端点需要认证（Bearer 令牌或 X-API-Key）");
        }
        return mine;
    }

    private static boolean isAdmin(AuthPrincipal principal) {
        return principal != null && AuthPrincipal.ROLE_ADMIN.equals(principal.role());
    }

    private static String credentialIdOf(AuthPrincipal principal) {
        return principal != null && principal.hasCredential() ? principal.credentialId() : null;
    }

    private static UpstreamLinks linksOf(String runId) {
        String base = "/api/v1/audits/" + runId;
        return new UpstreamLinks(base, base + "/events", base + "/result", base + "/report");
    }

    private static RunView toView(AuditRun run) {
        return new RunView(
                run.getId(),
                run.getRunId(),
                run.getCredentialId(),
                run.getRepoPath(),
                run.getQuestion(),
                run.getStatus(),
                run.getSubmittedAt(),
                run.getFinishedAt(),
                run.getElapsedS(),
                run.getTraceId(),
                new UsageView(run.getPromptTokens(), run.getCompletionTokens(), run.getTotalTokens()),
                run.getCountsJson(),
                run.getStopReason(),
                run.getError());
    }
}
