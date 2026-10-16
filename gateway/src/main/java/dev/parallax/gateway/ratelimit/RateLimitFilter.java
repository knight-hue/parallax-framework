package dev.parallax.gateway.ratelimit;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import io.github.bucket4j.Bucket;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 限流防刷（Bucket4j 令牌桶，按 IP + 主体维度）。
 *
 * 分两类桶：一般接口一个，`POST /api/v1/audits` 单独一个更小的——
 * 提交一次审查会真实消耗模型额度，它被刷的代价和读接口完全不是一个量级。
 *
 * 当前为单实例内存桶。多实例水平扩展时替换为 bucket4j-redis（接口不变），
 * 这一点写在这里而不是文档里，是因为换实现的人一定会先看这个类。
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private static final String EXPENSIVE_PATH = "/api/v1/audits";
    private static final int MAX_BUCKETS = 50_000;

    private final ParallaxProperties props;
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public RateLimitFilter(ParallaxProperties props) {
        this.props = props;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (!props.getRatelimit().isEnabled()) {
            return true;
        }
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        boolean expensive = isExpensive(request);
        String bucketKey = (expensive ? "audit:" : "api:")
                + clientIp(request) + ":" + currentSubject();

        // 防内存膨胀。重置必须在 computeIfAbsent 之外：
        // 在映射函数里改 Map 会让 JDK 抛 ConcurrentModificationException。
        if (buckets.size() > MAX_BUCKETS) {
            buckets.clear();
        }
        Bucket bucket = buckets.computeIfAbsent(bucketKey, key -> createBucket(expensive));
        if (bucket.tryConsume(1)) {
            chain.doFilter(request, response);
            return;
        }
        response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        response.getWriter().write(expensive
                ? "{\"success\":false,\"error\":\"提交审查过于频繁，请稍后再试\"}"
                : "{\"success\":false,\"error\":\"请求过于频繁，请稍后再试\"}");
    }

    /** 只有"提交"才贵，"查询/看进度"不该被同一个小桶卡住。 */
    private boolean isExpensive(HttpServletRequest request) {
        return EXPENSIVE_PATH.equals(request.getRequestURI())
                && "POST".equalsIgnoreCase(request.getMethod());
    }

    private Bucket createBucket(boolean expensive) {
        int capacity = expensive
                ? props.getRatelimit().getExpensiveCapacity()
                : props.getRatelimit().getDefaultCapacity();
        int windowSeconds = expensive
                ? props.getRatelimit().getExpensiveWindowSeconds()
                : props.getRatelimit().getDefaultWindowSeconds();
        return Bucket.builder()
                .addLimit(limit -> limit.capacity(capacity)
                        .refillGreedy(capacity, Duration.ofSeconds(windowSeconds)))
                .build();
    }

    private String currentSubject() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || auth.getPrincipal() == null) {
            return "anon";
        }
        return String.valueOf(auth.getPrincipal());
    }

    private String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            // 取最左侧：那是原始客户端；右侧是各级代理，可被伪造
            return forwarded.split(",")[0].trim();
        }
        String realIp = request.getHeader("X-Real-IP");
        if (realIp != null && !realIp.isBlank()) {
            return realIp.trim();
        }
        return request.getRemoteAddr();
    }
}
