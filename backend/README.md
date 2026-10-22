# Parallax Python 审查引擎

智能代码审查与修复协作平台的独立证据装配引擎，保留可插拔框架、CLI 和离线使用方式。平台目标由 Java 管理组织权限、任务、预算和审批，Python 负责分区、独立取证、反证与聚合；隔离执行由专用 Worker 承接。

最终职责见 [PROJECT_GOALS.md](../PROJECT_GOALS.md)。当前 Python 服务仍维护任务和 SSE，向平台模式迁移的协议与状态权威尚待实现，不能把目标架构当作当前实现。

完整介绍、机制说明与实验结果见仓库根目录的 [README.md](../README.md) 与
[说明材料/P0-验证结果.md](../../说明材料/P0-验证结果.md)。

## 快速开始

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"

:: 跑测试（不需要网络，也不会调用真实模型）
.venv\Scripts\python.exe -m pytest

:: 离线自检：只加载证据并分区，不调用模型
.venv\Scripts\python.exe -m parallax.cli audit .\parallax --dry-run
```

## 两个入口

| 命令 | 用途 |
| --- | --- |
| `python -m parallax.cli audit <repo>` | 命令行审查一个仓库 |
| `python -m parallax.cli experiment` | 跑对照实验（对照组 vs 实验组 + 消融） |
| `python -m parallax.smoke` | 连通性与结构化输出自检 |
| `parallax-serve` | 启动 HTTP 服务（FastAPI + SSE） |

## 目录结构

```text
parallax/
├─ domain/    领域模型与枚举（场景无关）
├─ ports/     扩展点协议：EvidenceAdapter / ReaderPlugin / ClaimValidator / Falsifier / Arbitrator
├─ core/      六个机制模块：partitioning / reader_pool / ledger / aggregator / coverage / independence
├─ graph/     LangGraph 编排
├─ infra/     模型客户端、仲裁器
├─ plugins/   内置场景插件（code_audit）
├─ service/   HTTP 服务层（FastAPI + SSE）
├─ eval/      评测指标、对照实验、语料生成器
├─ engine.py  装配与执行
├─ reporting.py / cli.py
```
