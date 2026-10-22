package dev.parallax.gateway.config;

import java.nio.charset.StandardCharsets;

import dev.parallax.gateway.auth.JwtAuthFilter;
import dev.parallax.gateway.identity.ApiKeyAuthFilter;
import dev.parallax.gateway.identity.QuotaFilter;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import jakarta.servlet.Filter;

/**
 * 安全链。
 *
 * 过滤器顺序是**有语义**的，不能随意调换：
 * 1. `ApiKeyAuthFilter`（API Key）先试——它带 `credentialId`，是配额的前提；
 * 2. `JwtAuthFilter` 随后，且**在已有认证时跳过**，避免把 API Key 主体覆盖掉；
 * 3. `QuotaFilter` 最后，此时认证结果已定，才能知道该按哪个凭据算额度。
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    private final ParallaxProperties props;

    public SecurityConfig(ParallaxProperties props) {
        this.props = props;
    }

    @Bean
    SecurityFilterChain filterChain(
            HttpSecurity http,
            ApiKeyAuthFilter apiKeyAuthFilter,
            JwtAuthFilter jwtAuthFilter,
            QuotaFilter quotaFilter)
            throws Exception {        http
                // 无状态 + 不存 Cookie ⇒ 没有会话可被 CSRF 利用
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(registry -> {
                    // The initial REQUEST is authorized once. Streaming responses dispatch
                    // again after its stateless SecurityContext has been cleared.
                    registry.dispatcherTypeMatchers(jakarta.servlet.DispatcherType.ASYNC,
                            jakarta.servlet.DispatcherType.ERROR).permitAll();
                    registry.requestMatchers("/actuator/health/**", "/actuator/info").permitAll();
                    registry.requestMatchers("/api/v1/auth/**").permitAll();
                    // The webhook service verifies the HMAC signature over the raw body.
                    registry.requestMatchers("/api/v1/platform/webhooks/**").permitAll();
                    // 完成回调由 X-Internal-Token 自行校验：它来自编排服务，
                    // 拿不到 JWT 也不该被要求拿
                    registry.requestMatchers("/api/v1/internal/**").permitAll();
                    if (!props.getGateway().isRequireAuth()) {
                        // 默认关闭鉴权：让本地与内网演示开箱即用。
                        // 公网暴露前必须打开 require-auth，见 SECURITY.md。
                        registry.anyRequest().permitAll();
                    } else {
                        // 修复涉及代码生成与执行，只允许操作员 ADMIN；读审计仍遵循原策略。
                        registry.requestMatchers("/api/v1/audits/*/repairs", "/api/v1/audits/*/repairs/**")
                                .hasRole("ADMIN");
                        registry.anyRequest().authenticated();
                    }
                })
                .exceptionHandling(ex -> ex.accessDeniedHandler((request, response, denied) -> {
                    response.setStatus(HttpStatus.FORBIDDEN.value());
                    response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                    response.setCharacterEncoding(StandardCharsets.UTF_8.name());
                    response.getWriter().write("{\"success\":false,\"error\":\"需要管理员权限\"}");
                }).authenticationEntryPoint((request, response, authException) -> {
                    response.setStatus(HttpStatus.UNAUTHORIZED.value());
                    response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                    response.setCharacterEncoding(StandardCharsets.UTF_8.name());
                    response.getWriter()
                            .write("{\"success\":false,\"error\":\"未提供有效的访问令牌\"}");
                }))
                .addFilterBefore(apiKeyAuthFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterAfter(jwtAuthFilter, ApiKeyAuthFilter.class)
                .addFilterAfter(quotaFilter, JwtAuthFilter.class);
        return http.build();
    }

    /**
     * 阻止这三个过滤器被 servlet 容器**再注册一次**。
     *
     * 它们是 Filter 类型的 Bean，Spring Boot 默认会把所有 Filter Bean 注册到 servlet 链上；
     * 而它们的语义要求恰好只运行一次、且必须位于 Security 链内：
     * - `QuotaFilter` 要按认证结果算额度，跑到 Security 链外面就取不到主体；
     * - `ApiKeyAuthFilter` 重复执行会重复刷新 `last_used_at`；
     * - `JwtAuthFilter` 重复执行无害，但顺手一起关掉，免得读者以为它特殊。
     */
    @Bean
    FilterRegistrationBean<ApiKeyAuthFilter> apiKeyAuthFilterRegistration(ApiKeyAuthFilter filter) {
        return disabled(filter);
    }

    @Bean
    FilterRegistrationBean<JwtAuthFilter> jwtAuthFilterRegistration(JwtAuthFilter filter) {
        return disabled(filter);
    }

    @Bean
    FilterRegistrationBean<QuotaFilter> quotaFilterRegistration(QuotaFilter filter) {
        return disabled(filter);
    }

    private static <T extends Filter> FilterRegistrationBean<T> disabled(T filter) {
        FilterRegistrationBean<T> registration = new FilterRegistrationBean<>(filter);
        registration.setEnabled(false);
        return registration;
    }
}
