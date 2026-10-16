package dev.parallax.gateway.identity;

import java.time.Instant;
import java.util.List;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;

/**
 * API Key 的签发、查看与吊销。
 *
 * **明文 key 只在创建响应里出现一次。** 没有"再查一次 key"的端点，
 * 因为服务端根本不存它——需要再取一次的正确做法是吊销旧的、签发新的。
 */
@RestController
@RequestMapping("/api/v1/credentials")
public class CredentialController {

    private final ApiKeyService apiKeys;
    private final ParallaxProperties props;

    public CredentialController(ApiKeyService apiKeys, ParallaxProperties props) {
        this.apiKeys = apiKeys;
        this.props = props;
    }

    public record CreateRequest(@NotBlank String name, String role, String quotaPolicy) {
    }

    public record QuotaView(String policy, int dailyRunLimit, long dailyTokenLimit, long monthlyTokenLimit) {
    }

    /** 创建响应：唯一一次携带明文 key。 */
    public record CreatedView(
            String id,
            String name,
            String role,
            String keyPrefix,
            String apiKey,
            QuotaView quota,
            Instant createdAt) {
    }

    public record CredentialView(
            String id,
            String name,
            String role,
            String keyPrefix,
            QuotaView quota,
            Instant createdAt,
            Instant revokedAt,
            Instant lastUsedAt) {
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public CreatedView create(@Valid @RequestBody CreateRequest request) {
        requireEnabled();
        String role = request.role() == null || request.role().isBlank()
                ? AuthPrincipal.ROLE_VIEWER
                : request.role().toUpperCase();
        ApiKeyService.Issued issued = apiKeys.issue(request.name(), role, request.quotaPolicy());
        return new CreatedView(
                issued.credential().getId(),
                issued.credential().getName(),
                issued.credential().getRole(),
                issued.credential().getKeyPrefix(),
                issued.plaintextKey(),
                quotaView(issued.credential().getQuotaPolicy()),
                issued.credential().getCreatedAt());
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public List<CredentialView> list() {
        requireEnabled();
        return apiKeys.list().stream().map(CredentialController::toView).toList();
    }

    /**
     * 吊销。**立即生效**：校验路径每次都读实时状态，被吊销的 key 下一个请求就被拒。
     *
     * 返回吊销后的视图而不是 204，是因为调用方需要确认吊销的确实是它以为的那把 key。
     */
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public CredentialView revoke(@PathVariable String id) {
        requireEnabled();
        apiKeys.revoke(id);
        return apiKeys.list().stream()
                .filter(c -> c.getId().equals(id))
                .findFirst()
                .map(CredentialController::toView)
                .orElseThrow(() -> ApiException.badRequest("凭据不存在：" + id));
    }

    private void requireEnabled() {
        if (!props.getIdentity().isEnabled()) {
            throw new ApiException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未启用身份与配额（PARALLAX_IDENTITY_ENABLED=false），凭据管理不可用");
        }
    }

    static QuotaView quotaView(QuotaPolicy policy) {
        return new QuotaView(
                policy.getName(),
                policy.getDailyRunLimit(),
                policy.getDailyTokenLimit(),
                policy.getMonthlyTokenLimit());
    }

    static CredentialView toView(ApiCredential credential) {
        return new CredentialView(
                credential.getId(),
                credential.getName(),
                credential.getRole(),
                credential.getKeyPrefix(),
                quotaView(credential.getQuotaPolicy()),
                credential.getCreatedAt(),
                credential.getRevokedAt(),
                credential.getLastUsedAt());
    }
}
