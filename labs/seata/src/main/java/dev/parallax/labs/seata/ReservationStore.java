package dev.parallax.labs.seata;

import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Reservation bookkeeping for the TCC branch. */
@Component
public class ReservationStore {

    private final JdbcTemplate jdbc;

    public ReservationStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insertTry(String xid, String sku, int quantity) {
        jdbc.update(
                "INSERT INTO tcc_reservation (xid, sku, quantity, status, created_at) "
                        + "VALUES (?, ?, ?, 'TRY', CURRENT_TIMESTAMP(6))",
                xid, sku, quantity);
    }

    public int markConfirmed(String xid, String sku) {
        return jdbc.update(
                "UPDATE tcc_reservation SET status = 'CONFIRMED' WHERE xid = ? AND sku = ? AND status = 'TRY'",
                xid, sku);
    }

    public int markCancelled(String xid, String sku) {
        return jdbc.update(
                "UPDATE tcc_reservation SET status = 'CANCELLED' WHERE xid = ? AND sku = ? AND status = 'TRY'",
                xid, sku);
    }

    public String statusOf(String xid, String sku) {
        List<String> statuses = jdbc.queryForList(
                "SELECT status FROM tcc_reservation WHERE xid = ? AND sku = ?", String.class, xid, sku);
        return statuses.isEmpty() ? "" : statuses.getFirst();
    }

    public String latestStatus(String sku) {
        List<String> statuses = jdbc.queryForList(
                "SELECT status FROM tcc_reservation WHERE sku = ? ORDER BY id DESC LIMIT 1",
                String.class, sku);
        return statuses.isEmpty() ? "" : statuses.getFirst();
    }

    public void deleteAll() {
        jdbc.update("DELETE FROM tcc_reservation");
    }
}
