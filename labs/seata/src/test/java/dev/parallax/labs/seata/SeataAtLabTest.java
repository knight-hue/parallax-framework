package dev.parallax.labs.seata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** AT mode: Seata drives commit/rollback against the real coordinator and real MySQL. */
@SpringBootTest
class SeataAtLabTest {

    private static final String SKU = "sku-1";

    @Autowired AtCheckoutService checkout;
    @Autowired InventoryStore inventory;
    @Autowired OrderStore orders;

    @BeforeEach
    void reset() {
        orders.deleteAll();
        inventory.clearUndoLog();
        inventory.reset(SKU, 10);
    }

    @Test
    void globalCommitAppliesBothLocalTransactions() {
        checkout.checkout(SKU, 2, false);

        assertThat(inventory.available(SKU)).isEqualTo(8);
        assertThat(orders.count(SKU)).isEqualTo(1);
    }

    @Test
    void failureAfterDeductRollsBackOrderAndStock() {
        assertThatThrownBy(() -> checkout.checkout(SKU, 2, true))
                .hasMessageContaining("simulated failure after deduct");

        assertThat(inventory.available(SKU))
                .as("undo_log rollback restores the deducted stock")
                .isEqualTo(10);
        assertThat(orders.count(SKU))
                .as("the order insert is rolled back with the global transaction")
                .isZero();
    }

    @Test
    void rollbackLeavesNoUndoLogForTheFailedBranch() {
        assertThatThrownBy(() -> checkout.checkout(SKU, 2, true))
                .hasMessageContaining("simulated failure after deduct");

        assertThat(inventory.undoLogRows())
                .as("the rollback path undoes and removes the branch undo_log rows itself")
                .isZero();
    }
}
