# Parallax 当前开发交接

更新：2026-10-21。

最终目标以 [PROJECT_GOALS.md](PROJECT_GOALS.md) 为准，技术执行以 [JAVA_BACKEND_PLAN_V2.md](JAVA_BACKEND_PLAN_V2.md) 为准；[PROJECT_STATUS.md](PROJECT_STATUS.md)、[ACCEPTANCE.md](ACCEPTANCE.md) 和 [OPERATIONS.md](OPERATIONS.md) 分别记录当前事实、既有验收和当前运行方式。`../说明材料/开发交接记录-2026-10-17.md` 保留历史记录，不代表当前状态。

## 当前接手方向

Java 从网关升级为平台业务主体；平台统一使用 MySQL；Python 保留独立证据装配和隔离执行。秒杀与 XA/TCC/Seata 放入独立实验，报告安全分享后置。不得沿用“Java 只做薄网关”“不需要组织用户体系”的旧范围限制。

已提交任务协议与用户/组织/项目权限基础。MySQL 默认运行档、独立 Flyway、旧库离线迁移工具及真库检查已实现，见 gateway/MYSQL_OPERATIONS.md；本机验证版本是 8.0.19，目标 8.4 待验收。继续实现仓库/策略、平台任务与原子预算，再接管可靠执行。完整阶段状态见 IMPLEMENTATION_LOG.md。

以下保留既有审查链路的验收入口；不能据此宣称新 Java 平台已完成。

此前已完成传递共同上游约束、隔离修复审批回归、Receipt 开放适配、可选 AST 风险上下文、认证前端代理和生产配置，并使用本机工具、缓存镜像和用户配置的兼容模型实测。密钥仅在忽略的 `backend/.env`，示例文件不保存密钥。

验收入口：

- Python：已有 .venv 执行 pytest，当前 312 项；Ruff/format/compileall。
- 前端：已有依赖下 lint、typecheck、test:sse、build。
- 网关：mvn -o verify；真实 PG/Redis 使用本地缓存镜像 override 且禁止拉取。
- 完整服务链路：`backend/tools/verify_native_stack.py`，显式使用 legacy-postgres，仅回环端口与自身临时资源，退出清理。
- 真实模型重复实验：`backend/tools/verify_real_model.py`，不得把失败目录混入有效统计。
- 真实模型修复：`backend/tools/verify_repair_flow.py`，先生成并审阅，--revise-plan 可修订，--approve 必须传确切摘要。
- 证据整理：`backend/tools/export_acceptance.py`，无模型调用，不导出服务日志或访问令牌。

现场交付需要部署方提供服务器、TLS 入口、正式运行镜像及工作负载。单 API worker 是当前支持的拓扑；完整动态语义分析与跨节点协调未实现。不得将本机验收说成公网生产已上线。
