package dev.parallax.gateway.platform;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.config.ParallaxProperties;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.redisson.Redisson;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.redisson.config.Config;
import org.springframework.beans.factory.ObjectProvider;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Real Redis verification for the advisory policy cache.
 *
 * H2/unit tests can only prove the fallback path. These tests prove that a real
 * Redis client is used for hit, eviction, corrupt-entry repair and bounded lock
 * waiting, and that loader failures are not swallowed or invoked twice.
 */
@Testcontainers(disabledWithoutDocker = true)
class PlatformPolicyCacheRedisIT {

    private static final int REDIS_PORT = 6379;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @SuppressWarnings("resource") // lifecycle is owned by the Testcontainers JUnit extension
    @Container
    static final GenericContainer<?> REDIS =
            new GenericContainer<>(DockerImageName.parse(
                    System.getProperty("parallax.test.redis-image", "redis:7-alpine")))
                    .withImagePullPolicy(image -> false)
                    .withExposedPorts(REDIS_PORT);

    private static RedissonClient client;

    @BeforeAll
    static void connect() {
        client = newClient();
        client.getKeys().flushall();
    }

    @AfterAll
    static void close() {
        if (client != null) client.shutdown();
    }

    @Test
    void cachesAndEvictsWithRealRedis() {
        var cache = cache(client);
        var loads = new AtomicInteger();
        var policy = policy("project-1", "policy-1");

        assertThat(cache.get("project-1", "policy-1", load(loads, policy))).isEqualTo(policy);
        assertThat(cache.get("project-1", "policy-1", load(loads, policy))).isEqualTo(policy);
        assertThat(loads).as("second read must be a cache hit").hasValue(1);

        cache.evict("project-1", "policy-1");
        assertThat(cache.get("project-1", "policy-1", load(loads, policy))).isEqualTo(policy);
        assertThat(loads).as("eviction must force an authoritative reload").hasValue(2);
    }

    @Test
    void corruptEntryIsDiscardedAndRebuilt() {
        var cache = cache(client);
        var loads = new AtomicInteger();
        var policy = policy("project-1", "policy-2");
        client.<String>getBucket(PlatformPolicyCache.key("project-1", "policy-2"))
                .set("{\"id\":\"policy-2\"}", Duration.ofMinutes(1));

        assertThat(cache.get("project-1", "policy-2", load(loads, policy))).isEqualTo(policy);
        assertThat(loads).hasValue(1);
        assertThat(client.<String>getBucket(PlatformPolicyCache.key("project-1", "policy-2")).get())
                .contains(policy.configSha256());

        assertThat(cache.get("project-1", "policy-2", load(loads, policy))).isEqualTo(policy);
        assertThat(loads).as("repaired entry must be reused").hasValue(1);
    }

    @Test
    @Timeout(10)
    void lockWaitUsesMillisecondsAndDoesNotBlockForSeconds() {
        var cache = cache(client);
        var key = PlatformPolicyCache.key("project-1", "policy-3");
        RedissonClient other = newClient();
        RLock held = other.getLock(key + ":rebuild");
        held.lock();
        try {
            long started = System.nanoTime();
            var policy = policy("project-1", "policy-3");
            assertThat(cache.get("project-1", "policy-3", () -> policy)).isEqualTo(policy);
            long elapsedMs = Duration.ofNanos(System.nanoTime() - started).toMillis();
            assertThat(elapsedMs)
                    .as("100 ms lock wait must not be interpreted as 100 seconds")
                    .isLessThan(5_000);
        } finally {
            held.unlock();
            other.shutdown();
        }
    }

    @Test
    void loaderFailurePropagatesAndIsCalledOnce() {
        var cache = cache(client);
        var calls = new AtomicInteger();

        assertThatThrownBy(() -> cache.get("project-1", "policy-4", () -> {
            calls.incrementAndGet();
            throw new IllegalStateException("database unavailable");
        })).isInstanceOf(IllegalStateException.class);
        assertThat(calls).hasValue(1);
    }

    private static RedissonClient newClient() {
        Config config = new Config();
        config.useSingleServer().setAddress(
                "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(REDIS_PORT));
        return Redisson.create(config);
    }

    private static PlatformPolicyCache cache(RedissonClient client) {
        var props = new ParallaxProperties();
        props.getCache().setTtlSeconds(60);
        props.getCache().setLockWaitMs(100);
        props.getCache().setLockLeaseSeconds(10);
        return new PlatformPolicyCache(MAPPER, provider(client), props);
    }

    private static ObjectProvider<RedissonClient> provider(RedissonClient client) {
        return new ObjectProvider<>() {
            @Override public RedissonClient getObject() { return client; }
            @Override public RedissonClient getObject(Object... args) { return client; }
            @Override public RedissonClient getIfAvailable() { return client; }
            @Override public RedissonClient getIfUnique() { return client; }
        };
    }

    private static java.util.function.Supplier<PlatformCatalogService.Policy> load(
            AtomicInteger loads, PlatformCatalogService.Policy policy) {
        return () -> { loads.incrementAndGet(); return policy; };
    }

    private static PlatformCatalogService.Policy policy(String projectId, String id) {
        var config = new PlatformCatalogService.PolicyConfig(3, 1, 2, 2, false, 1000L, 600);
        try {
            String json = MAPPER.writeValueAsString(config);
            return new PlatformCatalogService.Policy(id, projectId, 1, config,
                    PlatformTaskService.hash(json));
        } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
            throw new IllegalStateException(ex);
        }
    }
}
