package dev.parallax.gateway.ratelimit;

/**
 * 限流器的实现接口。
 *
 * 抽出接口的目的不是"将来可能换实现"，而是**两个实现要能同时存在**：
 * 单实例用内存桶，多实例用 Redis 桶，而 Redis 不可用时要能回退到内存桶。
 * 把选择逻辑收在 {@link ResilientRateLimiter} 里，过滤器不需要知道用的是哪个。
 */
public interface RateLimiter {

    /**
     * 尝试消耗一个令牌。
     *
     * @return true 表示放行；false 表示超出速率
     * @throws RuntimeException 后端不可用时抛出，由上层决定是否降级。
     *                          刻意不在这里吞掉：吞掉的话"限流器坏了"会变成
     *                          "所有请求都被限"，而正确行为应当是降级而不是拒绝服务。
     */
    boolean tryConsume(String key, BucketSpec spec);
}
