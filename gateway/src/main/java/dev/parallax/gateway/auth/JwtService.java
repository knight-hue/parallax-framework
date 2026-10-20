package dev.parallax.gateway.auth;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;

import javax.crypto.SecretKey;

import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.stereotype.Service;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

/**
 * JWT 服务：签发与校验访问令牌（HS256）。
 *
 */
@Service
public class JwtService {

    /** 令牌类型声明，防止别处签发的令牌被拿来当访问令牌用。 */
    public static final String CLAIM_TYPE = "typ";
    public static final String TYPE_ACCESS = "access";

    private final SecretKey key;
    private final long accessTtlMs;

    public JwtService(ParallaxProperties props) {
        String secret = props.getJwt().getSecret();
        if (secret == null || secret.isBlank()) {
            // 未配置密钥时不生成密钥而是保持不可用：随机密钥会让"重启后令牌全失效"
            // 变成一个难以复现的线上问题。是否启用鉴权由 require-auth 决定。
            this.key = null;
            this.accessTtlMs = 0;
            return;
        }
        byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            throw new IllegalStateException("PARALLAX_JWT_SECRET 长度必须 >= 32 字节");
        }
        this.key = Keys.hmacShaKeyFor(bytes);
        this.accessTtlMs = props.getJwt().getAccessTtlMinutes() * 60_000L;
    }

    public boolean isConfigured() {
        return key != null;
    }

    public String issueAccessToken(String subject, String role) {
        return issue(subject, role, null);
    }

    public String issueUserToken(String userId, String username) {
        return issue(username, AuthPrincipal.ROLE_VIEWER, userId);
    }

    private String issue(String subject, String role, String userId) {
        if (key == null) {
            throw new IllegalStateException("未配置 PARALLAX_JWT_SECRET，无法签发令牌");
        }
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(subject)
                .claim(CLAIM_TYPE, TYPE_ACCESS)
                .claim("role", role)
                .claim("user_id", userId)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusMillis(accessTtlMs)))
                .signWith(key)
                .compact();
    }

    /** 解析并校验签名与有效期；失败抛 {@link JwtException}。 */
    public Claims parse(String token) throws JwtException {
        if (key == null) {
            throw new JwtException("JWT 未配置");
        }
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}
