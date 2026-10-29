# 交接状态（新会话从这里开始）

> 读完这份再动手。旧对话上下文已很长，**不要重读历史，只信这份**。

---

## 0. 用户的三条硬约束

1. **不准自动提交/推送任何东西**（git commit / push 都要先问）。
2. 实验材料放 `exp-20261029-v4/`，**最终要上 GitHub，不要 gitignore 它**。
3. 每次报花费必须同时报 **本次 / 累计**。

---

## 1. 远端仓库状态（已完成，勿重复操作）

| 项 | 值 |
| --- | --- |
| 仓库 | `github.com/knight-hue/parallax-framework`（public） |
| 远端 HEAD | `8171575` → 后续 `docs` 提交 |
| 历史中 `eval/` | **0 次**（已 filter-branch 重写 + force push） |
| 现存 `eval/` 只含 3 个工程验收目录 | `java-platform`(26) `labs`(6) `acceptance`(7，排除 repair 下 5 个含代码的) |
| `.gitignore` | `eval/*` + 逐目录放行 + `eval/acceptance/20261020/repair/{claims,original-model-proposal,proposal,review.diff,verification}.json` |

**已被撤下并从历史删除的**：`eval/results/`、`eval/analysis/`、`eval/real/`、`eval/corpus/`（共 150 文件，含负结果与第三方代码报告）。

---

## 2. 本地数据（未丢，勿再"恢复"）

| 项 | 位置 |
| --- | --- |
| 全部实验产物 | 仓库内 `eval/`（305 文件，已 gitignore） |
| 完整目录备份 | `E:\tools\repo-backup-20261029-133948` |
| git bundle | `E:\tools\repo-backup-20261029-133948.bundle` |
| 远端旧快照 | `E:\tools\parallax-remote.tar.gz` |

---

## 3. 网络：`github.com:443` 不通，解法已就绪

- 根因：**DNS 污染**（解析到 `198.51.45.8` 等不可达地址）。不是 SNI 阻断。
- 可用 IP：`140.82.114.3` / `140.82.116.3` / `20.201.28.151` / `20.27.177.113` / `4.237.22.38` / `20.205.243.166`
- 解法：`E:\tools\e2e-work\github_proxy.py`（本地 CONNECT 代理，只听 127.0.0.1:8899，多 IP 故障切换）

```powershell
python E:\tools\e2e-work\github_proxy.py     # 先起代理
git -C <repo> -c http.proxy=http://127.0.0.1:8899 -c https.proxy=http://127.0.0.1:8899 push origin main
```

---

## 4. v4 实验计划（详见 `exp-20261029-v4/PLAN.md`）

5 个实验：E0 修度量(¥0) / E1 覆盖效应 / E2 对抗剂量 / E3 五臂消融 / E4 人工核实(¥0)。

**核心设计（必须保留）**：E1 每臂 `--budget-calls` 卡在 **读不完全部** 的位置（每片 40+ 文件需 7+ 批，预算只给 3–4 批）。**读得完时集中与分散必然打平**——这是此前所有实验失败的原因。

**判定写死在 PLAN.md，看到结果不许改。**

---

## 5. P0 进度（¥0，未完成）

| 项 | 状态 |
| --- | --- |
| 6 个切片目录 | ✅ 已生成（`p0-slices/S2..S6`，脚本 `backend/tools/build_slices.py`） |
| **可测性实测** | ✅ 见下 |
| 缺陷注入 | ❌ **未开始** |
| 验真测试 | ❌ 未开始 |

**可测性结论（关键）**：

| 切片 | 文件 | 可导入/失败 | 结论 |
| --- | ---: | --- | --- |
| S1 下单（`E:\tools\eval-corpus\slice_order_b`） | 43 | 全可导入 | ✅ 已有 9 缺陷、验真通过 |
| S4 会话缓存 | 26 | 13 / 0 | ✅ 可测 |
| S5 队列 | 9 | 3 / 0 | ✅ 太小（2 批读完） |
| S2 检索 / S3 编排 / S6 表现层 | 63/72/102 | 16/17/24 个失败 | ❌ 全部因 `agentscope` 未安装 |

**`agentscope` 安装代价**：60+ 个包，但主环境只有 `certifi 2026.7.22 → 2026.10.23` 一个版本变动，其余全是新增（主环境没有 openai/numpy/grpc）。**风险比我上轮判断的小**。
已建好独立环境 `backend/.venv-slices`（Python 3.13.5），**尚未安装**。

---

## 6. 未决决策（等用户拍板）

| 问题 | 选项 |
| --- | --- |
| agentscope | A：装进 `backend/.venv-slices`（主环境不动）→ S2/S3/S6 可用，6 个真实切片<br>B：不装 → 只有 2 个真实切片（S1 43 + S4+5 合并 35），需补合成语料 |
| 切片数量 | 原计划 6，实测真实可测只有 2–3 |

---

## 7. 账单真相（重要，别再报错数）

| 项 | 值 |
| --- | --- |
| 累计调用（有记录） | **1143 次** + 311 次未记 token |
| 输入 / 输出 tokens | **9,009,969 / 4,053,523** |
| **大头** | `real/b1`（urllib3）342 次 + `real/b1-anyio` 302 次 = **占输入 token 91%** |
| **单价** | **未知**。`deepseek-flash` 在 `api.deepseek.com`，我只能给区间（¥2.5 ~ ¥50），准确数字只能看 https://platform.deepseek.com/usage |
| v4 至今 | **¥0** |

**审计脚本**：`E:\tools\e2e-work\cost_audit.py`（零调用，随时可重跑）

---

## 8. 已确认的技术坑（别再踩）

1. **`match_claims` 有 bug**：把 `stance=not_a_defect` 也当成命中（d2 就是靠一条"确认并非缺陷"的 claim 命中的）。E0 要修。
2. **缺陷间距必须 ≥50 行**：d1/d2 相距 4 行，容差 25 行重叠，一条 claim 抢两个缺陷的配额。
3. **不设预算时集中读与分散读必然打平**。
4. **Reader 归属必须注入后实测**：`EvidenceUnit` id 含内容哈希，改一个字符切块归属就变。
5. **`git reset --hard` 会删掉被跟踪的工作区文件**（本轮丢过 261 个，靠 GitHub API tarball 抢回）。
6. **pytest 必须加 `-o addopts=""`**（pyproject 里 addopts 重复）。
7. `agentscope` / `qdrant_client` / `redis` / `sqlalchemy` / `aiosqlite` **主环境都没有**。

---

## 9. 下一步（从第 6 节决策之后开始）

1. 建独立环境装 agentscope
2. 为每个可用切片注入 8–10 个缺陷（间距 ≥50 行、在文件排序上均匀分布）
3. 写验真测试，**干净版全绿 + 注入版每个缺陷各自打红**
4. 进 P1（修 `match_claims`）
5. 进 P2（E1 Smoke，¥0.6 左右）
