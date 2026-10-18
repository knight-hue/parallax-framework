# Parallax 项目状态与版本口径

> 更新日期：2026-10-18
> 总计划：`../说明材料/最终完成路线图.md`

## 当前定位

Parallax 是面向 AI 生成代码审查的独立证据装配与可验证审计框架。它不是另一个通用 Agent 编排器，而是在 LangGraph 等编排能力之上，约束证据分区、输出隔离、Claim 来源、覆盖率补检和争议处理。

## 已实现

- 盲读分区、受控冗余、输出隔离和新 Reader 补检；
- Claim 账本、规则化聚合、覆盖率矩阵、声誉和仲裁接口；
- 代码审查插件、CLI、FastAPI/SSE、前端工作台和 Java 平台网关；
- 合成语料和真实仓库评估基础设施；
- Docker、CI、开源治理和三栈测试体系。
- Receipt 运行留痕、独立性运行时画像、可证伪 Claim、离线反证协议和基础证据血缘图；
- 报告、服务摘要和前端已展示独立性、Receipt 与 Claim 来源链。
- 相关性预算已成为运行约束：超出证据重叠上限或独立支持下限时，Claim 不得自动进入高置信；
- verification Receipt、仲裁节点和 `arbitrated_by` 来源关系已进入报告与前端数据模型。
- 文件租约任务领取已接入服务层：共享 runs 卷上的多副本不会重复领取同一运行，失联 worker 的租约过期后可恢复。
- Git 来源支持安全 HTTPS URL、固定 commit SHA、浅克隆和 detached checkout；GitHub PR webhook 使用 HMAC 校验。
- Claim 可携带最小复现计划；可选 argv 复现执行器具备超时、输出上限、环境脱敏和仓库路径边界。
- 跨任务声誉已由 SQLite 服务存储持久化，更新使用短事务，重启后可恢复；存储协议可替换为 Postgres/Redis。
- 真实模型反证器已接入主链路，输出 `confirmed` / `refuted` / `insufficient_evidence` 三态，默认关闭并受证据长度限制。
- 自适应补检调度已接入覆盖率节点，按硬缺口、争议和孤证稳定排序，不读取 Reader 自然语言输出。
- 跨文件组合型缺陷已加入可复现语料生成器、ground truth 和完整性测试。
- CLI、HTTP 请求契约和 `/api/v1/meta` 均可显式查看或覆盖上述可选能力。

本次升级已通过 Python 全量测试（当前收集 245 项）、Ruff 和 `compileall`，前端 `typecheck`、ESLint
源码检查和生产构建也已通过。测试数量以当前 `pytest --collect-only -q` 输出为准。
真实模型反证已实现但默认关闭；自动修复和完整共同污染依赖图仍属于后续阶段；
复现执行需要显式开启并部署到隔离 worker。

## 当前证据边界

- `K*` 是采用的有效独立通道评估思想，不是 Parallax 首创；
- 同口径实验应报告 `K*/N`，不能直接比较补检轮数不同的裸 `K*`；
- 固定预算/固定召回率结果支持“独立性、覆盖和成本效率改善”；
- 真实仓库无 ground truth 时，只报告独立性、冗余、覆盖、成本和失败数；
- 多 Agent 一致不等于事实正确，系统当前不把一致性直接当作正确率。
- urllib3 / anyio 的现有产物来自历史 DeepSeek 运行；2026-10-17 按要求切换 OpenAI，
  但执行环境到 `api.openai.com` 的 DNS/HTTPS 连接失败，fastapi 冒烟运行已作废，
  当前没有可发布的 OpenAI 真实仓库统计。

## 仍未完成的生产能力

1. 将共同污染检测从画像升级为完整的跨 Reader 依赖图与运行时阻断；
2. 完成 Claim → 修复建议 → 人工批准 → 回归验证的闭环，默认不自动写回源码；
3. 在可联网且有明确 ground truth 的外部仓库环境中完成 OpenAI 重复实验；
4. 在真实隔离 worker、Postgres/Redis 和 Docker 运行环境中做部署验收。

详细验收标准、非目标和最终交付清单见总计划。
