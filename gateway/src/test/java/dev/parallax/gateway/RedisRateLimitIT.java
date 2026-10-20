package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.observability.ParallaxMetrics;
import dev.parallax.gateway.ratelimit.BucketSpec;
import dev.parallax.gateway.ratelimit.InMemoryRateLimiter;
import dev.parallax.gateway.ratelimit.RedisRateLimiter;
import dev.parallax.gateway.ratelimit.ResilientRateLimiter;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;

/**
 * **真实 Redis** 上的分布式限流与降级测试。
 *
 * 两个必须被证明的命题：
 *
 * 1. **跨实例合并计算**：两个网关实例共享同一份配额。
 *    这正是引入 Redis 的唯一理由——只测单实例的话，内存实现也能通过。
 * 2. **Redis 挂了服务仍可用**：限流是保护手段，不该成为单点。
 *    这是 C3 里最关键的一条，也是内存桩无法替代验证的一条。
 *
 * 不拉起 Spring 上下文：这里要验证的是限流器本身的行为，
 * 拉整条 Web 栈只会让"到底哪一层坏了"变模糊。
 */
@Testcontainers(disabledWithoutDocker = true)
class RedisRateLimitIT {

    private static final int REDIS_PORT = 6379;
    private static final AtomicInteger BUCKET_SEQ = new AtomicInteger();

    @SuppressWarnings("resource") // 生命周期由 @Container（Testcontainers JUnit 扩展）托管，IDE 的"资源未关闭"是误报
    @Container
    static final GenericContainer<?> REDIS =
            new GenericContainer<>(DockerImageName.parse(
                    System.getProperty("parallax.test.redis-image", "redis:7-alpine")))
                    .withImagePullPolicy(image -> false).withExposedPorts(REDIS_PORT);

    private static String redisUrl() {
        return "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(REDIS_PORT);
    }

    /** 指向一个已关闭的端口，用来模拟"Redis 挂了"而不必真的停共享容器。 */
    private static String deadRedisUrl() {
        return "redis://127.0.0.1:1";
    }

    private static ParallaxProperties props(String url, int cooldownSeconds) {
        ParallaxProperties props = new ParallaxProperties();
        props.getRatelimit().setRedisUrl(url);
        props.getRatelimit().setRedisTimeoutMs(300);
        props.getRatelimit().setDegradedCooldownSeconds(cooldownSeconds);
        return props;
    }

    /** 每个用例用自己的桶键，避免用例之间互相消耗配额。 */
    private static String freshKey(String prefix) {
        return prefix + "-" + BUCKET_SEQ.incrementAndGet();
    }

    private static ParallaxMetrics metrics() {
        return new ParallaxMetrics(new SimpleMeterRegistry());
    }

    private static ResilientRateLimiter resilient(
            RedisRateLimiter redis, InMemoryRateLimiter fallback, ParallaxProperties props) {
        return new ResilientRateLimiter(new FixedProvider<>(redis), fallback, props, metrics());
    }

    // ---- 跨实例合并计算 ----

    @Test
    void twoInstancesShareTheSameQuota() {
        ParallaxProperties props = props(redisUrl(), 30);
        RedisRateLimiter instanceA = new RedisRateLimiter(props);
        RedisRateLimiter instanceB = new RedisRateLimiter(props);
        try {
            BucketSpec spec = new BucketSpec(4, Duration.ofMinutes(10));
            String key = freshKey("shared");

            // 两个实例各消耗 2 个：各自看都"没超"，合并才刚好用满
            assertThat(instanceA.tryConsume(key, spec)).isTrue();
            assertThat(instanceA.tryConsume(key, spec)).isTrue();
            assertThat(instanceB.tryConsume(key, spec)).isTrue();
            assertThat(instanceB.tryConsume(key, spec)).isTrue();

            assertThat(instanceB.tryConsume(key, spec))
                    .as("配额是合并计算的：A 用掉的额度必须对 B 可见")
                    .isFalse();
            assertThat(instanceA.tryConsume(key, spec)).as("反过来也成立").isFalse();
        } finally {
            instanceA.shutdown();
            instanceB.shutdown();
        }
    }

    @Test
    void redisBackendIsReachable() {
        RedisRateLimiter limiter = new RedisRateLimiter(props(redisUrl(), 30));
        try {
            assertThat(limiter.ping()).isTrue();
        } finally {
            limiter.shutdown();
        }
    }

    /**
     * 构造限流器**不能**连 Redis：否则 Redis 没就绪时网关会整体启动失败。
     * 服务因为一个可选组件而起不来，比限流精度下降严重得多。
     */
    @Test
    void constructingWithUnreachableRedisDoesNotThrow() {
        RedisRateLimiter limiter = new RedisRateLimiter(props(deadRedisUrl(), 30));
        limiter.shutdown();
    }

    // ---- 降级 ----

    @Test
    void unusableRedisDegradesToInMemoryAndLimitingStillWorks() {
        ParallaxProperties props = props(deadRedisUrl(), 30);
        RedisRateLimiter dead = new RedisRateLimiter(props);
        ResilientRateLimiter limiter = resilient(dead, new InMemoryRateLimiter(), props);
        try {
            BucketSpec spec = new BucketSpec(3, Duration.ofMinutes(10));
            String key = freshKey("degraded");

            // 前 3 次由内存桶放行，第 4 次被内存桶挡下。
            // 关键点：**没有任何一次因为 Redis 挂了而失败**。
            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.tryConsume(key, spec)).as("降级后限流仍然生效，不是形同虚设").isFalse();

            assertThat(limiter.isDegraded()).isTrue();
            assertThat(limiter.backendFailures())
                    .as("冷却期内不再逐请求试 Redis，因此只应产生一次失败")
                    .isEqualTo(1);
            assertThat(limiter.degradedAttempts()).isGreaterThanOrEqualTo(3);
        } finally {
            dead.shutdown();
        }
    }

    /** 冷却期结束后必须重新尝试主后端——否则 Redis 恢复后也永远回不来。 */
    @Test
    void afterCooldownItRetriesTheRedisBackend() throws Exception {
        ParallaxProperties props = props(deadRedisUrl(), 1);
        RedisRateLimiter dead = new RedisRateLimiter(props);
        ResilientRateLimiter limiter = resilient(dead, new InMemoryRateLimiter(), props);
        try {
            BucketSpec spec = new BucketSpec(10, Duration.ofMinutes(10));
            String key = freshKey("retry");

            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.backendFailures()).isEqualTo(1);

            Thread.sleep(1_200); // 越过 1 秒冷却

            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.backendFailures())
                    .as("冷却结束后应当再次尝试 Redis（仍然失败，所以计数增加）")
                    .isEqualTo(2);
        } finally {
            dead.shutdown();
        }
    }

    /** 健康后端不应被误判为降级。 */
    @Test
    void healthyRedisIsNotDegraded() {
        ParallaxProperties props = props(redisUrl(), 1);
        RedisRateLimiter healthy = new RedisRateLimiter(props);
        ResilientRateLimiter limiter = resilient(healthy, new InMemoryRateLimiter(), props);
        try {
            BucketSpec spec = new BucketSpec(2, Duration.ofMinutes(10));
            String key = freshKey("healthy");

            assertThat(limiter.tryConsume(key, spec)).isTrue();
            assertThat(limiter.isDegraded()).isFalse();
            assertThat(limiter.backendFailures()).isZero();
            assertThat(limiter.degradedAttempts()).isZero();
        } finally {
            healthy.shutdown();
        }
    }

    /** 没配 Redis 的部署走的是"单实例"，不是"降级"，两者不能混为一谈。 */
    @Test
    void withoutRedisConfiguredItIsSingleInstanceNotDegraded() {
        ParallaxProperties props = new ParallaxProperties();
        InMemoryRateLimiter inMemory = new InMemoryRateLimiter();
        ResilientRateLimiter limiter =
                new ResilientRateLimiter(new FixedProvider<RedisRateLimiter>(null), inMemory, props, metrics());

        BucketSpec spec = new BucketSpec(1, Duration.ofMinutes(10));
        assertThat(limiter.tryConsume(freshKey("single"), spec)).isTrue();
        assertThat(limiter.hasDistributedBackend()).isFalse();
        assertThat(limiter.isDegraded()).as("没有分布式后端 ≠ 降级").isFalse();
    }

    // ---- 工具 ----

    /** 固定返回某个实例的 provider，让测试不必拉起 Spring 上下文。 */
    private static final class FixedProvider<T> implements ObjectProvider<T> {

        private final T value;

        FixedProvider(T value) {
            this.value = value;
        }

        @Override
        public T getObject() {
            if (value == null) {
                throw new IllegalStateException("no bean");
            }
            return value;
        }

        @Override
        public T getObject(Object... args) {
            return getObject();
        }

        @Override
        public T getIfAvailable() {
            return value;
        }

        @Override
        public T getIfUnique() {
            return value;
        }
    }
}
