# MySQL 运行与备份恢复

Java 默认运行档为 `mysql`，Flyway 历史位于 `db/mysql`（V1–V11）。新库表为 InnoDB、utf8mb4_0900_bin，时间存 UTC DATETIME(6)，Hibernate/JDBC 会话均使用 UTC。

目标为 MySQL 8.4 LTS。本机已有 8.0.19，已使用真实临时实例验证；8.4 部署验收仍待完成。Compose 声明 mysql:8.4，但不会因此下载镜像；生产以 `--pull never --no-build` 启动已有镜像。

## 配置

- `SPRING_PROFILES_ACTIVE=mysql`（默认）；`PARALLAX_MYSQL_URL` 为 JDBC URL。
- `PARALLAX_DB_USER` 默认 parallax；`PARALLAX_DB_PASSWORD` 必须设置。
- Compose 初始化还需要独立的 `PARALLAX_MYSQL_ROOT_PASSWORD`；应用不使用 root。
- 远程数据库显式配置 TLS 校验，禁止照抄本机测试的 sslMode=DISABLED。

## 启动与校验

1. 执行 `mvn -o -Pit verify`（需要真实 MySQL / RabbitMQ / Redis）或 `gateway/tools/verify_native_mysql.py`。
2. 启动后检查 `/ready`、Flyway validate 与身份/权限冒烟。
3. 不使用 Hibernate 自动建表；schema 由 Flyway 拥有。

## 备份与恢复演练

`gateway/tools/verify_backup_restore.py` 在真实 MySQL 上跑一遍可重复的恢复演练，不接触任何已有业务库：每次运行创建两个临时库（源库与恢复目标库），按序执行 `db/mysql/V*.sql`，写入含中文与 emoji 的样本数据，用 `mysqldump --single-transaction --routines --triggers --events --hex-blob` 导出，再导入第二个库并逐表比对 `CHECKSUM TABLE` 与行数，最后删除两个临时库。

```powershell
backend/.venv/Scripts/python.exe gateway/tools/verify_backup_restore.py ^
  --mysql-home E:/tools/mysql-8.4.0-winx64 --password <root 口令> --port 3307 ^
  --out gateway/target/backup-restore
```

结果是逻辑备份演练：覆盖 11 个迁移、22 张表的校验和与行数一致，但不能当作物理备份、binlog 时间点恢复或在线热备的证明。
