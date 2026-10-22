# Parallax 项目状态

更新：2026-10-22。验收依据见 [ACCEPTANCE.md](ACCEPTANCE.md)，运行方式见 [OPERATIONS.md](OPERATIONS.md)。

最终目标已校准为：**Java 主导的智能代码审查与修复协作平台，以独立证据装配为审查引擎，平台统一使用 MySQL。** 目标与范围见 [PROJECT_GOALS.md](PROJECT_GOALS.md)，实施细节见 [JAVA_BACKEND_PLAN_V2.md](JAVA_BACKEND_PLAN_V2.md)。

Java 默认运行档和 Compose 已切为 MySQL，旧 PostgreSQL 作为显式回归/迁移入口保留；任务执行仍由 Python 管理。当前交付包含核心审查、人工审批后的隔离修复、协议适配和单机生产配置；本机服务链路已经实测，公网生产部署尚未发生。下面的历史验收不表示新的最终目标已完成。

## 新目标待完成范围

实施已开始：任务协议/生命周期、用户/组织/项目权限基础及 MySQL 运行档已落地；用户 JWT 禁止访问未关联项目的旧接口。已验证本机 MySQL 8.0.19 和 PostgreSQL → MySQL 离线复制，目标 8.4 尚待现场验收，尚未接管当前 runner。各模块记录见 [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md)。

| 范围 | 当前差距 |
| --- | --- |
| MySQL 平台数据 | 默认运行档、独立迁移、真库测试与离线复制已实现；已在 MySQL 8.4.0 上跑完 113 项单测 + 8 项真库集成，覆盖 V10/V11 新增表迁移与 19 张表离线复制；现场备份恢复与容量验收待完成 |
| Java 业务主体 | 用户/组织/项目权限、仓库/策略、集合分页、平台任务、报告产物及修复提案/审批/回归回执已实现；工作台已接入 Java 任务与审批入口，组织/项目管理 UI 待完善 |
| 可靠执行与额度 | 预占/结算/释放/对账、Outbox、Inbox、fencing/心跳/恢复与事件重放已实现；真实 RabbitMQ 4.1.4 上 3 项分发集成测试通过；Java MQ 发布/消费默认关闭，Python/工作台切换与多实例故障验收待完成 |
| 缓存与可观测 | 策略只读缓存、Redisson 可选重建锁、TTL/故障回源、真实 Redis 集成测试已通过；任务/Worker/审批/缓存/Outbox 指标已接入；Worker 已有可终止子进程模式和并发上限；容器/VM 隔离、Prometheus 采集、多实例故障、跨进程诊断及容量验收待完善 |
| 研发闭环 | Java 侧权限/审批/产物管理已实现；GitHub PR 签名、项目绑定、固定 commit 与 delivery 幂等已实现；GitLab、真实 webhook 现场验收、Java 缺陷样例和容器/VM 级隔离执行器仍待完成 |
| 后置扩展 | 报告安全分享已实现：128 位高熵短码、哈希存储、过期、撤销、访问上限和聚合统计；独立短链域名、热点容量与多实例验收待完成 |
| 原理与故障实验 | JVM、并发、Redis、Spring、秒杀、2PC/TCC 模拟已运行；Seata 2.6 AT/TCC 已对真实服务端与 MySQL 8.4 跑通 6 项；MySQL 原理实验（B+ 树、MVCC、隔离级别、锁与死锁、EXPLAIN）待补 |

2026-10-21 Worker 增量：平台模式已接入启动自动重放、周期续租、deadline 中断和退出取消；回执按 task/attempt 加锁，慢重放不阻塞其他任务心跳。执行中断或失联不以零用量退款，由 Java 保守恢复。Java↔Python 独立进程真实 HTTP 已通过，覆盖 STARTED、心跳、产物摘要、结算、重启去重、权限拒绝和取消失联；Python 全量 381 项、gateway 离线 Maven 测试通过。尚未据此证明真实 RabbitMQ、多实例或公网生产运行。

2026-10-22 基础设施验收增量：本机部署 MySQL 8.4.0、RabbitMQ 4.1.4 + Erlang OTP 27.3、Seata Server 2.6.0（均免安装于 E 盘，数据不落 C 盘）。在真 MySQL 8.4 与真 PostgreSQL 16 上跑完整 `verify`：单测 113、`MysqlPersistenceIT` 8 项全过；同时修复离线迁移表清单遗漏 V10/V11 三张表、以及 V10 种入 `system.webhook` 使空目标库判定永久失败两个缺陷。真 RabbitMQ 上 `RabbitDispatchIT` 3 项通过。`labs/seata` 6 项通过，并更正了此前“提交后 `undo_log` 不清理”的错误结论：RM 异步清理存在约 10 秒延迟。新增 `labs/mysql` 6 项（执行计划、MVCC 隔离级别、行锁超时 1205、死锁 1213）。新增 `gateway/tools/verify_backup_restore.py`，在真 MySQL 上完成 11 个迁移、22 张表的逻辑备份与恢复校验和比对。以上仍不构成多实例、容量或公网部署验收。

仅更新文档不会改变上述实现状态。阶段以升级方案 P0—P6、E1、L1 验收，历史数量不作为新增能力的测试结果。

## 已实现并验证

- 受控冗余分区、输出隔离、覆盖率补检、规则聚合、争议与仲裁、SQLite 跨任务声誉。
- Receipt、Claim 完整持久化、证据血缘和独立性画像；支持/反对分别计数，未裁决异见不结算声誉，重复裁决幂等。
- 对声明的传递上游分析共同摘要和工具结果，合并依赖通道；未解析血缘不计独立支持，支持不足或污染超限不得自动进入高置信。
- 真实模型反证与自适应补检，可配置启用；可选 Python AST 风险上下文分区。
- Claim → 模型或人工补丁计划 → diff 审阅 → 摘要批准 → Docker 基线失败 → 修复副本回归。审查版本与提案快照校验，原仓库永不自动写回。
- 框架无关的 Receipt JSONL/Callback 适配器和离线审计 CLI；外部生产者未声明隔离时显示 unknown。
- FastAPI/SSE、Next.js 同源认证代理与补丁工作台、Java 身份/配额/限流/运行记录/指标/回调。
- 强认证下 Java 异步响应不再被二次授权截断；非管理员无法生成或批准补丁。
- 生产 Compose 覆盖配置：内部令牌、强鉴权、数据库口令、最小端口、只读文件系统及资源上限。普通 API 的执行默认关闭。

## 2026-10-20 既有实现验收（Java 平台升级前）

| 验收 | 结果 |
| --- | --- |
| Python | 290 项，0 失败、0 跳过；Ruff/format/compileall 通过 |
| Java 离线 verify | 47 项单元/集成 + 12 项真实 PostgreSQL/Redis，全部通过 |
| 前端 | typecheck、ESLint、生产构建及 2 项认证 SSE 检查通过 |
| 完整本机链路 | 生产构建 web → 强认证 gateway → Python → PostgreSQL/Redis；SSE 重放、结果、Receipt、完成回调、指标通过 |
| 用户模型 | 兼容端点 gpt-6.1-sol，urllib3/util 三文件，5 臂 × 3 次重复，15/15 有效，Reader 失败 0 |
| 动态修复 | 真实模型发现并反证确认，操作员修订测试命令后批准；Docker 基线 exit 1，修复副本 exit 0 |
| Compose | 生产合并配置校验通过；未下载、未构建缺少的项目镜像 |

产物在 `eval/acceptance/20261020` 和 `eval/real/openai-20261020-accepted`。本机完整链路使用确定性假模型；真实模型实验和修复另有独立产物，二者不能混称。

## 能力边界

1. AST 导入、配置键、部分权限装饰器关联只是有限语法近似；完整动态调用图、数据流、权限流与共享状态证明尚未实现。
2. 共同污染检测依赖输入声明的血缘，不能发现未披露来源；Receipt 不是密码学远程证明。
3. high_confidence 表示支持结构达标，regression_passed 表示指定测试通过，均不等于完整事实证明。
4. 真实源码子集无人工 ground truth；precision/recall 未知。Claim 包含“并非缺陷”的反方观察，不能当作漏洞数。
5. 输出指纹 K*、仅产出者归一化比例、按证据分区计算的画像是不同量。补齐分母不能自动消除预算偏差；本批 n=3 不证明准确率或机制收益稳定。
6. 文件租约供单 API worker 部署；过期接管存在竞态，事件总线不是跨节点消息日志。不承诺任意副本、跨节点容灾或 exactly-once。
7. Docker 复现使用既有缓存镜像展示隔离机制，不是推荐生产镜像；正式 worker 需要预装运行时的镜像与专用隔离宿主。
8. 项目 app/正式 worker 镜像、公网服务器/TLS/域名、现场备份恢复与持续压测尚未交付。生产配置不能等同于已经上线。

创新定位是代码审查的系统组合创新；信息分区、先独立后共识、K* 不是本项目理论首创。
