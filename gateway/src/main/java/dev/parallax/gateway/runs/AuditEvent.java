package dev.parallax.gateway.runs;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * 网关视角的运行生命周期事件。
 *
 * 只记 `submitted` / `completed` / `failed` 这类网关自己观察到的事。
 * 编排内部的事件（分区、盲读、聚合、补检）留在上游的可重放事件总线里，
 * 不复制一份——两份事实来源迟早会不一致。
 */
@Entity
@Table(name = "audit_event")
public class AuditEvent {

    /** 提交：网关把请求转发给了上游。 */
    public static final String SUBMITTED = "submitted";
    /** 完成：上游回调报告了用量与统计。 */
    public static final String COMPLETED = "completed";
    /** 失败：没能转发成功，或上游报告运行失败。 */
    public static final String FAILED = "failed";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 网关的提交记录 id（**不是**上游 run_id）：提交那刻还不知道上游 id，见 RunService。 */
    @Column(name = "run_id", nullable = false)
    private String runId;

    @Column(name = "event_type", nullable = false)
    private String eventType;

    @Column(name = "at", nullable = false)
    private Instant at = Instant.now();

    @Column(name = "detail")
    private String detail;

    @Column(name = "trace_id")
    private String traceId;

    protected AuditEvent() {
    }

    public AuditEvent(String runId, String eventType, String detail, String traceId) {
        this.runId = runId;
        this.eventType = eventType;
        this.detail = detail;
        this.traceId = traceId;
        this.at = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getRunId() {
        return runId;
    }

    public String getEventType() {
        return eventType;
    }

    public Instant getAt() {
        return at;
    }

    public String getDetail() {
        return detail;
    }

    public String getTraceId() {
        return traceId;
    }
}
