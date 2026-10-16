package dev.parallax.gateway.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;

import org.springframework.stereotype.Component;

/**
 * 网关的业务指标。
 *
 * 只暴露**能被拿来决策**的三个量，不做"把什么都埋一遍"：
 * - `parallax_runs_total{status}`：运行成败分布。失败率突然抬头就该有人知道；
 * - `parallax_tokens_total{credential}`：token 消耗。这是成本，也是配额的现实依据；
 * - `parallax_quota_rejections_total{metric}`：被配额挡下的次数。
 *   这个数长期为 0 说明额度形同虚设，长期很大说明额度定得不合理——
 *   两种都需要人来判断，所以它必须先存在。
 *
 * **基数警告**：`credential` 标签的取值集合必须有限。凭据由管理员创建，
 * 不是用户自助注册，因此天然有界。若将来开放自助注册，这里必须改成
 * 按配额策略或租户分级打标签，否则 Prometheus 的时间序列会被打爆。
 */
@Component
public class ParallaxMetrics {

    private static final String RUNS = "parallax.runs";
    private static final String TOKENS = "parallax.tokens";
    private static final String QUOTA_REJECTIONS = "parallax.quota.rejections";
    private static final String RATELIMIT_DEGRADED = "parallax.ratelimit.degraded";

    private final MeterRegistry registry;

    public ParallaxMetrics(MeterRegistry registry) {
        this.registry = registry;
        // 预先注册零值：指标在第一次事件发生前就该可查，否则"没有曲线"
        // 与"还没有事件"看起来一样，正好错过最该告警的那段时间。
        for (String status : new String[] {"queued", "done", "failed"}) {
            Counter.builder(RUNS).tag("status", status).register(registry);
        }
        for (String metric : new String[] {"daily_runs", "daily_tokens", "monthly_tokens"}) {
            Counter.builder(QUOTA_REJECTIONS).tag("metric", metric).register(registry);
        }
        // 降级计数同样要预注册。第一次写这个测试时它没有预注册，
        // 于是"从没降级过"与"降级指标根本没接上"在 /actuator/prometheus 上完全一样——
        // 这与本类开头写的原则是同一条，只是当时漏了这一项。
        Counter.builder(RATELIMIT_DEGRADED).register(registry);
    }

    /** 一次运行走到终态。 */
    public void runFinished(String status) {
        Counter.builder(RUNS).tag("status", status).register(registry).increment();
    }

    /** 一次运行消耗的 token。由完成回调驱动，因此与账本是同一份事实。 */
    public void tokensUsed(String credentialId, long totalTokens) {
        if (totalTokens <= 0) {
            return;
        }
        Counter.builder(TOKENS)
                .tag("credential", credentialId == null ? "unknown" : credentialId)
                .register(registry)
                .increment(totalTokens);
    }

    /** 提交被配额挡下。 */
    public void quotaRejected(String metric) {
        Counter.builder(QUOTA_REJECTIONS)
                .tag("metric", metric == null ? "unknown" : metric)
                .register(registry)
                .increment();
    }

    /** 限流后端降级到内存桶。持续增长意味着分布式配额已经失效，需要有人处理。 */
    public void rateLimitDegraded() {
        Counter.builder(RATELIMIT_DEGRADED).register(registry).increment();
    }
}
