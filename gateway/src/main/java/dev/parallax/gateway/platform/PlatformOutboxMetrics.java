package dev.parallax.gateway.platform;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * Gauge-based visibility for outbox backlog. Queries are deliberately cheap and
 * run when metrics are scraped, not on the dispatch hot path.
 */
@Component
public class PlatformOutboxMetrics {

    public PlatformOutboxMetrics(MeterRegistry registry, JdbcTemplate jdbc) {
        Gauge.builder("parallax.outbox.pending", jdbc, this::pending).register(registry);
        Gauge.builder("parallax.outbox.inflight", jdbc, this::inflight).register(registry);
        Gauge.builder("parallax.outbox.oldest.age.seconds", jdbc, this::oldestAgeSeconds).register(registry);
    }

    private double pending(JdbcTemplate jdbc) {
        return count(jdbc, "PENDING");
    }

    private double inflight(JdbcTemplate jdbc) {
        return count(jdbc, "IN_FLIGHT");
    }

    private double oldestAgeSeconds(JdbcTemplate jdbc) {
        try {
            Timestamp oldest = jdbc.queryForObject(
                    "SELECT MIN(available_at) FROM platform_outbox WHERE status='PENDING'", Timestamp.class);
            return oldest == null ? 0 : Math.max(0, Duration.between(oldest.toInstant(), Instant.now()).getSeconds());
        } catch (RuntimeException ex) {
            // A metrics scrape must never break the health endpoint.
            return 0;
        }
    }

    private double count(JdbcTemplate jdbc, String status) {
        try {
            Integer value = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM platform_outbox WHERE status=?", Integer.class, status);
            return value == null ? 0 : value;
        } catch (RuntimeException ex) {
            return 0;
        }
    }
}
