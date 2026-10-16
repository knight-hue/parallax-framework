package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.ratelimit.InMemoryRateLimiter;
import dev.parallax.gateway.ratelimit.RedisRateLimiter;
import dev.parallax.gateway.ratelimit.ResilientRateLimiter;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.ActiveProfiles;

/**
 * 限流后端的装配。
 *
 * 存在的理由是一个**真实踩到过**的坑：`application.yml` 里
 * `redis-url: ${PARALLAX_RATELIMIT_REDIS_URL:}` 会让属性存在但为空串，
 * 而 `@ConditionalOnProperty` 把空串视为"匹配"——于是 `RedisClient.create("")`
 * 抛出 `URI must not be empty`，**整个应用起不来**。
 * 这种失败在没配 Redis 的所有部署上都会发生，所以必须有测试守住。
 */
@SpringBootTest
@ActiveProfiles("test")
class RateLimiterWiringTest {

    @Autowired
    private ApplicationContext context;

    @Autowired
    private ResilientRateLimiter limiter;

    @Test
    void emptyRedisUrlMeansNoRedisBackendAndApplicationStillStarts() {
        assertThat(context.getBeanNamesForType(RedisRateLimiter.class))
                .as("空地址不应创建 Redis 后端")
                .isEmpty();
        assertThat(limiter.hasDistributedBackend())
                .as("没配 Redis 是「单实例部署」，不是「降级」")
                .isFalse();
    }

    @Test
    void inMemoryLimiterIsAlwaysPresentBecauseItIsTheFallback() {
        assertThat(context.getBeanNamesForType(InMemoryRateLimiter.class))
                .as("降级实现不能因为「配了 Redis 就用不到」而被删掉")
                .hasSize(1);
    }

    @Test
    void limiterStillEnforcesLimitsWithoutAnyBackendConfiguration() {
        ParallaxProperties props = new ParallaxProperties();
        InMemoryRateLimiter fallback = new InMemoryRateLimiter();
        ResilientRateLimiter local =
                new ResilientRateLimiter(new EmptyProvider<>(), fallback, props, noopMetrics());

        var spec = new dev.parallax.gateway.ratelimit.BucketSpec(2, java.time.Duration.ofMinutes(1));
        assertThat(local.tryConsume("key", spec)).isTrue();
        assertThat(local.tryConsume("key", spec)).isTrue();
        assertThat(local.tryConsume("key", spec)).as("默认部署也必须真的限流").isFalse();
    }

    private static dev.parallax.gateway.observability.ParallaxMetrics noopMetrics() {
        return new dev.parallax.gateway.observability.ParallaxMetrics(
                new io.micrometer.core.instrument.simple.SimpleMeterRegistry());
    }

    /** 完全没有该类型 bean 的 provider，模拟"没配 Redis"。 */
    private static final class EmptyProvider<T>
            implements org.springframework.beans.factory.ObjectProvider<T> {

        @Override
        public T getObject() {
            throw new IllegalStateException("no bean");
        }

        @Override
        public T getObject(Object... args) {
            return getObject();
        }

        @Override
        public T getIfAvailable() {
            return null;
        }

        @Override
        public T getIfUnique() {
            return null;
        }
    }
}
