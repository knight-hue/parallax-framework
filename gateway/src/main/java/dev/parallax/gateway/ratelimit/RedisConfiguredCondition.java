package dev.parallax.gateway.ratelimit;

import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.core.type.AnnotatedTypeMetadata;

/**
 * 只有真的配了非空的 Redis 地址才创建分布式限流后端。
 *
 * **为什么不用 `@ConditionalOnProperty`**：`application.yml` 里写的是
 * `redis-url: ${PARALLAX_RATELIMIT_REDIS_URL:}`，即变量存在但默认为空串。
 * `@ConditionalOnProperty` 只把 null 与 "false" 视为不匹配，**空字符串算匹配**，
 * 于是 bean 会被创建、`RedisClient.create("")` 抛
 * `IllegalArgumentException: URI must not be empty`，整个应用起不来。
 * 这个坑在本地测试时被真实踩到过，所以这里用显式判断而不是注解默认语义。
 */
public class RedisConfiguredCondition implements Condition {

    static final String PROPERTY = "parallax.ratelimit.redis-url";

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String url = context.getEnvironment().getProperty(PROPERTY);
        return url != null && !url.isBlank();
    }
}
