# 对照实验结果

生成时间：2026-10-30T05:22:19+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S1；visibility=blind
- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S1；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `no_peers_all_evidence` | 22% (2/9) | 18% | 59% | 1.3199 / 3 | 44% | 22% | 1 | 6 | 0 | 11/11/11 → 合并 11 | OK |
| `blind_no_coverage` | 89% (8/9) | 53% | 3% | 2.9938 / 3 | 100% | 38% | 1 | 7 | 0 | 11/10/10 → 合并 31 | OK |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-stock-seed-overwrite | d2-get-many-missing-zero | d3-list-turns-earliest | d4-idempotency-key-scope | d5-empty-lines-allowed | d6-subtotal-off-by-one | d7-freight-renewal-40 | d8-exchange-rate-inverse | d9-from-major-truncates | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_peers_all_evidence` | ✗ | ✗ | ✗ | ✗ | ✗ | 3 | 3 | ✗ | ✗ | 0 | 7 |
| `blind_no_coverage` | 1 | ✗ | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 8 | 1 |

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

- 耗时 28.2s｜LLM 调用 6 次（输入 26736 / 输出 12380 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 44.0%
- 每 Reader 实读单元：reader-r0-0=11、reader-r0-1=11、reader-r0-2=11｜合并去重 11
- claim 总数 39（独立指纹 16｜冗余率 59%｜未匹配 32）
- 命中 2/9 个植入缺陷｜命中同一缺陷的重复 claim 5 条
- 漏检：d1-stock-seed-overwrite, d2-get-many-missing-zero, d3-list-turns-earliest, d4-idempotency-key-scope, d5-empty-lines-allowed, d8-exchange-rate-inverse, d9-from-major-truncates

### `blind_no_coverage`

- 耗时 19.9s｜LLM 调用 7 次（输入 35993 / 输出 11040 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 99.8%
- 每 Reader 实读单元：reader-r0-0=11、reader-r0-1=10、reader-r0-2=10｜合并去重 31
- claim 总数 32（独立指纹 31｜冗余率 3%｜未匹配 15）
- 命中 8/9 个植入缺陷｜命中同一缺陷的重复 claim 9 条
- 漏检：d2-get-many-missing-zero
