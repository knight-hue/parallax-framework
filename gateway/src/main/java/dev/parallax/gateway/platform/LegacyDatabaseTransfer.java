package dev.parallax.gateway.platform;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.HexFormat;
import java.util.List;
import java.util.TimeZone;

/** Offline, stopped-writer migration. Never drops tables, disables FKs or copies Flyway history. */
public final class LegacyDatabaseTransfer {
    private record Table(String name, String order, String columns) { }
    private static final List<Table> TABLES = List.of(
            new Table("quota_policy", "id", "id,name,daily_run_limit,daily_token_limit,monthly_token_limit,created_at"),
            new Table("api_credential", "id", "id,name,key_hash,key_prefix,role,quota_policy_id,created_at,revoked_at,last_used_at"),
            new Table("usage_ledger", "id", "id,credential_id,run_id,occurred_at,prompt_tokens,completion_tokens,total_tokens,trace_id"),
            new Table("audit_run", "id", "id,run_id,credential_id,repo_path,question,status,submitted_at,finished_at,elapsed_s,trace_id,prompt_tokens,completion_tokens,total_tokens,counts_json,stop_reason,error"),
            new Table("audit_event", "id", "id,run_id,event_type,at,detail,trace_id"),
            new Table("platform_user", "id", "id,username,password_hash,disabled,created_at"),
            new Table("platform_organization", "id", "id,name,created_at"),
            new Table("platform_membership", "organization_id,user_id", "organization_id,user_id,role"),
            new Table("platform_project", "id", "id,organization_id,name,created_at"),
            new Table("platform_access_audit", "id", "id,actor,action,resource_id,at"),
            new Table("platform_repository", "id", "id,project_id,name,clone_url,created_by,created_at"),
            new Table("platform_policy_version", "id", "id,project_id,version_number,config_json,config_sha256,created_by,created_at"),
            new Table("platform_budget_account", "organization_id", "organization_id,token_limit,reserved_tokens,used_tokens,updated_at"),
            new Table("platform_task", "id", "id,organization_id,project_id,repository_id,policy_version,created_by,request_key,request_sha256,commit_sha,token_budget,deadline,state,attempt,fencing_token,last_sequence,prompt_tokens,completion_tokens,settled,lease_until,result_sha256,created_at,updated_at,recovery_reason"),
            new Table("platform_budget_ledger", "id", "id,organization_id,task_id,kind,tokens,at"),
            new Table("platform_outbox", "id", "id,task_id,attempt,kind,payload,status,available_at,claim_token,claim_until,publish_attempts,created_at,published_at"),
            new Table("platform_task_event", "id", "id,event_id,task_id,attempt,fencing_token,sequence_number,kind,payload,payload_sha256,received_at"),
            new Table("platform_task_artifact", "id", "id,artifact_id,task_id,attempt,fencing_token,sha256,content,created_at"),
            new Table("platform_repair_review", "id", "id,task_id,project_id,created_by,source_commit_sha,patch_sha256,patch_content,test_command,approval_digest,status,approved_by,approved_at,verification_id,verification_sha256,verification_detail,created_at,updated_at"));

    public record Verification(String table, long rows, String sha256) { }
    private static Calendar utc() { return Calendar.getInstance(TimeZone.getTimeZone("UTC")); }

    public static List<Verification> verify(Connection source, Connection target) throws Exception {
        List<Verification> results = new ArrayList<>();
        for (var table : TABLES) {
            Verification expected = digest(source, table), actual = digest(target, table);
            if (!expected.equals(actual)) throw new SQLException("Migration verification mismatch: " + table.name);
            results.add(actual);
        }
        return List.copyOf(results);
    }

    public static List<Verification> copy(Connection source, Connection target, boolean writersStopped) throws Exception {
        if (!writersStopped) throw new IllegalArgumentException("Stop all writers and confirm maintenance before copying");
        if (!source.getAutoCommit() || !target.getAutoCommit()) throw new SQLException("Connections must start in autocommit mode");
        source.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
        source.setReadOnly(true);
        source.setAutoCommit(false);
        target.setAutoCommit(false);
        try {
            for (var table : TABLES) {
                try (var statement = target.createStatement(); var rows = statement.executeQuery("SELECT COUNT(*) FROM " + table.name)) {
                    rows.next();
                    if (rows.getLong(1) != 0 && !table.name.equals("quota_policy")) {
                        throw new SQLException("Destination must be empty: " + table.name);
                    }
                }
            }
            // Only the untouched Flyway seed is allowed in a fresh destination.
            try (var statement = target.createStatement(); var rows = statement.executeQuery("SELECT COUNT(*) FROM quota_policy WHERE id <> 1 OR name <> 'default' OR daily_run_limit <> 20 OR daily_token_limit <> 2000000 OR monthly_token_limit <> 20000000")) {
                rows.next();
                if (rows.getLong(1) != 0) throw new SQLException("Destination quota seed was modified");
            }
            try (var statement = target.createStatement()) { statement.executeUpdate("DELETE FROM quota_policy"); }
            for (var table : TABLES) {
                String[] columns = table.columns.split(",");
                String placeholders = String.join(",", java.util.Collections.nCopies(columns.length, "?"));
                try (var input = source.prepareStatement("SELECT " + table.columns + " FROM " + table.name + " ORDER BY " + table.order);
                     var insert = target.prepareStatement("INSERT INTO " + table.name + " (" + table.columns + ") VALUES (" + placeholders + ")")) {
                    input.setFetchSize(200);
                    try (var rows = input.executeQuery()) {
                    int batch = 0;
                    while (rows.next()) {
                        for (int i = 1; i <= columns.length; i++) {
                            int type = rows.getMetaData().getColumnType(i);
                            if (type == Types.TIMESTAMP || type == Types.TIMESTAMP_WITH_TIMEZONE) {
                                insert.setTimestamp(i, rows.getTimestamp(i, utc()), utc());
                            } else {
                                insert.setObject(i, rows.getObject(i));
                            }
                        }
                        insert.addBatch();
                        if (++batch % 200 == 0) insert.executeBatch();
                    }
                    if (batch % 200 != 0) insert.executeBatch();
                    }
                }
            }
            List<Verification> result = verify(source, target);
            target.commit();
            source.rollback();
            return result;
        } catch (Exception ex) {
            target.rollback(); source.rollback(); throw ex;
        } finally {
            target.setAutoCommit(true); source.setAutoCommit(true); source.setReadOnly(false);
        }
    }

    private static Verification digest(Connection connection, Table table) throws Exception {
        var digest = MessageDigest.getInstance("SHA-256");
        long count = 0;
        try (var statement = connection.createStatement();
             ResultSet rows = statement.executeQuery("SELECT " + table.columns + " FROM " + table.name + " ORDER BY " + table.order)) {
            while (rows.next()) {
                count++;
                for (int i = 1; i <= rows.getMetaData().getColumnCount(); i++) {
                    Object value = rows.getObject(i);
                    String normalized;
                    if (value == null) normalized = null;
                    else if (value instanceof Boolean flag) normalized = flag ? "1" : "0";
                    else if (value instanceof Number number) normalized = new BigDecimal(number.toString()).stripTrailingZeros().toPlainString();
                    else if (value instanceof Timestamp || rows.getMetaData().getColumnType(i) == Types.TIMESTAMP_WITH_TIMEZONE || value instanceof java.time.LocalDateTime) {
                        Instant timestamp = rows.getTimestamp(i, utc()).toInstant();
                        normalized = timestamp.truncatedTo(java.time.temporal.ChronoUnit.MICROS).toString();
                    } else normalized = value.toString();
                    if (normalized == null) digest.update((byte) 0);
                    else {
                        byte[] bytes = normalized.getBytes(StandardCharsets.UTF_8);
                        digest.update((byte) 1);
                        digest.update(java.nio.ByteBuffer.allocate(4).putInt(bytes.length).array());
                        digest.update(bytes);
                    }
                }
            }
        }
        return new Verification(table.name, count, HexFormat.of().formatHex(digest.digest()));
    }

    public static void main(String[] args) throws Exception {
        boolean copying = args.length == 1 && args[0].equals("--copy-stopped-writers");
        if (!copying && !(args.length == 1 && args[0].equals("--verify"))) {
            throw new IllegalArgumentException("Use --verify or --copy-stopped-writers; configure TRANSFER_SOURCE/TARGET_URL/USER/PASSWORD in environment");
        }
        try (var source = DriverManager.getConnection(required("TRANSFER_SOURCE_URL"), required("TRANSFER_SOURCE_USER"), required("TRANSFER_SOURCE_PASSWORD"));
             var target = DriverManager.getConnection(required("TRANSFER_TARGET_URL"), required("TRANSFER_TARGET_USER"), required("TRANSFER_TARGET_PASSWORD"))) {
            var result = copying ? copy(source, target, true) : verify(source, target);
            for (var row : result) System.out.println(row.table + ": rows=" + row.rows + ", SHA-256=" + row.sha256);
        }
    }

    private static String required(String key) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) throw new IllegalArgumentException("Missing environment variable " + key);
        return value;
    }
}
