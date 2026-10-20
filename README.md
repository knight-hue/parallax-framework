# Parallax（视差）

[![CI](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](backend/pyproject.toml)

> **面向 AI 生成代码审查的独立证据装配与可验证审计框架**
> 单眼无法判断深度，必须靠两只眼睛从不同位置观察，才能恢复被压平的立体信息。
> 多智能体从众的本质，就是把 N 个 Agent 压成了一只"平均眼"——视差消失，真相被拍平。
> Parallax 做的事，就是把视差还给系统。
>
> **先独立，后共识（Independence before consensus）。**

---

## 1. 要解决的问题

多智能体系统的直觉是"人多力量大"，但实证结果相反：

| 来源 | 结论 |
|---|---|
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
|---|---|---|
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

---

## 3. 架构

```
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

### 两层分工：Python 管装配，Java 管平台

```
前端 / 集成方
     │  X-API-Key
     ▼
┌───────────────────────────────────────────────┐
│  Java 网关（平台层）                          │
│  身份与配额 · 运行记录 · 分布式限流 · 可观测性 │
│                                               │
│  约定：**无编排逻辑，可有平台能力**            │
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

**为什么要拆成两层而不是都写在 Python 里**：这条边界不是为了炫技，
而是因为两者的失效方式完全不同。编排逻辑写错了会得到错结论；
平台能力写错了会让人**看不到**自己已经超支。后者需要的是事务、唯一约束、
跨实例计数——这些恰是 JVM 生态最成熟的地方。

分工的唯一判据：**能在 5 秒内说清"这段代码错了会导致什么"，就属于这一层。**

---

## 4. 快速开始

```bat
cd backend

python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"

:: 跑测试（不依赖网络与 API key）
.venv\Scripts\python.exe -m pytest

:: 离线自检：只走证据加载与分区，不调用模型
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --dry-run
```

配置模型后正式运行（复制 `.env.example` 为 `.env` 并填 key）：

```bat
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --out runs\report.md
```

> **本机没有全局 node / mvn / javac 时**：仓内 `.toolchain/` 放了一份便携工具链
> （node / JDK 21 / Maven，已 gitignore）。前端与网关的完整构建命令见
> [../说明材料/本地构建.md](../说明材料/本地构建.md)。

### 常用参数

| 参数 | 作用 |
|---|---|
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

## 6. 当前状态与边界

| 模块 | 状态 |
|---|---|
| 领域模型、扩展点协议 | ✅ 完成 |
| 盲读分区 / 账本 / 聚合器 / 覆盖率 / 声誉 | ✅ 完成 + 单测覆盖 |
| LangGraph 编排（含补检回环） | ✅ 完成 |
| 代码审查插件（RepoAdapter + CodeAuditReader） | ✅ 完成 |
| 模型客户端（OpenAI / OpenAI-compatible）+ 离线假客户端 | ✅ 已实现；真实外部调用按环境连通性单独验收 |
| LLM 仲裁器 | ✅ 完成（默认关闭） |
| CLI + Markdown/JSON 报告 | ✅ 完成 |
| 对照实验台（8 个实验臂） | ✅ 包含单轮分片盲读对照、生效配置与失败记录 |
| 语料生成器（可复现，三档规模至 2712 行） | ✅ 完成 |
| **FastAPI 服务层 + SSE** | ✅ 完成，**已端到端联调**（含断线重放） |
| **Next.js 可视化前端** | ✅ 完成，构建与 lint 通过（明暗双色工作台） |
| **Java 网关 · 平台层** | ✅ 完成（身份配额 / 运行记录 / 分布式限流 / 指标 / 链路追踪），**已端到端联调** |
| Docker 部署（compose 四服务 + 可选 infra profile） | ✅ 完成，`compose config` 校验通过 |
| 开源治理（License / 贡献指南 / 安全策略 / CI 八项门禁） | ✅ 完成 |
| Receipt、独立性画像、可证伪 Claim、离线/真实模型反证和证据血缘 | ✅ 已实现，真实模型反证默认关闭 |
| 自适应补检调度 | ✅ 已实现，按硬缺口/争议/孤证确定性排序，可配置关闭 |
| 跨任务声誉持久化 | ✅ 已实现，服务层 SQLite；多副本可替换 Postgres/Redis 端口 |
| 跨文件组合型缺陷（P0-4） | ✅ 已加入可复现语料生成器与 ground truth 校验 |
| 测试 | ✅ Python **290 项** + Java 47 项单元/集成与 12 项真实 PostgreSQL/Redis + 前端构建及 2 项 SSE 检查 |
| 任务领取与恢复 | ✅ 文件租约和事件恢复；当前支持单 API worker，不承诺跨节点协调 |
| 审阅修复与隔离回归 | ✅ 补丁摘要批准、审查版本校验、Docker 原副本失败/修复副本通过，原仓库不自动写回 |
| Receipt 开放适配与风险上下文 | ✅ JSONL/Callback 接口，可选 AST 导入/配置/权限装饰器关联 |

### 当前升级边界与后续路线

2026-10-20 已完成声明血缘的传递共同上游检测、独立支持阻断、人工审阅后的隔离修复回归、
协议适配和认证前端代理。共享摘要/工具结果不能靠更换 Reader 身份变成独立支持。
真实模型修复和本机完整生产构建链路均已实测，证据见 [ACCEPTANCE.md](ACCEPTANCE.md)。
可选 AST 上下文不是完整动态语义分析；未披露的共同来源无法被证明不存在。

`K*` 是本项目采用的有效独立通道评估思想，不是 Parallax 首创。真实仓库没有 ground truth 时，
只报告独立性、冗余、覆盖、成本和失败数，不把结果写成召回率或精确率。完整路线见
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) 和同级目录的 [`../说明材料/最终完成路线图.md`](../说明材料/最终完成路线图.md)。

历史 DeepSeek 产物仅作为旧基线。本次使用用户配置的兼容端点 gpt-6.1-sol，完成 urllib3/util
三文件子集的 5 臂 × 3 次重复，15/15 有效、Reader 失败 0。它不是完整仓库或准确率验收。
输出 K* 与证据分区画像分开解读；零输出者不能被静默从所有 Reader 的分母中排除。

> 本机已实际验证 Docker 隔离执行、PostgreSQL/Redis 及生产构建服务链路。
> 缺少的项目 app/正式 worker 镜像没有下载或构建，公网服务器/TLS 尚未部署。
> 生产配置、审批隔离、备份恢复和支持拓扑见 [OPERATIONS.md](OPERATIONS.md)。

### Java 网关的平台能力

| 能力 | 做法 | 为什么这样做 |
|---|---|---|
| 身份与配额 | `X-API-Key` → SHA-256 摘要查库；三重额度（日运行数 / 日 token / 月 token） | 明文 key 只在签发时返回一次，服务端不存；库被拖走也拿不到可用凭据 |
| 配额执行时机 | 在**转发之前**校验，超限 429 并带 `used`/`limit`/`resetsAt`/`Retry-After` | 事后扣减看起来一样能"记账"，但用户会在额度已满时继续烧掉真实模型费用 |
| 运行次数计数 | 按**提交**计数，不按完成计数 | 只统计完成的话，用户能在第一次完成之前并发提交上千次 |
| 记账 | 完成回调写账本，按 `run_id` 唯一约束**幂等** | 回调可能被重投，没有约束就会重复计费 |
| 运行历史 | `audit_run` + `audit_event`，按状态/凭据/时间过滤与分页 | 事件只记网关自己观察到的生命周期；编排内部事件留在上游总线，不复制第二份事实 |
| 分布式限流 | bucket4j-redis + Lettuce，多实例共享同一份配额 | 单实例内存桶在多副本下等于没有配额 |
| **限流降级** | Redis 不可用时**自动回退内存桶**并进入冷却期 | 限流是保护手段，不该成为单点；冷却避免每个请求都白等一次超时 |
| 可观测性 | Micrometer 三个业务指标 + `%X{traceId}` 日志格式 | "一直在降级"必须能被发现，否则配额会悄悄退化成单实例口径 |
| 链路追踪 | `X-Trace-Id` 贯穿网关 → 编排 → 完成回调，并写入 run meta | 没有它，"183 次模型调用"和"网关那边的 429"只能靠时间戳猜关系 |

### 已实测的行为

**机制层面**（[tests/test_engine_e2e.py](backend/tests/test_engine_e2e.py)）：

- 盲读 + `redundancy=2`：一轮内完成交叉验证并收敛
- **严格分区（`redundancy=1`）+ 覆盖率补检：交叉验证跨轮涌现**——第一轮全是孤证，
  监控发现独立证据覆盖不足后派出**全新 Reader**，第二轮把孤证升为高置信，随后因"无新增主体"收敛
- 反证：关掉补检后，严格分区只能得到孤证
- 对照组可测出从众损失（风格化从众模拟器）

**真实模型层面**（[../说明材料/P0-验证结果.md](../说明材料/P0-验证结果.md)，2712 行 / 48 缺陷 / 6 Reader）：

| 实验臂 | 轮次 | Agent 数 | 召回 | **K\\*** | **独立通道占比** | 冗余率 | 调用 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `baseline_shared`（全部证据 + 共享结论） | 1 | 6 | 48/48 | **1.02** | **17.1%** | 82% | 48 |
| `sharded_shared`（同分片 + 共享结论） | 1 | 6 | 48/48 | 2.34 | 39.1% | 63% | 26 |
| `no_peers_all_evidence`（全部证据，不共享） | 1 | 6 | 48/48 | 1.40 | 23.4% | 75% | 48 |
| `blind_no_coverage`（严格分区） | 1 | 6 | 48/48 | **3.56** | **59.3%** | **1%** | **11** |
| `blind_full`（本框架完整机制） | 3 | **18** | 48/48 | 5.04 | 28.0% | 73% | 72 |

> ⚠️ **不要直接比较裸 K\\*。** 每一轮补检都会生成**全新 Reader 身份**（这是"补检不破坏盲读"的前提），
> 所以 `blind_full` 的 3 轮意味着 **18 个 Agent**，它的 K\\* 上限是 18 而不是 6。
> `1.02 → 5.04` 是「6 Agent vs 18 Agent」的比法，**不是同口径**。
>
> **同口径比较**（都是 1 轮 / 6 Agent）应看独立通道占比：
> `baseline_shared` **17.1%** → `blind_no_coverage` **59.3%**，
> 固定预算组 `budget_shared` **16.7%** → `budget_blind` **62.5%**。
> 即：**同样的 Agent 数，传统协作只发挥出约 17% 的独立性，分区方案发挥出约 60%。**
>
> 这个口径错误是在[真实仓库验证](../说明材料/B1-真实仓库验证.md)阶段发现的，已修正。

**核心结论：无论固定哪个约束，信息分区都占优。**

| 约束 | 对照 | 本框架 |
|---|---|---|
| **固定预算**（同样 48 次文件读取、11–12 次调用） | 覆盖 8/48 文件 → **召回 17%** | 覆盖 48/48 → **召回 100%** |
| **固定召回**（都是 48/48） | 48 次调用、冗余率 82% | **11 次调用（−77%）、冗余率 1%** |

四条可测收益：

- **固定预算下召回率 17% → 100%**（`budget_shared` 8/48 vs `budget_blind` 48/48，花费相同）
- **同口径独立通道占比 17% → 59%**：传统协作下 **6 个 Agent 的信息量约等于 1 个**（重叠矩阵趋于秩 1）
- **同等召回率下调用量减少 77%**（48 → 11）
- **冗余率从 82% 降到 1%**（对应"重复发现/噪音"痛点）

**关于"不限预算"的重要说明**：此前测出"所有臂召回率都触顶"，但那是**不限预算**的结果——
控制组让 6 个 Reader 各自通读全部 48 个文件，总阅读量是盲读的 **6 倍**。
在这种前提下"所有人都读全部"必然是分区的超集，召回率**不可能**偏向分区。
**"不限预算"不是公平比较，因为它把约束偷偷送给了对照组。**
把预算约束显式建模后（上表第一行），差异立刻显现。

---

## 7. 目录

```
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
└─ tests/           290 项（以 pytest 实际收集数为准）

frontend/                       Next.js 工作台（提交 / 实时事件流 / 账本 / 覆盖率矩阵）
gateway/                        Java 网关：平台层（身份配额 / 运行记录 / 限流 / 指标）
├─ src/main/resources/db/migration/   Flyway 迁移（PG 与 H2 都可执行）
├─ src/test/java/.../support/         测试用的上游 HTTP 服务桩
└─ README.md                          网关自身的说明与取舍

eval/corpus/                    可复现语料（三档规模）
eval/results/                   合成语料上的对照实验原始产物
eval/real/                      真实开源仓库上的对照实验（urllib3 / anyio）与重复实验
```

> **详细文档与参赛材料不在本仓库内。** 它们位于本项目**同级目录**的 `说明材料/` 下：
> 实验结论与缺陷复盘、项目计划书、本地构建说明，以及参赛材料。
>
> 这也意味着 README 里指向 `../说明材料/` 的链接**在 GitHub 上是打不开的**（那不在仓库里），
> 但在本地开发环境中可达。

---

## 8. 跑起完整系统

三块可以独立运行，也可以串成一条链路。**推荐按下面顺序**：

```bat
:: ① 编排服务（必需）
cd backend
.venv\Scripts\python.exe -m parallax.service.app
::   http://localhost:8000/docs 是自动生成的接口文档

:: ② 工作台（可选，但演示效果好得多）
cd frontend
npm install
npm run dev
::   http://localhost:3000

:: ③ 网关（可选；需要平台能力——配额、运行历史、多实例限流——时才起）
::    需要 PostgreSQL。切到 gateway profile 会连 postgres 与 redis 一起起来。
docker compose --env-file backend/.env --profile gateway up -d
::   http://localhost:8080/swagger-ui.html 是自动生成的接口文档

::    本地直接跑（不用容器）时需要先备好 PostgreSQL：
::    set PARALLAX_IDENTITY_ENABLED=true
::    set PARALLAX_DB_URL=jdbc:postgresql://127.0.0.1:5432/parallax
::    cd gateway
::    mvn spring-boot:run
```

或一把起全部：

```bat
docker compose --env-file backend/.env up -d                    :: api + web
docker compose --env-file backend/.env --profile gateway up -d  :: 再加 网关 + PostgreSQL + Redis
```

### Git/PR 来源与复现验证

提交接口除了 `repo_path` 还接受 `repo_url` 与 `commit_sha`。远程来源只允许 HTTPS，服务会浅克隆并以 detached HEAD
检出指定提交；本地来源提供 `commit_sha` 时也会校验当前 HEAD，避免审查漂移代码。GitHub PR webhook 为
`POST /api/v1/webhooks/github`，配置 `PARALLAX_WEBHOOK_SECRET` 后，服务只接受 HMAC-SHA256 签名的
`opened`、`reopened`、`synchronize` 事件，并固定 PR head SHA。

Claim 的 `reproduction_plan.command` 是显式 argv 列表。设置 `PARALLAX_ENABLE_REPRODUCTION=true` 才会执行，
服务使用禁止拉取镜像、无网络、非 root、只读源码/根文件系统、资源受限的 Docker 执行器。
应部署在专用 worker；普通 API 保持执行关闭。Subprocess 执行器只供可信夹具，不是安全沙箱。

### 三条平台的取舍（写在这里，免得被当成遗漏）

- **不引入用户注册体系**：单租户部署，API Key 足够。引入用户库会让网关变成第二个业务后端。
- **任务领取与恢复**：文件租约用于单 API worker；过期接管有竞态，多副本扩容前应替换协调与事件存储。
- **不把编排事件再存一份到网关**：上游已有可重放的事件总线，复制只会造出
  两个可能不一致的事实来源。运行详情直接给出上游的事件流地址。

---

## 9. 许可

Apache-2.0

