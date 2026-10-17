package dev.parallax.gateway.runs;

import java.util.Optional;
import java.util.UUID;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.common.TraceFilter;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.observability.ParallaxMetrics;

import org.slf4j.Logger;import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 运行记录的写入。
 *
 * 只在两个时点被调用：代理提交审查时落 `queued`，完成回调时补统计。
 * 不做任何编排——编排是 Python 编排服务的事，这里只记录"发生了什么"。
 */
@Service
public class RunService {

    private static final Logger log = LoggerFactory.getLogger(RunService.class);

    private final AuditRunRepository runs;
    private final AuditEventRepository events;
    private final ParallaxProperties props;
    private final ParallaxMetrics metrics;

    public RunService(
            AuditRunRepository runs,
            AuditEventRepository events,
            ParallaxProperties props,
            ParallaxMetrics metrics) {
        this.runs = runs;
        this.events = events;
        this.props = props;
        this.metrics = metrics;
    }

    /**
     * 记录一次提交尝试。
     *
     * **在转发之前调用**：无论上游成功与否，这次尝试都已经发生了。
     * 若等成功后再记，用户可以对一个总是失败的上游无限次重试而不消耗额度。
     */
    @Transactional
    public String registerSubmission(String credentialId, String repoPath, String question) {
        if (!props.getIdentity().isEnabled() || credentialId == null || credentialId.isBlank()) {
            return null;
        }
        String traceId = TraceFilter.currentTraceId();
        AuditRun run = new AuditRun(
                UUID.randomUUID().toString(),
                credentialId,
                truncate(repoPath, 1024),
                truncate(question, 2000),
                traceId);
        runs.save(run);
        events.save(new AuditEvent(
                run.getId(), AuditEvent.SUBMITTED, "已接受提交，等待转发到编排服务", traceId));
        return run.getId();
    }

    /**
     * 拿到上游 run_id 后回填。
     *
     * 两种失败都不该影响转发结果——记录是尽力而为，转发才是本职：
     * - 提交记录不存在（网关重启过）：记 WARN 后跳过；
     * - 该 run_id 已被另一条提交记录占用：说明上游返回了重复 id，
     *   这是数据异常而不是客户端错误。直接跳过并记 WARN，
     *   否则一次本来成功的审查会因为记录不上而变成 500。
     */
    @Transactional
    public void attachUpstreamRunId(String submissionId, String upstreamRunId) {
        if (submissionId == null || upstreamRunId == null || upstreamRunId.isBlank()) {
            return;
        }
        Optional<AuditRun> claimed = runs.findByRunId(upstreamRunId);
        if (claimed.isPresent()) {
            if (!claimed.get().getId().equals(submissionId)) {
                log.warn(
                        "上游 run_id={} 已被提交记录 {} 占用，跳过为 {} 回填",
                        upstreamRunId,
                        claimed.get().getId(),
                        submissionId);
            }
            return;
        }
        runs.findById(submissionId).ifPresentOrElse(
                run -> run.attachUpstreamRunId(upstreamRunId),
                () -> log.warn("提交记录 {} 不存在，无法回填上游 run_id", submissionId));
    }

    @Transactional
    public void markFailed(String submissionId, String failure) {
        if (submissionId == null) {
            return;
        }
        runs.findById(submissionId).ifPresent(run -> {
            run.markFailed(truncate(failure, 2000));
            events.save(new AuditEvent(
                    run.getId(), AuditEvent.FAILED, truncate(failure, 1024), run.getTraceId()));
            metrics.runFinished(RunStatus.FAILED);
        });
    }

    /**
     * 完成回调写入统计。
     *
     * 找不到对应提交记录时会**新建一条**而不是报错：网关可能在运行期间重启过，
     * 而"这次运行确实发生了、确实花了钱"是比"我这边没有它的提交记录"更重要的事实。
     */
    @Transactional
    public AuditRun complete(
            String runId,
            String credentialId,
            String status,
            long promptTokens,
            long completionTokens,
            Double elapsedS,
            String countsJson,
            String stopReason) {
        Optional<AuditRun> existing = runs.findByRunId(runId);
        AuditRun run = existing.orElseGet(() -> {
            log.warn("完成回调找不到提交记录 run_id={}，按凭据 {} 补建一条", runId, credentialId);
            AuditRun created = new AuditRun(UUID.randomUUID().toString(), credentialId, null, null, null);
            created.attachUpstreamRunId(runId);
            return created;
        });
        run.complete(
                status,
                promptTokens,
                completionTokens,
                elapsedS,
                truncate(countsJson, 1024),
                truncate(stopReason, 64));
        AuditRun saved = runs.save(run);
        // 事件按**网关提交记录 id** 归档，而不是上游 run_id：
        // 提交那一刻还不知道上游 id，而"提交"这条事件必须立刻可查。
        // 上游 id 写进 detail 里做交叉引用，详情接口拿到 run 后再按提交 id 取事件。
        events.save(new AuditEvent(
                run.getId(),
                RunStatus.FAILED.equals(status)
                        ? AuditEvent.FAILED
                        : RunStatus.CANCELED.equals(status) ? AuditEvent.CANCELED : AuditEvent.COMPLETED,
                "上游 run_id=" + runId + "，用量 " + (promptTokens + completionTokens)
                        + " tokens，状态 " + status,
                run.getTraceId()));
        metrics.runFinished(status);
        metrics.tokensUsed(credentialId, promptTokens + completionTokens);
        return saved;
    }

    @Transactional(readOnly = true)
    public Optional<AuditRun> find(String runId) {
        return runs.findByRunId(runId);
    }

    @Transactional(readOnly = true)
    public Optional<AuditRun> findById(String id) {
        return runs.findById(id);
    }

    /** 上报里带了未知状态就拒绝，而不是把脏数据写进库。 */
    public static String requireKnownStatus(String status) {
        if (status == null || status.isBlank()) {
            throw ApiException.badRequest("status 必填");
        }
        if (!RunStatus.isKnown(status)) {
            throw ApiException.badRequest("未知的运行状态：" + status);
        }
        return status;
    }

    static String truncate(String value, int max) {
        if (value == null || value.length() <= max) {
            return value;
        }
        return value.substring(0, max);
    }
}
