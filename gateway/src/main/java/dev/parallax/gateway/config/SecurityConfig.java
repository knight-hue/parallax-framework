package dev.parallax.gateway.config;

import java.nio.charset.StandardCharsets;

import dev.parallax.gateway.auth.JwtAuthFilter;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final ParallaxProperties props;

    public SecurityConfig(ParallaxProperties props) {
        this.props = props;
    }

    @Bean
    SecurityFilterChain filterChain(HttpSecurity http, JwtAuthFilter jwtAuthFilter) throws Exception {
        http
                // 无状态 + Bearer 令牌 ⇒ 没有会话可被 CSRF 利用
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(registry -> {
                    registry.requestMatchers("/actuator/health/**", "/actuator/info").permitAll();
                    registry.requestMatchers("/api/v1/auth/**").permitAll();
                    if (!props.getGateway().isRequireAuth()) {
                        // 默认关闭鉴权：让本地与内网演示开箱即用。
                        // 公网暴露前必须打开 require-auth，见 SECURITY.md。
                        registry.anyRequest().permitAll();
                    } else {
                        registry.anyRequest().authenticated();
                    }
                })
                .exceptionHandling(ex -> ex.authenticationEntryPoint((request, response, authException) -> {
                    response.setStatus(HttpStatus.UNAUTHORIZED.value());
                    response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                    response.setCharacterEncoding(StandardCharsets.UTF_8.name());
                    response.getWriter()
                            .write("{\"success\":false,\"error\":\"未提供有效的访问令牌\"}");
                }))
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
