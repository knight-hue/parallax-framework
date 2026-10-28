# 更新日志

本文件记录本项目的显著变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 2026-10-25 产品接线与可选监控栈

- 仲裁器可配置：`PARALLAX_ARBITRATOR=null|blind|llm|llm-blind`，CLI 同步 `--arbitrator`；
  `LLMArbitrator(redact_statements=True)` 让真实模型仲裁也不再读取双方结论。
- `Report` 新增 `gap_attribution` 与 `gate` 字段，`service/runner.py` 返回体同步，
  前端新增「覆盖缺口归因」「独立性准入闸门」两块面板。
- `.env.example` 补齐 `PARALLAX_INDEPENDENCE_GATE` 等 5 个开关。
- 新增可选监控栈：compose `profile observability`（Prometheus + Grafana，只绑回环）；
  抓取配置只含 `gateway/actuator/prometheus`，Python 无 `/metrics` 故不设 job。
- 真实模型仲裁实验脚本已就绪，端点返回 403 `service_suspended`，无实测数据，
  如实记录为 `eval/java-platform/blind-arbitration-llm-blocked.json`。
- 后端 438 项测试、前端 typecheck/lint/build 通过。

### 2026-10-22 抗从众控制面：结论剥离、缺口归因、独立性闸门

- 新增 `core/arbitration.py`：仲裁输入改为不含 `statement` 的 `Observation`，
  仲裁器回到证据上重新推导三态信号。实验（12 场景 × 4 异见位置）显示结论粘性
  从 0 升到 1 时，错误裁决从 0/48 升到 24/48，正确少数被救回率从 67% 降到 0。
- 新增 `core/gap_attribution.py`：把空缺拆成 `partition_gap` 与 `reader_miss`，
  用 Chapman 中位数估计漏检；无重捕不发数字，检出率留 0.95 上限。
  模拟验证：p=0.4/0.6/0.8 时估计相对偏差 -0.5%/-0.2%/+0.6%。
- 新增 `core/admission.py`：独立性指标从报表变成闸门（off/observe/enforce），
  重叠超预算降冗余、通道不足加 Reader，用尽后把高置信降为待验证，
  并新增停止原因 `independence_below_budget`。
- 新增配置 `independence_gate`、`min_effective_channels`、`min_normalized_independence`、
  `max_independence_attempts`，默认 observe + 阈值 0，不改变既有行为。
- 新增 43 项测试；后端 435 passed。证据：`eval/java-platform/` 下三份 JSON。
- README 补充「与最近邻研究的边界（不主张的部分）」：信息分区、冲突感知账本、
  结构化异议、同伴可信度均已有 2026 年工作，本项目不声称首创。

### 2026-10-20 最终目标校准（文档）

- 新增 PROJECT_GOALS.md，统一定位为 Java 主导的智能代码审查与修复协作平台，保留独立证据装配引擎与开源协议。
- 平台数据库确定为 MySQL；Java 接管组织权限、任务、预算和审批，技术阶段及实验要求见 JAVA_BACKEND_PLAN_V2.md。
- 秒杀、XA/TCC/Seata 为独立实验；报告分享为后置扩展。当前状态、历史验收和目标分别说明。
- 以下“无编排逻辑，可有平台能力”记录描述旧网关范围，不再限制 Java 平台业务；此次文档变更不表示迁移已经实现。

### 约定修订 · Java 网关从「薄网关」改为「无编排逻辑，可有平台能力」

原约定是**网关不依赖数据库，以免有人把业务逻辑写进来**。这条理由依然成立，
但它把**平台能力**一起挡在了门外：身份、配额、用量账本、运行记录本来就是网关的本职。

修订后的约定：

> **无编排逻辑，可有平台能力。**
> 新增的每个依赖都必须能回答"它服务于身份 / 配额 / 持久化 / 可观测性中的哪一项"，
> 答不上来就不该加。

分工边界因此更清楚：

| | 负责 |
| --- | --- |
| **Python 编排服务** | 证据怎么装配（框架核心） |
| **Java 网关** | 谁在用、用了多少、跑过什么（平台层） |

### 新增

#### Java 网关 · 身份与配额（C1）

- API Key 签发 / 查看 / 吊销：`POST|GET /api/v1/credentials`、`DELETE /api/v1/credentials/{id}`
- **明文 key 只在创建响应里出现一次**，服务端只存 SHA-256 摘要；
  没有任何"再查一次 key"的端点，需要再取一次就吊销旧的、签发新的
- 配额策略表 + 每日运行次数 / 每日 token / 每月 token 三重额度；
  提交审查（`POST /api/v1/audits`）**转发之前**校验，超限返回 429，
  响应体带 `used` / `limit` / `resetsAt` 与 `Retry-After`
- 运行次数按**提交**计数而不是按完成计数——只统计完成的话，
  用户能在第一次完成之前并发提交上千次，每次都真实烧掉模型费用
- 用量账本 `usage_ledger`：完成回调写入，**按 run_id 幂等**（回调可被重投）
- 用量查询：`GET /api/v1/usage/me`（凭据从认证主体推导，不接受 id 参数）、
  `GET /api/v1/usage`（ADMIN，含零用量的凭据）
- 完成回调 `POST /api/v1/internal/runs/{runId}/complete`，用 `X-Internal-Token` 校验

#### Java 网关 · 运行记录（C2）

- `audit_run` 表：提交时落 `queued`，完成回调补 token / 统计 / 停止原因
- `audit_event` 表：只记网关自己观察到的 `submitted` / `completed` / `failed`。
  编排内部的事件**刻意不复制一份**——上游已有可重放的事件总线，
  两份事实来源迟早不一致；运行详情里直接给出上游的事件流地址
- `GET /api/v1/runs`：按 status / credentialId / since / until 过滤 + 分页，
  单页上限 200（没有上限的话一次 `size=100000` 就能把网关内存打满）
- `GET /api/v1/runs/{runId}`：运行详情 + 生命周期事件 + 上游端点地址
- 可见性在服务端强制：非 ADMIN 即使显式传了别人的 `credentialId`
  也只能看到自己的；越权查询返回 404 而不是 403，不给"这个 run 存在"的旁证
- `POST /api/v1/audits` 会从上游 202 响应里取出 `run_id` 回填，
  使"网关的提交记录"与"上游的运行"对得上

#### Java 网关 · Redis 分布式限流（C3）

- 抽出 `RateLimiter` 接口：内存桶与 Redis 桶并存，选择逻辑收在
  `ResilientRateLimiter` 里，过滤器不需要知道用的是哪个
- Redis 桶（bucket4j-redis + Lettuce）：多实例**共享同一份配额**
- **Redis 不可用时自动降级回内存桶**并打 WARN，服务继续提供
- **冷却期**：首次失败后 30 秒内不再逐请求试 Redis。没有冷却的话，
  Redis 挂掉时每个请求都要先等一次命令超时，降级就从"服务仍可用"
  变成"每个请求多花 250ms"
- Redis 连接**惰性建立**：在构造函数里连会让 Redis 没就绪时整个网关启动失败——
  服务因为一个可选组件而起不来，比限流精度下降严重得多
- 不做跨进程队列（见下文"明确不做"）

#### Java 网关 · 可观测性（C4）

- Micrometer：`parallax_runs_total{status}`、`parallax_tokens_total{credential}`、
  `parallax_quota_rejections_total{metric}`、`parallax_ratelimit_degraded_total`；
  零值预先注册，否则"没有曲线"与"还没有事件"看起来一样
- 日志格式加入 `%X{traceId}`：没有它，"两端日志能对上同一次请求"只能靠时间戳猜
- 网关通过 `X-Parallax-Credential-Id` 把身份带给上游，供其回调时回报归属

#### Python 侧配合

- 接收 `X-Trace-Id` 与 `X-Parallax-Credential-Id`，写进日志与 `meta.json`
- 用 `ContextVar` 而不是线程局部变量：asyncio 下并发运行会互相覆盖 traceId
- 完成回调 `PARALLAX_CALLBACK_URL`，**默认关闭**；失败只记 WARN，
  绝不让一次成功的审查因此变成失败
- **失败运行也回报**：网关已为这次提交扣了额度，不回传的话它会永远停在 `queued`
- 只发 prompt / completion 两个分量，**不发 total**——合计由服务端算，
  不给第二个事实来源

#### 数据库与部署

- PostgreSQL + Flyway 迁移（`V1__identity_and_quota.sql`、`V2__audit_run.sql`、
  `V3__audit_event.sql`）；SQL 刻意写成 PostgreSQL 与 H2 都能执行的子集，
  使迁移脚本在**每次测试**中都被执行
- `docker-compose.yml` 新增 `postgres` 服务（与 `gateway` 同 profile）与健康检查；
  Redis 同时挂在 `gateway` profile 下——"多实例共享同一配额"正是它在这里的职责

#### 测试

- 默认测试档用 **H2（PostgreSQL 兼容模式）**：让没有 Docker 的机器也能跑完整套测试
- 明确记录代价：**H2 不能替代真实 PostgreSQL 做验证**，因此另有
  `PostgresPersistenceIT`（真实 PG，用**独立 JDBC 连接**读库以证明
  "数据在库里而不是在 Hibernate 缓存里"）与 `RedisRateLimitIT`（真实 Redis，
  验证两实例配额合并计算、Redis 不可用降级、冷却后重试）
- 两者用 `disabledWithoutDocker` 自动跳过，本地无 Docker 不受阻塞；
  CI 新增独立的 `gateway-it` 任务（`mvn -Pit verify`），
  让"逻辑测试失败"和"真实基础设施上失败"能一眼区分

### 明确不做（记录理由，避免反复讨论）

- **跨进程任务队列**：单实例够用；引入它会把"崩溃恢复"的复杂度提前引爆，
  且不影响任何已有结论。留在路线图里。
- **用户注册 / 密码体系**：单租户平台，API Key 足够；
  引入用户库会让网关变成第二个业务后端。
- **把编排事件再存一份到网关**：上游已有可重放的事件总线，
  复制一份只会造出两个可能不一致的事实来源。

### 计划中

- 跨文件组合型缺陷的评测语料（检验聚合层的证据装配能力）
- Redis / Qdrant 适配器（当前为内存实现）
- 把有效独立通道数 K\\* 作为运行时指标对外暴露
- 跨进程任务队列与崩溃恢复（见 `说明材料/任务总表.md` 第 7 节的取舍理由）

## [0.1.0] - 2026-10-15

首个可用版本：核心机制闭环 + 命令行 + HTTP 服务 + 对照实验台。

### 新增

**核心机制（`parallax/core/`）**

- 盲读分区：确定性、分组感知、每轮生成全新 Reader 身份
- Claim 账本：准入校验、按指纹归并、独立来源计数、仲裁裁决落地
- 规则化聚合器：状态判定（高置信 / 待验证 / 争议）+ 对数几率置信度
- 覆盖率监控：区分"证据覆盖"与"claim 格填充"两种语义，驱动定向补检
- 声誉策略：Beta 后验均值 + **异见者不受惩罚**（争议未裁决时双方声誉都不变动）

**编排（`parallax/graph/`）**

- LangGraph 状态图：`ingest → partition → blind_read → collect → aggregate → coverage → finalize`
- 补检回环：覆盖率不足时派**全新 Reader** 定向补检，不破坏已有 Reader 的盲读状态

**扩展点（`parallax/ports/`）**

- `EvidenceAdapter` / `ReaderPlugin` / `ClaimValidator` 三个必需接口
- `Arbitrator` 一个可选接口（默认 `NullArbitrator`：不做裁决，争议原样保留）

**内置插件（`parallax/plugins/code_audit/`）**

- `RepoAdapter`：代码仓库 → 标准证据单元，按目录分组
- `CodeAuditReader`：8 类缺陷类目、行号桶指纹（容忍不同 Reader 报出的行号漂移）、
  支持主张"确认并非缺陷"（反极性，使争议检测真正可用）

**基础设施（`parallax/infra/`）**

- OpenAI 兼容模型客户端（适配 DeepSeek）：指数退避、schema 校验、JSON 容错提取
- 离线假客户端：让全部机制可以脱离网络被测试
- LLM 仲裁器（默认关闭）

**服务层（`parallax/service/`）**

- FastAPI 应用：`/health`、`/ready`、`/api/v1/meta`、`/api/v1/audits`（提交/列表/详情）
- **SSE 进度流**：带序号的事件历史，支持 `Last-Event-ID` 断线重放 + 心跳保活
- 运行记录与报告的持久化（`meta.json` / `report.md` / `summary.json`）
- 提交即返回，后台执行；并发上限由信号量控制；优雅停机等待收敛

**评测（`parallax/eval/`）**

- 五个指标：召回率、精确率、冗余率、覆盖率、**有效独立通道数 K\\***
- 语料生成器：模板 + 标记 → 自动计算行号，生成可复现
- 对照实验编排：7 个实验臂（含固定预算对照与消融）

**命令行（`parallax/cli.py`）**

- `audit`：审查一个仓库，输出 Markdown / JSON 报告
- `experiment`：跑对照实验并汇总
- `smoke`：连通性与结构化输出自检

**可视化工作台（`frontend/`）**

- Next.js 16 + React 19 + Tailwind v4；提交审查 → 实时事件流 → Claim 账本 → 覆盖率矩阵
- SSE 客户端依赖服务端的**带序号事件历史**：断线自动重连并由 `Last-Event-ID` 补发缺口
- 三个可切换的结论分类（高置信 / 待验证 / 争议）+ 结论详情（依据、指纹、主张者）
- 覆盖率热力图把"孤证"与"无结论"用不同底色区分——补检目标一眼可见

**Java 薄网关（`gateway/`）**

- 统一入口 + **正则白名单**转发（默认拒绝，避免网关变成开放代理）
- 共享密钥换 JWT + 无状态鉴权（`require-auth` 默认关闭，公网暴露前必须打开）
- 限流（Bucket4j）：`POST /audits` 单独一个更小的桶，因为它才是真正花钱的操作
- 熔断（Resilience4j）：**幂等请求才重试**——重试 `POST /audits` 会创建两个运行
- SSE 不间断透传：不缓冲、不聚合，并透传 `Last-Event-ID`

#### 工程与治理

- Apache-2.0 许可证、贡献指南、行为准则、安全策略（含**显式声明的安全边界**）
- Docker 多阶段构建 + docker-compose（api / web 核心，gateway 与 redis/qdrant 走 profile）
- GitHub Actions CI **六项门禁**：Python 测试（3.11/3.12/3.13）、Python 静态检查、
  **语料完整性**、Java 网关测试、前端检查、三镜像构建 + 容器冒烟
- **154 项测试**（Python 144 + Java 10），不需要网络与凭据
- 参赛材料：作品介绍（docx + pdf）、演示视频脚本

### 修复

P0 阶段用真实模型运行、以及服务层端到端联调逼出的自身缺陷
（详见 [../说明材料/P0-验证结果.md](../说明材料/P0-验证结果.md)）：

- K\\* 公式分母漏平方 → 完全互斥时算出"发现总数"而非"通道数"
- 匹配指标未把冗余 claim 计入发现者 → **系统性低估交叉验证数**，让"孤证数"虚高
- 覆盖率把"有人报无人确认的格子"当补检触发条件 → 补检永不收敛
- 结果输出路径层级写错 → 实验产物被写到项目目录之外
- 测试可能意外调用真实模型 → 加全局夹具强制清空凭据
- **一个 Reader 一次调用要吐出全部分片发现** → 输出截断导致 Reader 大批失败，
  一度把"Reader 挂了"误读成"从众导致漏检"；改为分片内分批调用
- `max_output_tokens` 未显式设置 → 长输出静默截断，系统性偏袒分片更小的实验组
- SSE 端点游标在生成器内被重新赋值 → `UnboundLocalError`，事件流完全不可用

### 修复（真实仓库验证阶段，2026-10-16）

在 **真实开源仓库**（anyio / fastapi / urllib3）上跑对照实验时暴露的问题。
它们与上面那批是同一类错误的不同触发条件：从「语料变长」变成「文件变大」。

- **分区按整模块分配，在模块大小不均时退化** → anyio 实测三个 Reader 拿到的
  文件数是 33 / 38 / 46（最重的读了 100%），**盲读完全失效**，
  而这种退化看起来像"从众"、实际是分区不均衡的假象。
  修正：给分组设单元数上限 `ceil(N / R)`，超过就切成连续块（块沿用原 group 标签，
  覆盖率矩阵不受影响），旋转下标加入块序号。上限取值保证**结构均匀的语料完全不受影响**
  （seed_c 是 6 模块各 8 文件，R=6 时上限恰为 8，不触发切块）。
- **分批只按文件条数，在真实仓库上失效** → 合成语料平均 1,521 字符/文件，
  真实仓库 11,500（差 8 倍），「6 个文件」从 9k 字符涨到 69k 字符，
  模型输出撞上 token 上限被截断 → Reader 批量失败。
  修正：新增 `llm_max_batch_chars`，按**累计字符数**分批，与条数上限取先到者。
- **`llm_max_output_tokens = 8000` 在真实仓库上不够** → 实测截断点 47,866 字符，
  即使只给 1 个文件，模型对它的完整答复仍会超限（该模型在真实代码上输出极详尽）。
  实测端点接受 `max_tokens` 至 32000，提到 **16000**。
  提高它不影响合成语料的结果——那批运行的输出远低于 8000，从未触碰上限。

> 这三条修正的共同点是：**合成语料掩盖了它们**。语料的文件大小、模块大小都过于均匀，
> 而真实仓库的分布是长尾的。这正是"只在合成语料上验证"会漏掉的东西。
> 每一项修正都带着一条回归测试，断言合成语料的行为**逐字节不变**。

- 服务层的运行 id 与引擎自派生的 id 不一致 → 报告标题里的 id 在运行记录里查不到；
  改为引擎接受调用方传入的 run_id（不传时仍按配置派生，保证 CLI / 实验可复现）
- 用量快照只读编排层那本账 → 报告出现"12 次调用、0 token"；改为合并模型客户端的
  token 计数，同时**保持 `calls` 语义不变**（两本账合一会让已发布的实验数字整体翻倍）
