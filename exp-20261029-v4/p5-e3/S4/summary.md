# 对照实验结果

生成时间：2026-10-30T05:36:03+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=False；git_revision=56184c334911da5e80bb14053ef544c49df96724；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind
- adaptive_scheduling=False；equal_exposure=False；git_revision=56184c334911da5e80bb14053ef544c49df96724；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=2；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind
- adaptive_scheduling=False；equal_exposure=False；git_revision=56184c334911da5e80bb14053ef544c49df96724；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind
- adaptive_scheduling=False；equal_exposure=False；git_revision=56184c334911da5e80bb14053ef544c49df96724；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=shared
- adaptive_scheduling=False；equal_exposure=False；git_revision=56184c334911da5e80bb14053ef544c49df96724；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=3；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=2；seed=0；semantic_partitioning=False；support_threshold=2；task=S4；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `baseline_shared` | 83% (10/12) | 53% | 59% | 1.2398 / 3 | 41% | 20% | 1 | 15 | 0 | 26/26/26 → 合并 26 | OK |
| `sharded_blind` | 92% (11/12) | 57% | 22% | 2.6118 / 3 | 87% | 25% | 1 | 9 | 0 | 18/17/17 → 合并 26 | OK |
| `no_peers_all_evidence` | 83% (10/12) | 56% | 46% | 1.7225 / 3 | 57% | 25% | 1 | 15 | 0 | 26/26/26 → 合并 26 | OK |
| `blind_no_coverage` | 75% (9/12) | 56% | 4% | 2.6422 / 3 | 88% | 16% | 1 | 6 | 0 | 9/9/8 → 合并 26 | OK |
| `blind_full` | 100% (12/12) | 57% | 57% | 4.5768 / 9 | 51% | 32% | 3 | 27 | 0 | 18/17/17/15/15/14/13/13/14 → 合并 26 | OK |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

> ⚠️ **本表各臂的 Agent 数不同，请勿直接比较裸 K\*。** 表中 N 只计产出者，排除了零产出的 Reader；同时报告非空分区 Reader 数、分区、轮数和 tokens。归一化本身不能消除预算或选择偏差。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-dislikes-truncated-by-total-budget | d2-zero-budget-drops-dislikes | d3-relevance-ranking-keeps-sorted-order | d4-money-accepts-bool | d5-conversation-role-unchecked | d6-embedding-key-drops-model | d7-embedding-missing-silently-emptied | d8-history-not-blocked | d9-error-reply-cached | d10-bucket-key-ignores-scope | d11-bucket-keeps-oldest | d12-output-guard-misses-api-key | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 3 | ✗ | 3 | 3 | 3 | 3 | 3 | 3 | 2 | ✗ | 3 | 3 | 0 | 2 |
| `sharded_blind` | 2 | ✗ | 2 | 2 | 1 | 1 | 2 | 2 | 2 | 1 | 2 | 2 | 3 | 1 |
| `no_peers_all_evidence` | 3 | ✗ | 3 | 3 | 3 | 3 | 3 | 3 | 3 | ✗ | 3 | 3 | 0 | 2 |
| `blind_no_coverage` | 1 | 1 | 1 | 1 | 1 | ✗ | 1 | 1 | ✗ | 1 | ✗ | 1 | 9 | 3 |
| `blind_full` | 4 | 3 | 4 | 6 | 5 | 4 | 6 | 6 | 5 | 4 | 5 | 6 | 0 | 0 |

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

- 耗时 145.65s｜LLM 调用 15 次（输入 62174 / 输出 28353 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 41.3%
- 每 Reader 实读单元：reader-r0-0=26、reader-r0-1=26、reader-r0-2=26｜合并去重 26
- claim 总数 90（独立指纹 37｜冗余率 59%｜未匹配 42）
- 命中 10/12 个植入缺陷｜命中同一缺陷的重复 claim 38 条
- 漏检：d2-zero-budget-drops-dislikes, d10-bucket-key-ignores-scope

### `sharded_blind`

- 耗时 40.42s｜LLM 调用 9 次（输入 31184 / 输出 19224 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 87.1%
- 每 Reader 实读单元：reader-r0-0=18、reader-r0-1=17、reader-r0-2=17｜合并去重 26
- claim 总数 60（独立指纹 47｜冗余率 22%｜未匹配 26）
- 命中 11/12 个植入缺陷｜命中同一缺陷的重复 claim 23 条
- 漏检：d2-zero-budget-drops-dislikes

### `no_peers_all_evidence`

- 耗时 55.87s｜LLM 调用 15 次（输入 50206 / 输出 28051 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 57.4%
- 每 Reader 实读单元：reader-r0-0=26、reader-r0-1=26、reader-r0-2=26｜合并去重 26
- claim 总数 80（独立指纹 43｜冗余率 46%｜未匹配 35）
- 命中 10/12 个植入缺陷｜命中同一缺陷的重复 claim 35 条
- 漏检：d2-zero-budget-drops-dislikes, d10-bucket-key-ignores-scope

### `blind_no_coverage`

- 耗时 22.29s｜LLM 调用 6 次（输入 16698 / 输出 9015 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 88.1%
- 每 Reader 实读单元：reader-r0-0=9、reader-r0-1=9、reader-r0-2=8｜合并去重 26
- claim 总数 25（独立指纹 24｜冗余率 4%｜未匹配 11）
- 命中 9/12 个植入缺陷｜命中同一缺陷的重复 claim 5 条
- 漏检：d6-embedding-key-drops-model, d9-error-reply-cached, d11-bucket-keeps-oldest

### `blind_full`

- 耗时 116.03s｜LLM 调用 27 次（输入 89871 / 输出 59882 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 3
- 非空分区 Reader 9｜产出 Claim 的 Reader 9｜输出 K*/已分配 Reader 50.8%
- 每 Reader 实读单元：reader-r0-0=18、reader-r0-1=17、reader-r0-2=17、reader-r1-0=15、reader-r1-1=15、reader-r1-2=14、reader-r2-0=13、reader-r2-1=13、reader-r2-2=14｜合并去重 26
- claim 总数 176（独立指纹 75｜冗余率 57%｜未匹配 75）
- 命中 12/12 个植入缺陷｜命中同一缺陷的重复 claim 89 条
- 漏检：无
