package dev.parallax.labs.seata;

import org.apache.seata.spring.annotation.GlobalTransactional;
import org.springframework.stereotype.Service;

/**
 * AT branch: both statements run in one global transaction.
 *
 * <p>Seata proxies the datasource, writes undo_log around each local transaction and drives the
 * two-phase commit/rollback against the transaction coordinator at 127.0.0.1:8091.
 */
@Service
public class AtCheckoutService {

    private final InventoryStore inventory;
    private final OrderStore orders;

    public AtCheckoutService(InventoryStore inventory, OrderStore orders) {
        this.inventory = inventory;
        this.orders = orders;
    }

    @GlobalTransactional(name = "at-checkout", rollbackFor = Exception.class)
    public void checkout(String sku, int quantity, boolean failAfterDeduct) {
        orders.place(sku, quantity);
        inventory.deduct(sku, quantity);
        if (failAfterDeduct) {
            throw new IllegalStateException("simulated failure after deduct");
        }
    }
}
