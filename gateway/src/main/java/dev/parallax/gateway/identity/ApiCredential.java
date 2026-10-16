package dev.parallax.gateway.identity;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

/**
 * API 凭据。
 *
 * **本类不持有明文 key 字段，这不是遗漏。** 明文只在签发那一次返回给调用方，
 * 之后服务端只有摘要；任何"再显示一次 key"的需求都应当被拒绝，
 * 而不是通过留一个可解密字段来满足。
 */
@Entity
@Table(name = "api_credential")
public class ApiCredential {

    @Id
    private String id;

    @Column(nullable = false)
    private String name;

    @Column(name = "key_hash", nullable = false, unique = true)
    private String keyHash;

    @Column(name = "key_prefix", nullable = false)
    private String keyPrefix;

    @Column(nullable = false)
    private String role;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "quota_policy_id", nullable = false)
    private QuotaPolicy quotaPolicy;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "revoked_at")
    private Instant revokedAt;

    @Column(name = "last_used_at")
    private Instant lastUsedAt;

    protected ApiCredential() {
    }

    public ApiCredential(
            String id, String name, String keyHash, String keyPrefix, String role, QuotaPolicy quotaPolicy) {
        this.id = id;
        this.name = name;
        this.keyHash = keyHash;
        this.keyPrefix = keyPrefix;
        this.role = role;
        this.quotaPolicy = quotaPolicy;
        this.createdAt = Instant.now();
    }

    public boolean isRevoked() {
        return revokedAt != null;
    }

    /** 吊销即刻生效：校验路径每次都读实时状态，不存在"令牌里带了旧状态"的窗口。 */
    public void revoke() {
        if (this.revokedAt == null) {
            this.revokedAt = Instant.now();
        }
    }

    public void touch(Instant at) {
        this.lastUsedAt = at;
    }

    public String getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getKeyHash() {
        return keyHash;
    }

    public String getKeyPrefix() {
        return keyPrefix;
    }

    public String getRole() {
        return role;
    }

    public QuotaPolicy getQuotaPolicy() {
        return quotaPolicy;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getRevokedAt() {
        return revokedAt;
    }

    public Instant getLastUsedAt() {
        return lastUsedAt;
    }
}
