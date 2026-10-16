# Parallax 运行报告 `a16d6a8f25aa`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 66 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 16 | 单一来源孤证 |
| 争议 | 6 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：6 个（每轮全新身份）
- 账本条目：238

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 6 | 88 | 100% | 21% |

## 高置信结论

- **[boundary/medium]** [boundary] analytics/window_alpha.py:41-45 WindowAlpha.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1（如 1.5）时 index 会超过 len-1，ordered[index] 抛 IndexError；当 ratio < 0 时 index 为负，会从尾部取值而不报错，返回错误结果。方法未对 ratio 做 [0,1] 校验。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_alpha.py:22-25 WindowAlpha.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不减去被淘汰的值。因此当样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，均值被严重高估。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_beta.py:41-45 WindowBeta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:41-45`
  - 依据：index 由 ratio 直接缩放得到，ratio>1 时索引越界抛 IndexError，ratio<0 时静默返回错误元素，缺少范围校验。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 WindowBeta.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，mean() 用 _total / len(_values) 会把全部历史之和除以当前窗口长度，均值错误。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_delta.py:41-45 WindowDelta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1（如 1.5）时 index 会超过 len-1，ordered[index] 抛 IndexError；ratio 为负时 index 为负，会静默返回错误元素（Python 负索引）。调用方传入未约束的 ratio 即触发。
- **[logic/high]** [logic] analytics/window_delta.py:22-25 WindowDelta.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不减去被淘汰的值。因此当样本数超过 size 后，_total 会持续累积所有历史样本，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度，分子却是全部历史之和，均值会随写入次数单调膨胀，完全错误。触发条件：add 调用次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_epsilon.py:41-45 WindowEpsilon.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:41-45`
  - 依据：ratio 未做范围校验，ratio > 1 时 index 越界抛 IndexError，ratio < 0 时负索引静默返回错误元素。
- **[logic/high]** [logic] analytics/window_epsilon.py:22-25 WindowEpsilon.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:22-25`
  - 依据：与 WindowDelta 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，mean() 用 _total / len(self._values) 得到被高估的均值。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_eta.py:41-45 WindowEta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:41-45`
  - 依据：ratio 未做 [0,1] 校验。当 ratio > 1 时 index 会超过 len(ordered)-1，ordered[index] 抛 IndexError；ratio < 0 时 index 为负，会静默返回错误元素。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_eta.py:22-25 WindowEta.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 _total 只增不减。因此当样本数超过 size 后，_total 累加了所有历史样本，而 len(self._values) 只反映窗口内样本数，mean() 返回 _total/len 会远大于真实窗口均值。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:41-45 WindowGamma.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:41-45`
  - 依据：ratio 未做 [0,1] 校验。当 ratio > 1 时 index = round(ratio*(n-1)) 会超过 n-1，ordered[index] 抛 IndexError；ratio < 0 时 index 为负，会静默返回错误元素（Python 负索引）。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 WindowGamma.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只增不减。因此当样本数超过 size 后，_total 累加了所有历史样本，而 len(self._values) 仅为 size，mean() 返回 _total/len 会远大于真实窗口均值。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_theta.py:41-45 WindowTheta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:41-45`
  - 依据：ratio 未做 [0,1] 校验，ratio>1 时 ordered[index] 越界抛 IndexError，ratio<0 时返回错误元素。
- **[logic/high]** [logic] analytics/window_theta.py:22-25 WindowTheta.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:22-25`
  - 依据：deque(maxlen=size) 淘汰旧样本后 _total 未同步扣减，mean() 分子包含已淘汰样本，窗口满后均值持续偏大。
- **[boundary/medium]** [boundary] analytics/window_zeta.py:41-45 WindowZeta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:41-45`
  - 依据：ratio 未校验范围，ratio>1 时 index 超出列表长度抛 IndexError，ratio<0 时负索引返回错误元素。
- **[logic/high]** [logic] analytics/window_zeta.py:22-25 WindowZeta.add 淘汰旧样本时未从 _total 扣除，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:22-25`
  - 依据：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，mean() 会随写入次数持续偏大。触发条件：add 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-58 JournalAlpha.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。此后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的文件，二者不一致；再次 append() 时 _flush() 会把内存中未裁剪的完整列表重新写回磁盘，使 compact 的效果被撤销。触发条件：compact() 后调用 replay/count/append。
- **[logic/high]** [logic] persistence/journal_beta.py:51-58 JournalBeta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。触发条件：记录数超过 keep 后调用 compact()，随后调用 replay()/count() 仍返回全部旧记录，而 disk_count() 返回裁剪后的数量，内存与磁盘状态分叉；后续 append() 还会用未裁剪的 _records 重写文件，把已丢弃的记录重新写回磁盘，使压缩失效。
- **[logic/high]** [logic] persistence/journal_delta.py:51-58 JournalDelta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_delta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写回磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的数量，二者不一致；后续 append() 调用 _flush() 会把内存中未裁剪的完整列表重新写回磁盘，使 compact 的效果被撤销。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_epsilon.py:51-58 compact() 未同步内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:51-58`
  - 依据：compact() 只把截断后的 kept 写入磁盘，却没有更新 self._records。调用 compact() 后，replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，内存与磁盘状态永久分叉；后续 append() 会以未压缩的 _records 重写文件，把已丢弃的旧记录重新写回磁盘，使压缩失效。
- **[logic/high]** [logic] persistence/journal_eta.py:51-58 compact() 未同步内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_eta.py:51-58`
  - 依据：与 journal_epsilon.py 相同：compact() 只写磁盘不更新 self._records。触发条件：append 超过 keep 条后调用 compact()，replay()/count() 仍返回全部记录，且下一次 append() 的 _flush() 会把未截断的记录全部写回，compact 失效。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 JournalGamma.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：与 JournalAlpha 相同：compact() 仅重写磁盘文件，未更新 self._records。replay()/count() 仍返回被裁剪掉的记录，后续 append() 触发 _flush() 会把旧记录重新写回磁盘，导致压缩无效。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_theta.py:51-58 JournalTheta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_theta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records，内存中仍保留全部旧记录。之后 replay()/count() 返回被压缩掉的数据，而 disk_count() 反映的是裁剪后的文件，二者不一致；再次 append 时 _flush 会把内存中的旧记录重新写回磁盘，使压缩失效。
- **[logic/high]** [logic] persistence/journal_zeta.py:51-58 JournalZeta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_zeta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的数量，二者不一致；后续 append() 还会用未裁剪的 _records 重写文件，使 compact 的效果被撤销。
- **[api_misuse/medium]** [api_misuse] resources/pool_alpha.py:60-66 close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：closer = getattr(self._factory, "close", None) 取的是工厂函数/工厂对象自身的 close 方法，而不是池中资源对象的 close。若 factory 是普通函数则 closer 为 None，资源永远不会被关闭（泄漏）；若 factory 恰好有 close 属性，则会被错误地当作资源关闭器调用。正确做法应对每个 resource 调用 getattr(resource, "close", None)。触发条件：调用 close() 时。
- **[concurrency/high]** [concurrency] resources/pool_alpha.py:47-50 PoolAlpha.release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release() 无条件把资源追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。同一资源被重复归还时，_free 中会出现多个引用，后续多次 acquire() 会返回同一个对象，导致资源被并发共享。触发条件：调用方重复 release 同一资源。
- **[performance/medium]** [performance] resources/pool_alpha.py:33-37 PoolAlpha.acquire() 在持锁状态下调用 factory()，可能阻塞整个池（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:33-37`
  - 依据：acquire() 在持有 self._available（即 self._lock）的情况下调用 self._factory()。若工厂创建资源耗时较长（如建立网络连接），所有其他 acquire/release 线程都会被阻塞在锁上，池吞吐严重下降。触发条件：工厂函数耗时。
- **[api_misuse/medium]** [api_misuse] resources/pool_beta.py:60-66 close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:60-66`
  - 依据：close() 取的是 self._factory 上的 close 属性（即工厂函数对象自身的 close），而非池中每个资源对象的 close。工厂函数一般没有 close 方法，导致 closer 为 None，资源永远不会被真正关闭；即便工厂碰巧有 close，也是关闭工厂而非资源，语义完全错误。正确做法应对 _free 中的每个 resource 调用其 close。
- **[concurrency/high]** [concurrency] resources/pool_beta.py:47-50 PoolBeta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现同一对象的多个副本，后续 acquire() 会把同一资源同时借给多个调用者，破坏池的互斥语义。触发条件：重复 release 同一资源。
- **[performance/medium]** [performance] resources/pool_beta.py:33-37 acquire() 在持锁状态下调用 factory()，可能阻塞整个池（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:33-37`
  - 依据：acquire() 在 with self._available 临界区内直接调用 self._factory()。工厂函数通常涉及网络连接、文件打开等耗时操作，持锁期间其他线程既无法借出空闲资源，也无法归还资源，整个池被串行阻塞，违背连接池的并发初衷。
- **[api_misuse/medium]** [api_misuse] resources/pool_delta.py:60-66 close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:60-66`
  - 依据：同 pool_alpha：close() 从 factory 上取 close 并传入 resource 调用，而非调用资源自身的 close()，无法正确释放资源。
- **[concurrency/high]** [concurrency] resources/pool_delta.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release()（或归还一个从未借出的对象），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏“池内资源总数不超过 size / 独占借出”的契约，并可能造成并发使用同一资源。
- **[performance/medium]** [performance] resources/pool_delta.py:33-37 acquire() 在持锁状态下调用 factory()，可能阻塞整个池（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:33-37`
  - 依据：factory() 在 with self._available 临界区内被调用。触发条件：factory 创建资源较慢（如建立网络连接）时，所有其他线程的 acquire/release 都会被阻塞在锁上，即使池中已有空闲资源也无法归还或借出，放大延迟甚至引发超时。
- **[api_misuse/medium]** [api_misuse] resources/pool_epsilon.py:60-66 close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:60-66`
  - 依据：与 pool_alpha.py 相同：closer 取自 self._factory 而非池中资源对象，导致资源无法被正确关闭（factory 为普通函数时 closer 为 None，资源泄漏）。触发条件：调用 close() 时。
- **[concurrency/high]** [concurrency] resources/pool_epsilon.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:47-50`
  - 依据：同 pool_alpha：release() 无条件归还，未从 _in_use 移除也未校验归属，重复归还导致同一资源被多次借出。
- **[performance/medium]** [performance] resources/pool_epsilon.py:33-37 PoolEpsilon.acquire() 在持锁状态下调用 factory()，可能阻塞整个池（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:33-37`
  - 依据：acquire() 在持有 self._available（即 self._lock）的情况下调用 self._factory()。若工厂创建资源耗时较长（如建立网络连接），所有其他 acquire/release 线程都会被阻塞在锁上，池吞吐严重下降。触发条件：工厂函数耗时。
- **[api_misuse/medium]** [api_misuse] resources/pool_eta.py:60-66 close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:60-66`
  - 依据：与 pool_delta.py 相同：从 self._factory 上取 close 属性而非从每个 resource 上取，普通工厂函数场景下空闲资源不会被关闭，造成资源泄漏。
- **[concurrency/high]** [concurrency] resources/pool_eta.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:47-50`
  - 依据：同 pool_alpha：release() 无条件归还，未从 _in_use 移除也未校验归属，重复归还导致同一资源被多次借出。
- **[performance/medium]** [performance] resources/pool_eta.py:33-37 acquire() 在持锁状态下调用 factory()，可能阻塞整个池（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:33-37`
  - 依据：与 pool_delta.py 相同：factory() 在 Condition 临界区内执行，慢速工厂会阻塞其他线程的 acquire/release。
- **[api_misuse/medium]** [api_misuse] resources/pool_gamma.py:60-66 PoolGamma.close() 通过 factory 的 close 属性关闭资源，语义错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_gamma.py:60-66`
  - 依据：close() 从 self._factory 上取 close 属性并对空闲资源调用，而 factory 是资源工厂，其 close 属性与资源自身的关闭方法无关。正确做法是调用每个 resource 的 close()。factory 无 close 属性时资源不会被关闭（泄漏）。触发条件：调用 close()。
- …另有 26 条未列出

## 待验证（孤证）

- **[boundary/low]** [boundary] resources/pool_alpha.py:38-41 acquire() 超时等待使用 wait(remaining) 但未处理虚假唤醒后的剩余时间（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:38-41`
  - 依据：wait(remaining) 返回后循环重新计算 deadline - time.monotonic()，因此虚假唤醒或提前唤醒都会被重新评估，remaining <= 0 时抛 TimeoutError。逻辑正确，不构成缺陷。
- **[resource_leak/low]** [resource_leak] resources/pool_alpha.py:60-66 close() 未清空 _in_use，已借出资源不被关闭（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：close() 只关闭空闲资源是常见设计（借出中的资源由调用方负责归还/关闭），且 _in_use 保留用于统计。这属于设计取舍而非明确缺陷，故不报告为缺陷。
- **[logic/low]** [logic] resources/pool_delta.py:30-37 acquire() 使用 id(resource) 跟踪在用资源，存在 id 复用风险（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:30-37`
  - 依据：虽然 _in_use 用 id() 记录，但资源对象在借出期间被 _free 移除且仍被调用方引用，不会被 GC 回收，因此 id 不会在借出期间被复用；release() 也不依赖 _in_use 做校验。在当前实现下不构成实际缺陷（真正的问题在 release 缺少校验，已单独报告）。
- **[logic/low]** [logic] resources/pool_eta.py:30-37 acquire() 使用 id(resource) 跟踪在用资源，存在 id 复用风险（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_eta.py:30-37`
  - 依据：同 pool_delta.py：借出期间资源被调用方持有，id 不会被复用，当前实现下不构成实际缺陷。
- **[logic/low]** [logic] scheduling/scheduler_beta.py:60-63 cancel() 只从 _items 删除，堆中残留项由 take() 惰性清理，行为正确（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:60-63`
  - 依据：cancel() 从 _items 删除后，堆中残留的 _Item 会在 take() 中因 item.name not in self._items 被跳过并丢弃，pending() 也基于 _items 计数，语义一致。这是标准的惰性删除模式，不构成缺陷。
- **[logic/medium]** [logic] wire/codec_alpha.py:45-46 CodecAlpha.total_size() 依赖 decode() 的 size 字段，v2 载荷下恒为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_alpha.py:45-46`
  - 依据：total_size() 对每个载荷调用 decode() 后取 ['size']。由于 decode() 对 v2 载荷读取不存在的 'size' 键而返回 0，total_size() 对 v2 载荷恒返回 0，无法反映真实总大小。这是 decode() 缺陷的直接下游后果。触发条件：传入 v2 载荷列表。
- **[logic/medium]** [logic] wire/codec_delta.py:45-46 CodecDelta.total_size() 依赖 decode() 的 size 字段，v2 载荷下恒为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_delta.py:45-46`
  - 依据：total_size() 对每个载荷调用 decode() 后取 ["size"] 求和。由于 decode() 对 v2 载荷错误地读取不存在的 size 字段（见上一条），v2 载荷的 size 恒为 0，total_size() 对 v2 数据总是返回 0，统计结果错误。
- **[logic/medium]** [logic] wire/codec_epsilon.py:45-46 CodecEpsilon.total_size() 依赖 decode() 的 size 字段，v2 载荷下恒为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_epsilon.py:45-46`
  - 依据：total_size() 对每个载荷调用 decode() 后取 ["size"] 求和。由于 decode() 对 v2 载荷读不到 size_bytes（见上一条），size 恒为 0，total_size() 对 v2 载荷永远返回 0，统计结果错误。
- **[logic/medium]** [logic] wire/codec_eta.py:45-46 CodecEta.total_size() 依赖 decode() 的 size 字段，v2 载荷下恒为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_eta.py:45-46`
  - 依据：total_size() 对每个载荷调用 decode() 并累加其 "size" 字段。由于 decode() 对 v2 载荷错误地读取 "size"（实际字段为 size_bytes），该字段恒为 0，因此 total_size() 对任何 v2 载荷列表都返回 0，无法反映真实总大小。
- **[logic/medium]** [logic] wire/codec_gamma.py:45-46 CodecGamma.total_size() 依赖 decode() 的 size 字段，v2 载荷下恒为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_gamma.py:45-46`
  - 依据：total_size() 通过 decode() 取 size 求和，而 decode() 对 v2 载荷无法读出 size_bytes，size 恒为 0，因此对 v2 载荷的求和结果始终为 0，统计失效。
- **[logic/low]** [logic] wiring/registry_alpha.py:43-44 RegistryAlpha.clear 只清实例不清 _build_count，计数语义不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_alpha.py:43-44`
  - 依据：clear() 仅清空 _instances 而保留 _build_count，这是合理的：build_count 表示累计构造次数，clear 后再次 get 会重新构造并继续累加，符合“累计”语义，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_delta.py:43-44 clear() 只清空实例缓存，build_count 不重置（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_delta.py:43-44`
  - 依据：clear() 清空 _instances 后，_build_count 保留历史累计值。build_count() 的语义是“累计构造次数”，clear() 只负责使缓存失效以便重新构造，并不承诺重置计数器。没有文档说明 clear() 应重置计数，因此不构成缺陷。
- **[logic/low]** [logic] wiring/registry_epsilon.py:43-44 RegistryEpsilon.clear 只清实例不清 _build_count，计数与状态不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_epsilon.py:43-44`
  - 依据：clear() 只清空 _instances，保留 _build_count。build_count 语义是“累计构造次数”，clear 后重新 get 会再次构造并累加，这符合累计计数语义，并非缺陷；若期望的是“当前存活实例数”则应由调用方另行统计。
- **[logic/low]** [logic] wiring/registry_eta.py:43-44 RegistryEta.clear 只清实例不清 _build_count，计数与状态不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_eta.py:43-44`
  - 依据：同 RegistryEpsilon：build_count 为累计构造次数，clear 后重新构造继续累加符合该语义，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_gamma.py:45-46 RegistryGamma.clear 只清实例不清 build_count，计数与实际构造不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:45-46`
  - 依据：clear() 仅清空 _instances，_build_count 保留。这是累计构造次数的语义（build_count 表示历史构造总数），clear 后再次 get 会重新构造并递增计数，行为自洽，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_zeta.py:43-44 clear() 只清空实例缓存，build_count 不重置（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_zeta.py:43-44`
  - 依据：与 registry_delta.py 相同：clear() 仅清空 _instances，_build_count 作为累计构造计数保留是合理语义，不构成缺陷。

## 争议（需裁决）

- **[logic/high]** [logic] scheduling/scheduler_beta.py:44-50 reprioritize() 直接修改堆内元素优先级，破坏堆序导致调度顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:44-50`
  - 依据：reprioritize() 直接对堆中已存在的 _Item 对象赋值 item.priority，但没有重新调整堆结构（heapq 不会感知元素内部字段变化）。堆的不变式被破坏后，take() 的 heappop 会返回错误的顺序：被提权的作业可能仍排在后面，被降权的作业可能仍被优先取出。触发条件：任何在 add() 之后、take() 之前调用 reprioritize() 的场景，这正是文档中描述的饥饿缓解用法。
  - 争议对手：c064a02e93a6
- **[logic/high]** [logic] scheduling/scheduler_epsilon.py:44-50 reprioritize() 直接修改堆内元素优先级，破坏堆序导致调度顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_epsilon.py:44-50`
  - 依据：与 scheduler_beta.py 相同：直接修改堆内元素 priority 而不重建堆，破坏堆序，take() 会返回错误的作业顺序。
  - 争议对手：95e6cbac8bbf
- **[logic/high]** [logic] wire/codec_beta.py:33-40 decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_beta.py:33-40`
  - 依据：encode() 在 v2 下写入的字段是 size_bytes，而 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，v2 载荷中并不存在 size 键，因此解码结果 size 恒为 0，编码时的大小信息被丢弃。触发条件：对 encode() 产生的 v2 载荷调用 decode()。
  - 争议对手：c2b484f6ea1f
- **[logic/high]** [logic] wire/codec_eta.py:33-40 decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_eta.py:33-40`
  - 依据：encode() 在 v2 下写入的字段是 size_bytes，而 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)。触发条件：对 encode() 产生的 v2 载荷调用 decode()，由于载荷中没有 "size" 键，out["size"] 恒为 0，大小信息丢失。total_size() 依赖 decode()["size"]，因此对 v2 载荷求和恒为 0。
  - 争议对手：f5d306bf0ccd
- **[logic/high]** [logic] wire/codec_theta.py:33-40 decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_theta.py:33-40`
  - 依据：与 codec_beta.py 相同：encode() 写入 size_bytes，decode() 的 v2 分支却读取 size，导致 v2 载荷解码后 size 恒为 0，大小信息丢失。触发条件：对 encode() 产生的 v2 载荷调用 decode()。
  - 争议对手：3655451e93de
- **[logic/high]** [logic] wire/codec_zeta.py:33-40 CodecZeta.decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_zeta.py:33-40`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version>=2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 字段，因此解码结果 size 恒为 0，丢失真实大小。触发条件：解码 v2 载荷。
  - 争议对手：85566595cc11

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 1 | 3 | 1 | 0 | 1 | 0 | 3 | 3 |
| `scheduling` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 27%（单元格值 = 独立 Agent 数）
