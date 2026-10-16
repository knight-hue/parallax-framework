# 对照实验结果

生成时间：2026-10-15T14:11:05+00:00

## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* | 覆盖率 | 轮次 | 调用 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 86% (6/7) | 100% | 68% | 1.0 | 33% | 1 | 3 |
| `no_peers_all_evidence` | 100% (7/7) | 100% | 59% | 1.2609 | 38% | 1 | 3 |
| `blind_no_coverage` | 86% (6/7) | 100% | 0% | 1.6575 | 38% | 1 | 2 |
| `blind_full` | 100% (7/7) | 100% | 70% | 2.8613 | 50% | 3 | 9 |

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | A1 | A2 | A3 | B1 | B2 | C1 | C2 | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 3 | 3 | 3 | ✗ | 3 | 3 | 3 | 0 | 1 |
| `no_peers_all_evidence` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 |
| `blind_no_coverage` | 1 | 1 | 1 | ✗ | 1 | 1 | 1 | 6 | 1 |
| `blind_full` | 6 | 6 | 6 | 2 | 2 | 6 | 5 | 0 | 0 |

## 实验臂说明

- `baseline_shared`：传统多智能体：所有人看全部证据 + 可见彼此结论
- `no_peers_all_evidence`：所有人看全部证据，但看不到彼此结论
- `blind_no_coverage`：严格互斥分区，关闭补检（redundancy=1, max_rounds=1）
- `blind_full`：本框架完整机制：受控冗余分区 + 覆盖率驱动补检

## 明细

### `baseline_shared`

- 耗时 32.44s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 31（命中 6｜冗余 25｜未匹配 0）
- 漏检：B1

### `no_peers_all_evidence`

- 耗时 15.37s｜LLM 调用 3 次（输入 0 / 输出 0 tokens）
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 32（命中 7｜冗余 25｜未匹配 0）
- 漏检：无

### `blind_no_coverage`

- 耗时 10.59s｜LLM 调用 2 次（输入 0 / 输出 0 tokens）
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 11（命中 6｜冗余 5｜未匹配 0）
- 漏检：B1

### `blind_full`

- 耗时 37.16s｜LLM 调用 9 次（输入 0 / 输出 0 tokens）
- 停止原因 `max_rounds_reached`｜轮次 3
- claim 总数 60（命中 7｜冗余 53｜未匹配 0）
- 漏检：无
