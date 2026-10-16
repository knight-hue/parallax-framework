package dev.parallax.gateway.identity;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 配额策略。
 *
 * 做成独立表而不是把三个上限直接挂在凭据上：调额度时改一处即可作用于一批凭据，
 * 否则"给所有试用账号提高日额度"会变成一次批量 UPDATE。
 */
@Entity
@Table(name = "quota_policy")
public class QuotaPolicy {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String name;

    @Column(name = "daily_run_limit", nullable = false)
    private int dailyRunLimit;

    @Column(name = "daily_token_limit", nullable = false)
    private long dailyTokenLimit;

    @Column(name = "monthly_token_limit", nullable = false)
    private long monthlyTokenLimit;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();

    protected QuotaPolicy() {
    }

    public QuotaPolicy(String name, int dailyRunLimit, long dailyTokenLimit, long monthlyTokenLimit) {
        this.name = name;
        this.dailyRunLimit = dailyRunLimit;
        this.dailyTokenLimit = dailyTokenLimit;
        this.monthlyTokenLimit = monthlyTokenLimit;
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public int getDailyRunLimit() {
        return dailyRunLimit;
    }

    public long getDailyTokenLimit() {
        return dailyTokenLimit;
    }

    public long getMonthlyTokenLimit() {
        return monthlyTokenLimit;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
