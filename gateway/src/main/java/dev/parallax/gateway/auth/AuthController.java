package dev.parallax.gateway.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用共享密钥换取访问令牌。
 *
 * 这是一个**单租户**部署的鉴权方式：没有用户库、没有注册流程。
 * 之所以不引入用户体系，是因为网关的价值在于"把不可信的调用挡在编排服务之外"，
 * 而不是再实现一遍账号系统——后者会让这个薄网关变成第二个业务后端。
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final ParallaxProperties props;
    private final JwtService jwtService;

    public AuthController(ParallaxProperties props, JwtService jwtService) {
        this.props = props;
        this.jwtService = jwtService;
    }

    public record TokenRequest(String secret) {
    }

    public record TokenResponse(String accessToken, String tokenType, String role) {
    }

    @PostMapping("/token")
    public TokenResponse issue(@RequestBody(required = false) TokenRequest request) {
        String expected = props.getGateway().getAdminSecret();
        if (expected == null || expected.isBlank()) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "未配置 PARALLAX_GATEWAY_ADMIN_SECRET，令牌签发不可用");
        }
        if (!jwtService.isConfigured()) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "未配置 PARALLAX_JWT_SECRET，令牌签发不可用");
        }
        String provided = request == null ? null : request.secret();
        if (provided == null || !constantTimeEquals(expected, provided)) {
            // 与失败原因无关的统一措辞：不要告诉调用方"密钥对了但别的错了"
            throw ApiException.unauthorized("密钥不正确");
        }
        String token = jwtService.issueAccessToken("admin", AuthPrincipal.ROLE_ADMIN);
        return new TokenResponse(token, "Bearer", AuthPrincipal.ROLE_ADMIN);
    }

    /** 定长比较，避免用 == 或 equals 泄漏逐字节的时序信息。 */
    private boolean constantTimeEquals(String a, String b) {
        return MessageDigest.isEqual(
                a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
}
