-- C2 · 运行记录（提交与结果）
--
-- 【为什么 C1 就需要这张表】配额里的"每日运行次数"必须在**提交时**计数。
-- 若只统计完成回调，用户可以在任何一次完成之前并发提交上千次，
-- 每次都会真实烧掉模型费用——那正好是配额要防的事。
-- 因此提交时先落一条 `queued`，完成回调再补齐统计。
-- 查询端点（分页/过滤）与事件留痕属于 C2，见 V3。

CREATE TABLE audit_run (
    -- 网关侧的提交记录 id。与上游的 run_id 分开，因为提交失败时还没有 run_id，
    -- 但那次尝试同样应当计入额度。
    id                VARCHAR(36) PRIMARY KEY,
    -- 上游编排服务的 run_id。提交成功后才拿得到，故可空。
    run_id            VARCHAR(64),
    credential_id     VARCHAR(36) NOT NULL REFERENCES api_credential (id),
    repo_path         VARCHAR(1024),
    question          VARCHAR(2000),
    status            VARCHAR(24) NOT NULL,
    submitted_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at       TIMESTAMP WITH TIME ZONE,
    elapsed_s         DOUBLE PRECISION,
    trace_id          VARCHAR(64),
    prompt_tokens     BIGINT,
    completion_tokens BIGINT,
    total_tokens      BIGINT,
    -- 统计快照存 JSON 文本而不是 PG 的 jsonb：迁移要能在 H2 上执行，
    -- 否则本机没 Docker 的贡献者就永远跑不到这段建表
    counts_json       VARCHAR(1024),
    stop_reason       VARCHAR(64),
    error             VARCHAR(2000),
    -- 同一次上游运行只能对应一条提交记录。PG 与 H2 都允许多个 NULL，故可空也能加唯一约束。
    CONSTRAINT uq_audit_run_upstream UNIQUE (run_id)
);

CREATE INDEX idx_audit_run_credential_submitted ON audit_run (credential_id, submitted_at);
CREATE INDEX idx_audit_run_status ON audit_run (status);
