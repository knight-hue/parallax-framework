# 对照实验结果

生成时间：2026-10-15T15:20:30+00:00

## 主指标对照

| 实验臂 | 召回率 | 精确率 | 冗余率 | 有效独立通道 K* | 覆盖率 | 轮次 | 调用 | Reader 失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `budget_shared` | 17% (8/48) | 100% | 83% | 1.0 | 4% | 1 | 12 | 0 |
| `budget_blind` | 100% (48/48) | 100% | 0% | 3.7492 | 25% | 1 | 11 | 0 |

## 逐缺陷命中矩阵

每一格是该缺陷被几个 Agent 独立发现。**只被 1 个 Agent 发现 = 孤证**，
被 0 个发现 = 漏检。这一栏是从众现象最直接的证据。

| 实验臂 | SCHEDULER1-alpha | SCHEDULER1-beta | SCHEDULER1-gamma | SCHEDULER1-delta | SCHEDULER1-epsilon | SCHEDULER1-zeta | SCHEDULER1-eta | SCHEDULER1-theta | JOURNAL1-alpha | JOURNAL1-beta | JOURNAL1-gamma | JOURNAL1-delta | JOURNAL1-epsilon | JOURNAL1-zeta | JOURNAL1-eta | JOURNAL1-theta | POOL1-alpha | POOL1-beta | POOL1-gamma | POOL1-delta | POOL1-epsilon | POOL1-zeta | POOL1-eta | POOL1-theta | CODEC1-alpha | CODEC1-beta | CODEC1-gamma | CODEC1-delta | CODEC1-epsilon | CODEC1-zeta | CODEC1-eta | CODEC1-theta | REGISTRY1-alpha | REGISTRY1-beta | REGISTRY1-gamma | REGISTRY1-delta | REGISTRY1-epsilon | REGISTRY1-zeta | REGISTRY1-eta | REGISTRY1-theta | WINDOW1-alpha | WINDOW1-beta | WINDOW1-gamma | WINDOW1-delta | WINDOW1-epsilon | WINDOW1-zeta | WINDOW1-eta | WINDOW1-theta | 孤证数 | 漏检 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `budget_shared` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 0 | 40 |
| `budget_blind` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 48 | 0 |

## 实验臂说明

- `baseline_shared`：传统多智能体：所有人看全部证据 + 可见彼此结论
- `sharded_shared`：公平对照：分片大小与实验组完全相同，但可见彼此结论（隔离出「共享」单独的效果）
- `no_peers_all_evidence`：所有人看全部证据，但看不到彼此结论
- `blind_no_coverage`：严格互斥分区，关闭补检（redundancy=1, max_rounds=1）
- `blind_full`：本框架完整机制：受控冗余分区 + 覆盖率驱动补检
- `budget_shared`：固定预算对照：每 Reader 预算相同，但所有人读同样的 K 个维度并共享结论
- `budget_blind`：固定预算实验组：每 Reader 预算相同，各读不同的维度（联合覆盖 n 倍）

## 明细

### `budget_shared`

- 耗时 85.62s｜LLM 调用 12 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 96（命中 8｜冗余 88｜未匹配 0）
- 漏检：SCHEDULER1-alpha, SCHEDULER1-beta, SCHEDULER1-gamma, SCHEDULER1-delta, SCHEDULER1-epsilon, SCHEDULER1-zeta, SCHEDULER1-eta, SCHEDULER1-theta, JOURNAL1-alpha, JOURNAL1-beta, JOURNAL1-gamma, JOURNAL1-delta, JOURNAL1-epsilon, JOURNAL1-zeta, JOURNAL1-eta, JOURNAL1-theta, POOL1-alpha, POOL1-beta, POOL1-gamma, POOL1-delta, POOL1-epsilon, POOL1-zeta, POOL1-eta, POOL1-theta, CODEC1-alpha, CODEC1-beta, CODEC1-gamma, CODEC1-delta, CODEC1-epsilon, CODEC1-zeta, CODEC1-eta, CODEC1-theta, REGISTRY1-alpha, REGISTRY1-beta, REGISTRY1-gamma, REGISTRY1-delta, REGISTRY1-epsilon, REGISTRY1-zeta, REGISTRY1-eta, REGISTRY1-theta

### `budget_blind`

- 耗时 29.07s｜LLM 调用 11 次（输入 0 / 输出 0 tokens）｜失败 0｜schema 重试 0｜Reader 失败 0
- 停止原因 `max_rounds_reached`｜轮次 1
- claim 总数 84（命中 48｜冗余 36｜未匹配 0）
- 漏检：无
