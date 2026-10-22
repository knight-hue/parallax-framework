package dev.parallax.corpus.java;

import java.time.Clock;

/** 令牌桶限流：容量固定，按固定速率补充。 */
public class TokenBucket {

    private final int capacity;
    private final int refillPerSecond;
    private final Clock clock;

    private int tokens;
    private long lastRefillMillis;

    public TokenBucket(int capacity, int refillPerSecond, Clock clock) {
        this.capacity = capacity;
        this.refillPerSecond = refillPerSecond;
        this.clock = clock;
        this.tokens = capacity;
        this.lastRefillMillis = clock.millis();
    }

    /**
     * 缺陷：用整秒除数计算补充量，并且无论是否补到令牌都把 lastRefillMillis 重置到当前时刻，
     * 于是连续的亚秒级调用会把不足一秒的时间片全部丢掉，桶永远补不回来。
     */
    public boolean tryAcquire() {
        long now = clock.millis();
        long elapsedSeconds = (now - lastRefillMillis) / 1000;
        tokens = Math.min(capacity, tokens + (int) elapsedSeconds * refillPerSecond);
        lastRefillMillis = now;
        if (tokens <= 0) {
            return false;
        }
        tokens--;
        return true;
    }

    public int availableTokens() {
        return tokens;
    }
}
