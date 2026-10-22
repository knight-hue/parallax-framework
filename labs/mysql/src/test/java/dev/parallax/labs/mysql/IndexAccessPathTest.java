package dev.parallax.labs.mysql;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 执行计划实验：全表扫描 → 二级索引 range/ref → 覆盖索引，观察 rows 与 Extra 的变化。
 */
class IndexAccessPathTest {

    private static final int ROWS = 20_000;

    @BeforeAll
    static void seed() throws Exception {
        try (Connection connection = LabConnections.open(); Statement statement = connection.createStatement()) {
            statement.execute("DROP TABLE IF EXISTS lab_user");
            statement.execute("""
                    CREATE TABLE lab_user (
                        id INT NOT NULL AUTO_INCREMENT,
                        email VARCHAR(96) NOT NULL,
                        city VARCHAR(32) NOT NULL,
                        created_at DATETIME(6) NOT NULL,
                        PRIMARY KEY (id)
                    ) ENGINE = InnoDB
                    """);
            connection.setAutoCommit(false);
            try (PreparedStatement insert = connection.prepareStatement(
                    "INSERT INTO lab_user (email, city, created_at) VALUES (?, ?, NOW(6))")) {
                for (int i = 0; i < ROWS; i++) {
                    insert.setString(1, "user" + i + "@example.com");
                    insert.setString(2, i % 2 == 0 ? "beijing" : "shanghai");
                    insert.addBatch();
                    if (i % 1000 == 999) {
                        insert.executeBatch();
                    }
                }
                insert.executeBatch();
            }
            connection.commit();
            connection.setAutoCommit(true);
            try (Statement analyze = connection.createStatement()) {
                analyze.execute("ANALYZE TABLE lab_user");
            }
        }
    }

    @Test
    void accessPathEvolvesFromFullScanToCoveringIndex() throws Exception {
        Map<String, String> fullScan = explain("SELECT * FROM lab_user WHERE email = 'user12345@example.com'");
        assertThat(fullScan.get("type")).as("没有索引时只能全表扫描").isEqualTo("ALL");
        assertThat(Long.parseLong(fullScan.get("rows"))).isGreaterThan(ROWS / 2);

        execute("ALTER TABLE lab_user ADD INDEX idx_email (email)", "ANALYZE TABLE lab_user");
        Map<String, String> indexLookup = explain("SELECT * FROM lab_user WHERE email = 'user12345@example.com'");
        assertThat(indexLookup.get("type")).as("等值查询命中二级索引").isEqualTo("ref");
        assertThat(Long.parseLong(indexLookup.get("rows"))).as("扫描行数应降到个位数").isLessThan(10);

        // 先去掉较窄的 idx_email，否则优化器可能仍选它而退化成回表查询。
        execute("ALTER TABLE lab_user DROP INDEX idx_email",
                "ALTER TABLE lab_user ADD INDEX idx_email_city (email, city)",
                "ANALYZE TABLE lab_user");
        Map<String, String> covering = explain("SELECT email, city FROM lab_user WHERE email = 'user12345@example.com'");
        assertThat(covering.get("type")).isEqualTo("ref");
        assertThat(covering.get("Extra")).as("两列都在索引里，不需要回表").contains("Using index");

        Map<String, String> range = explain("SELECT id FROM lab_user WHERE email LIKE 'user1234%'");
        assertThat(range.get("type")).as("前缀 LIKE 走范围扫描").isEqualTo("range");
    }

    private static void execute(String... statements) throws Exception {
        try (Connection connection = LabConnections.open(); Statement statement = connection.createStatement()) {
            for (String sql : statements) {
                statement.execute(sql);
            }
        }
    }

    private static Map<String, String> explain(String sql) throws Exception {
        try (Connection connection = LabConnections.open();
             Statement statement = connection.createStatement();
             ResultSet rows = statement.executeQuery("EXPLAIN " + sql)) {
            int columns = rows.getMetaData().getColumnCount();
            Map<String, String> plan = new HashMap<>();
            while (rows.next()) {
                for (int i = 1; i <= columns; i++) {
                    plan.put(rows.getMetaData().getColumnLabel(i), String.valueOf(rows.getString(i)));
                }
                return plan;
            }
            throw new IllegalStateException("EXPLAIN returned no rows");
        }
    }
}
