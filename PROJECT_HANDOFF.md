# Parallax 当前开发交接

更新：2026-10-20。

以 [PROJECT_STATUS.md](PROJECT_STATUS.md)、[ACCEPTANCE.md](ACCEPTANCE.md) 和 [OPERATIONS.md](OPERATIONS.md) 为当前事实来源。`../说明材料/开发交接记录-2026-10-17.md` 保留历史记录，不代表当前状态。

本轮完成传递共同上游约束、隔离修复审批回归、Receipt 开放适配、可选 AST 风险上下文、认证前端代理和生产配置，并使用本机工具、缓存镜像和用户配置的兼容模型实测。密钥仅在忽略的 `backend/.env`，示例文件不保存密钥。

验收入口：

- Python：已有 .venv 执行 pytest，当前 290 项；Ruff/format/compileall。
- 前端：已有依赖下 lint、typecheck、test:sse、build。
- 网关：mvn -o verify；真实 PG/Redis 使用本地缓存镜像 override 且禁止拉取。
- 完整服务链路：`backend/tools/verify_native_stack.py`，仅回环端口与自身临时资源，退出清理。
- 真实模型重复实验：`backend/tools/verify_real_model.py`，不得把失败目录混入有效统计。
- 真实模型修复：`backend/tools/verify_repair_flow.py`，先生成并审阅，--revise-plan 可修订，--approve 必须传确切摘要。
- 证据整理：`backend/tools/export_acceptance.py`，无模型调用，不导出服务日志或访问令牌。

现场交付需要部署方提供服务器、TLS 入口、正式运行镜像及工作负载。单 API worker 是当前支持的拓扑；完整动态语义分析与跨节点协调未实现。不得将本机验收说成公网生产已上线。
