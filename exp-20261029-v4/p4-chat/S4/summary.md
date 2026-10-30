# 对照实验结果

生成时间：2026-10-30T02:50:24+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind
- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `no_peers_all_evidence` | 25% (3/12) | 54% | 54% | 1.3981 / 3 | 47% | 10% | 1 | 6 | 0 | 9/9/9 → 合并 9 | OK |
| `blind_no_coverage` | 83% (10/12) | 54% | 7% | 2.6202 / 3 | 87% | 19% | 1 | 6 | 0 | 9/9/8 → 合并 26 | OK |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-dislikes-truncated-by-total-budget | d2-zero-budget-drops-dislikes | d3-relevance-ranking-keeps-sorted-order | d4-money-accepts-bool | d5-conversation-role-unchecked | d6-embedding-key-drops-model | d7-embedding-missing-silently-emptied | d8-history-not-blocked | d9-error-reply-cached | d10-bucket-key-ignores-scope | d11-bucket-keeps-oldest | d12-output-guard-misses-api-key | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_peers_all_evidence` | 3 | ✗ | 3 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 3 | 0 | 9 |
| `blind_no_coverage` | ✗ | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | ✗ | 1 | 10 | 2 |

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

- 耗时 14.83s｜LLM 调用 6 次（输入 16554 / 输出 7522 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 46.6%
- 每 Reader 实读单元：reader-r0-0=9、reader-r0-1=9、reader-r0-2=9｜合并去重 9
- claim 总数 24（独立指纹 11｜冗余率 54%｜未匹配 11）
- 命中 3/12 个植入缺陷｜命中同一缺陷的重复 claim 10 条
- 漏检：d2-zero-budget-drops-dislikes, d4-money-accepts-bool, d5-conversation-role-unchecked, d6-embedding-key-drops-model, d7-embedding-missing-silently-emptied, d8-history-not-blocked, d9-error-reply-cached, d10-bucket-key-ignores-scope, d11-bucket-keeps-oldest

### `blind_no_coverage`

- 耗时 23.41s｜LLM 调用 6 次（输入 16816 / 输出 9950 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 87.3%
- 每 Reader 实读单元：reader-r0-0=9、reader-r0-1=9、reader-r0-2=8｜合并去重 26
- claim 总数 28（独立指纹 26｜冗余率 7%｜未匹配 13）
- 命中 10/12 个植入缺陷｜命中同一缺陷的重复 claim 5 条
- 漏检：d1-dislikes-truncated-by-total-budget, d11-bucket-keeps-oldest
