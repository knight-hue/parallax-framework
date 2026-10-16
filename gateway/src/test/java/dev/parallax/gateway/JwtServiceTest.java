package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.config.ParallaxProperties;

import org.junit.jupiter.api.Test;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;

class JwtServiceTest {

    private static final String SECRET = "0123456789abcdef0123456789abcdef";

    private JwtService service(String secret) {
        ParallaxProperties props = new ParallaxProperties();
        props.getJwt().setSecret(secret);
        props.getJwt().setAccessTtlMinutes(60);
        return new JwtService(props);
    }

    @Test
    void issuesTokenThatParsesBackWithTypeAndRole() {
        JwtService jwt = service(SECRET);
        String token = jwt.issueAccessToken("admin", "ADMIN");

        Claims claims = jwt.parse(token);
        assertThat(claims.getSubject()).isEqualTo("admin");
        assertThat(claims.get("role", String.class)).isEqualTo("ADMIN");
        assertThat(claims.get(JwtService.CLAIM_TYPE, String.class)).isEqualTo(JwtService.TYPE_ACCESS);
    }

    @Test
    void rejectsTokenSignedWithAnotherKey() {
        String token = service(SECRET).issueAccessToken("admin", "ADMIN");
        JwtService other = service("ffffffffffffffffffffffffffffffff");

        assertThatThrownBy(() -> other.parse(token)).isInstanceOf(JwtException.class);
    }

    @Test
    void isUnusableWithoutSecretInsteadOfGeneratingOne() {
        // 随机密钥会让"重启后所有令牌失效"变成难以复现的线上问题，所以选择显式不可用
        JwtService jwt = service("");
        assertThat(jwt.isConfigured()).isFalse();
        assertThatThrownBy(() -> jwt.issueAccessToken("admin", "ADMIN"))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void rejectsTooShortSecretAtStartup() {
        assertThatThrownBy(() -> service("short"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(">= 32");
    }
}
