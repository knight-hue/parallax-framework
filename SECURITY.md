# 安全策略

## 支持范围

目前只维护 `main` 分支上的最新版本。最终权限目标见 [PROJECT_GOALS.md](PROJECT_GOALS.md)，当前实现及运行边界见 [PROJECT_STATUS.md](PROJECT_STATUS.md) 和 [OPERATIONS.md](OPERATIONS.md)。

## 报告漏洞

**请勿通过公开 issue 报告安全漏洞。**

请通过以下方式私下联系维护者：

- 在 GitHub 上对该仓库发起 [Security Advisory](https://docs.github.com/en/code-security/security-advisories)
  （推荐，便于留痕与协作）
- 或发送邮件至项目维护者（见仓库主页联系方式）

报告时请尽量包含：

- 受影响的版本或提交
- 复现步骤（最小可复现的原则）
- 影响评估：能读到什么、能改到什么
- 如果方便，附上修复建议

我们会在 7 天内确认收到，并在评估后同步处理进度。

## 本项目的安全边界（部署前请务必了解）

Parallax 会**读取**你指定的代码仓库，并调用外部大模型 API。以下风险在部署时需要明确处理：

| 风险 | 说明 | 缓解方式 |
|---|---|---|
| **凭据泄露** | 模型 API key 通过环境变量注入 | `backend/.env` 已被 `.gitignore` 排除；镜像构建时通过 `.dockerignore` 排除；**不要**把 key 写进任何提交文件 |
| **被审查代码的越权访问** | 容器内进程能读到挂载进来的代码 | `docker-compose.yml` 中以 `:ro` **只读**方式挂载待审代码；容器以非 root 用户运行 |
| **代码内容外发** | 被审代码片段会作为提示词发给模型服务商 | 这是本工具的工作前提。**审计私有代码前，请确认你的组织允许将该代码发送给所选模型服务商**，或改用内网/本地模型端点（`PARALLAX_LLM_BASE_URL` 可指向任意 OpenAI 兼容端点） |
| **任意路径读取** | `POST /api/v1/audits` 接受服务端路径 | 当前按可信工作区使用，受控挂载与目录边界需独立限制。普通 API 不直接暴露公网，网关鉴权和路由白名单不能代替项目代码访问授权 |

## 已知的设计取舍

- 服务默认 CORS 为 `*`，便于本地前端联调。生产部署请通过 `create_app(cors_origins=[...])` 收紧。
- Python HTTP 服务配置 `PARALLAX_GATEWAY_INTERNAL_TOKEN` 后会校验内部凭据；它不等于用户/组织/项目授权。当前用户入口由 Java 网关管理，生产普通 API 需内部令牌且不直接公开。
- Java 将接管平台业务与逐资源权限，Python 保留审查机制；升级尚未完成，当前共享管理员入口不代表多组织隔离已实现。
