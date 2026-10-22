package dev.parallax.gateway.config;

import org.redisson.Redisson;
import org.redisson.api.RedissonClient;
import org.redisson.config.Config;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Conditional;

/**
 * Optional Redisson client for cache coordination.
 *
 * The client is created only when the cache URL is non-blank; a missing or
 * unavailable Redis must never prevent the gateway from starting. Rate limiting
 * intentionally keeps its existing Lettuce/Bucket4j client and fallback contract.
 */
@Configuration
public class RedissonConfiguration {

    @Bean(destroyMethod = "shutdown")
    @Conditional(CacheRedisConfiguredCondition.class)
    RedissonClient redissonClient(ParallaxProperties properties) {
        var cache = properties.getCache();
        Config config = new Config();
        config.useSingleServer()
                .setAddress(cache.getRedisUrl())
                .setConnectionMinimumIdleSize(1)
                .setConnectionPoolSize(4)
                .setTimeout(Math.max(100, cache.getLockWaitMs() + 100));
        return Redisson.create(config);
    }

    static final class CacheRedisConfiguredCondition
            implements org.springframework.context.annotation.Condition {
        @Override
        public boolean matches(org.springframework.context.annotation.ConditionContext context,
                org.springframework.core.type.AnnotatedTypeMetadata metadata) {
            String value = context.getEnvironment().getProperty("parallax.cache.redis-url", "");
            return value != null && !value.isBlank();
        }
    }
}
