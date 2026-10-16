package dev.parallax.gateway.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** 网关配置。所有字段都有安全默认值，缺少配置时能起来但会被明确拒绝转发。 */
@ConfigurationProperties(prefix = "parallax")
public class ParallaxProperties {

    private final Gateway gateway = new Gateway();
    private final Jwt jwt = new Jwt();
    private final Ratelimit ratelimit = new Ratelimit();

    public Gateway getGateway() {
        return gateway;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public Ratelimit getRatelimit() {
        return ratelimit;
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
    }
}
