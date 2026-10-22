package dev.parallax.corpus.java;

import java.util.Map;

/** 配置读取：把字符串配置按需转成整数。 */
public class ConfigLoader {

    private final Map<String, String> values;

    public ConfigLoader(Map<String, String> values) {
        this.values = values;
    }

    /**
     * 缺陷：键不存在或值不是数字时静默返回 0，调用方无法区分"配置为 0"和"配置写错/漏配"。
     */
    public int getInt(String key) {
        String raw = values.get(key);
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }
}
