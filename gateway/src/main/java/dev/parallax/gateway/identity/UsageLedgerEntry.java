package dev.parallax.gateway.identity;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 用量账本条目：一次审查运行消耗了多少。
 *
 * 只追加。写入时机是 Python 编排服务的**完成回调**，而不是提交时——
 * 提交时还不知道用了多少 token，先记一笔再回改就等于把账本变成了可变状态，
 * 那样"本月用了多少"这个问题的答案会随着时间变化，对不上账。
 */
@Entity
@Table(name = "usage_ledger")
public class UsageLedgerEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "credential_id", nullable = false)
    private String credentialId;

    @Column(name = "run_id", nullable = false, unique = true)
    private String runId;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt = Instant.now();

    @Column(name = "prompt_tokens", nullable = false)
    private long promptTokens;

    @Column(name = "completion_tokens", nullable = false)
    private long completionTokens;

    @Column(name = "total_tokens", nullable = false)
    private long totalTokens;

    @Column(name = "trace_id")
    private String traceId;

    protected UsageLedgerEntry() {
    }

    public UsageLedgerEntry(
            String credentialId,
            String runId,
            long promptTokens,
            long completionTokens,
            String traceId) {
        this.credentialId = credentialId;
        this.runId = runId;
        this.promptTokens = promptTokens;
        this.completionTokens = completionTokens;
        this.totalTokens = promptTokens + completionTokens;
        this.traceId = traceId;
        this.occurredAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getCredentialId() {
        return credentialId;
    }

    public String getRunId() {
        return runId;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public long getPromptTokens() {
        return promptTokens;
    }

    public long getCompletionTokens() {
        return completionTokens;
    }

    public long getTotalTokens() {
        return totalTokens;
    }

    public String getTraceId() {
        return traceId;
    }
}
