package dev.parallax.labs.seata;

import org.apache.seata.rm.tcc.api.BusinessActionContext;
import org.apache.seata.rm.tcc.api.BusinessActionContextParameter;
import org.apache.seata.rm.tcc.api.LocalTCC;
import org.apache.seata.rm.tcc.api.TwoPhaseBusinessAction;
import org.springframework.stereotype.Component;

/**
 * TCC branch: try freezes stock, confirm consumes it, cancel releases it.
 *
 * <p>Idempotency comes from the {@code TRY -> CONFIRMED/CANCELLED} conditional updates, so a
 * retried confirm or cancel is a no-op instead of double counting.
 */
@Component
@LocalTCC
public class TccReservationAction {

    private final InventoryStore inventory;
    private final ReservationStore reservations;

    public TccReservationAction(InventoryStore inventory, ReservationStore reservations) {
        this.inventory = inventory;
        this.reservations = reservations;
    }

    @TwoPhaseBusinessAction(name = "tccReserveStock", commitMethod = "commit", rollbackMethod = "rollback")
    public boolean tryReserve(
            BusinessActionContext context,
            @BusinessActionContextParameter(paramName = "sku") String sku,
            @BusinessActionContextParameter(paramName = "quantity") int quantity) {
        String xid = context == null ? org.apache.seata.core.context.RootContext.getXID() : context.getXid();
        if (xid == null || xid.isBlank()) {
            throw new IllegalStateException("TCC try must run inside a global transaction");
        }
        inventory.freeze(sku, quantity);
        reservations.insertTry(xid, sku, quantity);
        return true;
    }

    public boolean commit(BusinessActionContext context) {
        String sku = (String) context.getActionContext("sku");
        int quantity = ((Number) context.getActionContext("quantity")).intValue();
        if (reservations.markConfirmed(context.getXid(), sku) == 0) {
            return true; // 已经确认或已取消，幂等返回
        }
        inventory.consumeFrozen(sku, quantity);
        return true;
    }

    public boolean rollback(BusinessActionContext context) {
        String sku = (String) context.getActionContext("sku");
        int quantity = ((Number) context.getActionContext("quantity")).intValue();
        if (reservations.markCancelled(context.getXid(), sku) == 0) {
            return true; // 已经取消，幂等返回
        }
        inventory.releaseFrozen(sku, quantity);
        return true;
    }
}
