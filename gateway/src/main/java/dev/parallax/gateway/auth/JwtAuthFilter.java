package dev.parallax.gateway.auth;

import java.io.IOException;
import java.util.List;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.platform.PlatformIdentityService;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;

/**
 * 解析 Authorization: Bearer，写入 SecurityContext。
 *
 */
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final PlatformIdentityService users;

    public JwtAuthFilter(JwtService jwtService, PlatformIdentityService users) {
        this.jwtService = jwtService;
        this.users = users;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        // 已经由 API Key 认证过就不再解析 Bearer：那次认证带着 credentialId，
        // 被 JWT 覆盖会让配额归属悄悄消失。
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            chain.doFilter(request, response);
            return;
        }
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7).trim();
            try {
                Claims claims = jwtService.parse(token);
                if (JwtService.TYPE_ACCESS.equals(claims.get(JwtService.CLAIM_TYPE, String.class))) {
                    String role = claims.get("role", String.class);
                    String userId = claims.get("user_id", String.class);
                    AuthPrincipal principal;
                    if (userId != null) {
                        // Legacy audit/report endpoints have no project ownership yet.
                        // Do not let a tenant token bypass the new resource boundary there.
                        if (!request.getRequestURI().startsWith("/api/v1/platform/")) {
                            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                            response.setContentType("application/json");
                            response.getWriter().write("{\"success\":false,\"error\":\"Use project-scoped platform endpoints\"}");
                            return;
                        }
                        var user = users.activeUser(userId);
                        // Tenant privileges are read live from membership, never from JWT roles.
                        principal = new AuthPrincipal(user.username(), AuthPrincipal.ROLE_VIEWER, null, user.id());
                    } else {
                        principal = new AuthPrincipal(
                                claims.getSubject(), role == null ? AuthPrincipal.ROLE_VIEWER : role);
                    }
                    var auth = new UsernamePasswordAuthenticationToken(
                            principal,
                            null,
                            List.of(new SimpleGrantedAuthority("ROLE_" + principal.role())));
                    SecurityContextHolder.getContext().setAuthentication(auth);
                }
            } catch (JwtException | IllegalArgumentException | ApiException ignored) {
                // 令牌无效时保持匿名，由 SecurityConfig 的入口点统一返回 401
            }
        }
        chain.doFilter(request, response);
    }
}
