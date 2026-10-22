package dev.parallax.corpus.java;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.Test;

class ConfigLoaderTest {

    @Test
    void validValueIsParsed() {
        ConfigLoader loader = new ConfigLoader(Map.of("port", "8080"));

        assertThat(loader.getInt("port")).isEqualTo(8080);
    }

    @Test
    void invalidValueFailsLoudlyInsteadOfReturningZero() {
        ConfigLoader loader = new ConfigLoader(Map.of("port", "not-a-number"));

        assertThatThrownBy(() -> loader.getInt("port"))
                .as("配置写错必须报错，不能静默变成 0")
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("port");
    }

    @Test
    void missingKeyFailsLoudly() {
        ConfigLoader loader = new ConfigLoader(new HashMap<>());

        assertThatThrownBy(() -> loader.getInt("missing"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("missing");
    }
}
