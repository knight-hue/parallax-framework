package dev.parallax.gateway.runs;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 一次审查运行。
 *
 * 分两段写入，因为信息分两批才拿得到：
 * 1. **提交时**（网关代理 `POST /api/v1/audits`）先落 `queued`，只知凭据与时间；
 *    这一步是配额计数的事实来源——只统计已完成的运行，用户就能在第一次完成之前
 *    并发提交上千次，每次都真实烧掉模型费用。
 * 2. **完成回调时**补 `status` / token / 统计，此时才知道真实用量。
 */
@Entity
@Table(name = "audit_run")
public class AuditRun {

    @Id
    private String id;

    @Column(name = "run_id")
    private String runId;

    @Column(name = "credential_id", nullable = false)
    private String credentialId;

    @Column(name = "repo_path")
    private String repoPath;

    @Column(name = "question")
    private String question;

    @Column(nullable = false)
    private String status;

    @Column(name = "submitted_at", nullable = false)
    private Instant submittedAt = Instant.now();

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Column(name = "elapsed_s")
    private Double elapsedS;

    @Column(name = "trace_id")
    private String traceId;

    @Column(name = "prompt_tokens")
    private Long promptTokens;

    @Column(name = "completion_tokens")
    private Long completionTokens;

    @Column(name = "total_tokens")
    private Long totalTokens;

    @Column(name = "counts_json")
    private String countsJson;

    @Column(name = "stop_reason")
    private String stopReason;

    @Column(name = "error")
    private String error;

    protected AuditRun() {
    }

    public AuditRun(String id, String credentialId, String repoPath, String question, String traceId) {
        this.id = id;
        this.credentialId = credentialId;
        this.repoPath = repoPath;
        this.question = question;
        this.status = RunStatus.QUEUED;
        this.traceId = traceId;
        this.submittedAt = Instant.now();
    }

    /** 拿到上游 run_id。 */
    public void attachUpstreamRunId(String upstreamRunId) {
        this.runId = upstreamRunId;
    }

    public void markFailed(String failure) {
        this.status = RunStatus.FAILED;
        this.error = failure;
        this.finishedAt = Instant.now();
    }

    public void complete(
            String status,
            long promptTokens,
            long completionTokens,
            Double elapsedS,
            String countsJson,
            String stopReason) {
        this.status = status;
        this.promptTokens = promptTokens;
        this.completionTokens = completionTokens;
        this.totalTokens = promptTokens + completionTokens;
        this.elapsedS = elapsedS;
        this.countsJson = countsJson;
        this.stopReason = stopReason;
        this.finishedAt = Instant.now();
    }

    public String getId() {
        return id;
    }

    public String getRunId() {
        return runId;
    }

    public String getCredentialId() {
        return credentialId;
    }

    public String getRepoPath() {
        return repoPath;
    }

    public String getQuestion() {
        return question;
    }

    public String getStatus() {
        return status;
    }

    public Instant getSubmittedAt() {
        return submittedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    public Double getElapsedS() {
        return elapsedS;
    }

    public String getTraceId() {
        return traceId;
    }

    public Long getPromptTokens() {
        return promptTokens;
    }

    public Long getCompletionTokens() {
        return completionTokens;
    }

    public Long getTotalTokens() {
        return totalTokens;
    }

    public String getCountsJson() {
        return countsJson;
    }

    public String getStopReason() {
        return stopReason;
    }

    public String getError() {
        return error;
    }
}
