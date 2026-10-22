package dev.parallax.corpus.java;

import java.time.Clock;

/** 参考修复：保留不足一秒的余量，连续亚秒调用也能累积补令牌。 */
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

    public boolean tryAcquire() {
        long now = clock.millis();
        long elapsedMillis = now - lastRefillMillis;
        if (elapsedMillis >= 1000) {
            long wholeSeconds = elapsedMillis / 1000;
            tokens = Math.min(capacity, tokens + (int) wholeSeconds * refillPerSecond);
            lastRefillMillis += wholeSeconds * 1000;
        }
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
