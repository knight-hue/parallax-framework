# 对照实验结果

生成时间：2026-10-20T10:56:00+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- 生效配置：adaptive_scheduling=False；git_revision=de7410b66340b3b5b123c2b0bd72a1a0b7e85ae0；group_depth=2；implementation_sha256=f0fa93a989a77709ff439012bdeeb3ef57ab2d2293f302d405ec5cc6955a1e3b；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_files=3；max_llm_calls=24；max_output_tokens=10000；max_rounds=1；max_tokens=0；min_independent_support=2；model=gpt-6.1-sol；readers=3；redundancy=3；repo=util；seed=0；support_threshold=2；visibility=shared


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* / Agent 数 | 独立通道占比 | 覆盖率 | 轮次 | 调用 | Reader 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | N/A | N/A | 0% | 0.0 / 0 | 0% | 0% | 1 | 3 | 3 |

> **召回率与精确率为 `N/A` 说明该任务没有 ground truth。** 这不会削弱 K\* 的价值——它由 Agent 之间的**重叠矩阵**算出，不需要知道哪条结论是对的，因此是这类无标注任务上唯一仍可测的核心指标。

## 实验臂说明

- `baseline_shared`：传统多智能体：所有人看全部证据 + 可见彼此结论
- `sharded_shared`：公平对照：分片大小与实验组完全相同，但可见彼此结论（隔离出「共享」单独的效果）
- `sharded_blind`：分片与 sharded_shared 相同且均为单轮，只隔离同伴输出可见性
- `no_peers_all_evidence`：所有人看全部证据，但看不到彼此结论
- `blind_no_coverage`：严格互斥分区，关闭补检（redundancy=1, max_rounds=1）
- `blind_full`：本框架完整机制：受控冗余分区 + 覆盖率驱动补检
- `budget_shared`：固定预算对照：每 Reader 预算相同，但所有人读同样的 K 个维度并共享结论
- `budget_blind`：固定预算实验组：每 Reader 预算相同，各读不同的维度（联合覆盖 n 倍）

## 明细

### `baseline_shared`

- 耗时 270.39s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）｜失败 3｜schema 重试 0｜Reader 失败 3
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 0（独立指纹 0｜冗余率 0%｜未匹配 0）
- 命中情况：**无 ground truth，跳过**（召回/精确不适用）
- ⚠️ 错误：Reader failures: 3
