/*
 * P-6 补测探针：EXPLAIN ANALYZE 耗时对比 + innodb_deadlock_detect=OFF 超时路径
 *
 * 为什么用 Java 而不是 Python：本机 backend/.venv 里没有任何 MySQL 驱动
 * （Python 引擎不连 MySQL），而网关侧本来就用 mysql-connector-j，
 * 本地 Maven 仓库已有 9.7.0 的 jar。这样整份验收**不下载任何东西**。
 *
 * 运行（在仓库根目录）：
 *   .\.toolchain\jdk\bin\java.exe -cp "$env:USERPROFILE\.m2\repository\com\mysql\mysql-connector-j\9.7.0\mysql-connector-j-9.7.0.jar" `
 *       eval\labs\MysqlExtraProbe.java > eval\labs\mysql-extra-probe.log 2>&1
 *
 * 产出：控制台 JSON（再落成 eval/labs/mysql-extra.json）
 *
 * 两项实验都只在独立的 lab_probe 库里做，不碰 parallax 库。
 */
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

public final class MysqlExtraProbe {

    private static final String HOST = "127.0.0.1:3307";
    private static final String ROOT_URL =
            "jdbc:mysql://" + HOST + "/?useSSL=false&allowPublicKeyRetrieval=true&connectionTimeZone=UTC";
    private static final String DB_URL =
            "jdbc:mysql://" + HOST + "/lab_probe?useSSL=false&allowPublicKeyRetrieval=true&connectionTimeZone=UTC";
    private static final String USER = "root";
    private static final String PASS = "parallax-root";

    private static final int ROWS = 50_000;
    private static final int TARGET_ROW = 37_777;
    private static final String TARGET_EMAIL = "user37777@example.com";

    public static void main(String[] args) throws Exception {
        prepare();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("mysql_server_version", scalar("SELECT VERSION()"));
        out.put("isolation_default", scalar("SELECT @@transaction_isolation"));
        out.put("rows", ROWS);
        out.put("probe_query", "SELECT id, name FROM lab_index_probe WHERE email = '" + TARGET_EMAIL + "'");
        out.put("index_access_path", indexExperiment());
        out.put("deadlock_detect", deadlockExperiment());

        try (Connection c = DriverManager.getConnection(DB_URL, USER, PASS);
             Statement s = c.createStatement()) {
            s.execute("DROP TABLE IF EXISTS lab_index_probe");
            s.execute("DROP TABLE IF EXISTS lab_lock_probe");
        }
        System.out.println(Json.write(out));
    }

    // ---------------------------------------------------------------- 准备

    private static void prepare() throws Exception {
        try (Connection c = DriverManager.getConnection(ROOT_URL, USER, PASS);
             Statement s = c.createStatement()) {
            s.execute("CREATE DATABASE IF NOT EXISTS lab_probe DEFAULT CHARACTER SET utf8mb4");
        }
        try (Connection c = DriverManager.getConnection(DB_URL, USER, PASS)) {
            try (Statement s = c.createStatement()) {
                s.execute("DROP TABLE IF EXISTS lab_index_probe");
                s.execute("""
                        CREATE TABLE lab_index_probe (
                            id INT NOT NULL AUTO_INCREMENT,
                            email VARCHAR(120) NOT NULL,
                            name VARCHAR(80) NOT NULL,
                            PRIMARY KEY (id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """);
                s.execute("DROP TABLE IF EXISTS lab_lock_probe");
                s.execute("CREATE TABLE lab_lock_probe (id INT PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB");
                s.execute("INSERT INTO lab_lock_probe VALUES (1,0),(2,0),(3,0)");
            }
            c.setAutoCommit(false);
            try (PreparedStatement ps = c.prepareStatement(
                    "INSERT INTO lab_index_probe (email, name) VALUES (?, ?)")) {
                for (int i = 1; i <= ROWS; i++) {
                    ps.setString(1, "user" + i + "@example.com");
                    ps.setString(2, "name-" + i);
                    ps.addBatch();
                    if (i % 5_000 == 0) {
                        ps.executeBatch();
                    }
                }
                ps.executeBatch();
            }
            c.commit();
            c.setAutoCommit(true);
        }
    }

    // ------------------------------------------------- 实验一：EXPLAIN ANALYZE

    private static Map<String, Object> indexExperiment() throws Exception {
        List<Map<String, Object>> steps = new ArrayList<>();
        String eq = "SELECT id, name FROM lab_index_probe WHERE email = '" + TARGET_EMAIL + "'";
        String covering = "SELECT email, name FROM lab_index_probe WHERE email = '" + TARGET_EMAIL + "'";
        String prefix = "SELECT id, name FROM lab_index_probe WHERE email LIKE 'user3777%'";

        steps.add(step("no_index", null, null, eq));
        steps.add(step("idx_email", null,
                "CREATE INDEX idx_email ON lab_index_probe(email)", eq));
        // 先删掉窄索引，否则优化器永远选 idx_email，覆盖索引观察不到
        steps.add(step("covering_idx_email_name",
                "ALTER TABLE lab_index_probe DROP INDEX idx_email",
                "CREATE INDEX idx_email_name ON lab_index_probe(email, name)", covering));
        steps.add(step("prefix_like_range", null, null, prefix));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("steps", steps);
        result.put("note", "每一档都记录经典 EXPLAIN、EXPLAIN ANALYZE 原文、Handler 计数与 5 次实际执行耗时中位数");
        return result;
    }

    private static Map<String, Object> step(String label, String preDdl, String ddl, String query)
            throws Exception {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("label", label);
        entry.put("query", query);
        try (Connection c = DriverManager.getConnection(DB_URL, USER, PASS)) {
            try (Statement s = c.createStatement()) {
                if (preDdl != null) {
                    s.execute(preDdl);
                }
                if (ddl != null) {
                    s.execute(ddl);
                }
            }

            // 1) 经典 EXPLAIN：type / key / rows / Extra
            try (Statement s = c.createStatement();
                 ResultSet rs = s.executeQuery("EXPLAIN " + query)) {
                List<Map<String, Object>> plan = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("table", rs.getString("table"));
                    row.put("type", rs.getString("type"));
                    row.put("key", rs.getString("key"));
                    row.put("rows", rs.getString("rows"));
                    row.put("Extra", rs.getString("Extra"));
                    plan.add(row);
                }
                entry.put("explain", plan);
            }

            // 2) EXPLAIN ANALYZE 原文（含 actual time）
            try (Statement s = c.createStatement();
                 ResultSet rs = s.executeQuery("EXPLAIN ANALYZE " + query)) {
                List<String> plan = new ArrayList<>();
                while (rs.next()) {
                    plan.add(rs.getString(1));
                }
                entry.put("explain_analyze", plan);
            }

            // 3) Handler 计数：真正读了多少行（比估算更硬）
            try (Statement s = c.createStatement()) {
                s.execute("FLUSH STATUS");
            }
            Map<String, Long> before = handlerStatus(c);
            try (Statement s = c.createStatement();
                 ResultSet rs = s.executeQuery(query)) {
                int found = 0;
                while (rs.next()) {
                    found++;
                }
                entry.put("rows_returned", found);
            }
            Map<String, Long> after = handlerStatus(c);
            Map<String, Long> delta = new LinkedHashMap<>();
            for (Map.Entry<String, Long> e : after.entrySet()) {
                long d = e.getValue() - before.getOrDefault(e.getKey(), 0L);
                if (d != 0) {
                    delta.put(e.getKey(), d);
                }
            }
            entry.put("handler_delta", delta);

            // 4) 5 次实际执行耗时
            List<Double> times = new ArrayList<>();
            for (int i = 0; i < 5; i++) {
                long t0 = System.nanoTime();
                try (Statement s = c.createStatement();
                     ResultSet rs = s.executeQuery(query)) {
                    while (rs.next()) {
                        // 消费结果集，避免驱动提前短路
                    }
                }
                times.add((System.nanoTime() - t0) / 1_000_000.0);
            }
            times.sort(Double::compare);
            entry.put("wall_ms_runs", times);
            entry.put("wall_ms_median", Math.round(times.get(times.size() / 2) * 1000) / 1000.0);
        }
        return entry;
    }

    private static Map<String, Long> handlerStatus(Connection c) throws SQLException {
        Map<String, Long> out = new LinkedHashMap<>();
        try (Statement s = c.createStatement();
             ResultSet rs = s.executeQuery("SHOW SESSION STATUS LIKE 'Handler_read%'")) {
            while (rs.next()) {
                out.put(rs.getString(1), Long.parseLong(rs.getString(2)));
            }
        }
        return out;
    }

    // -------------------------------------- 实验二：deadlock_detect OFF 超时路径

    private static Map<String, Object> deadlockExperiment() throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("lock_wait_timeout_s", 5);
        result.put(
                "note",
                "innodb_deadlock_detect 在 8.4 是 GLOBAL 变量，无法按会话设置，"
                        + "因此两档都是整台服务器级别；跑完立即恢复为 ON");
        try {
            result.put("detect_on", lockScenario(true));
            result.put("detect_off", lockScenario(false));
        } finally {
            try (Connection c = DriverManager.getConnection(ROOT_URL, USER, PASS);
                 Statement s = c.createStatement()) {
                s.execute("SET GLOBAL innodb_deadlock_detect = ON");
            }
        }
        result.put("restored_to", scalar("SELECT @@global.innodb_deadlock_detect"));
        return result;
    }

    private static Map<String, Object> lockScenario(boolean detect) throws Exception {
        try (Connection c = DriverManager.getConnection(ROOT_URL, USER, PASS);
             Statement s = c.createStatement()) {
            s.execute("SET GLOBAL innodb_deadlock_detect = " + (detect ? "ON" : "OFF"));
        }
        try (Connection c = DriverManager.getConnection(DB_URL, USER, PASS);
             Statement s = c.createStatement()) {
            s.execute("UPDATE lab_lock_probe SET v = 0");
        }

        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch firstLocked = new CountDownLatch(1);
        try {
            Future<Map<String, Object>> a = pool.submit(() -> worker("T1", detect, 1, 2, 0, 800, firstLocked, true));
            Future<Map<String, Object>> b = pool.submit(() -> worker("T2", detect, 2, 1, 100, 300, firstLocked, false));
            Map<String, Object> ra = a.get(40, TimeUnit.SECONDS);
            Map<String, Object> rb = b.get(40, TimeUnit.SECONDS);
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("T1", ra);
            out.put("T2", rb);
            out.put("deadlock_1213", count(ra, 1213) + count(rb, 1213));
            out.put("lock_wait_timeout_1205", count(ra, 1205) + count(rb, 1205));
            return out;
        } finally {
            pool.shutdownNow();
        }
    }

    private static int count(Map<String, Object> row, int code) {
        Object v = row.get("error_code");
        return (v instanceof Integer && (Integer) v == code) ? 1 : 0;
    }

    private static Map<String, Object> worker(
            String name, boolean detect, int firstId, int secondId,
            long startDelayMs, long holdMs, CountDownLatch firstLocked, boolean signal) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("reader", name);
        row.put("order", firstId + "->" + secondId);
        long t0 = System.nanoTime();
        Connection c = null;
        try {
            Thread.sleep(startDelayMs);
            c = DriverManager.getConnection(DB_URL, USER, PASS);
            c.setAutoCommit(false);
            try (Statement s = c.createStatement()) {
                s.execute("SET SESSION innodb_lock_wait_timeout = 5");
                s.execute("UPDATE lab_lock_probe SET v = v + 1 WHERE id = " + firstId);
            }
            row.put("first_lock_ms", ms(t0));
            if (signal) {
                firstLocked.countDown();
            } else {
                firstLocked.await(5, TimeUnit.SECONDS);
            }
            Thread.sleep(holdMs);
            try (Statement s = c.createStatement()) {
                s.execute("UPDATE lab_lock_probe SET v = v + 1 WHERE id = " + secondId);
            }
            c.commit();
            row.put("outcome", "committed");
            row.put("error_code", 0);
        } catch (SQLException e) {
            row.put("outcome", "failed");
            row.put("error_code", e.getErrorCode());
            row.put("sql_state", e.getSQLState());
            row.put("message", trim(e.getMessage()));
            try {
                if (c != null) {
                    c.rollback();
                }
            } catch (SQLException ignored) {
                // 回滚失败不改变结论，连接已不可用时由驱动关闭
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            row.put("outcome", "interrupted");
            row.put("error_code", -1);
        } finally {
            row.put("elapsed_ms", ms(t0));
            if (c != null) {
                try {
                    c.close();
                } catch (SQLException ignored) {
                    // 关闭失败不影响证据
                }
            }
        }
        return row;
    }

    private static long ms(long sinceNanos) {
        return Math.round((System.nanoTime() - sinceNanos) / 1_000_000.0);
    }

    private static String trim(String text) {
        if (text == null) {
            return "";
        }
        return text.length() > 200 ? text.substring(0, 200) : text;
    }

    private static String scalar(String sql) throws Exception {
        try (Connection c = DriverManager.getConnection(DB_URL, USER, PASS);
             Statement s = c.createStatement();
             ResultSet rs = s.executeQuery(sql)) {
            return rs.next() ? rs.getString(1) : "";
        }
    }

    /** 极简 JSON 序列化：只支持 Map / List / String / Number / Boolean。 */
    private static final class Json {
        static String write(Object value) {
            StringBuilder sb = new StringBuilder();
            emit(sb, value, 0);
            return sb.toString();
        }

        private static void emit(StringBuilder sb, Object value, int indent) {
            if (value instanceof Map<?, ?> map) {
                sb.append("{\n");
                int i = 0;
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    pad(sb, indent + 1);
                    sb.append('"').append(escape(String.valueOf(e.getKey()))).append("\": ");
                    emit(sb, e.getValue(), indent + 1);
                    sb.append(++i < map.size() ? ",\n" : "\n");
                }
                pad(sb, indent);
                sb.append('}');
            } else if (value instanceof List<?> list) {
                if (list.isEmpty()) {
                    sb.append("[]");
                    return;
                }
                sb.append("[\n");
                for (int i = 0; i < list.size(); i++) {
                    pad(sb, indent + 1);
                    emit(sb, list.get(i), indent + 1);
                    sb.append(i + 1 < list.size() ? ",\n" : "\n");
                }
                pad(sb, indent);
                sb.append(']');
            } else if (value instanceof String s) {
                sb.append('"').append(escape(s)).append('"');
            } else {
                sb.append(value);
            }
        }

        private static void pad(StringBuilder sb, int indent) {
            sb.append("  ".repeat(indent));
        }

        private static String escape(String s) {
            StringBuilder out = new StringBuilder();
            for (char ch : s.toCharArray()) {
                switch (ch) {
                    case '"' -> out.append("\\\"");
                    case '\\' -> out.append("\\\\");
                    case '\n' -> out.append("\\n");
                    case '\r' -> out.append("\\r");
                    case '\t' -> out.append("\\t");
                    default -> {
                        if (ch < 0x20) {
                            out.append(String.format("\\u%04x", (int) ch));
                        } else {
                            out.append(ch);
                        }
                    }
                }
            }
            return out.toString();
        }
    }
}
