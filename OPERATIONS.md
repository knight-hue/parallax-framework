# 运行与隔离验证

当前 Java 默认使用 MySQL，Compose 同步切换；旧 PostgreSQL 通过 legacy-postgres 显式保留。新库运行、停写迁移和回退见 [MySQL 运维](gateway/MYSQL_OPERATIONS.md)。任务仍由单 Python API worker 管理，RabbitMQ 与 Java 调度尚未接管。最终目标见 [PROJECT_GOALS.md](PROJECT_GOALS.md)。

## 配置和构建

实际密钥只写 `backend/.env`，不要填写或提交 `.env.example`。支持 `PARALLAX_LLM_*` 和 `OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL`；PARALLAX 配置优先。兼容服务的模型别名不能当作官方 OpenAI 型号证明。

不联网构建：Python 使用已有 `.venv`；前端执行已有 `node_modules` 中的 lint、typecheck、build；网关执行 `mvn -o verify`。禁止用 `npm ci`、pip 安装或 Docker build 来冒充离线验证。

生产 Compose 覆盖文件要求预先准备项目镜像和基础设施镜像，缺少就失败，不会下载：

```powershell
docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.production.yml --profile gateway config --quiet
docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.production.yml --profile gateway up -d --no-build --pull never
```

生产必须配置 JWT、管理口令、内部令牌和数据库密码。仅 web 绑定本机回环端口；由现场现有反向代理提供 TLS。控制台默认走 `/backend` 同源代理，服务端 `PARALLAX_SERVER_API` 指向 Java 网关。访问令牌只保存在当前页面内存。管理员使用 JWT；集成方使用 API Key。不要把模型密钥填入控制台访问令牌。

核心 API 的 `PARALLAX_GATEWAY_INTERNAL_TOKEN` 与网关相同，拒绝缺少内部凭据的 API 请求；探针保留。公网入口只开放 web/TLS，模型服务、数据库、Redis 均不直接暴露。

## 修复闭环

`PARALLAX_ENABLE_REPAIR=true` 只应在专用隔离 worker 服务实例开启。普通生产 API 默认关闭。专用 worker 必须本地安装 Docker CLI，拥有已缓存的执行镜像，并能把快照的绝对路径挂入该宿主的 Docker daemon；不要给公网 API 容器挂宿主 Docker socket。

执行镜像必须提供 `/usr/bin/timeout` 和项目所需测试运行时；测试依赖预装，执行时禁止下载。`PARALLAX_REPRODUCTION_IMAGE` 指定镜像，默认不存在的 `parallax-repro:local` 会安全失败。`PARALLAX_REPRODUCTION_TIMEOUT_S` 是服务端硬期限。

流程：完成审查 → 选 Claim → 生成提案 → 查看 diff/测试/命令 → 勾选已审阅 → 批准特定摘要 → 原始副本执行同一回归测试失败且出现指定标记 → 仅修复副本应用补丁 → 同一测试通过 → 下载补丁。也可 POST 人工准备的 `RepairPlan`，不用模型生成补丁。

端点：

```text
POST /api/v1/audits/{run}/repairs             {claim_id, plan?}
GET  /api/v1/audits/{run}/repairs/{repair}
POST /api/v1/audits/{run}/repairs/{repair}/approve  {approval_digest}
GET  /api/v1/audits/{run}/receipts
```

补丁摘要绑定 Claim、运行、修复代码、回归测试和快照哈希。审批和执行记录落在 `runs/.repairs`。请求断开后先 GET 查询状态；不能重复批准已执行提案。执行中宿主故障留下 `executing` 时应保留该提案调查并创建新提案；容器内部期限会结束遗留执行。

服务同时核对审查时保存的源码 SHA-256 与提案快照；源码已偏离审查版本时拒绝提案和批准，必须重新审查。缺少摘要的历史运行也必须重审。模型建议的测试和命令需要实际审阅，本次真实示例就修正了模型的测试导入路径问题。

Docker 执行使用 `--pull=never`、无网络、只读源码/根文件系统、非 root、无 capabilities、禁止提权、PID/CPU/内存上限和临时目录。缺镜像、启动失败、超时均不能算复现。`SubprocessReproductionExecutor` 只供明确可信的本地测试夹具，不能作为安全沙箱。

源仓库永不自动写回。报告中的 `high_confidence` 只表示支持结构；修复的 `regression_passed` 只表示该副本通过指定测试。Docker 并非强租户隔离，敌对代码建议使用独立 VM/专用 worker。

## 备份、恢复与运行边界

单机建议一个 API worker。`runs` 包含任务、事件日志、完整 Claim/manifest、修复凭证和声誉 SQLite；必须一起备份。在停止写入后备份卷，或对 SQLite 使用在线备份 API。旧 PostgreSQL 用 `pg_dump`，新 MySQL 用 `mysqldump --single-transaction`（细节及恢复演练边界见 MySQL 运维），恢复后用 Flyway validate 和 `/ready` 验证，不使用自动 schema update。未完成任务会在服务重启时恢复；已取消任务不会重跑。

共享文件租约只能避免一般重复领取，文件事件总线不是分布式消息日志。当前不承诺任意多副本、跨节点容灾或 exactly-once；上线按单 API worker 部署，扩容需先替换任务租约/事件总线。

监控 `/health`、`/ready`、网关 `/actuator/prometheus`，对模型失败、Reader 失败、任务堆积、Redis 降级和磁盘使用率报警。Redis 故障降级内存桶时不能宣称仍保证跨实例统一限流。

## 可选风险闭包

`PARALLAX_SEMANTIC_PARTITIONING=true` 或 CLI `--semantic-partitioning` 启用 Python AST 导入、共同环境配置键和部分权限装饰器关联，按跳数/上下文数补充相关文件。实际扩充后的分区写入 manifest，相关性预算仍生效。

这是可解释、有限深度的语法近似；不宣称完整调用图、动态数据流、别名/共享状态或权限流证明。默认关闭，不改变既有实验分区。
