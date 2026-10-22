package dev.parallax.labs.seata;

import org.apache.seata.spring.annotation.GlobalTransactional;
import org.springframework.stereotype.Service;

/** TCC branch driver: the global transaction decides whether the reservation commits or cancels. */
@Service
public class TccCheckoutService {

    private final TccReservationAction action;

    public TccCheckoutService(TccReservationAction action) {
        this.action = action;
    }

    @GlobalTransactional(name = "tcc-checkout", rollbackFor = Exception.class)
    public void reserve(String sku, int quantity, boolean failAfterTry) {
        action.tryReserve(null, sku, quantity);
        if (failAfterTry) {
            throw new IllegalStateException("simulated failure after TCC try");
        }
    }
}
