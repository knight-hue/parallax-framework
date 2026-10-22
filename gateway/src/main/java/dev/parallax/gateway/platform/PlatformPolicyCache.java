package dev.parallax.gateway.platform;

import java.time.Duration;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.config.ParallaxProperties;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

/**
 * Advisory read-through cache for immutable policy versions.
 *
 * Authorization is deliberately outside this class: callers must check project
 * membership before asking for a cached value. A cache hit therefore cannot
 * grant access after a membership change. Redis failures are swallowed and the
 * caller's database loader remains authoritative.
 */
@Component
public final class PlatformPolicyCache {
    private static final Logger log = LoggerFactory.getLogger(PlatformPolicyCache.class);
    private final ObjectMapper mapper;
    private final ObjectProvider<RedissonClient> redisson;
    private final ParallaxProperties properties;

    public PlatformPolicyCache(ObjectMapper mapper, ObjectProvider<RedissonClient> redisson,
            ParallaxProperties properties) {
        this.mapper = mapper;
        this.redisson = redisson;
        this.properties = properties;
    }

    public PlatformCatalogService.Policy get(String projectId, String policyId,
            Supplier<PlatformCatalogService.Policy> loader) {
        String key = key(projectId, policyId);
        RedissonClient client = redisson.getIfAvailable();
        if (client == null) return loader.get();
        String encoded;
        try {
            encoded = client.<String>getBucket(key).get();
        } catch (Exception ex) {
            log.debug("policy cache read failed; using database", ex);
            return loader.get();
        }
        if (encoded == null) return rebuild(client, key, loader);
        try {
            return decode(encoded);
        } catch (Exception ex) {
            log.warn("discarding invalid policy cache entry key={}", key, ex);
            deleteQuietly(client, key);
            return rebuild(client, key, loader);
        }
    }

    public void evict(String projectId, String policyId) {
        String key = key(projectId, policyId);
        try {
            RedissonClient client = redisson.getIfAvailable();
            if (client != null) client.getBucket(key).delete();
        } catch (Exception ex) {
            log.debug("policy cache eviction failed", ex);
        }
    }

    static String key(String projectId, String policyId) {
        return "parallax:policy:v1:" + projectId + ":" + policyId;
    }

    private PlatformCatalogService.Policy rebuild(RedissonClient client, String key,
            Supplier<PlatformCatalogService.Policy> loader) {
        RLock lock = client.getLock(key + ":rebuild");
        boolean acquired = false;
        try {
            var cache = properties.getCache();
            long waitMs = Math.max(0, cache.getLockWaitMs());
            long leaseMs = Math.max(1, cache.getLockLeaseSeconds()) * 1000L;
            acquired = lock.tryLock(waitMs, leaseMs, TimeUnit.MILLISECONDS);
        } catch (Exception ex) {
            log.debug("policy cache rebuild lock failed; using database", ex);
            return loader.get();
        }
        try {
            if (!acquired) return loader.get();
            String encoded;
            try {
                encoded = client.<String>getBucket(key).get();
            } catch (Exception ex) {
                log.debug("policy cache re-read failed; using database", ex);
                return loader.get();
            }
            if (encoded != null) {
                try {
                    return decode(encoded);
                } catch (Exception ex) {
                    log.warn("discarding invalid policy cache entry key={}", key, ex);
                    deleteQuietly(client, key);
                }
            }
            // Loader failures must propagate: the database remains authoritative and a
            // second invocation could turn one transient error into surprising behavior.
            PlatformCatalogService.Policy value = loader.get();
            try {
                var cache = properties.getCache();
                client.<String>getBucket(key).set(mapper.writeValueAsString(value),
                        Duration.ofSeconds(Math.max(1, cache.getTtlSeconds())));
            } catch (Exception ex) {
                log.debug("policy cache write failed; database value is still authoritative", ex);
            }
            return value;
        } finally {
            if (acquired) {
                try { lock.unlock(); } catch (Exception ex) { log.debug("policy cache unlock failed", ex); }
            }
        }
    }

    private PlatformCatalogService.Policy decode(String encoded) throws Exception {
        PlatformCatalogService.Policy value = mapper.readValue(encoded, PlatformCatalogService.Policy.class);
        verify(value);
        return value;
    }

    private void deleteQuietly(RedissonClient client, String key) {
        try { client.getBucket(key).delete(); }
        catch (Exception ex) { log.debug("policy cache cleanup failed", ex); }
    }

    private void verify(PlatformCatalogService.Policy value) throws Exception {
        if (value == null || value.config() == null || value.configSha256() == null) {
            throw new IllegalArgumentException("cached policy is incomplete");
        }
        value.config().validate();
        String json = mapper.writeValueAsString(value.config());
        if (!PlatformTaskService.hash(json).equals(value.configSha256())) {
            throw new IllegalArgumentException("cached policy digest mismatch");
        }
    }
}
