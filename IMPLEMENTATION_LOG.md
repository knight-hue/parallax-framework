# Java 平台升级实施记录

## P0.1 任务协议与生命周期

状态：已实现并验证，尚未接管旧 HTTP/file runner。

- Java/Python 共用 v1 任务/事件 JSON 样例与严格字段校验。
- 固定提交、策略版本、资源归属、预算、期限、attempt/fencing 和用量溢出约束。
- 状态机保留取消竞态和终态不重开；重试、事件去重和 fencing 的原子持久化由后续协调器实现，协议解析不冒充可靠执行。
- 验证：Java WorkerProtocolTest 9 项；Python test_worker_protocol.py 22 项及 Ruff 通过。
- 改动前 Java 离线 verify 47 项通过；该基线未运行真实数据库 IT。

当前资源核查：本机有 MySQL 8.0.19、Java 21、Maven、Node、Docker；未找到 MySQL Connector/J、Flyway MySQL、Redisson、RabbitMQ Java 客户端的已有 jar。目标 MySQL 8.4 尚未在本机发现。未下载资源，不能以现有 PostgreSQL/H2 证明 MySQL 完成。

下一步：平台用户/组织/项目权限与 MySQL 运行档。最终全项目完成情况见 PROJECT_STATUS.md，单模块完成不代表最终目标完成。

## 用户、组织与项目权限基础

状态：已实现，当前 PostgreSQL/H2 迁移基线；尚未管理旧审查任务的项目归属。

- 管理员创建/停用用户、BCrypt 密码、用户 JWT 与当前有效状态检查。
- 组织 OWNER/MAINTAINER/REVIEWER/VIEWER，项目资源授权、成员撤销即时生效、保护唯一所有者及事务内操作审计。
- 用户 JWT 暂时禁止访问没有项目归属的旧接口；旧管理员/API Key 兼容，不能冒充平台用户。
- 真 HTTP 权限测试 5 项通过；Java 全量离线 verify 61 项通过，未运行数据库 IT。Python 全量 312 项通过。
- API 契约及边界见 gateway/PLATFORM_API.md。当前成员权限以组织为范围，尚无单项目覆盖和管理 UI。
- 用户已授权仅由 Maven 补齐必需依赖及传递依赖；不下载工具、数据库安装包或镜像。已获取 MySQL Connector/J 9.7.0。

## MySQL 运行档与旧库离线迁移

状态：已实现并通过本机真库检查；目标 MySQL 8.4 与生产恢复现场验收未完成。

- 默认 mysql 运行档、独立 InnoDB/utf8mb4/UTC DATETIME(6) Flyway、显式外键；旧历史保持不变，legacy-postgres 可回归。
- Compose 使用独立 mysql-data，保留 postgres-data；应用与 root 分离口令。没有拉取或构建镜像。
- 停写迁移工具按白名单复制十张表，目标本地事务、源只读、逐字段数量/SHA-256 核对，拒绝非空目标与错误数据。
- 本机现有 MySQL 8.0.19 + 缓存 PostgreSQL 16.15 完成真库迁移；所有表有数据，含中文/emoji、微秒、空值、用量和外键关联，篡改被拒绝。
- Java 全量 61 项 + 真实 PostgreSQL/Redis 12 项通过；独立 MySQL 4 项通过（同时重跑身份/协议 14 项）。Ruff、Compose 生产合并配置和 diff 检查通过。
- 运行与回退步骤：gateway/MYSQL_OPERATIONS.md；脱敏验收摘要：eval/java-platform/mysql-runtime.json。Python 既有全量 312 项未在本模块重复运行，仅变更旧验收脚本的显式 profile。

下一模块：受控仓库登记、不可变策略版本，随后平台任务/原子预算/Outbox。
