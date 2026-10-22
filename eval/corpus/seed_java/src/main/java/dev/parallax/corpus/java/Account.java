package dev.parallax.corpus.java;

import java.util.HashMap;
import java.util.Map;

/** 简单账户账本：对外只暴露转账与余额查询。 */
public class Account {

    private final Map<String, Long> balances = new HashMap<>();

    public Account(Map<String, Long> initial) {
        balances.putAll(initial);
    }

    public long balanceOf(String owner) {
        return balances.getOrDefault(owner, 0L);
    }

    /**
     * 转账：扣付款方、加收款方。
     *
     * <p>缺陷：先扣款再判断余额，付方余额可以被扣成负数。
     */
    public void transfer(String from, String to, long amount) {
        long fromBalance = balances.getOrDefault(from, 0L);
        balances.put(from, fromBalance - amount);
        balances.put(to, balances.getOrDefault(to, 0L) + amount);
    }
}
