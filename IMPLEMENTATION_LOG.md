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
