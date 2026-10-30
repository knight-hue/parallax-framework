# E-6 精确率抽样（p9-precision）

> 花费 **¥0**（离线抽样 + 人工判定）。
> 工具：`tools/precision_sample.py`；原始样本：`samples/sample-a.txt`、`samples/sample-b.txt`。

## 1. 为什么必须做

`score.py` 只回答「植入的缺陷有没有被找到」（召回），**从不回答「报出来的问题是不是真的」**。
全部产物约 387 条 claim 里只有约 48 条落在植入缺陷上，其余 339 条从未逐条判定。
因此此前材料里任何 precision 主张都没有依据。这一节把它测出来。

## 2. 方法

- 总体：`p4-chat`（E1 主数据集，5 切片）里**未匹配到任何植入缺陷**的缺陷断言，
  共 **113 条**。
- 抽样：固定种子随机抽两批各 12 条（种子 20261030 / 777001），合计 24 条。
- 判定：把每条 claim 与它 `locator` 指向的文件前后 ±5~6 行源码一起打印，逐条读：
  - **real** —— 代码确实存在该问题；
  - **false** —— 代码没有该问题（含「把设计取舍当缺陷」「把正确的代码读错」）；
  - **suggestion** —— 代码没错，但属于合理的加固建议；
  - **unverifiable** —— 引用的位置看不到所描述的函数（错位/摘录为空）。
- 判定由单人完成，未做双人复核。

## 3. 结果

| 判定 | 条数 | 占比 |
| --- | ---: | ---: |
| **real**（真缺陷） | **11** | **45.8%** |
| **false**（明显不成立） | **7** | 29.2% |
| suggestion（加固建议） | 5 | 20.8% |
| unverifiable（错位/空摘录） | 1 | 4.2% |
| 合计 | 24 | 100% |

**严格口径精确率 = 11/24 ≈ 46%（Wilson 95% CI 28%~65%）。**
若把「加固建议」也算作「不算错」，则为 16/24 ≈ 67%。

## 4. 逐条明细

| # | 切片 | 位置 | 判定 | 依据 |
| --- | --- | --- | --- | --- |
| A1 | S6 | `seed_products.py:88` | false | 「P1023 价格币种 USD 但量级与 CNY 商品不一致」——跨境商品用本币标价是正常的，且引用的是另一条商品 |
| A2 | S2 | `llm.py:155` | **real** | `except BaseException` 会把 `CancelledError` 当瞬时故障重试，取消被延迟 |
| A3 | S6 | `order_usecases.py:175` | **real** | 先 `stock_repo.release()` 再 `order_repo.save()`；save 失败后状态机仍允许重试 → **重复回补库存** |
| A4 | S2 | `eventbus.py:158` | **real** | 淘汰会话时清 `_seq` 不清订阅，`seq` 从 1 重来会让客户端去重误判 |
| A5 | S6 | `sql/repositories.py:212` | **real** | `order_by(turn_index).limit(N)` 取的是**最早** N 条，会话超过 N 轮后最近的对话全丢 |
| A6 | S3 | `order_usecases.py:118` | **real** | `save(order)` 在 `record()` 之前；幂等键冲突时只 `_rollback(reserved)`，**已保存的订单没撤销**，而注释写着「订单都要撤销」 |
| A7 | S1 | `sql/repositories.py:196` | **real**（错位） | 讲的是 `append_turn` 的「读最大值 +1」，但引用的是 `append_events` |
| A8 | S6 | `in_memory_repositories.py:62` | false | 内存实现无容量上限——它是**测试替身**，docstring 已说明生产要用落库实现 |
| A9 | S6 | `in_memory_stock_repository.py:38` | false | 「release 对未登记 SKU 补登记」是**注释里写明的取舍**（宁可不静默丢弃），属设计分歧 |
| A10 | S4 | `content_filter.py:24` | **false（严重）** | 断言 `(?i)` 内联标志位置导致**编译失败**，严重度标 `critical`。实际 `(?i)` 在开头是合法写法，模块正常导入、24 条测试全绿 |
| A11 | S6 | `catalog_search.py:213` | suggestion | `rerank_scores[i]` 越界——但 `Reranker` 端口契约已写明「返回与 documents 等长」 |
| A12 | S6 | `sql/repositories.py:245` | suggestion | `inserted_primary_key` 的可靠性担忧，commit 后读取确有风险，但这不是明确缺陷 |
| B1 | S1 | `sql/repositories.py:298` | suggestion | 同上（`next_order_id`） |
| B2 | S2 | `resilience.py:76` | **real** | 半开状态只置 `half_open_probing = True` 就放行，**并发请求会同时被放行**，docstring 承诺的「放行一次探测」不成立 |
| B3 | S6 | `http_reranker.py:38` | **real** | 字段存在但值为 `None` 时 `float(None)` 抛 `TypeError`，绕过上面刚做的 `RuntimeError` 校验 |
| B4 | S2 | `exchange_rate.py:41` | **real** | `convert` 只校验目标币种，源币种不支持时抛 `KeyError` 而非 `ValueError`，与自身校验口径不一致 |
| B5 | S2 | `eventbus.py:196` | unverifiable | 摘录为空，看不到所描述的函数 |
| B6 | S6 | `in_memory_stock_repository.py:38` | false | 同 A9（同一切片内另一臂的重复 claim） |
| B7 | S1 | `in_memory_repositories.py:62` | false | 断言「find+record 非原子可双写」——`record` 内部是一把锁内的「查了再写」，正是正确的原子写法 |
| B8 | S6 | `redis_stream_queue.py:78` | **real** | `queue_position = depth()` 给的是**整条流的 lag**，不是本任务在队列中的位置 |
| B9 | S6 | `catalog_search.py:213` | suggestion | 同 A11（重复 claim） |
| B10 | S1 | `sql/repositories.py:196` | **real**（错位） | 同 A7（重复 claim） |
| B11 | S6 | `sql/repositories.py:330` | false | 断言 `seed` 非原子，引用的却是 `reserve`——而 `reserve` 用的是条件 UPDATE，**恰恰是正确实现** |
| B12 | S6 | `sql/repositories.py:245` | suggestion | 同 A12（重复 claim） |

## 5. 三个必须写进材料的结论

### 5.1 精确率约 46%，三成明显不成立

11/24 为真缺陷，7/24 明显不成立，5/24 是加固建议。
**因此不得再宣称「准确率」，也不得把召回数字当质量证明。**

### 5.2 失败模式是可归因的，不是随机噪声

- **把设计取舍当缺陷**（A8、A9/B6）：测试替身无上限、注释里写明的取舍；
- **读错代码**（B7、B11）：`record` 的锁内「查了再写」、`reserve` 的条件 UPDATE，
  都被读成了缺陷——这两处恰恰是全项目最正确的并发写法；
- **错位**（A7、B10、B11）：描述的是函数 X，引用的是函数 Y；
- **一条 `critical` 是假的**（A10）：`(?i)` 编译失败不成立，而该模块 24 条测试全绿。

### 5.3 「387 条 claim」高估了独立发现数

24 条样本里有 5 条是**同一问题在不同臂/不同切片重复出现**
（`in_memory_stock` ×2、`next_order_id` ×3、`catalog_search` ×2、`append_turn` ×2）。
按独立问题去重后，有效发现数明显少于 claim 计数——这与 E3b 的「冗余率上升」是同一枚硬币的两面。

## 6. 限制

1. **n=24**，Wilson 95% CI 为 28%~65%，跨度很宽。结论只能用于否定「精确率很高」，不能用于精确报告数值。
2. 单人判定，无第二人复核；「suggestion vs false」的边界带主观性。
3. 总体是 `p4-chat` 的 113 条未匹配 claim，不代表 `p5`–`p8` 各臂的分布。
4. 未按严重度分层估计（`critical`/`high` 的精确率可能显著低于 `low`，
   A10 这条假 `critical` 提示存在「严重度通胀」，但样本量不足以量化）。
