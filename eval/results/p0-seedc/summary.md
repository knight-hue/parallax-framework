# 对照实验结果

生成时间：2026-10-15T15:15:04+00:00

## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* | 覆盖率 | 轮次 | 调用 | Reader 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 100% (48/48) | 100% | 82% | 1.0231 | 19% | 1 | 48 | 0 |
| `sharded_shared` | 100% (48/48) | 100% | 63% | 2.3449 | 27% | 1 | 26 | 0 |
| `no_peers_all_evidence` | 100% (48/48) | 100% | 75% | 1.4047 | 31% | 1 | 48 | 0 |
| `blind_no_coverage` | 100% (48/48) | 100% | 1% | 3.5556 | 25% | 1 | 11 | 0 |
| `blind_full` | 100% (48/48) | 100% | 73% | 5.041 | 44% | 3 | 72 | 0 |

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | SCHEDULER1-alpha | SCHEDULER1-beta | SCHEDULER1-gamma | SCHEDULER1-delta | SCHEDULER1-epsilon | SCHEDULER1-zeta | SCHEDULER1-eta | SCHEDULER1-theta | JOURNAL1-alpha | JOURNAL1-beta | JOURNAL1-gamma | JOURNAL1-delta | JOURNAL1-epsilon | JOURNAL1-zeta | JOURNAL1-eta | JOURNAL1-theta | POOL1-alpha | POOL1-beta | POOL1-gamma | POOL1-delta | POOL1-epsilon | POOL1-zeta | POOL1-eta | POOL1-theta | CODEC1-alpha | CODEC1-beta | CODEC1-gamma | CODEC1-delta | CODEC1-epsilon | CODEC1-zeta | CODEC1-eta | CODEC1-theta | REGISTRY1-alpha | REGISTRY1-beta | REGISTRY1-gamma | REGISTRY1-delta | REGISTRY1-epsilon | REGISTRY1-zeta | REGISTRY1-eta | REGISTRY1-theta | WINDOW1-alpha | WINDOW1-beta | WINDOW1-gamma | WINDOW1-delta | WINDOW1-epsilon | WINDOW1-zeta | WINDOW1-eta | WINDOW1-theta | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_shared` | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 0 | 0 |
| `sharded_shared` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 |
| `no_peers_all_evidence` | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 0 | 0 |
| `blind_no_coverage` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 48 | 0 |
| `blind_full` | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 8 | 8 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 0 |

## 实验臂说明

- `baseline_shared`：传统多智能体：所有人看全部证据 + 可见彼此结论
- `sharded_shared`：公平对照：分片大小与实验组完全相同，但可见彼此结论（隔离出「共享」单独的效果）
- `no_peers_all_evidence`：所有人看全部证据，但看不到彼此结论
- `blind_no_coverage`：严格互斥分区，关闭补检（redundancy=1, max_rounds=1）
- `blind_full`：本框架完整机制：受控冗余分区 + 覆盖率驱动补检

## 明细

### `baseline_shared`

- 耗时 330.94s｜LLM 调用 48 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 294（命中 48｜冗余 246｜未匹配 0）
- 漏检：无

### `sharded_shared`

- 耗时 224.81s｜LLM 调用 26 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 238（命中 48｜冗余 190｜未匹配 0）
- 漏检：无

### `no_peers_all_evidence`

- 耗时 143.19s｜LLM 调用 48 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 370（命中 48｜冗余 322｜未匹配 0）
- 漏检：无

### `blind_no_coverage`

- 耗时 33.32s｜LLM 调用 11 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 89（命中 48｜冗余 41｜未匹配 0）
- 漏检：无

### `blind_full`

- 耗时 198.09s｜LLM 调用 72 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 3
- claim 总数 658（命中 48｜冗余 610｜未匹配 0）
- 漏检：无
