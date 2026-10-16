package dev.parallax.gateway.identity;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import dev.parallax.gateway.auth.AuthPrincipal;
import dev.parallax.gateway.config.ParallaxProperties;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * API Key 的签发与校验。
 *
 * 三条设计约束：
 * 1. **明文只在签发时返回一次**，之后服务端只存 SHA-256 摘要；
 * 2. **查找走摘要索引**，不做逐字节比较——那会泄漏前缀匹配长度的时序信息；
 * 3. 校验时按需 touch `last_used_at`，但**不在只读事务里写库**，
 *    否则高频校验会把它变成写热点。
 */
@Service
public class ApiKeyService {

    private static final int KEY_BYTES = 32;
    private static final int PREFIX_KEEP = 12;

    private final ApiCredentialRepository credentials;
    private final QuotaPolicyRepository policies;
    private final ParallaxProperties props;
    private final SecureRandom random = new SecureRandom();

    public ApiKeyService(
            ApiCredentialRepository credentials, QuotaPolicyRepository policies, ParallaxProperties props) {
        this.credentials = credentials;
        this.policies = policies;
        this.props = props;
    }

    /** 签发结果。明文 key 只在此对象里出现，调用方负责只返回给创建者。 */
    public record Issued(ApiCredential credential, String plaintextKey) {
    }

    @Transactional
    public Issued issue(String name, String role, String policyName) {
        QuotaPolicy policy = policies
                .findByName(policyName == null || policyName.isBlank() ? "default" : policyName)
                .orElseThrow(() -> new IllegalArgumentException("配额策略不存在：" + policyName));

        String plaintext = generateKey();
        String hash = hash(plaintext);
        ApiCredential credential = credentials.save(new ApiCredential(
                UUID.randomUUID().toString(),
                name,
                hash,
                prefix(plaintext),
                role,
                policy));
        return new Issued(credential, plaintext);
    }

    /** 按明文 key 找凭据；已吊销的视为不存在。 */
    @Transactional
    public Optional<ApiCredential> resolve(String plaintextKey) {
        if (plaintextKey == null || plaintextKey.isBlank()) {
            return Optional.empty();
        }
        return credentials.findByKeyHash(hash(plaintextKey)).filter(c -> !c.isRevoked());
    }

    @Transactional
    public void touch(ApiCredential credential) {
        credential.touch(Instant.now());
        credentials.save(credential);
    }

    @Transactional
    public void revoke(String credentialId) {
        credentials
                .findById(credentialId)
                .ifPresentOrElse(ApiCredential::revoke, () -> {
                    throw new IllegalArgumentException("凭据不存在：" + credentialId);
                });
    }

    @Transactional(readOnly = true)
    public List<ApiCredential> list() {
        return credentials.findAllByOrderByCreatedAtDesc();
    }

    @Transactional
    public void ensureDefaultPolicy(String name, int runs, long dailyTokens, long monthlyTokens) {
        if (policies.findByName(name).isEmpty()) {
            policies.save(new QuotaPolicy(name, runs, dailyTokens, monthlyTokens));
        }
    }

    /** `plx_` 前缀让人一眼认出手里这串是什么，也便于泄漏时做内容扫描。 */
    private String generateKey() {
        byte[] bytes = new byte[KEY_BYTES];
        random.nextBytes(bytes);
        String body = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        return props.getIdentity().getKeyPrefix() + body;
    }

    private String prefix(String plaintext) {
        return plaintext.substring(0, Math.min(PREFIX_KEEP, plaintext.length())) + "…";
    }

    public static String hash(String plaintext) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(plaintext.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 是所有合规 JVM 的必备算法，走到这里说明运行环境本身不可信
            throw new IllegalStateException("运行环境缺少 SHA-256", ex);
        }
    }

    public static AuthPrincipal principalOf(ApiCredential credential) {
        return new AuthPrincipal(credential.getName(), credential.getRole(), credential.getId());
    }
}
