# 运行与隔离验证

当前 Java 默认使用 MySQL，Compose 同步切换；旧 PostgreSQL 通过 legacy-postgres 显式保留。新库运行、停写迁移和回退见 [MySQL 运维](gateway/MYSQL_OPERATIONS.md)。任务仍由单 Python API worker 管理，RabbitMQ 与 Java 调度尚未接管。最终目标见 [PROJECT_GOALS.md](PROJECT_GOALS.md)。

## 配置和构建

实际密钥只写 `backend/.env`，不要填写或提交 `.env.example`。支持 `PARALLAX_LLM_*` 和 `OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL`；PARALLAX 配置优先。兼容服务的模型别名不能当作官方 OpenAI 型号证明。

### 模型供应商差异（`PARALLAX_LLM_PROVIDER`）

当前接入 DeepSeek（OpenAI 兼容协议）。`PARALLAX_LLM_PROVIDER` 取 `auto`（默认，按 `base_url` 域名推断）/ `openai` / `openai_compat` / `deepseek`，差异只影响请求参数，不改协议：

| 供应商 | temperature | token 字段 | `reasoning_effort` | `response_format` |
| --- | --- | --- | --- | --- |
| openai | 推理模型不发 | 推理模型用 `max_completion_tokens` | 有配置才发 | 受 `PARALLAX_LLM_USE_JSON_MODE` 控制 |
| openai_compat | 同上 | 同上 | 有配置才发 | 同上 |
| deepseek | 非推理模型才发 | `max_tokens` | **从不发**（DeepSeek 无此字段） | 推理模型不发 |

显式把 `PARALLAX_LLM_PROVIDER` 设为 `deepseek` 且没改 `PARALLAX_LLM_BASE_URL`（仍是 OpenAI 默认值）时，会自动改用 `https://api.deepseek.com`；`PARALLAX_LLM_MODEL` 仍留 OpenAI 默认值时会退到 `deepseek-chat`。使用自建代理时请同时显式设置 base_url 与 model。

解析结果可在 `GET /health`（`provider`、`model`）与 `GET /api/v1/meta` 看到，两者都不回显端点与密钥。

不联网构建：Python 使用已有 `.venv`；前端执行已有 `node_modules` 中的 lint、typecheck、build；网关执行 `mvn -o verify`。禁止用 `npm ci`、pip 安装或 Docker build 来冒充离线验证。

生产 Compose 覆盖文件要求预先准备项目镜像和基础设施镜像，缺少就失败，不会下载：

```powershell
docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.production.yml --profile gateway config --quiet
docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.production.yml --profile gateway up -d --no-build --pull never
```

生产必须配置 JWT、管理口令、内部令牌和数据库密码。仅 web 绑定本机回环端口；由现场现有反向代理提供 TLS。控制台默认走 `/backend` 同源代理，服务端 `PARALLAX_SERVER_API` 指向 Java 网关。访问令牌只保存在当前页面内存。管理员使用 JWT；集成方使用 API Key。不要把模型密钥填入控制台访问令牌。

核心 API 的 `PARALLAX_GATEWAY_INTERNAL_TOKEN` 与网关相同，拒绝缺少内部凭据的 API 请求；探针保留。公网入口只开放 web/TLS，模型服务、数据库、Redis 均不直接暴露。

## 平台 Worker 执行模式

默认 `PARALLAX_PLATFORM_EXECUTION_MODE=inline`，与既有部署兼容。设为 `process` 后，平台 Worker 为每个任务启动一个子 Python 进程，父进程按 Java deadline 等待；超时或取消时先 terminate，宽限期 `PARALLAX_PLATFORM_PROCESS_TERMINATE_GRACE_SECONDS` 后 kill。`PARALLAX_PLATFORM_MAX_CONCURRENT_TASKS` 限制同时执行的引擎数量，超出槽位的任务等待且仍受 deadline 约束。

这是**进程级**隔离，不是容器/VM 安全沙箱；子进程共享宿主文件系统和网络，并通过环境继承模型配置。敌对租户或不可信代码仍需专用容器/VM。子进程请求文件不包含密钥，结果由父进程重新校验 SHA-256。

### 容器模式（`container`）

需要更强边界时设 `PARALLAX_PLATFORM_EXECUTION_MODE=container`。先在 `backend/` 下构建镜像（不拉取外部镜像）：

```powershell
docker build -f docker/sandbox.Dockerfile -t parallax-engine-sandbox:local .
```

每个任务起一个一次性容器：`--network none`、`--read-only` + `/tmp` tmpfs、源码只读挂到 `/src`、唯一可写的 `/work`、`--cap-drop ALL`、`no-new-privileges`、非 root（65534:65534）、PID/CPU/内存上限。超时或取消时容器被强制删除，结果仍要过 SHA-256 校验。引擎看到的只有 `/src`，拿不到宿主路径。

两个边界必须说清：它**共享宿主内核**（不是 VM），且本次只验证了执行器与边界行为，生产镜像的构建与部署需在目标环境另行验收。限额参数：`PARALLAX_PLATFORM_CONTAINER_IMAGE` / `_MEMORY_MB` / `_CPUS` / `_PIDS` / `_TMPFS_MB`。

## 抗从众控制面

三个开关默认都不改变既有行为，可以按需启用：

| 配置 | 默认 | 作用 |
| --- | --- | --- |
| `PARALLAX_INDEPENDENCE_GATE` | `observe` | `off` 只记录；`observe` 报告本应如何处置；`enforce` 真正重分区并在用尽尝试后把高置信降为待验证 |
| `PARALLAX_MIN_EFFECTIVE_CHANNELS` | `0` | 有效独立通道数下限；`0` 表示不要求 |
| `PARALLAX_MIN_NORMALIZED_INDEPENDENCE` | `0` | 归一化独立性下限；`0` 表示不要求 |
| `PARALLAX_MAX_INDEPENDENCE_ATTEMPTS` | `1` | 为提高独立性最多重分区几次 |

只有同时设置了阈值，`enforce` 才可能触发；触发后停止原因记为 `independence_below_budget`，
报告中的结论均为待验证，不得当作高置信采信。整改方向是自适应的：证据重叠超过
`PARALLAX_MAX_EVIDENCE_OVERLAP_RATE` 时降冗余，否则加 Reader；两者都到顶时不再空转，下一轮直接降级。

仲裁是可选扩展点。不注入仲裁器时争议组原样保留为 `disputed`；注入 `core.arbitration.BlindArbitrator`
后，仲裁输入不含任何一方的结论文本，只给指针、引用与可证伪条件，并与原始证据重新核对。
回执里的 `statement_digests` 只能在事后验证“当时账本确实是这句话”，不能反推出被剥离的结论。

## 运行产物镜像（对象存储）

默认 `PARALLAX_ARTIFACT_STORE=off`，报告/摘要/claims 只落在 `PARALLAX_RUNS_DIR`。需要把证据再留一份到别处时：

| 取值 | 行为 | 前提 |
| --- | --- | --- |
| `local` | 额外镜像到 `PARALLAX_ARTIFACT_LOCAL_ROOT`（默认 `<runs_dir>/_artifacts`） | 无 |
| `s3` | 镜像到 S3 兼容端点（AWS S3 / MinIO / OSS S3 网关） | **需先安装 boto3**；未安装时启动即报错并提示改用 `local` |

对象 key 固定为 `runs/<run_id>/report.md`、`result.json`、`claims.json`（带 `PARALLAX_ARTIFACT_S3_PREFIX` 时会加前缀）。
镜像失败只记日志、返回已写入列表，**不会**让已经成功的审查变成失败——本地产物仍在。

S3 分支目前只用假客户端做过单元测试，**没有在真实端点上验收**；上生产前需用目标端点跑一次 put/get/list。

## 可选监控栈

默认不启动。镜像需在工作环境自行准备，本仓库不代你拉取：

```powershell
docker compose --env-file backend/.env --profile gateway --profile observability up -d --pull never
```

- Prometheus 只绑定 `127.0.0.1:${PARALLAX_PROMETHEUS_PORT:-9090}`，按 `observability/prometheus.yml` 抓
  `gateway:8080/actuator/prometheus`；`gateway` 服务属于 `gateway` profile，所以两个 profile 要一起启用。
- Grafana 只绑定 `127.0.0.1:${PARALLAX_GRAFANA_PORT:-3001}`，管理员口令取 `PARALLAX_GRAFANA_PASSWORD`。
- **Python 审查服务目前没有 `/metrics` 路由**，因此抓取配置里不列它。不写一个永远 down 的 job
  比写一个好看的目标列表更诚实；需要时先在服务端加导出器，再加 job。

仅校验配置而不启动：

```powershell
docker compose --env-file backend/.env --profile observability --profile gateway config --quiet
```

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
