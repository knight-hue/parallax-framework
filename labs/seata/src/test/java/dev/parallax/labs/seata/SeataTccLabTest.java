package dev.parallax.labs.seata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** TCC mode: try/confirm/cancel are driven by the coordinator, not by local rollback. */
@SpringBootTest
class SeataTccLabTest {

    private static final String SKU = "sku-1";

    @Autowired TccCheckoutService tcc;
    @Autowired InventoryStore inventory;
    @Autowired ReservationStore reservations;

    @BeforeEach
    void reset() {
        reservations.deleteAll();
        inventory.reset(SKU, 10);
    }

    @Test
    void globalCommitConfirmsTheReservation() {
        tcc.reserve(SKU, 3, false);

        assertThat(inventory.available(SKU)).isEqualTo(7);
        assertThat(inventory.frozen(SKU)).isZero();
        assertThat(reservations.latestStatus(SKU)).isEqualTo("CONFIRMED");
    }

    @Test
    void failureAfterTryCancelsTheReservation() {
        assertThatThrownBy(() -> tcc.reserve(SKU, 3, true))
                .hasMessageContaining("simulated failure after TCC try");

        assertThat(inventory.available(SKU))
                .as("cancel releases the frozen stock back to available")
                .isEqualTo(10);
        assertThat(inventory.frozen(SKU)).isZero();
        assertThat(reservations.latestStatus(SKU)).isEqualTo("CANCELLED");
    }
}
