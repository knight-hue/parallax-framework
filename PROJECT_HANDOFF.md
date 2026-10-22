# Parallax 当前开发交接

更新：2026-10-22。

最终目标以 [PROJECT_GOALS.md](PROJECT_GOALS.md) 为准，技术执行以 [JAVA_BACKEND_PLAN_V2.md](JAVA_BACKEND_PLAN_V2.md) 为准；[PROJECT_STATUS.md](PROJECT_STATUS.md)、[ACCEPTANCE.md](ACCEPTANCE.md) 和 [OPERATIONS.md](OPERATIONS.md) 分别记录当前事实、既有验收和当前运行方式。`../说明材料/开发交接记录-2026-10-17.md` 保留历史记录，不代表当前状态。

## 当前接手方向

Java 从网关升级为平台业务主体；平台统一使用 MySQL；Python 保留独立证据装配和隔离执行。秒杀与 XA/TCC/Seata 放入独立实验，报告安全分享后置。不得沿用“Java 只做薄网关”“不需要组织用户体系”的旧范围限制。

已实现任务协议、身份权限、MySQL 运行档、仓库/策略、平台任务/预算、Inbox、心跳/fencing、事件重放、可靠 Outbox、不可变执行快照、Python 内部客户端、持久投递日志、平台 Worker 生命周期、报告产物、修复审批和隔离回归回执。Java↔Python 已完成本机独立进程 HTTP 联调；前端工作台已接入 Java 任务和审批入口。最新 Java 全量测试、Python 381 项、前端检查均已通过；本机 MySQL 8.0.19 与迁移核对已通过。Redis/Redisson 策略只读缓存、TTL、重建锁和故障回源已实现，并通过真实 Redis 集成测试（4 项），缓存不承担权限或业务事实。Docker 已可用，但 RabbitMQ 镜像未在本机缓存，真实 broker IT 未运行；目标 MySQL 8.4、现场备份恢复、多实例故障和公网生产部署仍未验收。

以下保留既有审查链路的验收入口；不能据此宣称新 Java 平台已完成。

此前已完成传递共同上游约束、隔离修复审批回归、Receipt 开放适配、可选 AST 风险上下文、认证前端代理和生产配置，并使用本机工具、缓存镜像和用户配置的兼容模型实测。密钥仅在忽略的 `backend/.env`，示例文件不保存密钥。

验收入口：

- Python：已有 .venv 执行 pytest，当前 381 项；Ruff/format。
- 前端：已有依赖下 lint、typecheck、test:sse、build。
- 网关：mvn -o verify；真实 PG/Redis 使用本地缓存镜像 override 且禁止拉取。
- 完整服务链路：`backend/tools/verify_native_stack.py`，显式使用 legacy-postgres，仅回环端口与自身临时资源，退出清理。
- 真实模型重复实验：`backend/tools/verify_real_model.py`，不得把失败目录混入有效统计。
- 真实模型修复：`backend/tools/verify_repair_flow.py`，先生成并审阅，--revise-plan 可修订，--approve 必须传确切摘要。
- 证据整理：`backend/tools/export_acceptance.py`，无模型调用，不导出服务日志或访问令牌。

## 2026-10-22 接手顺序

1. 先运行 Java `mvn -o -q test`、Python pytest/Ruff 和前端 typecheck/lint/build，确认环境没有回归。
2. 优先补 PR 托管平台接入：至少实现 GitHub webhook/query 的签名校验、项目绑定、固定 head commit 和幂等；禁止把客户端 URL 当作拉取地址。
3. 补平台任务、Outbox、Worker、审批验证和缓存的 Micrometer 指标与运行诊断；为长任务执行器设置有界线程/进程资源。
4. 在不下载镜像的前提下，若本机已有 RabbitMQ/Redis/MySQL 目标服务，运行真实 broker、多实例故障、备份恢复和容量验收；没有服务就记录为未验收，不伪造结果。
5. 独立完成 `labs/jvm`、`labs/concurrency`、`labs/mysql`、`labs/redis`、`labs/spring`、`labs/distributed-tx`、`labs/flash-sale` 实验；实验不能接入默认生产拓扑。
6. 核心闭环完成后再做安全报告分享/短链：高熵短码、过期、撤销、权限、缓存失效和统计幂等。

## 当前明确未完成

- GitHub/GitLab PR 接入及 webhook 真实验收。
- RabbitMQ 真 broker、跨节点协调、多实例故障和容量压测。
- MySQL 8.4 目标环境、现场备份恢复、正式镜像/TLS/公网部署。
- S3 兼容产物存储；当前报告产物仍是有大小上限的 MySQL 存储。
- Worker 专用隔离执行器的容量和强制终止验收。
- 全套 JVM/AQS/MySQL/Redis/Spring/分布式事务/秒杀实验。
- 报告安全分享与短链扩展。

现场交付需要部署方提供服务器、TLS 入口、正式运行镜像及工作负载。单 API worker 是当前支持的拓扑；完整动态语义分析与跨节点协调未实现。不得将本机验收说成公网生产已上线。
