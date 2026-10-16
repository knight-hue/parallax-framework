# 对照实验结果

生成时间：2026-10-15T15:29:31+00:00

## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* | 覆盖率 | 轮次 | 调用 | Reader 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 86% (6/7) | 100% | 65% | 1.0434 | 42% | 1 | 3 | 0 |
| `sharded_shared` | 86% (6/7) | 100% | 53% | 1.467 | 33% | 1 | 3 | 0 |
| `no_peers_all_evidence` | 100% (7/7) | 100% | 57% | 1.3244 | 38% | 1 | 3 | 0 |
| `blind_no_coverage` | 100% (7/7) | 100% | 9% | 1.7241 | 33% | 1 | 2 | 0 |
| `blind_full` | 100% (7/7) | 100% | 74% | 2.3406 | 46% | 3 | 9 | 0 |
| `baseline_shared` | 100% (18/18) | 100% | 64% | 1.0712 | 23% | 1 | 9 | 0 |
| `sharded_shared` | 100% (18/18) | 100% | 47% | 2.0203 | 27% | 1 | 7 | 0 |
| `no_peers_all_evidence` | 100% (18/18) | 100% | 58% | 1.261 | 25% | 1 | 9 | 0 |
| `blind_no_coverage` | 100% (18/18) | 100% | 10% | 2.7413 | 17% | 1 | 4 | 0 |
| `blind_full` | 100% (18/18) | 100% | 67% | 3.3373 | 33% | 3 | 17 | 0 |

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | A1 | A2 | A3 | B1 | B2 | C1 | C2 | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 3 | 3 | 3 | ✗ | 3 | 3 | 3 | 0 | 1 |
| `sharded_shared` | 2 | 2 | 2 | ✗ | 2 | 2 | 2 | 0 | 1 |
| `no_peers_all_evidence` | 3 | 3 | 3 | 1 | 3 | 3 | 2 | 1 | 0 |
| `blind_no_coverage` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 7 | 0 |
| `blind_full` | 6 | 6 | 6 | 2 | 6 | 6 | 4 | 0 | 0 |
| `baseline_shared` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 |
| `sharded_shared` | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 0 | 0 |
| `no_peers_all_evidence` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 |
| `blind_no_coverage` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 18 | 0 |
| `blind_full` | 6 | 6 | 6 | 2 | 2 | 2 | 6 | 6 | 6 | 4 | 4 | 4 | 6 | 6 | 6 | 6 | 6 | 6 | 0 | 0 |

## 实验臂说明

- `baseline_shared`：传统多智能体：所有人看全部证据 + 可见彼此结论
- `sharded_shared`：公平对照：分片大小与实验组完全相同，但可见彼此结论（隔离出「共享」单独的效果）
- `no_peers_all_evidence`：所有人看全部证据，但看不到彼此结论
- `blind_no_coverage`：严格互斥分区，关闭补检（redundancy=1, max_rounds=1）
- `blind_full`：本框架完整机制：受控冗余分区 + 覆盖率驱动补检
- `budget_shared`：固定预算对照：每 Reader 预算相同，但所有人读同样的 K 个维度并共享结论
- `budget_blind`：固定预算实验组：每 Reader 预算相同，各读不同的维度（联合覆盖 n 倍）

## 明细

### `baseline_shared`

- 耗时 28.53s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 31（命中 6｜冗余 25｜未匹配 0）
- 漏检：B1

### `sharded_shared`

- 耗时 22.9s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 19（命中 6｜冗余 13｜未匹配 0）
- 漏检：B1

### `no_peers_all_evidence`

- 耗时 11.39s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 30（命中 7｜冗余 23｜未匹配 0）
- 漏检：无

### `blind_no_coverage`

- 耗时 9.03s｜LLM 调用 2 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 11（命中 7｜冗余 4｜未匹配 0）
- 漏检：无

### `blind_full`

- 耗时 32.21s｜LLM 调用 9 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 3
- claim 总数 65（命中 7｜冗余 58｜未匹配 0）
- 漏检：无

### `baseline_shared`

- 耗时 73.27s｜LLM 调用 9 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 77（命中 18｜冗余 59｜未匹配 0）
- 漏检：无

### `sharded_shared`

- 耗时 57.29s｜LLM 调用 7 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 60（命中 18｜冗余 42｜未匹配 0）
- 漏检：无

### `no_peers_all_evidence`

- 耗时 31.71s｜LLM 调用 9 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 96（命中 18｜冗余 78｜未匹配 0）
- 漏检：无

### `blind_no_coverage`

- 耗时 13.72s｜LLM 调用 4 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 31（命中 18｜冗余 13｜未匹配 0）
- 漏检：无

### `blind_full`

- 耗时 55.97s｜LLM 调用 17 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 3
- claim 总数 151（命中 18｜冗余 133｜未匹配 0）
- 漏检：无
