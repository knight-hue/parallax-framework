package dev.parallax.gateway.ratelimit;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

import dev.parallax.gateway.config.ParallaxProperties;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Conditional;
import org.springframework.stereotype.Component;

import io.github.bucket4j.BucketConfiguration;
import io.github.bucket4j.distributed.BucketProxy;
import io.github.bucket4j.distributed.proxy.RemoteBucketBuilder;
import io.github.bucket4j.redis.lettuce.cas.LettuceBasedProxyManager;
import io.lettuce.core.ClientOptions;
import io.lettuce.core.RedisClient;
import io.lettuce.core.SocketOptions;
import io.lettuce.core.TimeoutOptions;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.codec.ByteArrayCodec;
import jakarta.annotation.PreDestroy;

/**
 * Redis 上的令牌桶：多个网关实例共享同一份配额。
 *
 * **只在配了 `parallax.ratelimit.redis-url` 时才存在**（`@ConditionalOnProperty`），
 * 因此没配 Redis 的部署完全不会加载 Lettuce。
 *
 * ## 连接刻意做成惰性的
 *
 * 如果在构造函数里连 Redis，那么 **Redis 没就绪时网关会启动失败**——
 * 服务因为一个可选组件而整体起不来，比限流精度下降严重得多。
 * 所以推迟到第一次使用才连；连接失败后把连接置空，下一次调用重新建立，
 * 这样 Redis 恢复后不需要重启网关。
 * 连接失败抛出的异常由 {@link ResilientRateLimiter} 捕获并降级到内存桶。
 *
 * ## 超时刻意很短
 *
 * 限流在请求关键路径上。一个慢的 Redis 会让每个请求都变慢，那比限流失效更糟。
 *
 * 键用 byte[]（Lettuce 的 `ByteArrayCodec`）而不是自定义 String 编解码器：
 * bucket4j 的 builder 要求值类型是 byte[]，为键再写一个编解码器只增加维护面，
 * 而键本来就是我们自己拼的 ASCII 字符串。
 */
@Component
@Conditional(RedisConfiguredCondition.class)
public class RedisRateLimiter implements RateLimiter {

    private static final Logger log = LoggerFactory.getLogger(RedisRateLimiter.class);
    private static final String KEY_NAMESPACE = "parallax:ratelimit:";

    private final RedisClient client;

    private volatile StatefulRedisConnection<byte[], byte[]> connection;
    private volatile RemoteBucketBuilder<byte[]> buckets;

    public RedisRateLimiter(ParallaxProperties props) {
        Duration timeout = Duration.ofMillis(props.getRatelimit().getRedisTimeoutMs());
        this.client = RedisClient.create(props.getRatelimit().getRedisUrl());
        this.client.setOptions(ClientOptions.builder()
                .autoReconnect(true)
                .socketOptions(SocketOptions.builder().connectTimeout(timeout).build())
                .timeoutOptions(TimeoutOptions.enabled(timeout))
                .build());
        log.info("限流后端：Redis（跨实例共享配额），命令超时 {}ms", timeout.toMillis());
    }

    @Override
    public boolean tryConsume(String key, BucketSpec spec) {
        BucketConfiguration configuration = BucketConfiguration.builder()
                .addLimit(limit -> limit.capacity(spec.capacity())
                        .refillGreedy(spec.capacity(), spec.window()))
                .build();
        try {
            BucketProxy bucket = buckets().build(redisKey(key, spec), configuration);
            return bucket.tryConsume(1);
        } catch (RuntimeException ex) {
            // 连接可能在故障期间失效：置空让下一次调用重建，
            // 否则会一直拿着一个坏连接，Redis 恢复了也回不来。
            reset();
            throw ex;
        }
    }

    private RemoteBucketBuilder<byte[]> buckets() {
        RemoteBucketBuilder<byte[]> current = buckets;
        if (current != null) {
            return current;
        }
        synchronized (this) {
            if (buckets == null) {
                StatefulRedisConnection<byte[], byte[]> fresh = client.connect(ByteArrayCodec.INSTANCE);
                connection = fresh;
                buckets = LettuceBasedProxyManager.builderFor(fresh).build().builder();
            }
            return buckets;
        }
    }

    /**
     * 桶规格要进键：同一个主体在"贵操作桶"和"一般桶"上必须落到不同的桶，
     * 否则改容量配置后旧桶会带着旧容量继续生效，看起来像配置没生效。
     */
    private byte[] redisKey(String key, BucketSpec spec) {
        String composite = KEY_NAMESPACE + spec.capacity() + ":" + spec.window().toSeconds() + "|" + key;
        return composite.getBytes(StandardCharsets.UTF_8);
    }

    /** 供探活使用：连不上或拿不到 PONG 都算不可用。 */
    public boolean ping() {
        buckets();
        return "PONG".equalsIgnoreCase(connection.sync().ping());
    }

    private synchronized void reset() {
        StatefulRedisConnection<byte[], byte[]> stale = connection;
        connection = null;
        buckets = null;
        if (stale != null) {
            try {
                stale.close();
            } catch (RuntimeException ignored) {
                // 关闭一个已经坏掉的连接失败是可以接受的，不必再制造一个异常
            }
        }
    }

    @PreDestroy
    public void shutdown() {
        reset();
        client.shutdown();
    }
}
