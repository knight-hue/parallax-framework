# Parallax（视差）

[![CI](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](backend/pyproject.toml)

> **面向研发团队的智能代码审查与修复协作平台，以独立证据装配为审查引擎，由 Java 主导平台业务。**
> 单眼无法判断深度，必须靠两只眼睛从不同位置观察，才能恢复被压平的立体信息。
> 多智能体从众的本质，就是把 N 个 Agent 压成了一只"平均眼"——视差消失，真相被拍平。
> Parallax 做的事，就是把视差还给系统。
>
> **先独立，后共识（Independence before consensus）。**

---

## 项目目标与文档入口

最终目标是 Java 平台后端 + MySQL + Redis + RabbitMQ + Python 审查引擎 + Next.js 工作台，形成仓库接入、权限与预算、可靠审查、人工审批和隔离回归的完整闭环。保留可插拔框架、CLI、Receipt 协议和可复现实验，服务 Java 后端主力项目与开源框架工具展示。

**Java 默认运行档已切换 MySQL，组织/项目权限基础已实现，任务管理仍主要在 Python。目标升级尚未完成。** 秒杀与 XA/TCC/Seata 是独立实验，报告安全分享与短链后置。

| 文档 | 用途 |
| --- | --- |
| [最终目标](PROJECT_GOALS.md) | 定位、职责、范围和完成判据 |
| [技术升级方案](JAVA_BACKEND_PLAN_V2.md) | Java 技术栈、实施阶段、原理实验与验收 |
| [当前状态](PROJECT_STATUS.md) / [开发交接](PROJECT_HANDOFF.md) | 已实现事实、差距和下一步 |
| [验收记录](ACCEPTANCE.md) / [运行说明](OPERATIONS.md) | 历史证据与当前代码的可执行命令 |

以下核心机制属于可复用的审查引擎，不因平台升级而移除。

## 1. 要解决的问题

多智能体系统的直觉是"人多力量大"，但实证结果相反：

| 来源 | 结论 |
| --- | --- |
| HIDDENBENCH（CMU, ICML 2026, arXiv 2505.11556） | 信息分散任务上，多智能体 **30.1%**，单智能体拿到全量信息 **80.7%** |
| Correlated Errors in LLMs（ICML 2025） | 同源模型的错误高度相关 |
| Agent Scaling via Diversity（arXiv 2602.03794） | 同质 Agent 收益急速递减；**2 个异构 Agent 可抵 16 个同质 Agent** |
| Diversity Collapse（ACL 2026 Findings, arXiv 2604.18005） | 多样性崩塌的根因是**共享模型 + 共享 prompt 的结构耦合**；过度收敛会让群体**漏掉非平凡缺陷** |
| InfoDelphi（CMU 2026, arXiv 2607.01661） | **证据分区**可降低误差相关性（Brier 改善 12–18%、准确率提升 4–8pp）；**移除信息不对称后增益几乎归零** |

学术界的多样化杠杆是**模型 / prompt / 工具异构**。但现实中多数团队只有一两个模型可用
（预算、合规、内网），这条杠杆常常拉不动。

> **Parallax 的位置：当所有 Agent 都是同一个模型时，如何把独立证据、争议和覆盖率做成可审计的代码审查协议？**
> **答案是信息分区，不是模型异构。**

Diversity Collapse 的作者给出的建议是 NGT（先独立产出、后群体综合）。这类研究和 InfoDelphi
构成了本项目的公开研究背景；Parallax 不把信息分区或有效独立通道指标宣称为理论首创，
而是把相关认识落成面向代码审查的可运行、可追溯协议。

---

## 2. 四步机制

| # | 机制 | 做什么 |
| --- | --- | --- |
| 1 | **盲读分区** | N 个 Reader 各读不重叠的证据子集，**互相看不到对方的 claim** |
| 2 | **Claim 账本** | 每条 claim 记录提取者、声誉快照、独立交叉验证数、争议对手、**源指针** |
| 3 | **声誉加权聚合** | **规则化**判定高置信 / 待验证 / 争议；争议触发仲裁 |
| 4 | **覆盖率驱动补检** | 系统层计算覆盖缺口，**派全新 Reader** 定向补检 |

### 关键设计一：盲读在 Reader 层，覆盖率在系统层

- Reader **不知道**全局缺口——它只知道自己的那片证据，这正是它能保持独立的原因；
- 系统**知道**全局缺口；
- 补检是**派新的 Reader**（新身份、新分区）去收集，**不是让老 Reader 补读**。

所以补检**不破坏盲读**。代码上体现为 `BlindPartitioner.reader_ids()` 每轮生成全新身份。

### 关键设计二：`redundancy` 是独立性与可验证性的旋钮

"不重叠"若严格按字面执行（每条证据只给 1 个 Reader），会立刻自相矛盾：
**没有任何两条 claim 来自同一证据 → 交叉验证计数恒为 1 → 所有 claim 永远停在待验证状态
→ 机制 3 直接变成死代码。**

因此本框架把"不重叠"精确化为两条可验证的约束：

1. **输出隔离**（真正的抗从众约束）——Reader 之间永远看不到对方的 claim，这条不让步；
2. **输入受控冗余**（可调旋钮 `redundancy`）——每条证据分给 `redundancy` 个 Reader。

这与 InfoDelphi 的"共享公开子集 + 互斥私有子集"结构同构：每个 Reader 既有别人也有的部分
（可交叉验证），也有别人没有的部分（提供独立性）。

### 关键设计三：异见者不受惩罚

直觉做法是用"少数服从多数"更新 Agent 声誉——**但那本身就是一种从众压力**：
Agent 会迅速学会"不要第一个说不同意见"，于是我们在框架内部亲手重建了想消灭的东西。

因此本实现规定：**争议未裁决时，双方声誉都不变动**；只有仲裁裁决落地后才结算。

### 关键设计四：审计层必须比它审计的结论更独立

`Audit Without Verification`（arXiv 2609.07680）用 34.5 万次请求证明：只读上游报告的问责层
会退化成**转发**——在无人提对真因的情形里只找回 4.1% 的真因（低于 20% 的随机猜）；
把「Agent 自己给出的结论」字段删掉后，同一批证据下准确率升到 45.2%（+41.2pp）。

`Claim.statement` 就是那个「结论字段」。因此本轮把三条控制面做进引擎：

| 控制面 | 做什么 | 证据 |
| --- | --- | --- |
| 结论剥离仲裁（`core/arbitration.py`） | 仲裁器只拿到指针/引用/可证伪条件，回到证据重新推导三态信号；结论只留不可逆摘要 | `eval/java-platform/blind-arbitration.json` |
| 缺口归因（`core/gap_attribution.py`） | 把「没覆盖到」拆成系统层漏派与读者层漏报，用 Chapman 估计漏检，无重捕不发数字 | `eval/java-platform/gap-attribution.json` |
| 独立性闸门（`core/admission.py`） | 独立性不足时自适应调整分区（重叠过高降冗余、通道不足加 Reader），用尽后把高置信降级 | `eval/java-platform/independence-gate.json` |

三条设计都遵守同一条纪律：**不确定就升级人工，不猜**。证据沉默时保留争议，
无重捕时拒绝给漏检率，无法再提独立性时不再空转。

### 与最近邻研究的边界（不主张的部分）

本项目**不**把以下能力当作首创：

- 信息不对称分区：InfoDelphi（arXiv 2607.01661）已提出共享公开 + 互斥私有子集并给出 Brier 改善；
- 冲突感知账本：LatticeMind（arXiv 2608.08236）已做显式条目状态与延迟调和；
- 结构化异议：FinCom（arXiv 2606.00939）的 Disagree-or-Commit 已把异议当治理原语；
- 同伴可信度估计：ECL（arXiv 2601.21742）已用历史交互建模抗盲从。

可核查的差异点只有三个：①把上述认识合成到**代码审查**的可运行、可审计协议；
②覆盖率驱动的补检闭环（系统层知缺口、Reader 层不知）；③把独立性指标**当作运行时闸门**而不是报表。

---

## 3. 审查引擎与平台架构

```text
┌──────────────────────────────────────────────────────┐
│  LangGraph 编排（graph/build.py）                     │
│                                                      │
│   ingest → partition → blind_read → collect          │
│               ↑                        ↓             │
│               │                    aggregate         │
│               │                        ↓             │
│               └──── coverage ←─────────┘             │
│                        │                             │
│                     finalize                         │
└──────────────────────────────────────────────────────┘

核心机制（core/，与场景无关）
    partitioning.py   盲读分区（确定性、分组感知、每轮换新身份）
    reader_pool.py    并发盲读 + 输出隔离 + schema 重试
    ledger.py         账本：准入、归并、独立来源计数、仲裁裁决落地
    aggregator.py     规则化聚合：状态判定 + 对数几率置信度
    coverage.py       覆盖率监控：两个覆盖语义 + 补检调度
    gap_attribution.py 缺口归因：分区缺口 vs 读者漏检 + Chapman 漏检估计
    arbitration.py    结论剥离仲裁：观察视图 + 证据信号 + 度量曲线
    admission.py      独立性准入闸门：度量 → 重分区 → 降级
    reputation.py     声誉：Beta 后验 + 反从众更新策略
    independence.py   独立性运行时画像 + 证据血缘图

扩展点（ports/，边界清晰、按需注入）
    EvidenceAdapter   证据从哪来、怎么切、按什么维度分区
    ReaderPlugin      怎么问、怎么解析、怎么给 claim 打指纹
    ClaimValidator    入账前的否决权（可选，可串联）
    Falsifier         Claim 的独立反证/验证（可选，离线规则 + OpenAI 真实模型）
    Arbitrator        争议仲裁（可选，默认 NullArbitrator 不做裁决）
```

**领域模型**（`domain/models.py`）刻意保持场景无关：
`EvidenceUnit` / `Claim`（指纹 + 极性 + 源指针 + 可证伪字段）/ `AgentReputation` /
`CoverageMatrix` / `RunManifest` / `AuditReceipt` / `IndependenceProfile` /
`ProvenanceGraph`。

### 当前实现：Java 平台网关与 Python 审查服务

```text
前端 / 集成方
     │  X-API-Key
     ▼
┌───────────────────────────────────────────────┐
│  Java 网关（平台层）                          │
│  身份与配额 · 运行记录 · 分布式限流 · 可观测性 │
│                                               │
│  当前：网关入口，尚未接管完整业务              │
└───────────────────────────────────────────────┘
     │  X-Trace-Id / X-Parallax-Credential-Id
     ▼
┌───────────────────────────────────────────────┐
│  Python 编排服务（框架核心）                  │
│  证据怎么装配 —— 分区 / 盲读 / 账本 / 聚合 /   │
│  覆盖率驱动补检                               │
│                                               │
│  每次运行结束 → 完成回调把用量回报给网关        │
└───────────────────────────────────────────────┘
```

这张图描述当前实现。Java 网关现有认证、配额、运行记录与流控能力；Python 仍负责任务管理与内部事件。当前边界不代表最终平台范围。

### 目标架构：Java 管业务生命周期，Python 管审查机制

```text
前端 / CI → Java 平台后端 → MySQL（业务、任务、事件、额度、Outbox）
                  │       → Redis（缓存、限流、通知）
                  │       → 产物存储（快照、报告、补丁）
                  └→ Outbox 派发 → RabbitMQ → Python 审查 Worker / 隔离执行
                                             └→ 版本化事件和结果回报 Java
```

Java 模块化单体管理用户/组织/项目、仓库、策略、任务状态、预算、结果与审批。Python 保留独立取证、反证、聚合和补检；平台状态由 Java 统一管理，CLI/离线模式保持独立可用。跨进程协议、attempt/fencing、幂等和恢复按技术方案实施，尚未以当前服务链路验收。

---

## 4. 快速开始

```bat
cd backend

:: 使用已有虚拟环境与依赖；先核查本地工具，不自动安装

:: 跑测试（不依赖网络与 API key）
.venv\Scripts\python.exe -m pytest

:: 离线自检：只走证据加载与分区，不调用模型
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --dry-run
```

配置模型后正式运行（复制 `.env.example` 为 `.env` 并填 key）：

```bat
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --out runs\report.md
```

> 使用本机已有 Python、Node、JDK 21、Maven 和 Docker，先定位工具及缓存。当前完整链路与离线验证见 [OPERATIONS.md](OPERATIONS.md)；已有 `.toolchain/` 仅为本地缓存，不作为重新下载或安装的理由。

### 常用参数

| 参数 | 作用 |
| --- | --- |
| `--readers N` | Reader 数量 |
| `--redundancy K` | 每条证据被几个 Reader 看到（**核心实验旋钮**） |
| `--support N` | 判定高置信所需的独立来源数 |
| `--visibility blind\|shared` | `blind` = 框架正常模式；`shared` = 传统协作**对照组** |
| `--max-rounds N` | 补检轮次上限 |
| `--json` | 输出 JSON 而非 Markdown |

---

## 5. 怎么写一个插件

框架本身不含任何场景知识。要接入新场景，实现三个对象即可：

```python
from parallax.domain.models import Claim, EvidenceUnit, SourceRef
from parallax.ports.llm import ChatMessage


class MyAdapter:                      # ① 证据从哪来
    name = "my-source"

    def load(self, question) -> list[EvidenceUnit]: ...
    def dimension_rows(self, units) -> list[str]: ...       # 覆盖率矩阵的行


class MyReader:                       # ② 盲读怎么做
    name = "my-reader"

    def claim_types(self) -> list[str]: ...                 # 矩阵的列
    def output_schema(self): return MyOutputModel           # 强制结构化
    def build_messages(self, question, shard, reader_id):
        # ⚠️ 只能传 shard，不得传其他 Reader 的产出
        return [ChatMessage(role="system", content=...), ...]
    def parse(self, payload, shard, reader_id, round_index, reputation) -> list[Claim]:
        # 指纹必须确定性；同主体不同立场要共享指纹，否则矛盾检不出来
        ...


class MyValidator:                    # ③ 可选：入账否决权
    name = "my-check"
    def validate(self, claim, shard): ...
```

参考实现见 `parallax/plugins/code_audit/`。

---

## 6. 当前状态与目标差距

已实现独立证据装配引擎、Claim/Receipt 与声明血缘约束、可选反证和风险上下文、审阅后隔离修复、FastAPI/SSE、Next.js 工作台及 Java 网关的平台基础。

2026-10-20 既有验收：Python 290 项，Java 47 项单元/集成与 12 项真实 PostgreSQL/Redis 检查，前端构建及 2 项 SSE 检查。本机强认证链路和独立真实模型/修复实验有原始产物；本轮文档校准没有重跑测试。

| 最终目标 | 当前差距 |
| --- | --- |
| MySQL + Java 平台业务 | 默认 MySQL 运行档、组织/项目权限、仓库/策略、任务/预算、产物和审批已实现；MySQL 8.4.0 迁移（V1–V11）、19 表离线复制与 22 表备份恢复校验和一致已验收 |
| 原子预算与可靠执行 | 预占/结算/Outbox/Inbox/fencing/心跳/恢复已实现；真实 RabbitMQ 4.1.4 分发、双实例共享配额、容量与故障注入已验收（单机短时，不作生产容量结论） |
| 研发闭环 | Java 侧审批/产物管理已实现；GitHub PR 与 GitLab MR 的签名/token webhook、项目绑定与 delivery 幂等已实现；容器级隔离执行器 6 项边界测试通过；真实 webhook 现场验收与 VM 级隔离仍待完成 |
| 缓存、容量与诊断 | 策略只读缓存、真实 Redis IT、任务/Worker/审批/缓存/Outbox 指标、可终止子进程与容器执行器已实现；网关与 Python 服务均有指标端点（`/actuator/prometheus`、`/metrics`），可选 Prometheus/Grafana 编排已提供；生产采集端、VM 隔离与跨主机部署待完善 |
| 后置扩展与独立实验 | 报告安全分享与短链已实现；JVM/并发/Redis/Spring 已运行验证；2PC/TCC 为 SQLite 模拟；MySQL 8.4.0 真库索引/隔离/死锁与 Seata 2.6 AT/TCC 已运行验证；独立短链域名与热点容量待完善 |

当前文件租约按单 API worker 使用，不承诺跨节点协调或 exactly-once。AST 上下文只是有限语法近似；声明血缘不能发现所有未知共同来源；high_confidence 不是正确性证明，指定回归通过不等于完整无缺陷。

真实无标注仓库不能报告 precision/recall。兼容端点 gpt-6.1-sol 的 urllib3/util 三文件子集完成 5 臂 × 3 次有效重复，不代表完整仓库或机制收益已获得统计证明。历史 DeepSeek/合成语料结果按原条件保留，不混入新验收。

详见 [当前状态](PROJECT_STATUS.md)、[历史验收](ACCEPTANCE.md)、[最终目标](PROJECT_GOALS.md) 与 [实施方案](JAVA_BACKEND_PLAN_V2.md)。公网部署、正式执行镜像和现场运维验收仍未完成。

---

## 7. 目录

```text
backend/                        Python 编排核心（唯一包含机制的部分）
├─ parallax/
│   ├─ domain/      领域模型与枚举、异常
│   ├─ ports/       扩展点协议（EvidenceAdapter / ReaderPlugin / ClaimValidator / Falsifier / Arbitrator）
│   ├─ core/        七模块机制实现（含独立性画像与血缘）
│   ├─ graph/       LangGraph 编排
│   ├─ infra/       模型客户端、仲裁器
│   ├─ plugins/     内置场景插件
│   ├─ service/     FastAPI + SSE 服务层
│   ├─ config.py    全部可调参数（无隐藏魔法数字）
│   ├─ engine.py    装配与执行
│   ├─ reporting.py 报告渲染
│   └─ cli.py       命令行入口
└─ tests/           381 项（以 pytest 实际收集数为准）

frontend/                       Next.js 工作台（提交 / 实时事件流 / 账本 / 覆盖率矩阵 / Java 平台任务）
gateway/                        Java 平台业务后端（身份、项目、任务、预算、Worker 协调、审批与 webhook）
├─ src/main/resources/db/migration/   Flyway 迁移（PG 与 H2 都可执行）
├─ src/test/java/.../support/         测试用的上游 HTTP 服务桩
└─ README.md                          网关自身的说明与取舍

eval/corpus/                    可复现语料（三档规模）
eval/results/                   合成语料上的对照实验原始产物
eval/real/                      真实开源仓库上的对照实验（urllib3 / anyio）与重复实验
```

> 最终目标、技术方案、当前状态、验收与运行文档均在本仓库内。工作区同级 `说明材料/` 额外保留计划摘要、历史复盘及参赛材料。
>
> 这也意味着 README 里指向 `../说明材料/` 的链接**在 GitHub 上是打不开的**（那不在仓库里），
> 但在本地开发环境中可达。

---

## 8. 运行当前实现

使用已有工具、依赖与缓存镜像，按 [OPERATIONS.md](OPERATIONS.md) 配置并运行。当前默认运行档为工作台 → Java → Python + MySQL/Redis；旧本机全链路验收显式使用 legacy-postgres。MySQL 真库与迁移检查见 [MySQL 运维](gateway/MYSQL_OPERATIONS.md)，RabbitMQ 尚未接管执行。

仅校验生产合并配置，不启动服务或下载镜像：

```powershell
docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.production.yml --profile gateway config --quiet
```

实际启动要求本地已经具备对应镜像，使用运行文档中的 `--no-build --pull never`。Python CLI 可独立使用；目标平台业务以 Java 为必需入口。

### Git/PR 来源与复现验证

提交接口除了 `repo_path` 还接受 `repo_url` 与 `commit_sha`。远程来源只允许 HTTPS，服务会浅克隆并以 detached HEAD
检出指定提交；本地来源提供 `commit_sha` 时也会校验当前 HEAD，避免审查漂移代码。旧 Python 流程的 GitHub PR webhook 为
`POST /api/v1/webhooks/github`，配置 `PARALLAX_WEBHOOK_SECRET` 后，服务只接受 HMAC-SHA256 签名的
`opened`、`reopened`、`synchronize` 事件，并固定 PR head SHA。

Java 平台的 PR 接入为 `POST /api/v1/platform/webhooks/github`：必须先把已登记仓库绑定到 GitHub repository id，
配置 `PARALLAX_GITHUB_WEBHOOK_SECRET` 后按 `X-GitHub-Delivery` 幂等创建 Java 任务；详见
[平台 API](gateway/PLATFORM_API.md)。GitHub PR 与 GitLab MR 共用一条受理路径；真实 webhook 现场验收仍未完成。

Claim 的 `reproduction_plan.command` 是显式 argv 列表。设置 `PARALLAX_ENABLE_REPRODUCTION=true` 才会执行，
服务使用禁止拉取镜像、无网络、非 root、只读源码/根文件系统、资源受限的 Docker 执行器。
应部署在专用 worker；普通 API 保持执行关闭。Subprocess 执行器只供可信夹具，不是安全沙箱。

### 平台升级边界

- 用户、组织与项目资源权限已由 Java 平台实现；旧管理员/API Key 入口仅作兼容。
- Java/MySQL 维护平台任务、租约、预算和事件权威状态；Python 保留独立证据装配和 Worker 执行。
- 秒杀与分布式事务组件只在独立实验中启动；安全分享后置，默认平台依赖与实验依赖分别管理。

---

## 9. 许可

Apache-2.0
