package dev.parallax.corpus.java;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;

import org.junit.jupiter.api.Test;

class AccountTest {

    @Test
    void transferWithinBalanceMovesMoney() {
        Account account = new Account(Map.of("alice", 100L, "bob", 0L));

        account.transfer("alice", "bob", 40L);

        assertThat(account.balanceOf("alice")).isEqualTo(60);
        assertThat(account.balanceOf("bob")).isEqualTo(40);
    }

    @Test
    void transferBeyondBalanceIsRejectedAndLeavesBalancesUntouched() {
        Account account = new Account(Map.of("alice", 100L, "bob", 0L));

        assertThatThrownBy(() -> account.transfer("alice", "bob", 150L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("insufficient");

        assertThat(account.balanceOf("alice")).as("余额不足时不能扣款").isEqualTo(100);
        assertThat(account.balanceOf("bob")).as("余额不足时不能入账").isZero();
    }
}
