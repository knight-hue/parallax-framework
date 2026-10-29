# 2026-10-20 本机验收记录

范围声明：本文记录 Java 平台升级前的既有实现与原始产物，保留 PostgreSQL 等当时环境。最终目标见 [PROJECT_GOALS.md](PROJECT_GOALS.md)。本文不证明 MySQL 迁移、Java 业务接管、分布式执行或新增原理实验已经通过验收。

使用已有 .venv、Node、JDK、Maven、Docker 和缓存镜像；本轮没有下载安装依赖、工具或镜像，没有使用 DeepSeek。一级目录 .github 未改动。

## 软件门禁

- Python：290 passed，0 skipped；Ruff check/format、compileall 通过。
- Java：离线 Maven verify；47 项单元/集成、真实 PostgreSQL 5 项、Redis 7 项，0 失败、0 跳过。
- 前端：ESLint、TypeScript、Next.js 生产构建通过；Node 原生测试验证认证 SSE、Last-Event-ID、UTF-8/CRLF 分块和累计消息大小上限，共 2 项。
- Docker：生产 Compose 合并配置检查通过。只使用已有镜像，不拉取缺少的 app 镜像。
- 仓库既有变异审计：Python 20/20、网关离线 2/2 均被回归测试检出。

机器计数：[test-totals.json](../eval/acceptance/20261020/test-totals.json)。

## 完整本机链路

运行生产 Next.js 产物、实际 Java jar、Uvicorn、独立 PostgreSQL/Redis 临时容器，全部绑定回环地址。随机临时密钥、认证启用；验证匿名拒绝、绕过网关拒绝、API Key 提交、SSE 终态与重放、结果/Receipt、管理员修复权限、真实完成回调入库、受保护指标。结束清理自身进程和容器。

编排使用确定性假模型，验证平台通信而不调用外网模型。该链路发现并修复 Spring Security 在 ASYNC dispatch 丢失初始请求认证后截断响应的问题；新增强认证回归保护管理员及普通用户路径。

产物：[native-stack.json](../eval/acceptance/20261020/native-stack.json)。脚本：backend/tools/verify_native_stack.py。

## 用户模型重复实验

用户配置的 OpenAI 兼容端点、模型别名 gpt-6.1-sol；显式 reasoning_effort=low 已获该端点实际接受。该名称不构成官方型号证明。

输入为缓存 urllib3/util 的 __init__.py、connection.py、proxy.py，不是完整 urllib3。固定 seed=0，3 Reader，5 臂各重复 3 次，15/15 有效、Reader 失败 0。保存生效配置、版本、输入哈希；implementation.zip 冻结当时实现，后续修正不改写旧源码快照。

| 臂 | 输出 K* 均值±样本标准差 | K*/已分配 Reader | 输入 tokens 均值 |
| --- | ---: | ---: | ---: |
| baseline_shared | 0.60 ± 1.04 | 20.0% | 10959 |
| sharded_shared | 1.53 ± 0.46 | 51.1% | 12951 |
| sharded_blind | 1.93 ± 0.12 | 64.4% | 17705 |
| blind_no_coverage | 0.67 ± 0.58 | 22.2% | 7717 |
| blind_full | 1.93 ± 0.12 | 64.4% | 17705 |

解释限制：

- 无 ground truth，precision/recall 为 N/A；Claim 包括“并非缺陷”的反方观察，不能当作漏洞数。
- 原始 agent_count 仅计产出 Claim 的 Reader；analysis.json 根据报告实际分区 Reader 数补算分母，本批均为 3。空结果 K*=0 表示无输出结构可测，不等于源码无缺陷。
- 输出指纹 K* 与证据分区画像不同，不能由输出差异证明认知独立或正确。
- sharded_shared 与 sharded_blind 分区/轮次相同，仅改同伴输出可见性，但实际 tokens 不同；不宣称相同总成本。
- 所有有效臂最终只执行 1 轮；本批未验证多轮补检收益。n=3、同一小子集不足以证明统计稳定性或准确率提升。
- 原报告早于最终极性元数据修复，部分 DENY 的 independent_support 误为 0；保留原件和源码快照，不拿错误字段做收益结论。
- 较早的大上下文/默认推理尝试发生超时并中断，保存在 openai-20261020 / openai-20261020-small；不混入有效重复统计。

原始产物（`acceptance.json` / `analysis.json`）与历史 `variance.md` 只保留在本地，未随仓库分发；
  其定性结论不能当作因果效果证据。

## 真实模型到修复回归

支付分摊最小契约示例：除数为零应返回 None，原实现直接除法。真实模型提出 Claim，独立反证调用 confirmed；模型生成精确补丁和失败测试。

审阅发现原测试启动命令的导入路径问题，操作员创建新提案，修正启动方式、增加非零输入断言后才批准。Docker 无网络、只读源码/根文件系统、非 root、资源上限、禁止拉取；原副本出现指定 AssertionError，exit 1，修复副本同一测试 exit 0，状态 regression_passed。原始源码未改变，补丁未写回。

缓存 ibmcom/db2:latest 的 Python 3.6.8 仅供标准库夹具展示隔离机制，不是项目生产运行镜像；后端要求 Python ≥3.11。容器隔离不能替代敌对租户的专用 VM。

证据：[verification.json](../eval/acceptance/20261020/repair/verification.json)、[review.diff](../eval/acceptance/20261020/repair/review.diff)，同目录保留模型原提案、审阅后提案、Claim、manifest、源码摘要。

## 现场交付边界

未发生公网部署，未构建缺少的项目 app/正式 worker 镜像。域名、TLS、服务器、现场备份恢复、持续压测仍需实际环境。完整动态数据流/权限流分析和跨节点任务协调未实现。生产按单 API worker 运行，普通 API 执行开关关闭，详见 OPERATIONS.md。
