package dev.parallax.gateway.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** 网关配置。所有字段都有安全默认值，缺少配置时能起来但会被明确拒绝转发。 */
@ConfigurationProperties(prefix = "parallax")
public class ParallaxProperties {

    private final Gateway gateway = new Gateway();
    private final Jwt jwt = new Jwt();
    private final Ratelimit ratelimit = new Ratelimit();
    private final Identity identity = new Identity();
    private final Cache cache = new Cache();

    public Gateway getGateway() {
        return gateway;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public Ratelimit getRatelimit() {
        return ratelimit;
    }

    public Identity getIdentity() {
        return identity;
    }

    public Cache getCache() {
        return cache;
    }

    /** Redis-backed read cache settings. Cache is advisory and never an authorization source. */
    public static class Cache {
        private String redisUrl = "";
        private int ttlSeconds = 300;
        private int lockWaitMs = 100;
        private int lockLeaseSeconds = 10;

        public String getRedisUrl() { return redisUrl; }
        public void setRedisUrl(String redisUrl) { this.redisUrl = redisUrl; }
        public int getTtlSeconds() { return ttlSeconds; }
        public void setTtlSeconds(int ttlSeconds) { this.ttlSeconds = ttlSeconds; }
        public int getLockWaitMs() { return lockWaitMs; }
        public void setLockWaitMs(int lockWaitMs) { this.lockWaitMs = lockWaitMs; }
        public int getLockLeaseSeconds() { return lockLeaseSeconds; }
        public void setLockLeaseSeconds(int lockLeaseSeconds) { this.lockLeaseSeconds = lockLeaseSeconds; }
    }

    /**
     * 身份与配额。
     *
     * 默认**关闭**：开启后 `POST /api/v1/audits` 需要 API Key 并计入额度，
     * 会让"本机开箱跑一遍"多出建凭据这一步。演示用 compose 档会显式打开它。
     */
    public static class Identity {
        private boolean enabled;
        private String headerName = "X-API-Key";
        /** API Key 前缀。留可见前缀是为了让泄漏能被内容扫描发现。 */
        private String keyPrefix = "plx_";
        /** 凭据 `last_used_at` 的刷新间隔下限，避免每次校验都写库。 */
        private int touchIntervalSeconds = 60;

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public String getHeaderName() {
            return headerName;
        }

        public void setHeaderName(String headerName) {
            this.headerName = headerName;
        }

        public String getKeyPrefix() {
            return keyPrefix;
        }

        public void setKeyPrefix(String keyPrefix) {
            this.keyPrefix = keyPrefix;
        }

        public int getTouchIntervalSeconds() {
            return touchIntervalSeconds;
        }

        public void setTouchIntervalSeconds(int touchIntervalSeconds) {
            this.touchIntervalSeconds = touchIntervalSeconds;
        }
    }

    public static class Gateway {
        /** Python 编排服务地址。 */
        private String upstreamBaseUrl = "http://127.0.0.1:8000";
        private int connectTimeoutMs = 5_000;
        private int readTimeoutMs = 30_000;
        /** 是否要求 JWT。默认关闭：本地/内网演示开箱即用。 */
        private boolean requireAuth;
        /** 换取访问令牌的共享密钥（单租户部署，不引入用户库）。 */
        private String adminSecret = "";
        /** 转发时注入的上游内部令牌（上游可选校验）。 */
        private String internalToken = "";

        public Duration connectTimeout() {
            return Duration.ofMillis(connectTimeoutMs);
        }

        public Duration readTimeout() {
            return Duration.ofMillis(readTimeoutMs);
        }

        public String getUpstreamBaseUrl() {
            return upstreamBaseUrl;
        }

        public void setUpstreamBaseUrl(String upstreamBaseUrl) {
            this.upstreamBaseUrl = upstreamBaseUrl;
        }

        public int getConnectTimeoutMs() {
            return connectTimeoutMs;
        }

        public void setConnectTimeoutMs(int connectTimeoutMs) {
            this.connectTimeoutMs = connectTimeoutMs;
        }

        public int getReadTimeoutMs() {
            return readTimeoutMs;
        }

        public void setReadTimeoutMs(int readTimeoutMs) {
            this.readTimeoutMs = readTimeoutMs;
        }

        public boolean isRequireAuth() {
            return requireAuth;
        }

        public void setRequireAuth(boolean requireAuth) {
            this.requireAuth = requireAuth;
        }

        public String getAdminSecret() {
            return adminSecret;
        }

        public void setAdminSecret(String adminSecret) {
            this.adminSecret = adminSecret;
        }

        public String getInternalToken() {
            return internalToken;
        }

        public void setInternalToken(String internalToken) {
            this.internalToken = internalToken;
        }
    }

    public static class Jwt {
        private String secret = "";
        private int accessTtlMinutes = 720;

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public int getAccessTtlMinutes() {
            return accessTtlMinutes;
        }

        public void setAccessTtlMinutes(int accessTtlMinutes) {
            this.accessTtlMinutes = accessTtlMinutes;
        }
    }

    public static class Ratelimit {
        private boolean enabled = true;
        private int defaultCapacity = 120;
        private int defaultWindowSeconds = 60;
        private int expensiveCapacity = 10;
        private int expensiveWindowSeconds = 60;
        /**
         * Redis 地址。留空（默认）表示只用单实例内存桶。
         *
         * 配了它之后限流改为跨实例合并计算——多副本部署时这才是正确的配额语义。
         * **Redis 不可用时会自动降级回内存桶**，服务不受影响。
         */
        private String redisUrl = "";
        /** Redis 命令超时。限流在请求关键路径上，不能等一个慢 Redis。 */
        private int redisTimeoutMs = 250;
        /**
         * 降级后的冷却时间：这段时间内直接用内存桶，不再尝试 Redis。
         *
         * 没有冷却的话，Redis 挂掉时每个请求都要先等一次超时，
         * 降级就从"服务仍可用"变成"每个请求多花 250ms"。
         */
        private int degradedCooldownSeconds = 30;

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public int getDefaultCapacity() {
            return defaultCapacity;
        }

        public void setDefaultCapacity(int defaultCapacity) {
            this.defaultCapacity = defaultCapacity;
        }

        public int getDefaultWindowSeconds() {
            return defaultWindowSeconds;
        }

        public void setDefaultWindowSeconds(int defaultWindowSeconds) {
            this.defaultWindowSeconds = defaultWindowSeconds;
        }

        public int getExpensiveCapacity() {
            return expensiveCapacity;
        }

        public void setExpensiveCapacity(int expensiveCapacity) {
            this.expensiveCapacity = expensiveCapacity;
        }

        public int getExpensiveWindowSeconds() {
            return expensiveWindowSeconds;
        }

        public void setExpensiveWindowSeconds(int expensiveWindowSeconds) {
            this.expensiveWindowSeconds = expensiveWindowSeconds;
        }

        public String getRedisUrl() {
            return redisUrl;
        }

        public void setRedisUrl(String redisUrl) {
            this.redisUrl = redisUrl;
        }

        public int getRedisTimeoutMs() {
            return redisTimeoutMs;
        }

        public void setRedisTimeoutMs(int redisTimeoutMs) {
            this.redisTimeoutMs = redisTimeoutMs;
        }

        public int getDegradedCooldownSeconds() {
            return degradedCooldownSeconds;
        }

        public void setDegradedCooldownSeconds(int degradedCooldownSeconds) {
            this.degradedCooldownSeconds = degradedCooldownSeconds;
        }
    }
}
