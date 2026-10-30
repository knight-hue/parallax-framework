# 对照实验结果

生成时间：2026-10-30T05:25:42+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S6；visibility=blind
- adaptive_scheduling=False；equal_exposure=True；git_revision=05435102c7467a2d5cd3186fd2c5636be782a902；group_depth=3；implementation_sha256=38a1314e62352306801b261d124d5a104d526ffd2cee6904a877fbd9a44d688d；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=0；max_output_tokens=16000；max_rounds=1；max_tokens=0；max_units_per_reader=0；min_independent_support=2；model=deepseek-chat；partition_assignment=greedy；readers=3；redundancy=3；seed=0；semantic_partitioning=False；support_threshold=2；task=S6；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 | 实读单元（每人 → 合并） | 完整性 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `no_peers_all_evidence` | 0% (0/10) | 0% | 35% | 2.141 / 3 | 71% | 8% | 1 | 9 | 0 | 11/11/11 → 合并 11 | OK |
| `blind_no_coverage` | 60% (6/10) | 14% | 2% | 2.8143 / 3 | 94% | 23% | 1 | 7 | 0 | 11/10/10 → 合并 31 | OK |

> **「实读单元（每人 → 合并）」是曝光量操纵的验证点。** 若各臂在这一列上看不出差别，就说明「集中臂每人只读 N 条」根本没生效，此时两臂的召回差异**不能**归因于分配方式。

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-auto-pk-loses-sqlite-variant | d2-preference-unique-key-narrowed | d3-message-index-drops-turn | d4-order-line-loses-foreign-key | d5-sku-stock-version-no-default | d6-path-traversal-not-sanitized | d7-preference-dedupe-ignores-kind | d8-jsonl-append-becomes-overwrite | d9-list-turns-includes-events | d10-delete-only-removes-dislike | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_peers_all_evidence` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 0 | 10 |
| `blind_no_coverage` | ✗ | ✗ | 1 | ✗ | 1 | 1 | ✗ | 1 | 1 | 1 | 6 | 4 |

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

- 耗时 33.27s｜LLM 调用 9 次（输入 38310 / 输出 17695 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 71.4%
- 每 Reader 实读单元：reader-r0-0=11、reader-r0-1=11、reader-r0-2=11｜合并去重 11
- claim 总数 55（独立指纹 36｜冗余率 35%｜未匹配 55）
- 命中 0/10 个植入缺陷｜命中同一缺陷的重复 claim 0 条
- 漏检：d1-auto-pk-loses-sqlite-variant, d2-preference-unique-key-narrowed, d3-message-index-drops-turn, d4-order-line-loses-foreign-key, d5-sku-stock-version-no-default, d6-path-traversal-not-sanitized, d7-preference-dedupe-ignores-kind, d8-jsonl-append-becomes-overwrite, d9-list-turns-includes-events, d10-delete-only-removes-dislike

### `blind_no_coverage`

- 耗时 33.32s｜LLM 调用 7 次（输入 44628 / 输出 17976 tokens）｜失败 0｜schema 重试 1｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 93.8%
- 每 Reader 实读单元：reader-r0-0=11、reader-r0-1=10、reader-r0-2=10｜合并去重 31
- claim 总数 44（独立指纹 43｜冗余率 2%｜未匹配 38）
- 命中 6/10 个植入缺陷｜命中同一缺陷的重复 claim 0 条
- 漏检：d1-auto-pk-loses-sqlite-variant, d2-preference-unique-key-narrowed, d4-order-line-loses-foreign-key, d7-preference-dedupe-ignores-kind
