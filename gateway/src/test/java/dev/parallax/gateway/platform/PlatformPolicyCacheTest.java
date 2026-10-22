package dev.parallax.gateway.platform;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.config.ParallaxProperties;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

class PlatformPolicyCacheTest {
    @Test
    void withoutRedisEveryReadFallsBackToAuthoritativeLoader() {
        var properties = new ParallaxProperties();
        var cache = new PlatformPolicyCache(new ObjectMapper(), emptyProvider(), properties);
        var loads = new AtomicInteger();
        var policy = new PlatformCatalogService.Policy("p-1", "project-1", 1,
                new PlatformCatalogService.PolicyConfig(2, 1, 1, 1, false, 100, 60), "hash");

        assertThat(cache.get("project-1", "p-1", () -> { loads.incrementAndGet(); return policy; })).isEqualTo(policy);
        assertThat(cache.get("project-1", "p-1", () -> { loads.incrementAndGet(); return policy; })).isEqualTo(policy);
        assertThat(loads).hasValue(2);
    }

    @Test
    void cacheKeysAreProjectScopedAndEvictionForcesReload() {
        var properties = new ParallaxProperties();
        var cache = new PlatformPolicyCache(new ObjectMapper(), emptyProvider(), properties);
        var loads = new AtomicInteger();
        var policy = new PlatformCatalogService.Policy("p-1", "project-1", 1,
                new PlatformCatalogService.PolicyConfig(2, 1, 1, 1, false, 100, 60), "hash");

        cache.get("project-1", "p-1", () -> { loads.incrementAndGet(); return policy; });
        cache.get("project-2", "p-1", () -> { loads.incrementAndGet(); return policy; });
        assertThat(PlatformPolicyCache.key("project-1", "p-1"))
                .isNotEqualTo(PlatformPolicyCache.key("project-2", "p-1"));
        cache.evict("project-1", "p-1");
        cache.get("project-1", "p-1", () -> { loads.incrementAndGet(); return policy; });
        assertThat(loads).hasValue(3);
    }

    private static <T> ObjectProvider<T> emptyProvider() {
        return new ObjectProvider<>() {
            @Override public T getObject() { throw new IllegalStateException("no bean"); }
            @Override public T getObject(Object... args) { return getObject(); }
            @Override public T getIfAvailable() { return null; }
            @Override public T getIfUnique() { return null; }
        };
    }
}
