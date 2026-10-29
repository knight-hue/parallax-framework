# 对照实验结果

生成时间：2026-10-29T12:11:52+00:00

**生效配置**（跨臂不同会被分别列出，避免拿不同口径的结果互相比较）

- 生效配置：adaptive_scheduling=False；git_revision=f0cbd789f8f5d4c27498798d9b9798dc37908379；implementation_sha256=231beb698a72cf61e851995cf78a9cac4c554fa28e7bd364e65f3e402da18000；llm_falsifier=False；max_batch_chars=24000；max_evidence_overlap_rate=1.0；max_evidence_per_call=6；max_llm_calls=4；max_output_tokens=32000；max_rounds=1；max_tokens=0；min_independent_support=2；model=deepseek-flash；readers=3；redundancy=1；seed=0；semantic_partitioning=False；support_threshold=2；task=S4-session-cache-injected；visibility=blind


## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 输出 K* / 产出者数 | 产出者归一化占比 | 矩阵填充 | 轮次 | 调用 | Reader 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `blind_no_coverage@calls4` | 83% (10/12) | 74% | 4% | 2.9157 / 3 | 97% | 34% | 1 | 6 | 0 |

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | d1-dislikes-truncated-by-total-budget | d2-zero-budget-drops-dislikes | d3-relevance-ranking-keeps-sorted-order | d4-money-accepts-bool | d5-conversation-role-unchecked | d6-embedding-key-drops-model | d7-embedding-missing-silently-emptied | d8-history-not-blocked | d9-error-reply-cached | d10-bucket-key-ignores-scope | d11-bucket-keeps-oldest | d12-output-guard-misses-api-key | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `blind_no_coverage@calls4` | 1 | 1 | 1 | 1 | 1 | 1 | ✗ | 1 | ✗ | 1 | 1 | 1 | 10 | 2 |

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

### `blind_no_coverage@calls4`

- 耗时 140.34s｜LLM 调用 6 次（输入 17039 / 输出 54222 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `budget_exhausted`｜轮次 1
- 非空分区 Reader 3｜产出 Claim 的 Reader 3｜输出 K*/已分配 Reader 97.2%
- claim 总数 23（独立指纹 22｜冗余率 4%｜未匹配 6）
- 命中 10/12 个植入缺陷｜命中同一缺陷的重复 claim 7 条
- 漏检：d7-embedding-missing-silently-emptied, d9-error-reply-cached
