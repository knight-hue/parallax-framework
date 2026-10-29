# 对照实验结果

生成时间：2026-10-29T16:11:05+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=True；git_revision=f70c541549b26c8dc582ed4c8d6d158b7cf1cc5d；group_depth=3；implementation_sha256=ddf8e26b616b74d9119719433930b78fe6354d76ffaa983904b866be3658b1a3；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-flash；partition_assignment=greedy；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S2-discovery-injected；visibility=blind
- adaptive_scheduling=False；equal_exposure=True；git_revision=f70c541549b26c8dc582ed4c8d6d158b7cf1cc5d；group_depth=3；implementation_sha256=ddf8e26b616b74d9119719433930b78fe6354d76ffaa983904b866be3658b1a3；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-flash；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S2-discovery-injected；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_peers_all_evidence` | 40% (4/10) | 50% | 29% | 2.1176 / 3 | 71% | 10% | 1 | 12 | 0 | 21/21/21 → 合并 21 |
| `blind_no_coverage` | 20% (2/10) | 9% | 4% | 2.8402 / 3 | 95% | 20% | 1 | 12 | 0 | 21/21/21 → 合并 63 |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-tie-break-lost | d2-price-cap-boundary | d3-zero-score-candidates | d4-context-ratios-swapped | d5-primary-sku-is-last | d6-top-k-validation-dropped | d7-budget-tier-boundary | d8-budget-remaining-negative | d9-budget-zero-not-disabled | d10-negative-charge-accepted | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_peers_all_evidence` | 3 | 2 | 3 | ✗ | ✗ | 1 | ✗ | ✗ | ✗ | ✗ | 1 | 6 |
| `blind_no_coverage` | ✗ | ✗ | ✗ | 1 | ✗ | 1 | ✗ | ✗ | ✗ | ✗ | 2 | 8 |

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

### `no_peers_all_evidence`

- 耗时 385.36s｜LLM 调用 12 次（输入 69967 / 输出 207345 tokens）｜失败 7｜schema 重试 2｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 70.6%
- 每 Reader 实读单元：reader-r0-0=21、reader-r0-1=21、reader-r0-2=21｜合并去重 21
- claim 总数 24（独立指纹 17｜冗余率 29%｜未匹配 12）
- 命中 4/10 个植入缺陷｜命中同一缺陷的重复 claim 8 条
- 漏检：d4-context-ratios-swapped, d5-primary-sku-is-last, d7-budget-tier-boundary, d8-budget-remaining-negative, d9-budget-zero-not-disabled, d10-negative-charge-accepted

### `blind_no_coverage`

- 耗时 330.21s｜LLM 调用 12 次（输入 63314 / 输出 176848 tokens）｜失败 3｜schema 重试 2｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 94.7%
- 每 Reader 实读单元：reader-r0-0=21、reader-r0-1=21、reader-r0-2=21｜合并去重 63
- claim 总数 45（独立指纹 43｜冗余率 4%｜未匹配 41）
- 命中 2/10 个植入缺陷｜命中同一缺陷的重复 claim 2 条
- 漏检：d1-tie-break-lost, d2-price-cap-boundary, d3-zero-score-candidates, d5-primary-sku-is-last, d7-budget-tier-boundary, d8-budget-remaining-negative, d9-budget-zero-not-disabled, d10-negative-charge-accepted
