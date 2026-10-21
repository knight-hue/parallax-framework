# Java 平台升级实施记录

## P0.1 任务协议与生命周期

状态：已实现并验证，尚未接管旧 HTTP/file runner。

- Java/Python 共用 v1 任务/事件 JSON 样例与严格字段校验。
- 固定提交、策略版本、资源归属、预算、期限、attempt/fencing 和用量溢出约束。
- 状态机保留取消竞态和终态不重开；重试、事件去重和 fencing 的原子持久化由后续协调器实现，协议解析不冒充可靠执行。
- 验证：Java WorkerProtocolTest 9 项；Python test_worker_protocol.py 22 项及 Ruff 通过。
- 改动前 Java 离线 verify 47 项通过；该基线未运行真实数据库 IT。

当前资源核查：本机有 MySQL 8.0.19、Java 21、Maven、Node、Docker；未找到 MySQL Connector/J、Flyway MySQL、Redisson、RabbitMQ Java 客户端的已有 jar。目标 MySQL 8.4 尚未在本机发现。未下载资源，不能以现有 PostgreSQL/H2 证明 MySQL 完成。

下一步：平台用户/组织/项目权限与 MySQL 运行档。最终全项目完成情况见 PROJECT_STATUS.md，单模块完成不代表最终目标完成。

## 用户、组织与项目权限基础

状态：已实现，当前 PostgreSQL/H2 迁移基线；尚未管理旧审查任务的项目归属。

- 管理员创建/停用用户、BCrypt 密码、用户 JWT 与当前有效状态检查。
- 组织 OWNER/MAINTAINER/REVIEWER/VIEWER，项目资源授权、成员撤销即时生效、保护唯一所有者及事务内操作审计。
- 用户 JWT 暂时禁止访问没有项目归属的旧接口；旧管理员/API Key 兼容，不能冒充平台用户。
- 真 HTTP 权限测试 5 项通过；Java 全量离线 verify 61 项通过，未运行数据库 IT。Python 全量 312 项通过。
- API 契约及边界见 gateway/PLATFORM_API.md。当前成员权限以组织为范围，尚无单项目覆盖和管理 UI。
- 用户已授权仅由 Maven 补齐必需依赖及传递依赖；不下载工具、数据库安装包或镜像。已获取 MySQL Connector/J 9.7.0。

## MySQL 运行档与旧库离线迁移

状态：已实现并通过本机真库检查；目标 MySQL 8.4 与生产恢复现场验收未完成。

- 默认 mysql 运行档、独立 InnoDB/utf8mb4/UTC DATETIME(6) Flyway、显式外键；旧历史保持不变，legacy-postgres 可回归。
- Compose 使用独立 mysql-data，保留 postgres-data；应用与 root 分离口令。没有拉取或构建镜像。
- 停写迁移工具按白名单复制十张表，目标本地事务、源只读、逐字段数量/SHA-256 核对，拒绝非空目标与错误数据。
- 本机现有 MySQL 8.0.19 + 缓存 PostgreSQL 16.15 完成真库迁移；所有表有数据，含中文/emoji、微秒、空值、用量和外键关联，篡改被拒绝。
- Java 全量 61 项 + 真实 PostgreSQL/Redis 12 项通过；独立 MySQL 4 项通过（同时重跑身份/协议 14 项）。Ruff、Compose 生产合并配置和 diff 检查通过。
- 运行与回退步骤：gateway/MYSQL_OPERATIONS.md；脱敏验收摘要：eval/java-platform/mysql-runtime.json。Python 既有全量 312 项未在本模块重复运行，仅变更旧验收脚本的显式 profile。

下一模块：受控仓库登记、不可变策略版本，随后平台任务/原子预算/Outbox。

## 仓库登记与不可变策略版本

状态：已实现，尚未连接新平台 Worker 执行。

- 项目级仓库登记、精确 HTTPS 域名白名单与路径检查；不接收客户端宿主路径，不执行网络拉取。
- 不可变策略 ID/版本/摘要，项目锁 + 当前读分配版本；读取时验证摘要，避免静默修改任务依据。
- 仓库和策略读写均核对实时组织角色及项目归属，创建与操作审计同事务。
- 所有新平台集合（含原身份集合）改为 UUID 游标分页，limit 1..100。
- 新增 5 项 HTTP/业务测试通过；MySQL 真库增加 8 次并发发布验证；MySQL 5 项、身份/策略/协议 19 项检查通过。
- 提交前 Java 全量离线 verify：66 项通过；本轮未重复运行 Redis IT（上模块 12 项 PG/Redis 检查已通过）。
- 离线复制工具扩充至 12 张表，源库先用 legacy-postgres 升级至 V5，再迁移至新空库；真 PostgreSQL → MySQL 核对通过。
- 仓库网络取回的 DNS/重定向/凭据边界、策略传入引擎和工作台均留在执行集成阶段，不以登记接口冒充完成审查。

## 平台任务、预算预占与事务 Outbox

状态：提交链路已实现并验证；消息发布和 Worker 接管尚未连接。

- 系统管理员配置累计 Token 额度，租户不能自行授予；成员按项目角色提交/查看任务。
- 账户行锁 + 条件更新，预算预占/任务/RESERVE 流水/Outbox/操作审计同事务；固定仓库、提交与策略 ID，复合外键防止跨项目关联。
- 按项目/用户/请求键幂等；输入冲突返回 409，额度耗尽返回 429，取消后重放不会重新执行或预占。
- 排队取消只退款一次并使待派发消息失效；额度对账比较任务预占与结算流水，报告差异，不修改历史。
- Trace ID 限制字符和长度，避免外部非法头污染日志或破坏任务协议。
- Java 全量 72 项、真实 MySQL 6 项通过；包含 20 请求争抢额度、8 次幂等重试、重复取消、事务回滚、权限及对账篡改检测。MySQL 真库执行同类并发检查。
- 真实 PostgreSQL → MySQL 复制扩展至 16 张非空表，预算/任务/流水/Outbox 逐字段核对通过。源/目标均需先升级至 V6。
- 本模块不运行模型，也没有发布队列消息；运行中结算、取消、失联处理、Inbox/事件重放由下一协调模块实现。

## Worker 协调、Inbox 与持久事件

状态：数据库协调服务和 HTTP 入口已实现；后台派发/扫描及 Python 适配尚未连接。

- STARTED 作为执行授权，使用服务器租约；事件要求当前 attempt/fence、连续序号、单调累计用量及预算上限，拒绝终态重开和过期心跳。
- 事件 ID + 内容摘要去重，Inbox/事件、状态和终态结算在同一事务；多个重复完成回调只结算一次。
- 取消与成功允许实际竞态；取消后心跳不续期，未开工 Worker 不得上报进度、成功或消费。
- 未获 STARTED 的派发可最多 3 次尝试并增加 fence；已开工失联则以完整预占保守结算，不立即重新派发。记录费用不确定原因，不能当作真实模型账单。
- 系统转换与 Worker 回执共用 MySQL 事件日志，项目权限下按数据库 ID 分页重放，不依赖进程内队列。
- Java 全量 82 项、真实 MySQL 7 项通过；新增 10 项协调测试，真库覆盖不同组织并发开工、重复完成及额度核对。
- 真 PostgreSQL → MySQL 迁移扩展至 V7/17 张非空表，逐字段核对通过。脱敏摘要：eval/java-platform/worker-coordinator.json。
- 已按授权用 Maven 补齐 Spring AMQP 3.2.12、RabbitMQ Java client 5.25.0、Redisson 3.52.0，尚未修改主 POM 或声明其运行验收完成。

## 可靠消息派发与恢复接线

状态：Java 派发运行代码、后台恢复与 HTTP 桥已实现，默认关闭；Python 平台 Worker 接入和真实 RabbitMQ 验收待完成。

- 事务 Outbox 使用短事务领取、30 秒租约、随机领取令牌、过期重领和发布失败退避；broker I/O 不持有数据库事务。
- 真实 MySQL 并发测试发现默认 RR 下状态索引更新发生死锁，领取事务改为 READ COMMITTED 后通过；过期领取者不能覆盖新领取者。
- RabbitMQ 持久消息、mandatory 路由返回、关联确认及超时；quorum 队列、手动 ACK、有限重投和至少一次死信转移；后台分批发布和失联恢复。
- 固定私网 Worker HTTP 地址、内部令牌、禁止跳转；2xx/安全重复或过期确认，临时错误重投，永久错误进入死信。当前不能开启派发替代尚未实现的 Python 接口。
- Java 全量 92 项、真实 MySQL 8 项通过；真 PostgreSQL → MySQL V7/17 张非空表复制核验通过。Ruff/format、diff 检查通过。
- RabbitMQ 的确认/返回/超时和 HTTP ACK 分类有 5 项测试，broker/channel 为 mock；另有 3 项真实 broker IT 已编译，未运行。本机无 RabbitMQ 缓存镜像，验收脚本预检查明确退出，无下载。
- 运行与故障处理：gateway/DISPATCH_OPERATIONS.md；脱敏记录：eval/java-platform/reliable-dispatch.json。未证明 RabbitMQ 集群容错、容量或生产上线。

## 不可变执行快照与 Worker 持久通信基础

状态：已实现并验证；尚未连接实际引擎执行，派发仍默认关闭。

- Java 内部执行快照核对当前 attempt/fence、组织/项目/仓库/策略、提交、预算和有效租约；重新校验仓库白名单与策略摘要。快照查询不授予执行权，只有 STARTED 回执可以授权。
- Python 固定平台地址客户端禁止跳转，验证快照摘要和回执，临时错误可重试；内部令牌不通过租户 JWT 替代。
- SQLite WAL/FULL 本地投递日志先落盘后确认；每 attempt 仅一次本地启动领取，回执 ID/序号/用量持久化，重启不重启已领取任务。跨节点仍依赖 Java fencing。
- Java 全量 94 项、本地 MySQL 8 项及 PostgreSQL → MySQL 17 张非空表核对通过；Python 全量 343 项通过，Ruff/format 和 diff 检查通过。
- 新增快照 HTTP 测试 2 项、客户端测试 22 项、持久日志测试 9 项；快照测试使用测试数据库，不能表述为目标 MySQL 8.4 现场验收。
- 真实 RabbitMQ、实际 Worker 执行/产物接入、多实例故障和公网部署尚未完成。
