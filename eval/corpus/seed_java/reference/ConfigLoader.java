package dev.parallax.corpus.java;

import java.util.Map;

/** 参考修复：缺键或格式错误都抛出带键名的异常。 */
public class ConfigLoader {

    private final Map<String, String> values;

    public ConfigLoader(Map<String, String> values) {
        this.values = values;
    }

    public int getInt(String key) {
        String raw = values.get(key);
        if (raw == null) {
            throw new IllegalArgumentException("missing config: " + key);
        }
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("invalid integer for " + key + ": " + raw, ex);
        }
    }
}
