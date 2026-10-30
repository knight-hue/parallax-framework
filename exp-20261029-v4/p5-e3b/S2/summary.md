# 对照实验结果

生成时间：2026-10-30T14:43:18+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=False；git_revision=f19c5f02267b88f458788308eabeefdb32a7312b；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=2；seed=0；semantic_partitioning=False；support_threshold=2；task=S2；visibility=blind
- adaptive_scheduling=False；equal_exposure=False；git_revision=f19c5f02267b88f458788308eabeefdb32a7312b；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=2；seed=0；semantic_partitioning=False；support_threshold=2；task=S2；visibility=shared


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `sharded_shared` | 80% (8/10) | 24% | 39% | 2.1677 / 3 | 72% | 33% | 1 | 12 | 0 | 20/20/20 → 合并 30 | OK |
| `sharded_blind` | 80% (8/10) | 18% | 16% | 2.7033 / 3 | 90% | 46% | 1 | 12 | 0 | 20/20/20 → 合并 30 | OK |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-tie-break-lost | d2-price-cap-boundary | d3-zero-score-candidates | d4-context-ratios-swapped | d5-primary-sku-is-last | d6-top-k-validation-dropped | d7-budget-tier-boundary | d8-budget-remaining-negative | d9-budget-zero-not-disabled | d10-negative-charge-accepted | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `sharded_shared` | 2 | 2 | 2 | 2 | 2 | 2 | ✗ | 2 | 2 | ✗ | 0 | 2 |
| `sharded_blind` | ✗ | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 2 | ✗ | 5 | 2 |

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

### `sharded_shared`

- 耗时 169.73s｜LLM 调用 12 次（输入 75161 / 输出 33267 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 72.3%
- 每 Reader 实读单元：reader-r0-0=20、reader-r0-1=20、reader-r0-2=20｜合并去重 30
- claim 总数 85（独立指纹 52｜冗余率 39%｜未匹配 65）
- 命中 8/10 个植入缺陷｜命中同一缺陷的重复 claim 12 条
- 漏检：d7-budget-tier-boundary, d10-negative-charge-accepted

### `sharded_blind`

- 耗时 54.82s｜LLM 调用 12 次（输入 61818 / 输出 28567 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 90.1%
- 每 Reader 实读单元：reader-r0-0=20、reader-r0-1=20、reader-r0-2=20｜合并去重 30
- claim 总数 85（独立指纹 71｜冗余率 16%｜未匹配 70）
- 命中 8/10 个植入缺陷｜命中同一缺陷的重复 claim 7 条
- 漏检：d1-tie-break-lost, d10-negative-charge-accepted
