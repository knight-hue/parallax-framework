package dev.parallax.gateway.identity;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.config.ParallaxProperties;
import dev.parallax.gateway.observability.ParallaxMetrics;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 提交审查前的配额闸门。
 *
 * 只拦 `POST /api/v1/audits`：其余端点不消耗模型额度，把它们一起限死
 * 会让前端连"看进度"都被拒，那不是配额，是故障。
 *
 * 未携带凭据时**放行**，交由 SecurityConfig 决定是否要求鉴权——
 * 否则在 `require-auth=false` 的本地演示档下会直接把功能锁死。
 */
@Component
public class QuotaFilter extends OncePerRequestFilter {

    private static final String EXPENSIVE_PATH = "/api/v1/audits";

    private final QuotaService quota;
    private final ParallaxProperties props;
    private final ObjectMapper mapper;
    private final ParallaxMetrics metrics;

    public QuotaFilter(
            QuotaService quota, ParallaxProperties props, ObjectMapper mapper, ParallaxMetrics metrics) {
        this.quota = quota;
        this.props = props;
        this.mapper = mapper;
        this.metrics = metrics;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !props.getIdentity().isEnabled()
                || !EXPENSIVE_PATH.equals(request.getRequestURI())
                || !"POST".equalsIgnoreCase(request.getMethod());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Optional<AuthPrincipal> principal = currentPrincipal();
        if (principal.isEmpty() || !principal.get().hasCredential()) {
            chain.doFilter(request, response);
            return;
        }

        Instant now = Instant.now();
        QuotaService.Decision decision = quota.check(principal.get().credentialId(), now);
        if (decision.allowed()) {
            chain.doFilter(request, response);
            return;
        }

        writeRejection(response, decision, now);
    }

    private void writeRejection(HttpServletResponse response, QuotaService.Decision decision, Instant now)
            throws IOException {
        metrics.quotaRejected(decision.metric());
        response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        if (decision.resetsAt() != null) {
            long seconds = Math.max(1, Duration.between(now, decision.resetsAt()).toSeconds());
            response.setHeader("Retry-After", Long.toString(seconds));
        }
        mapper.writeValue(response.getWriter(), decision.asBody());
    }

    private Optional<AuthPrincipal> currentPrincipal() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) {
            return Optional.empty();
        }
        return auth.getPrincipal() instanceof AuthPrincipal p ? Optional.of(p) : Optional.empty();
    }
}
