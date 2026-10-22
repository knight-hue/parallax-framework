package dev.parallax.labs.mysql;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 行锁等待与死锁检测：MySQL 自己选一个牺牲者并回滚它。 */
class LockingAndDeadlockTest {

    private static final int LOCK_WAIT_TIMEOUT_SECONDS = 1;

    @BeforeAll
    static void seed() throws Exception {
        try (Connection connection = LabConnections.open(); Statement statement = connection.createStatement()) {
            statement.execute("DROP TABLE IF EXISTS lab_lock_row");
            statement.execute("""
                    CREATE TABLE lab_lock_row (
                        id INT PRIMARY KEY,
                        amount INT NOT NULL
                    ) ENGINE = InnoDB
                    """);
            statement.execute("INSERT INTO lab_lock_row (id, amount) VALUES (1, 10), (2, 20)");
        }
    }

    @Test
    void selectForUpdateBlocksAnotherWriterUntilTimeout() throws Exception {
        try (Connection holder = LabConnections.open(); Connection waiter = LabConnections.open()) {
            holder.setAutoCommit(false);
            try (Statement statement = holder.createStatement()) {
                statement.executeQuery("SELECT amount FROM lab_lock_row WHERE id = 1 FOR UPDATE").close();
            }

            waiter.setAutoCommit(true);
            try (Statement statement = waiter.createStatement()) {
                statement.execute("SET SESSION innodb_lock_wait_timeout = " + LOCK_WAIT_TIMEOUT_SECONDS);
            }

            long start = System.nanoTime();
            SQLException failure = null;
            try (Statement statement = waiter.createStatement()) {
                statement.executeUpdate("UPDATE lab_lock_row SET amount = amount + 1 WHERE id = 1");
            } catch (SQLException ex) {
                failure = ex;
            }
            long elapsedMs = (System.nanoTime() - start) / 1_000_000;

            assertThat((Throwable) failure).as("被持锁行上的写操作应当等待后超时").isNotNull();
            assertThat(failure.getErrorCode()).as("1205 = lock wait timeout").isEqualTo(1205);
            assertThat(elapsedMs).isGreaterThanOrEqualTo(900);
            holder.commit();
        }
    }

    @Test
    void oppositeUpdateOrderTriggersDeadlockDetection() throws Exception {
        CountDownLatch bothStarted = new CountDownLatch(2);
        List<Integer> errorCodes = new CopyOnWriteArrayList<>();
        List<String> outcomes = new CopyOnWriteArrayList<>();

        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<?> first = pool.submit(() -> updateTwoRows(1, 2, bothStarted, errorCodes, outcomes));
            Future<?> second = pool.submit(() -> updateTwoRows(2, 1, bothStarted, errorCodes, outcomes));
            first.get(20, TimeUnit.SECONDS);
            second.get(20, TimeUnit.SECONDS);
        } finally {
            pool.shutdownNow();
        }

        assertThat(errorCodes)
                .as("MySQL 死锁检测会回滚其中一个事务（1213）")
                .contains(1213);
        assertThat(outcomes).contains("committed");
    }

    private static void updateTwoRows(int firstId, int secondId, CountDownLatch bothStarted,
            List<Integer> errorCodes, List<String> outcomes) {
        try (Connection connection = LabConnections.open()) {
            connection.setAutoCommit(false);
            try (Statement statement = connection.createStatement()) {
                statement.execute("SET SESSION innodb_lock_wait_timeout = 5");
                statement.executeUpdate("UPDATE lab_lock_row SET amount = amount + 1 WHERE id = " + firstId);
            }
            bothStarted.countDown();
            bothStarted.await(5, TimeUnit.SECONDS);
            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate("UPDATE lab_lock_row SET amount = amount + 1 WHERE id = " + secondId);
            }
            connection.commit();
            outcomes.add("committed");
        } catch (SQLException ex) {
            errorCodes.add(ex.getErrorCode());
            outcomes.add("failed:" + ex.getErrorCode());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }
}
