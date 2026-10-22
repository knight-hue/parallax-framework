package dev.parallax.labs.seata;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Thin JDBC access to the stock table; every statement runs inside the Seata-proxied datasource. */
@Component
public class InventoryStore {

    private final JdbcTemplate jdbc;

    public InventoryStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public int available(String sku) {
        Integer value = jdbc.queryForObject(
                "SELECT available FROM inventory WHERE sku = ?", Integer.class, sku);
        return value == null ? -1 : value;
    }

    public int frozen(String sku) {
        Integer value = jdbc.queryForObject(
                "SELECT frozen FROM inventory WHERE sku = ?", Integer.class, sku);
        return value == null ? -1 : value;
    }

    /** AT branch: plain UPDATE, Seata records the before/after image into undo_log. */
    public void deduct(String sku, int quantity) {
        int updated = jdbc.update(
                "UPDATE inventory SET available = available - ?, updated_at = CURRENT_TIMESTAMP(6) "
                        + "WHERE sku = ? AND available >= ?",
                quantity, sku, quantity);
        if (updated != 1) {
            throw new IllegalStateException("insufficient stock for " + sku);
        }
    }

    /** TCC try: move stock from available to frozen. */
    public void freeze(String sku, int quantity) {
        int updated = jdbc.update(
                "UPDATE inventory SET available = available - ?, frozen = frozen + ?, "
                        + "updated_at = CURRENT_TIMESTAMP(6) WHERE sku = ? AND available >= ?",
                quantity, quantity, sku, quantity);
        if (updated != 1) {
            throw new IllegalStateException("cannot freeze " + quantity + " of " + sku);
        }
    }

    /** TCC confirm: the frozen stock is consumed for good. */
    public void consumeFrozen(String sku, int quantity) {
        jdbc.update("UPDATE inventory SET frozen = frozen - ?, updated_at = CURRENT_TIMESTAMP(6) "
                + "WHERE sku = ? AND frozen >= ?", quantity, sku, quantity);
    }

    /** TCC cancel: frozen stock goes back to available. */
    public void releaseFrozen(String sku, int quantity) {
        jdbc.update("UPDATE inventory SET available = available + ?, frozen = frozen - ?, "
                + "updated_at = CURRENT_TIMESTAMP(6) WHERE sku = ? AND frozen >= ?",
                quantity, quantity, sku, quantity);
    }

    public int undoLogRows() {
        Integer value = jdbc.queryForObject("SELECT COUNT(*) FROM undo_log", Integer.class);
        return value == null ? 0 : value;
    }

    public void clearUndoLog() {
        jdbc.update("DELETE FROM undo_log");
    }

    /** 实验前把单个 SKU 恢复成固定库存。 */
    public void reset(String sku, int available) {
        jdbc.update("UPDATE inventory SET available = ?, frozen = 0, updated_at = CURRENT_TIMESTAMP(6) "
                + "WHERE sku = ?", available, sku);
    }
}
