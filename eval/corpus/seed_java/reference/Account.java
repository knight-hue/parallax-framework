package dev.parallax.corpus.java;

import java.util.HashMap;
import java.util.Map;

/** 参考修复：先校验余额再动账。 */
public class Account {

    private final Map<String, Long> balances = new HashMap<>();

    public Account(Map<String, Long> initial) {
        balances.putAll(initial);
    }

    public long balanceOf(String owner) {
        return balances.getOrDefault(owner, 0L);
    }

    public void transfer(String from, String to, long amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("amount must be positive");
        }
        long fromBalance = balances.getOrDefault(from, 0L);
        if (fromBalance < amount) {
            throw new IllegalStateException("insufficient balance for " + from);
        }
        balances.put(from, fromBalance - amount);
        balances.put(to, balances.getOrDefault(to, 0L) + amount);
    }
}
