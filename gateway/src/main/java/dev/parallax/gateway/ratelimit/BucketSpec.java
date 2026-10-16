package dev.parallax.gateway.ratelimit;

import java.time.Duration;

/**
 * 一个令牌桶的规格。
 *
 * 做成值对象而不是两个 int 参数：容量与窗口在调用点总是一起出现的，
 * 分开传容易把"贵操作的小桶"和"一般接口的大桶"对调，
 * 而那种错误不会报错，只会静静地放行超额流量。
 */
public record BucketSpec(int capacity, Duration window) {

    /** 贪心补充：把容量在窗口内均匀分配，避免"窗口末突然放行一整桶"。 */
    public Duration refillPeriod() {
        return Duration.ofNanos(Math.max(1, window.toNanos() / Math.max(1, capacity)));
    }
}
