package dev.parallax.gateway.runs;

/**
 * 运行状态。
 *
 * 刻意用字符串常量而不是 Java enum 存库：状态集合几乎必然会增长
 * （将来可能有 `cancelled`、`timed_out`），存 enum 名一旦改名就要写数据迁移。
 */
public final class RunStatus {

    public static final String QUEUED = "queued";
    public static final String RUNNING = "running";
    public static final String DONE = "done";
    public static final String FAILED = "failed";
    public static final String CANCELED = "canceled";

    private RunStatus() {
    }

    public static boolean isKnown(String status) {
        return QUEUED.equals(status)
                || RUNNING.equals(status)
                || DONE.equals(status)
                || FAILED.equals(status)
                || CANCELED.equals(status);
    }
}
