package dev.parallax.gateway.runs;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class RunStatusTest {

    @Test
    void acceptsOnlyPersistedRunStates() {
        assertThat(RunStatus.isKnown(RunStatus.QUEUED)).isTrue();
        assertThat(RunStatus.isKnown(RunStatus.RUNNING)).isTrue();
        assertThat(RunStatus.isKnown(RunStatus.DONE)).isTrue();
        assertThat(RunStatus.isKnown(RunStatus.FAILED)).isTrue();
        assertThat(RunStatus.isKnown(RunStatus.CANCELED)).isTrue();
        assertThat(RunStatus.isKnown("completed")).isFalse();
        assertThat(RunStatus.isKnown("admin")).isFalse();
        assertThat(RunStatus.isKnown(null)).isFalse();
    }
}
