# Parallax 开发交接记录（2026-10-22）

本记录是 2026-10-22 的交接快照。最终目标以 [PROJECT_GOALS.md](PROJECT_GOALS.md) 为准，当前实现以 [PROJECT_STATUS.md](PROJECT_STATUS.md) 和 [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) 为准；运行命令见 [OPERATIONS.md](OPERATIONS.md)。

## 今日完成

- 完成 Redis/Redisson 治理模块：Maven 接入 Redisson 3.52.0；缓存 Redis 未配置时不创建客户端，Redis 不可用时回源 MySQL。
- 策略读取先做实时项目权限检查，再使用项目/策略隔离的只读缓存；缓存 JSON 在使用前进行结构校验和 SHA-256 校验。
- 缓存重建使用有界等待和短租约锁抑制击穿；锁只负责协调回源，不承担预算、权限、任务状态或结果完整性。
- 增加 `PARALLAX_CACHE_REDIS_URL`、TTL、锁等待和锁租约配置；保留原有 Lettuce/Bucket4j 限流及内存降级路径。
- 修正缓存重建锁的等待单位：`lock-wait-ms` 现在按毫秒传入 `tryLock`，租约秒数换算为毫秒，避免默认 100 毫秒被误当成 100 秒。
- 缓存损坏条目会被删除并从权威数据库重建；数据库 loader 异常不再被缓存层吞掉或重复调用。
- 增加真实 Redis 集成测试 4 项（命中/驱逐、损坏条目重建、毫秒级锁等待、loader 异常只调用一次），使用本机 `redis:latest`，未拉取镜像。
- 增加缓存单元测试；Java 全量离线 Maven 测试 101 项通过；Python 381 项、Ruff/format、前端 typecheck/lint 通过；提交前执行 `git diff --check`。

## GitHub PR 接入

- 新增 `platform_repository_link`、`platform_webhook_delivery` 和禁用的 `system.webhook` 账号（V10）。
- GitHub webhook 校验 HMAC-SHA256 原始请求体，只接受 `pull_request` 的 `opened/reopened/synchronize`。
- 仓库外部 ID 必须绑定到项目仓库，载荷 clone URL 必须与登记仓库一致；任务固定使用 `pull_request.head.sha` 和项目最新不可变策略。
- `X-GitHub-Delivery` 作为任务幂等键；重复投递返回原任务，同一 delivery 不同内容返回 409。
- `PlatformPrWebhookIntegrationTest` 6 项、Java 全量 107 项通过；真实 GitHub 投递、GitLab 和目标 MySQL 8.4 验收未完成。

## 已完成主线

Java 已接管身份/组织/项目权限、仓库和不可变策略、任务状态机、MySQL 预算预占/结算、Outbox/Inbox、attempt/fencing、心跳与恢复、产物完整性、修复提案审批和 Worker 回归回执。Python 保留独立证据装配和隔离执行；前端已接入 Java 工作台。Java↔Python 本机独立进程 HTTP 联调已通过，Python 381 项测试通过。

## 尚未完成

- GitLab PR 接入、真实 GitHub webhook 现场验收；GitHub 签名、项目绑定、固定 commit 与 delivery 幂等已实现。
- RabbitMQ 真 broker、多实例故障、跨节点协调、容量压测和消息链路现场验收；当前本机没有 RabbitMQ 镜像，不能下载补齐。
- MySQL 8.4 目标环境验收、现场备份恢复、正式镜像、TLS、公网部署和 S3 兼容产物存储。
- Worker 专用隔离执行器的容量/强制终止验收；当前报告产物为有大小上限的 MySQL 存储。
- `labs/jvm`、`labs/concurrency`、`labs/mysql`、`labs/redis`、`labs/spring`、`labs/distributed-tx`、`labs/flash-sale` 全套可运行实验。
- 报告安全分享与短链扩展。

## 下一步

在已有服务条件下做 RabbitMQ、多实例、备份恢复和容量验收；补齐 Prometheus 采集、跨进程 trace 和运行诊断。所有未实际运行的环境和性能数据必须保持“未验收”状态。

## 约束

不读取或提交密钥，不修改工作区一级 `.github`，不下载工具、数据库安装包或 Docker 镜像；Maven 仅使用已授权的项目必需依赖。模块完成后运行对应测试、`git diff --check` 并单独提交。
