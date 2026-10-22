package dev.parallax.labs.seata;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Order table access used by the AT branch. */
@Component
public class OrderStore {

    private final JdbcTemplate jdbc;

    public OrderStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void place(String sku, int quantity) {
        jdbc.update(
                "INSERT INTO shop_order (sku, quantity, status, created_at) "
                        + "VALUES (?, ?, 'CREATED', CURRENT_TIMESTAMP(6))",
                sku, quantity);
    }

    public int count(String sku) {
        Integer value = jdbc.queryForObject(
                "SELECT COUNT(*) FROM shop_order WHERE sku = ?", Integer.class, sku);
        return value == null ? 0 : value;
    }

    public void deleteAll() {
        jdbc.update("DELETE FROM shop_order");
    }
}
