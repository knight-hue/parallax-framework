package dev.parallax.gateway.ratelimit;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

import io.github.bucket4j.Bucket;

/**
 * 单实例内存令牌桶。
 *
 * 也是 **Redis 不可用时的降级实现**——所以它必须始终存在、始终可用，
 * 不能因为"配了 Redis 就用不到它"而删掉。
 */
@Component
public class InMemoryRateLimiter implements RateLimiter {

    /** 防内存膨胀。键里含 IP，不加限制的话大量不同来源会把它撑爆。 */
    private static final int MAX_BUCKETS = 50_000;

    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    public boolean tryConsume(String key, BucketSpec spec) {
        String composite = spec.capacity() + ":" + spec.window().toSeconds() + "|" + key;

        // 重置必须在 computeIfAbsent 之外：在映射函数里改 Map 会让 JDK 抛
        // ConcurrentModificationException。代价是清空后桶会重新计数，
        // 这是有意的——宁可短暂多放行，也不愿因为内存保护把服务拖垮。
        if (buckets.size() > MAX_BUCKETS) {
            buckets.clear();
        }
        Bucket bucket = buckets.computeIfAbsent(composite, ignored -> build(spec));
        return bucket.tryConsume(1);
    }

    private Bucket build(BucketSpec spec) {
        return Bucket.builder()
                .addLimit(limit -> limit.capacity(spec.capacity())
                        .refillGreedy(spec.capacity(), spec.window()))
                .build();
    }

    /** 供测试断言"降级后确实换了桶"。 */
    public int bucketCount() {
        return buckets.size();
    }

    public void clear() {
        buckets.clear();
    }
}
