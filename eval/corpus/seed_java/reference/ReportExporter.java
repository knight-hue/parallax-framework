package dev.parallax.corpus.java;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

/** 参考修复：先校验，再写临时文件，最后原子替换目标文件。 */
public class ReportExporter {

    public void export(Path target, String content) throws IOException {
        if (content.contains("FAIL")) {
            throw new IOException("report content rejected by post-write validation");
        }
        Path directory = target.toAbsolutePath().getParent();
        Path temporary = Files.createTempFile(directory, ".report-", ".tmp");
        try {
            Files.writeString(temporary, content, StandardCharsets.UTF_8);
            try {
                Files.move(temporary, target,
                        StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (java.nio.file.AtomicMoveNotSupportedException ex) {
                Files.move(temporary, target, StandardCopyOption.REPLACE_EXISTING);
            }
        } finally {
            Files.deleteIfExists(temporary);
        }
    }
}
