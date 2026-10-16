# Parallax（视差）

[![CI](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/knight-hue/parallax-framework/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](backend/pyproject.toml)

> **抗从众的多智能体证据装配框架**
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

> **Parallax 的位置：当所有 Agent 都是同一个模型时，如何造出有效的独立通道？**
> **答案是信息分区，不是模型异构。**

Diversity Collapse 的作者给出的建议是 NGT（先独立产出、后群体综合）——方向与我们一致，
但他们只给了设计原则，没有给出可用的框架。

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

扩展点（ports/，只此三个 + 一个可选）
    EvidenceAdapter   证据从哪来、怎么切、按什么维度分区
    ReaderPlugin      怎么问、怎么解析、怎么给 claim 打指纹
    ClaimValidator    入账前的否决权（可选，可串联）
    Arbitrator        争议仲裁（可选，默认 NullArbitrator 不做裁决）
```

**领域模型**（`domain/models.py`）刻意保持场景无关：
`EvidenceUnit` / `Claim`（指纹 + 极性 + 源指针）/ `AgentReputation` / `CoverageMatrix` / `RunManifest`。

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

## 6. 当前状态

| 模块 | 状态 |
|---|---|
| 领域模型、三个扩展点协议 | ✅ 完成 |
| 盲读分区 / 账本 / 聚合器 / 覆盖率 / 声誉 | ✅ 完成 + 单测覆盖 |
| LangGraph 编排（含补检回环） | ✅ 完成 |
| 代码审查插件（RepoAdapter + CodeAuditReader） | ✅ 完成 |
| 模型客户端（DeepSeek / OpenAI 兼容）+ 离线假客户端 | ✅ 已连真实模型验证 |
| LLM 仲裁器 | ✅ 完成（默认关闭） |
| CLI + Markdown/JSON 报告 | ✅ 完成 |
| 对照实验台（7 个实验臂 + 5 项指标） | ✅ 完成，**已跑出真实数字** |
| 语料生成器（可复现，三档规模至 2712 行） | ✅ 完成 |
| **FastAPI 服务层 + SSE** | ✅ 完成，**已端到端联调**（含断线重放） |
| **Next.js 可视化前端** | ✅ 完成，构建与 lint 通过（明暗双色工作台） |
| **Java 薄网关** | ✅ 完成，**已端到端联调**（含鉴权、限流、SSE 透传、白名单） |
| Docker 部署（compose 三服务 + 可选 infra profile） | ✅ 完成，`compose config` 校验通过 |
| 开源治理（License / 贡献指南 / 安全策略 / CI 六项门禁） | ✅ 完成 |
| 测试 | ✅ **Python 144 项（约 5 秒）+ Java 10 项**，均不需网络与凭据 |
| 跨文件组合型缺陷（P0-4） | ⬜ 未开始——**唯一能测出召回差异的路径** |
| Redis / Qdrant 适配器 | ⬜ 未开始（当前用内存实现，compose 里已有可选 profile） |

> Docker 镜像的实际构建与容器冒烟在 CI 里执行；本地开发机未启动 Docker 守护进程，
> 因此本地只验证了 `docker compose config`。这一点不做"已验证"的表述。

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
│   ├─ ports/       扩展点协议（EvidenceAdapter / ReaderPlugin / ClaimValidator / Arbitrator）
│   ├─ core/        五模块机制实现
│   ├─ graph/       LangGraph 编排
│   ├─ infra/       模型客户端、仲裁器
│   ├─ plugins/     内置场景插件
│   ├─ service/     FastAPI + SSE 服务层
│   ├─ config.py    全部可调参数（无隐藏魔法数字）
│   ├─ engine.py    装配与执行
│   ├─ reporting.py 报告渲染
│   └─ cli.py       命令行入口
└─ tests/           144 项测试

frontend/                       Next.js 工作台（提交 / 实时事件流 / 账本 / 覆盖率矩阵）
gateway/                        Java 薄网关（鉴权 / 限流 / 熔断 / 白名单转发 / SSE 透传）
eval/corpus/                    可复现语料（三档规模）
eval/results/                   实验原始产物（每次运行一个目录）
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

:: ③ 薄网关（可选；需要网关的鉴权/限流时才起）
cd gateway
mvn spring-boot:run
::   起后把前端指向它：NEXT_PUBLIC_PARALLAX_API=http://localhost:8080 npm run build
```

或一把起：

```bat
docker compose --env-file backend/.env up -d                    :: api + web
docker compose --env-file backend/.env --profile gateway up -d  :: 再加网关
```

---

## 9. 许可

Apache-2.0
