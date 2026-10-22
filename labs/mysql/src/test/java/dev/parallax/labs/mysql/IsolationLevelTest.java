package dev.parallax.labs.mysql;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * MVCC 与隔离级别：同一份数据在 REPEATABLE READ 下对同一事务保持快照，
 * 在 READ COMMITTED 下能看到别的事务刚提交的新值。
 */
class IsolationLevelTest {

    @BeforeAll
    static void seed() throws Exception {
        try (Connection connection = LabConnections.open(); Statement statement = connection.createStatement()) {
            statement.execute("DROP TABLE IF EXISTS lab_account");
            statement.execute("""
                    CREATE TABLE lab_account (
                        id INT PRIMARY KEY,
                        owner VARCHAR(32) NOT NULL,
                        balance INT NOT NULL
                    ) ENGINE = InnoDB
                    """);
            statement.execute("INSERT INTO lab_account (id, owner, balance) VALUES (1, 'alice', 100)");
        }
    }

    @Test
    void repeatableReadKeepsTheSnapshotAfterAnotherCommit() throws Exception {
        try (Connection reader = LabConnections.open(); Connection writer = LabConnections.open()) {
            reader.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
            reader.setAutoCommit(false);
            assertThat(balance(reader)).isEqualTo(100);

            writer.setAutoCommit(true);
            update(writer, 200);

            assertThat(balance(reader))
                    .as("RR 下同一事务第二次读仍是快照里的旧值")
                    .isEqualTo(100);

            reader.commit();
            assertThat(balance(reader))
                    .as("提交后新事务才能看到已提交的新值")
                    .isEqualTo(200);
            reader.setAutoCommit(true);
        }
    }

    @Test
    void readCommittedSeesTheLatestCommittedValue() throws Exception {
        try (Connection reader = LabConnections.open(); Connection writer = LabConnections.open()) {
            reader.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
            reader.setAutoCommit(false);
            assertThat(balance(reader)).isEqualTo(200);

            writer.setAutoCommit(true);
            update(writer, 300);

            assertThat(balance(reader))
                    .as("RC 下每条语句都读最新已提交版本")
                    .isEqualTo(300);
            reader.commit();
            reader.setAutoCommit(true);
        }
    }

    @Test
    void serializableTakesSharedLocksSoWritersWait() throws Exception {
        try (Connection reader = LabConnections.open(); Connection writer = LabConnections.open()) {
            reader.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
            reader.setAutoCommit(false);
            assertThat(balance(reader)).isEqualTo(300);

            writer.setAutoCommit(true);
            try (Statement statement = writer.createStatement()) {
                statement.execute("SET SESSION innodb_lock_wait_timeout = 1");
            }
            writer.setAutoCommit(false);
            long start = System.nanoTime();
            Throwable failure = null;
            try {
                update(writer, 400);
                writer.commit();
            } catch (Exception ex) {
                failure = ex;
                writer.rollback();
            }
            long elapsedMs = (System.nanoTime() - start) / 1_000_000;
            assertThat(failure)
                    .as("SERIALIZABLE 读会加共享锁，写事务必须等待或超时")
                    .isNotNull();
            assertThat(elapsedMs).isGreaterThanOrEqualTo(900);
            reader.commit();
            reader.setAutoCommit(true);
        }
    }

    private static int balance(Connection connection) throws Exception {
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT balance FROM lab_account WHERE id = 1");
             ResultSet rows = statement.executeQuery()) {
            rows.next();
            return rows.getInt(1);
        }
    }

    private static void update(Connection connection, int balance) throws Exception {
        try (PreparedStatement statement = connection.prepareStatement(
                "UPDATE lab_account SET balance = ? WHERE id = 1")) {
            statement.setInt(1, balance);
            statement.executeUpdate();
        }
    }
}
