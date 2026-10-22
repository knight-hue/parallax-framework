package dev.parallax.corpus.java;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ReportExporterTest {

    @Test
    void successfulExportWritesContent(@TempDir Path directory) throws Exception {
        Path target = directory.resolve("report.json");

        new ReportExporter().export(target, "{\"ok\":true}");

        assertThat(Files.readString(target, StandardCharsets.UTF_8)).isEqualTo("{\"ok\":true}");
    }

    @Test
    void rejectedContentLeavesTheExistingFileUntouched(@TempDir Path directory) throws Exception {
        Path target = directory.resolve("report.json");
        Files.writeString(target, "{\"previous\":true}", StandardCharsets.UTF_8);

        assertThatThrownBy(() -> new ReportExporter().export(target, "FAIL: broken payload"))
                .isInstanceOf(IOException.class);

        assertThat(Files.readString(target, StandardCharsets.UTF_8))
                .as("导出失败不能破坏已有文件")
                .isEqualTo("{\"previous\":true}");
    }
}
