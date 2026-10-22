# MySQL 原理实验

对**真实 MySQL 8.4** 运行，验证执行计划、MVCC 隔离级别和 InnoDB 锁行为。

## 前置条件

- MySQL 8.4，库 `mysql_lab`，账号默认 `parallax` / `parallax`（可用环境变量覆盖）
- JDK 21

```sql
CREATE DATABASE IF NOT EXISTS mysql_lab CHARACTER SET utf8mb4;
GRANT ALL PRIVILEGES ON mysql_lab.* TO 'parallax'@'%';
```

```powershell
powershell -File .\run.ps1
```

## 三个用例类

### `IndexAccessPathTest` — 执行计划演进

两万行数据上，同一条查询在四种状态下看 `EXPLAIN`：

| 状态 | 期望的 access type | 期望的 Extra |
| --- | --- | --- |
| 无索引 | `ALL`，扫描行数接近全表 | — |
| 加 `idx_email` | `ref`，扫描行数 < 10 | — |
| 换成 `idx_email_city` 且只查索引列 | `ref` | `Using index`（覆盖索引，不回表） |
| 前缀 `LIKE 'user1234%'` | `range` | — |

### `IsolationLevelTest` — MVCC 与隔离级别

- `REPEATABLE READ`：同一事务内两次读，即使别的事务已经提交，仍读到快照旧值；提交后再开新读才看到新值；
- `READ COMMITTED`：每条语句读最新已提交版本；
- `SERIALIZABLE`：普通读会加共享锁，并发写必须等待，超时报 1205。

### `LockingAndDeadlockTest` — 锁与死锁

- `SELECT ... FOR UPDATE` 持锁后，另一个连接的写操作等待到 `innodb_lock_wait_timeout` 后报 **1205**；
- 两个事务按相反顺序更新两行，InnoDB 死锁检测回滚其中一个，报 **1213**，另一个正常提交。

## 环境变量

| 变量 | 默认值 |
| --- | --- |
| `PARALLAX_MYSQL_LAB_URL` | `jdbc:mysql://127.0.0.1:3307/mysql_lab?...` |
| `PARALLAX_MYSQL_LAB_USER` | `parallax` |
| `PARALLAX_MYSQL_LAB_PASSWORD` | `parallax` |

## 已知限制

- 单实例、单机；没有主从复制、组复制或崩溃恢复演练；
- 没有直接读 InnoDB 页/B+ 树结构，索引结论来自 `EXPLAIN` 与 `ANALYZE`，不是页级证据；
- 没做 `EXPLAIN ANALYZE` 的实际耗时对比与慢查询参数调优；
- 死锁用例依赖 InnoDB 默认死锁检测，未覆盖 `innodb_deadlock_detect=OFF` 时的超时路径。
