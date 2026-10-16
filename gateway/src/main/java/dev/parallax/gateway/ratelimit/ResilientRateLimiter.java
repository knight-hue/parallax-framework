package dev.parallax.gateway.ratelimit;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;

import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.observability.ParallaxMetrics;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

/**
 * 带降级的限流器：优先 Redis，Redis 不可用时回退内存桶。
 *
 * **这是 C3 里最关键的一条**。分布式限流最常见的失败方式是：
 * Redis 一挂，整个网关跟着不可用——限流是保护手段，不该成为单点。
 * 因此这里的行为是"限流精度下降，但服务继续提供服务"。
 *
 * 三个细节：
 * - **冷却期**：首次失败后 N 秒内直接用内存桶，不再逐请求去试 Redis。
 *   没有冷却的话，Redis 挂掉时每个请求都要先等一次命令超时，
 *   降级就从"服务仍可用"变成"每个请求多花 250ms"。
 * - **不吞异常地降级**：{@link RateLimiter#tryConsume} 抛出的异常在这里被捕获，
 *   但读作"后端不可用"，而不是"应当拒绝请求"。把限流器故障当成超限，
 *   会让一次 Redis 抖动变成全站 429。
 * - **降级计数**：暴露给可观测性，因为"一直在降级"必须能被发现，
 *   否则配额会悄悄退化成单实例口径。
 */
@Component
public class ResilientRateLimiter implements RateLimiter {

    private static final Logger log = LoggerFactory.getLogger(ResilientRateLimiter.class);

    /** 降级日志的最小间隔，避免 Redis 挂掉时刷屏把真正的错误挤掉。 */
    private static final Duration LOG_INTERVAL = Duration.ofSeconds(30);

    private final RateLimiter primary;
    private final InMemoryRateLimiter fallback;
    private final ParallaxMetrics metrics;
    private final Duration cooldown;
    private final AtomicLong fallbackCount = new AtomicLong();
    private final AtomicLong failureCount = new AtomicLong();

    private volatile Instant skipPrimaryUntil = Instant.EPOCH;
    private volatile Instant lastLogAt = Instant.EPOCH;

    public ResilientRateLimiter(
            ObjectProvider<RedisRateLimiter> redis,
            InMemoryRateLimiter fallback,
            ParallaxProperties props,
            ParallaxMetrics metrics) {
        // 没配 Redis 时 primary 为 null——这条路径是"单实例部署"，不是"降级"
        this.primary = redis.getIfAvailable();
        this.fallback = fallback;
        this.metrics = metrics;
        this.cooldown = Duration.ofSeconds(props.getRatelimit().getDegradedCooldownSeconds());
    }

    @Override
    public boolean tryConsume(String key, BucketSpec spec) {
        if (primary == null) {
            return fallback.tryConsume(key, spec);
        }
        if (Instant.now().isBefore(skipPrimaryUntil)) {
            fallbackCount.incrementAndGet();
            return fallback.tryConsume(key, spec);
        }
        try {
            return primary.tryConsume(key, spec);
        } catch (RuntimeException ex) {
            degrade(ex);
            fallbackCount.incrementAndGet();
            return fallback.tryConsume(key, spec);
        }
    }

    private void degrade(RuntimeException ex) {
        failureCount.incrementAndGet();
        skipPrimaryUntil = Instant.now().plus(cooldown);
        metrics.rateLimitDegraded();
        Instant now = Instant.now();
        if (Duration.between(lastLogAt, now).compareTo(LOG_INTERVAL) >= 0) {
            lastLogAt = now;
            log.warn(
                    "Redis 限流后端不可用，已降级为内存桶（{} 秒内不再尝试）：{}。"
                            + "服务继续提供，但多实例之间的配额不再合并计算。",
                    cooldown.toSeconds(),
                    ex.toString());
        }
    }

    /** 累计降级次数。可观测性据此告警。 */
    public long degradedAttempts() {
        return fallbackCount.get();
    }

    /** 触发降级的失败次数（与降级次数不同：冷却期内不会产生新的失败）。 */
    public long backendFailures() {
        return failureCount.get();
    }

    public boolean isDegraded() {
        return primary != null && Instant.now().isBefore(skipPrimaryUntil);
    }

    /** 是否配置了分布式后端。false 表示这是单实例部署，不是降级。 */
    public boolean hasDistributedBackend() {
        return primary != null;
    }

    /** 测试用：清掉冷却，让下一次调用重新尝试 Redis。 */
    void resetCooldown() {
        skipPrimaryUntil = Instant.EPOCH;
    }
}
