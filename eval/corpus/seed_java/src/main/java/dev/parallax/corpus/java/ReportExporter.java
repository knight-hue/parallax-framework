package dev.parallax.corpus.java;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** 报告导出：把内容写到目标文件。 */
public class ReportExporter {

    /**
     * 缺陷：直接写目标文件，写完之后才做校验；校验失败时目标文件已经被截断/写坏。
     */
    public void export(Path target, String content) throws IOException {
        Files.writeString(target, content, StandardCharsets.UTF_8);
        if (content.contains("FAIL")) {
            throw new IOException("report content rejected by post-write validation");
        }
    }
}
