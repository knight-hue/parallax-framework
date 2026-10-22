# MySQL 运行与离线迁移

Java 默认运行档为 `mysql`，独立 Flyway 历史位于 `db/mysql`；旧库使用 `legacy-postgres` 与原有 `db/migration`。两套历史不能交叉执行。新库表为 InnoDB、utf8mb4_0900_bin，时间存 UTC DATETIME(6)，Hibernate/JDBC 会话均使用 UTC。

目标为 MySQL 8.4 LTS。本机已有 8.0.19，已使用真实临时实例验证；8.4 部署验收仍待完成。Compose 声明 mysql:8.4，但不会因此下载镜像；生产以 `--pull never --no-build` 启动已有镜像。

## 配置

- `SPRING_PROFILES_ACTIVE=mysql`（默认）；`PARALLAX_MYSQL_URL` 为 JDBC URL。
- `PARALLAX_DB_USER` 默认 parallax；`PARALLAX_DB_PASSWORD` 必须设置。
- Compose 初始化还需要独立的 `PARALLAX_MYSQL_ROOT_PASSWORD`；应用不使用 root。
- 远程数据库显式配置 TLS 校验，禁止照抄本机测试的 sslMode=DISABLED。
- 不要直接改旧 PostgreSQL 连接串。保留旧应用版本、备份和原 `postgres-data` 卷。Compose 新用 `mysql-data`，不删除旧卷。

## 停写迁移与核对

1. 停止全部网关/任务写入并冻结入口，备份 PostgreSQL、runs 产物和配置；记录应用提交号。恢复备份到隔离实例后核对才能确认备份有效。
2. 源库先在 legacy-postgres 档迁移至 V8（补齐仓库/策略/平台任务、预算、事件和产物表），目标是执行 MySQL V1—V8 后的空库。不要在两端运行新任务。
3. 设置 `TRANSFER_SOURCE_URL/USER/PASSWORD` 和 `TRANSFER_TARGET_URL/USER/PASSWORD` 环境变量；口令不得写入命令或版本库。
4. 用已构建 jar 的 Boot loader 启动离线工具：

```powershell
java -Dloader.main=dev.parallax.gateway.platform.LegacyDatabaseTransfer -cp gateway/target/parallax-gateway-0.1.0.jar org.springframework.boot.loader.launch.PropertiesLauncher --copy-stopped-writers
# 独立复核，仍然保持停写
java -Dloader.main=dev.parallax.gateway.platform.LegacyDatabaseTransfer -cp gateway/target/parallax-gateway-0.1.0.jar org.springframework.boot.loader.launch.PropertiesLauncher --verify
```

工具只复制白名单十八张业务表，保留主键和外键顺序，不复制 Flyway 历史、不删表、不关闭外键。只允许空目标库或原始默认额度种子；复制在一个目标事务中，逐字段规范化为 UTC 微秒/数值/布尔值后核对每表数量及 SHA-256，通过才提交。源库只读，异常回滚。`--verify` 要在停写状态使用，避免边读边写造成不一致。

1. 使用 MySQL 运行档启动 Java，执行 Flyway validate、健康检查、身份/权限和提交回调冒烟，核对原报告/产物仍可访问，再开放写入。
2. 开放写入前可退回旧应用和未改动的源库。开放后 MySQL 出现新数据时，禁止简单切回旧库：重新停写、备份并逐项对账，处理新增任务/账本/产物后再决定恢复方案。工具不实现在线双写或增量同步。

## 本机真库验收

使用现有 MySQL 二进制与已缓存 PostgreSQL 镜像，创建独立临时数据目录/随机回环端口，退出仅清理自身资源；不连接用户现有数据库，不拉取镜像，Maven 离线执行：

```powershell
backend/.venv/Scripts/python.exe gateway/tools/verify_native_mysql.py --mysql-home E:/mysql/mysql-8.0.19-winx64 --maven .toolchain/maven/bin/mvn.cmd --java-home .toolchain/jdk --postgres-image pgvector/pgvector:pg16 --out gateway/target/mysql-postgres-transfer
```

覆盖真实 InnoDB/Flyway、外键和 CHECK、JPA/JDBC 时间和用量往返、PostgreSQL → MySQL 复制/校验/篡改检测。日志只放忽略的 target；验收摘要单独归档。新库备份使用现有 mysqldump 的 `--single-transaction --routines --triggers --events`，在隔离库恢复并核对 Flyway 与业务数量；不要把声明的备份命令当作已完成生产恢复演练。
