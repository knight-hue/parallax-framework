# 实验目录 exp-20261029-v4

本目录存放 **2026-10-29 起执行的 v4 实验**的全部材料：计划、切片、注入脚本产物、逐次运行结果、分析结论。

> 本目录**随主仓库入库**（用户要求，`.gitignore` 不再整目录忽略）。
> 但逐条 claim 明细含被审代码的原文引用与推理过程，部分运行涉及第三方开源项目，对外发布前需逐份复核。
>
> **唯一交接文档：`STATE.md`。** 判定标准见 `PLAN.md`，进度与门禁结论见 `PROGRESS.md`，花费见 `LEDGER.md`。

---

## 目录结构

| 路径 | 内容 | 产生阶段 |
| --- | --- | --- |
| `PLAN.md` | 计划书 v4（定版） | — |
| `LEDGER.md` | **预算台账**：每阶段实际花费与累计 | 全程更新 |
| `PROGRESS.md` | 进度与每阶段的门禁结论 | 全程更新 |
| `p0-slices/` | 切片与注入产物（`repo/`、`tests_verify/`、`ground_truth.json`） | P0 |
| `p1-metrics/` | 度量修正与历史重算对照表 | P1 |
| `p2-smoke/` | E1 的管线验证运行 | P2 |
| `p3-e1-coverage/` | E1：6 切片 × 2 臂 | P3 |
| `p4-smoke/` | E2 的污染注入验证 | P4 |
| `p5-e2-adversarial/` | E2：4 档剂量 | P5 |
| `p6-smoke/` | E3 的管线验证 | P6 |
| `p7-e3-ablation/` | E3：5 臂 × 2 切片 | P7 |
| `p8-e4-verification/` | E4：逐条人工核实结果 | P8 |
| `analysis/` | 最终分析：配对检验、结论表 | P8 之后 |

---

## 运行约定

```powershell
# 所有实验都用仓库内的 venv
$py = 'backend\.venv\Scripts\python.exe'

# 关键环境变量（历史踩过坑：不设会撞默认的 8000 token 输出上限）
$env:PARALLAX_LLM_MAX_OUTPUT_TOKENS = '32000'
$env:PARALLAX_LLM_TIMEOUT_S = '180'
$env:PARALLAX_LLM_MAX_RETRIES = '5'
```

**每次运行必须确认三件事**（Smoke 阶段强制）：

1. 配置快照里的 `llm_calls` 符合预期（预算生效）
2. `readers_failed == 0`
3. `stop_reason` 不是预算耗尽以外的原因

---

## 当前状态

进度只维护一处：见 [PROGRESS.md](PROGRESS.md)；花费只维护一处：见 [LEDGER.md](LEDGER.md)；接手指南见 [STATE.md](STATE.md)。本 README 不再复制状态表，避免三处数字打架。
