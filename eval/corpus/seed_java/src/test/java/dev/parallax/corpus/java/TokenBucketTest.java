package dev.parallax.corpus.java;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;

class TokenBucketTest {

    @Test
    void bucketStartsFullAndRejectsWhenDrained() {
        MutableClock clock = new MutableClock(0);
        TokenBucket bucket = new TokenBucket(2, 2, clock);

        assertThat(bucket.tryAcquire()).isTrue();
        assertThat(bucket.tryAcquire()).isTrue();
        assertThat(bucket.tryAcquire()).as("容量用尽后应拒绝").isFalse();
    }

    @Test
    void repeatedSubSecondCallsStillRefillAccumulatedTime() {
        MutableClock clock = new MutableClock(0);
        TokenBucket bucket = new TokenBucket(2, 2, clock);
        assertThat(bucket.tryAcquire()).isTrue();
        assertThat(bucket.tryAcquire()).isTrue();

        boolean acquired = false;
        for (int i = 0; i < 6 && !acquired; i++) {
            clock.advance(500);
            acquired = bucket.tryAcquire();
        }

        assertThat(acquired)
                .as("每 500ms 调用一次，累计 3 秒应当补回令牌，而不是把亚秒时间片全部丢弃")
                .isTrue();
    }

    @Test
    void refillNeverExceedsCapacity() {
        MutableClock clock = new MutableClock(0);
        TokenBucket bucket = new TokenBucket(2, 2, clock);
        assertThat(bucket.tryAcquire()).isTrue();
        assertThat(bucket.tryAcquire()).isTrue();

        clock.advance(60_000);
        assertThat(bucket.tryAcquire()).isTrue();
        assertThat(bucket.availableTokens()).isLessThanOrEqualTo(2);
    }

    private static final class MutableClock extends Clock {
        private long millis;

        private MutableClock(long startMillis) {
            this.millis = startMillis;
        }

        void advance(long deltaMillis) {
            millis += deltaMillis;
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return Instant.ofEpochMilli(millis);
        }

        @Override
        public long millis() {
            return millis;
        }
    }
}
