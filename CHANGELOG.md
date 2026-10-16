# 更新日志

本文件记录本项目的显著变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- 跨文件组合型缺陷的评测语料（检验聚合层的证据装配能力）
- Redis / Qdrant 适配器（当前为内存实现）
- 把有效独立通道数 K\\* 作为运行时指标对外暴露

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

**工程与治理**

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
- 服务层的运行 id 与引擎自派生的 id 不一致 → 报告标题里的 id 在运行记录里查不到；
  改为引擎接受调用方传入的 run_id（不传时仍按配置派生，保证 CLI / 实验可复现）
- 用量快照只读编排层那本账 → 报告出现"12 次调用、0 token"；改为合并模型客户端的
  token 计数，同时**保持 `calls` 语义不变**（两本账合一会让已发布的实验数字整体翻倍）
