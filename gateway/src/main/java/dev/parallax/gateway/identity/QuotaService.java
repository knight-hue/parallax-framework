package dev.parallax.gateway.identity;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.runs.AuditRunRepository;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 配额校验与记账。
 *
 * **校验发生在转发之前**，不是之后。事后扣减的实现看起来一样能"记账"，
 * 但用户会在额度已经用完的情况下继续烧掉真实模型费用——那正是配额要防的事。
 *
 * 已知局限（写在这里而不是文档里，因为改这里的人必须知道）：
 * 校验与记账之间存在**竞态窗口**：并发提交的多个请求可能同时通过校验。
 * 当前刻意不做分布式锁，理由与不做跨进程队列相同——见「任务总表」第 7 节。
 */
@Service
public class QuotaService {

    private final ApiCredentialRepository credentials;
    private final UsageLedgerRepository ledger;
    private final AuditRunRepository runs;

    public QuotaService(
            ApiCredentialRepository credentials, UsageLedgerRepository ledger, AuditRunRepository runs) {
        this.credentials = credentials;
        this.ledger = ledger;
        this.runs = runs;
    }

    /** 某个时间窗口内已用了多少。 */
    public record Usage(long runs, long tokens) {
    }

    /** 一次额度判定，同时是 429 响应体的来源。 */
    public record Decision(boolean allowed, String metric, long used, long limit, Instant resetsAt) {

        public static Decision allow() {
            return new Decision(true, null, 0, 0, null);
        }

        public Map<String, Object> asBody() {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("success", false);
            body.put("error", "额度已用尽，请稍后再试或申请提高配额");
            Map<String, Object> quota = new LinkedHashMap<>();
            quota.put("metric", metric);
            quota.put("used", used);
            quota.put("limit", limit);
            quota.put("resetsAt", resetsAt == null ? null : resetsAt.toString());
            body.put("quota", quota);
            return body;
        }
    }

    /** 自然日窗口：按 UTC 零点切分。用 UTC 而非服务器本地时区，避免迁移机器时额度突然重置。 */
    public static Instant startOfUtcDay(Instant now) {
        return ZonedDateTime.ofInstant(now, ZoneOffset.UTC).toLocalDate().atStartOfDay(ZoneOffset.UTC).toInstant();
    }

    public static Instant startOfUtcMonth(Instant now) {
        return ZonedDateTime.ofInstant(now, ZoneOffset.UTC)
                .withDayOfMonth(1)
                .toLocalDate()
                .atStartOfDay(ZoneOffset.UTC)
                .toInstant();
    }

    public static Instant endOfUtcDay(Instant now) {
        return startOfUtcDay(now).plusSeconds(86_400);
    }

    @Transactional(readOnly = true)
    public Decision check(String credentialId, Instant now) {
        ApiCredential credential = credentials
                .findWithQuotaById(credentialId)
                .orElseThrow(() -> ApiException.unauthorized("凭据不存在或已吊销"));
        if (credential.isRevoked()) {
            throw ApiException.unauthorized("凭据不存在或已吊销");
        }
        QuotaPolicy policy = credential.getQuotaPolicy();

        // 运行次数按**提交**计数，不是按完成计数：
        // 只统计完成的话，用户能在第一次完成之前并发提交上千次，
        // 每次都真实烧掉模型费用——那正是配额要防的事。
        long dayRuns = runs.countByCredentialIdAndSubmittedAtGreaterThanEqual(
                credentialId, startOfUtcDay(now));
        if (dayRuns >= policy.getDailyRunLimit()) {
            return new Decision(false, "daily_runs", dayRuns, policy.getDailyRunLimit(), endOfUtcDay(now));
        }

        long dayTokens = ledger.sumTokensSince(credentialId, startOfUtcDay(now));
        if (dayTokens >= policy.getDailyTokenLimit()) {
            return new Decision(false, "daily_tokens", dayTokens, policy.getDailyTokenLimit(), endOfUtcDay(now));
        }

        long monthTokens = ledger.sumTokensSince(credentialId, startOfUtcMonth(now));
        if (monthTokens >= policy.getMonthlyTokenLimit()) {
            return new Decision(
                    false,
                    "monthly_tokens",
                    monthTokens,
                    policy.getMonthlyTokenLimit(),
                    startOfUtcMonth(now).atOffset(ZoneOffset.UTC).plusMonths(1).toInstant());
        }
        return Decision.allow();
    }

    @Transactional(readOnly = true)
    public Usage usageOf(String credentialId, Instant since) {
        long runs = this.runs.countByCredentialIdAndSubmittedAtGreaterThanEqual(credentialId, since);
        long tokens = ledger.sumTokensSince(credentialId, since);
        return new Usage(runs, tokens);
    }

    /**
     * 记一笔账。**幂等**：同一次运行重复回调不会重复计费。
     *
     * @return true 表示这次真的写入了（首次回调），false 表示此前已记过
     */
    @Transactional
    public boolean record(String credentialId, String runId, long promptTokens, long completionTokens, String traceId) {
        if (ledger.existsByRunId(runId)) {
            return false;
        }
        ledger.save(new UsageLedgerEntry(credentialId, runId, promptTokens, completionTokens, traceId));
        return true;
    }

    /** 抛出 429 并带上已用量与上限，让调用方能自己算出还要等多久。 */
    public static ApiException toException(Decision decision) {
        return new QuotaApiException(decision);
    }

    /** 带入额度细节的 429。单独一个类型是为了让异常处理器能取到结构化字段。 */
    public static class QuotaApiException extends ApiException {

        private final transient Decision decision;

        QuotaApiException(Decision decision) {
            super(HttpStatus.TOO_MANY_REQUESTS, "额度已用尽");
            this.decision = decision;
        }

        public Decision getDecision() {
            return decision;
        }
    }
}
