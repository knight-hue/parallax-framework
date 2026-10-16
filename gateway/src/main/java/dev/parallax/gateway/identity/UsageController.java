package dev.parallax.gateway.identity;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用量查询。
 *
 * 两个视角刻意分开：
 * - `GET /api/v1/usage/me`  → 集成方看自己，凭据从认证主体推导，**不接受 id 参数**，
 *   否则就变成了"传别人的 id 就能看别人的用量"。
 * - `GET /api/v1/usage`     → 运营方看全局，仅 ADMIN。
 */
@RestController
@RequestMapping("/api/v1/usage")
public class UsageController {

    private final QuotaService quota;
    private final ApiKeyService apiKeys;
    private final UsageLedgerRepository ledger;
    private final ParallaxProperties props;

    public UsageController(
            QuotaService quota,
            ApiKeyService apiKeys,
            UsageLedgerRepository ledger,
            ParallaxProperties props) {
        this.quota = quota;
        this.apiKeys = apiKeys;
        this.ledger = ledger;
        this.props = props;
    }

    public record WindowUsage(long runs, long tokens) {
    }

    public record UsageView(
            String credentialId,
            String name,
            CredentialController.QuotaView quota,
            WindowUsage today,
            WindowUsage month,
            Instant dailyWindowResetsAt) {
    }

    public record FleetRow(String credentialId, String name, String role, long runs, long tokens) {
    }

    public record FleetView(List<FleetRow> rows, long totalRuns, long totalTokens, Instant since) {
    }

    @GetMapping("/me")
    public UsageView me(@AuthenticationPrincipal AuthPrincipal principal) {
        requireEnabled();
        if (principal == null || !principal.hasCredential()) {
            throw ApiException.unauthorized("该端点需要 API Key 认证（X-API-Key 头）");
        }
        ApiCredential credential = apiKeys.list().stream()
                .filter(c -> c.getId().equals(principal.credentialId()))
                .findFirst()
                .orElseThrow(() -> ApiException.unauthorized("凭据不存在或已吊销"));
        Instant now = Instant.now();
        var today = quota.usageOf(credential.getId(), QuotaService.startOfUtcDay(now));
        var month = quota.usageOf(credential.getId(), QuotaService.startOfUtcMonth(now));
        return new UsageView(
                credential.getId(),
                credential.getName(),
                CredentialController.quotaView(credential.getQuotaPolicy()),
                new WindowUsage(today.runs(), today.tokens()),
                new WindowUsage(month.runs(), month.tokens()),
                QuotaService.endOfUtcDay(now));
    }

    /** 本月所有凭据的用量汇总。窗口取本月，与月度额度同一口径，便于直接对着额度读。 */
    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public FleetView fleet() {
        requireEnabled();
        Instant since = QuotaService.startOfUtcMonth(Instant.now());

        Map<String, long[]> aggregates = new LinkedHashMap<>();
        for (Object[] row : ledger.aggregateSince(since)) {
            String credentialId = (String) row[0];
            long runs = ((Number) row[1]).longValue();
            long tokens = ((Number) row[2]).longValue();
            aggregates.put(credentialId, new long[] {runs, tokens});
        }

        Map<String, ApiCredential> byId = apiKeys.list().stream()
                .collect(Collectors.toMap(ApiCredential::getId, c -> c, (a, b) -> a));

        // 没有任何用量的凭据也要出现在表里——只列有用量的会让运营方以为凭据丢了
        List<FleetRow> rows = new ArrayList<>();
        for (ApiCredential credential : byId.values()) {
            long[] usage = aggregates.getOrDefault(credential.getId(), new long[] {0, 0});
            rows.add(new FleetRow(
                    credential.getId(),
                    credential.getName(),
                    credential.getRole(),
                    usage[0],
                    usage[1]));
        }
        rows.sort(Comparator.comparingLong(FleetRow::tokens).reversed());

        long totalRuns = rows.stream().mapToLong(FleetRow::runs).sum();
        long totalTokens = rows.stream().mapToLong(FleetRow::tokens).sum();
        return new FleetView(rows, totalRuns, totalTokens, since);
    }

    private void requireEnabled() {
        if (!props.getIdentity().isEnabled()) {
            throw new ApiException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "未启用身份与配额（PARALLAX_IDENTITY_ENABLED=false），用量查询不可用");
        }
    }
}
