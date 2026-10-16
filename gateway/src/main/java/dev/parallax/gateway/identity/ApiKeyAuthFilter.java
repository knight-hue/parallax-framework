package dev.parallax.gateway.identity;

import java.io.IOException;
import java.util.List;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 用 `X-API-Key` 认证。
 *
 * 与 JWT 并存而不是替换：JWT 给运营人员用（短期、可轮换），
 * API Key 给集成方用（长期、可单独吊销、可配额）。
 * 两者的生命周期完全不同，硬塞进一套令牌里会让"吊销一个集成方"
 * 变成"让所有运营人员重新登录"。
 *
 * 认证成功后主体里带 `credentialId`——配额与记账都靠它归属；
 * 主体名用凭据的 `name` 而不是 id，因为日志里"ci-bot 超了额度"
 * 比一串 UUID 有用得多。
 */
@Component
public class ApiKeyAuthFilter extends OncePerRequestFilter {

    private final ApiKeyService apiKeys;
    private final ParallaxProperties props;

    public ApiKeyAuthFilter(ApiKeyService apiKeys, ParallaxProperties props) {
        this.apiKeys = apiKeys;
        this.props = props;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !props.getIdentity().isEnabled();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String raw = request.getHeader(props.getIdentity().getHeaderName());
        if (raw != null && !raw.isBlank()) {
            apiKeys.resolve(raw.trim()).ifPresent(credential -> {
                AuthPrincipal principal = ApiKeyService.principalOf(credential);
                var auth = new UsernamePasswordAuthenticationToken(
                        principal,
                        null,
                        List.of(new SimpleGrantedAuthority("ROLE_" + principal.role())));
                SecurityContextHolder.getContext().setAuthentication(auth);
                apiKeys.touch(credential);
            });
        }
        chain.doFilter(request, response);
    }
}
