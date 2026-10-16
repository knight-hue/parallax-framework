# 贡献指南

感谢你有兴趣参与 Parallax。本文档说明如何搭建环境、跑测试、以及提交代码的流程。

## 1. 环境准备

需要 **Python 3.11+**。

```bat
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

跑测试：

```bat
.venv\Scripts\python.exe -m pytest
```

> 前端（Node >= 20）与网关（**必须是 JDK 21** + Maven >= 3.8）的构建命令，
> 以及本机没有全局工具时如何用仓内 `.toolchain/`，见 [../说明材料/本地构建.md](../说明材料/本地构建.md)。

**测试不需要网络、不需要 API key、也不会调用真实模型。** 这不是巧合——
`tests/conftest.py` 里有一个 autouse 夹具会强制清空模型凭据，
从结构上杜绝"某个测试意外发起付费请求"这类事故。

如果要手动验证真实的端到端流程，先在 `backend/.env` 里配置凭据（见 `.env.example`），然后：

```bat
.venv\Scripts\python.exe -m parallax.smoke              # 连通性与结构化输出自检
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --out runs\report.md
```

## 2. 代码规范

- **静态检查**：`ruff check .` 与 `ruff format --check .`
- **类型**：公共接口必须有类型标注；新增代码请保持 `from __future__ import annotations`
- **注释**：只注释"为什么这么做"，不注释"这行在做什么"。所有非显然的取舍都应在模块 docstring 里写清楚动机。
- **测试**：新机制、新分支、以及任何修过的 bug，都必须带测试。

> 关于测试的一条硬性要求：**修 bug 时先写出能复现该 bug 的测试，再改代码。**
> 本项目在 P0 阶段踩过一个教训——一个由工程故障（输出截断导致 Reader 大批失败）
> 造成的假象，差点被当成核心实验结论。测试是唯一能拦住这类错误的东西。

## 3. 提交信息

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>
```

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档 |
| `test` | 只改测试 |
| `refactor` | 重构，行为不变 |
| `perf` | 性能优化 |
| `build` / `ci` | 构建与 CI |
| `chore` | 其他 |

`scope` 用模块名，例如 `core`、`graph`、`service`、`eval`、`plugins`。

**破坏性变更**在 body 里以 `BREAKING CHANGE:` 开头说明。

## 4. 开发一个插件

框架本身不含任何场景知识，所有场景相关的东西都在插件里。要接入新场景，只需要实现三个对象：

- `EvidenceAdapter` —— 证据从哪来、怎么切成标准单元、按什么维度分区
- `ReaderPlugin` —— 盲读怎么问、怎么解析、怎么给 claim 打指纹
- `ClaimValidator`（可选）—— 入账前的否决权

详见 [README.md](README.md) 第 5 节「怎么写一个插件」。参考实现见 `backend/parallax/plugins/code_audit/`。

**提交插件前请自查两条契约**：

1. `build_messages()` 里**不得**出现本 Reader 分片之外的内容，也不得出现其他 Reader 的产出。
   这是盲读不被破坏的最后一道防线。
2. `parse()` 产出的指纹必须满足：确定性（同输入同输出）、可区分（不是所有 claim 都塌缩到同一个指纹）、
   语义正确（**同主体的相反主张必须共享指纹**，否则矛盾检测失效）。

## 5. Pull Request 流程

1. 从 `main` 切出分支：`feat/xxx` 或 `fix/xxx`
2. 保证 `pytest` 全绿、`ruff check .` 无告警
3. 在 PR 描述里说明：**改了什么、为什么这么改、怎么验证的**
4. 涉及机制行为的改动，请在描述里附上对照实验的前后数字（`python -m parallax.cli experiment`）

代码评审关注三件事，按优先级排序：

1. **正确性**——有没有破坏四条机制的前提（尤其是盲读隔离）
2. **可复现性**——新增的随机性或阈值是否可控、是否写进了 run manifest
3. **可读性**——非显然的取舍有没有在 docstring 里交代动机

## 6. 报告问题

- Bug：用 [Bug 报告模板](.github/ISSUE_TEMPLATE/bug_report.yml)
- 新插件 / 新场景：用 [功能建议模板](.github/ISSUE_TEMPLATE/feature_request.yml)
- 安全漏洞：**不要开公开 issue**，见 [SECURITY.md](SECURITY.md)

报告实验相关的 Bug 时，请附上 `eval/results/<run_id>/summary.md` 或运行报告——
框架承诺可复现，而没有原始数据的复现报告无法定位问题。

## 7. 许可证

本项目采用 [Apache-2.0](LICENSE)。提交贡献即表示你同意以同一许可证发布你的贡献。
