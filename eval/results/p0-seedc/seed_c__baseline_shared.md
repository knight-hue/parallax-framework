# Parallax 运行报告 `4e7863205788`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 47 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 4 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：6 个（每轮全新身份）
- 账本条目：294

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 6 | 52 | 100% | 12% |

## 高置信结论

- **[logic/high]** [logic] analytics/window_alpha.py:24-27 WindowAlpha 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只增不减。因此当窗口满后继续 add，_total 会持续累加所有历史样本，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口大小，分子却是全部历史之和，均值随样本增多而虚高。触发条件：add 次数超过 size。
- **[logic/high]** [logic] analytics/window_beta.py:24-27 WindowBeta 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:24-27`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只增不减，mean() 用累积总和除以当前窗口长度，样本数超过 size 后均值错误。
- **[logic/high]** [logic] analytics/window_delta.py:24-27 WindowDelta 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:24-27`
  - 依据：deque(maxlen=size) 淘汰旧样本时 _total 未相应减少，mean() 分子包含已淘汰样本，导致窗口均值计算错误。
- **[logic/high]** [logic] analytics/window_epsilon.py:24-27 WindowEpsilon 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 _total 只增不减，因此 _total 会持续累积所有历史样本的和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度。一旦样本数超过 size，均值就会被历史数据污染并持续偏大。触发条件：add() 调用次数超过 size。
- **[logic/high]** [logic] analytics/window_eta.py:24-27 WindowEta 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不减去被淘汰的值。因此一旦窗口写满并继续 add，_total 会持续增长，而 len(self._values) 恒为 size，mean() 返回 _total/len 会远大于真实窗口均值。触发条件：add 次数超过 size（默认 32）。
- **[logic/high]** [logic] analytics/window_gamma.py:24-27 WindowGamma 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只增不减。因此当窗口满后继续 add，_total 会累积所有历史样本的和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口大小，分子却是全部历史之和，均值随样本增多而单调膨胀，完全错误。触发条件：add 次数超过 size。
- **[logic/high]** [logic] analytics/window_theta.py:24-27 WindowTheta 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:24-27`
  - 依据：add() 每次累加 self._total += value，但 deque 设置了 maxlen=size，当窗口满时 append 会自动淘汰最旧样本，而 _total 从未减去被淘汰的值。因此一旦样本数超过 size，_total 会持续偏大，mean() 返回 self._total / len(self._values) 就会高于真实窗口均值。触发条件：连续 add 超过 size 个样本后调用 mean()。
- **[logic/high]** [logic] analytics/window_zeta.py:24-27 WindowZeta 淘汰样本时未同步 _total，导致均值错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:24-27`
  - 依据：与 WindowGamma 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，超过容量后 mean() 会因残留的已淘汰样本而偏高/偏低。触发条件：add() 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-58 JournalAlpha.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的文件，二者不一致；后续 append() 还会用未裁剪的 _records 重写文件，把已压缩掉的记录重新写回磁盘。
- **[logic/high]** [logic] persistence/journal_beta.py:51-58 JournalBeta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records，内存中仍保留全部旧记录。之后 replay()/count() 返回被压缩掉的记录，而 append() 调用 _flush() 会把内存中的旧记录重新写回磁盘，使压缩结果被撤销。触发条件：compact() 后调用 replay()/count() 或再 append()。
- **[logic/high]** [logic] persistence/journal_delta.py:51-58 JournalDelta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_delta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。此后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 返回裁剪后的数量，两者不一致；再次 append() 时 _flush() 会把内存中未裁剪的完整列表重新写回磁盘，使 compact() 的效果被完全撤销。触发条件：len(_records) > keep 后调用 compact()。
- **[logic/medium]** [logic] persistence/journal_epsilon.py:51-58 JournalEpsilon.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的文件，二者不一致；再次 append() 时 _flush() 会把内存中未裁剪的全部记录重新写回磁盘，使 compact 的效果被撤销。
- **[logic/high]** [logic] persistence/journal_eta.py:51-58 JournalEta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_eta.py:51-58`
  - 依据：与 JournalEpsilon 相同：compact() 仅写盘不更新 self._records，导致 replay()/count() 与磁盘内容不一致，且后续 append() 会把被压缩掉的记录重新写回。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 JournalGamma.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：与 JournalBeta 相同：compact() 仅重写磁盘文件，未更新 self._records。压缩后 replay()/count() 仍返回被丢弃的记录，且后续 append() 的 _flush() 会把内存中的完整列表写回磁盘，撤销压缩。触发条件：compact() 后调用 replay()/count() 或再 append()。
- **[logic/high]** [logic] persistence/journal_theta.py:51-58 JournalTheta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_theta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的磁盘内容，两者不一致；后续 append() 调用 _flush() 会把内存中未裁剪的 _records 全量重写回磁盘，使 compact 的效果被撤销。触发条件：compact() 后调用 replay()/count() 或再 append()。
- **[logic/high]** [logic] persistence/journal_zeta.py:51-58 JournalZeta.compact() 未同步内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_zeta.py:51-58`
  - 依据：与 JournalDelta 相同：compact() 仅写盘裁剪后的 kept，未更新 self._records。replay()/count() 仍返回被丢弃记录，且后续 append() 的 _flush() 会把未裁剪的 _records 全量写回，撤销压缩效果。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] resources/pool_alpha.py:51-54 PoolAlpha.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除其 id。调用方若重复归还同一资源（或归还从未借出的资源），_free 中会出现同一对象的多个副本，后续 acquire() 会多次弹出同一资源交给不同调用者，破坏池的互斥语义；同时 _in_use 集合因从未删除而持续膨胀，stats() 的 in_use 计数永久失真。触发条件：任何一次重复 release 或错误 release。
- **[logic/high]** [logic] resources/pool_beta.py:51-54 PoolBeta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:51-54`
  - 依据：release() 无条件把传入的 resource 追加到 _free 并 notify，既不检查该资源是否真的在 _in_use 中，也不从 _in_use 中移除其 id。调用方若对同一资源调用两次 release（或归还一个从未借出的对象），_free 中会出现重复条目，后续两次 acquire 会返回同一个对象，破坏“池内资源总数不超过 size、同一资源同时只被一个借用者持有”的契约。
- **[logic/high]** [logic] resources/pool_delta.py:51-54 PoolDelta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:51-54`
  - 依据：release() 无条件把资源 append 到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：同一资源被 release 两次（或释放从未借出的资源），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏“池内资源总数不超过 size”的互斥保证。
- **[logic/high]** [logic] resources/pool_epsilon.py:51-54 PoolEpsilon.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:51-54`
  - 依据：与 PoolBeta 相同：release() 只做 append + notify，不校验 resource 是否属于本池、是否处于借出状态，也不更新 _in_use。重复归还会让同一资源在 _free 中出现多次，被并发 acquire() 同时借出。
- **[logic/high]** [logic] resources/pool_eta.py:51-54 PoolEta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:51-54`
  - 依据：与 PoolAlpha 相同：release() 直接把 resource 放入 _free 并 notify，没有验证该资源确实处于借出状态，也没有从 _in_use 中删除。重复归还会让同一资源在 _free 中出现多次，acquire() 可将其同时分配给多个线程，且 _in_use 计数只增不减。
- **[logic/high]** [logic] resources/pool_gamma.py:51-54 PoolGamma.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_gamma.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire() 会把同一对象同时借给多个调用者，破坏池的互斥语义。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] resources/pool_theta.py:51-54 PoolTheta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_theta.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现同一对象的多个副本，后续多个 acquire() 会同时拿到同一资源，破坏池的互斥语义；同时 _in_use 集合永不缩减，stats() 的 in_use 计数也失真。
- **[logic/high]** [logic] resources/pool_zeta.py:51-54 PoolZeta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_zeta.py:51-54`
  - 依据：与 PoolGamma 相同：release() 不校验资源是否属于本池、是否处于借出状态，也不从 _in_use 移除，重复归还会让 _free 中出现重复条目，acquire() 可能把同一对象同时交给多个调用者。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] scheduling/scheduler_alpha.py:47-53 SchedulerAlpha.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:47-53`
  - 依据：reprioritize() 直接对已入堆的 _Item 对象赋值 item.priority，而没有调用 heapq 的修复操作（如 _siftdown/_siftup 或先删后插）。堆的不变式依赖元素在插入后不再改变排序键；就地修改后堆序被破坏，take() 的 heappop 不再保证返回当前优先级最高的作业，调度顺序错误。文档明确说该方法用于饥饿缓解，即会被频繁调用，触发概率高。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:47-53 SchedulerBeta.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:47-53`
  - 依据：item 是已经通过 heapq.heappush 放入 _heap 的对象，reprioritize() 直接改写其 priority 字段而不调用 heapq.heapify 或做上浮/下沉调整。堆的不变式（父节点 <= 子节点）被破坏后，take() 的 heappop 不再返回真正优先级最高的作业，调度顺序错误；文档声称用于饥饿缓解的提权操作恰恰是最容易触发该问题的场景。
- **[logic/high]** [logic] scheduling/scheduler_delta.py:47-53 SchedulerDelta.reprioritize 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_delta.py:47-53`
  - 依据：reprioritize() 直接对堆中已存在的 _Item 对象赋值 item.priority，而没有重新调整堆结构（heapq 不感知元素内部字段变化）。修改后堆序不再满足小顶堆性质，take() 的 heappop 会返回错误的“最高优先级”作业，调度顺序出错。触发条件：对队列中已有作业调用 reprioritize() 后再 take()。
- **[logic/high]** [logic] scheduling/scheduler_epsilon.py:47-53 SchedulerEpsilon.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_epsilon.py:47-53`
  - 依据：同 SchedulerBeta：reprioritize() 就地修改堆中 _Item 的 priority，未重建堆。堆序被破坏后 heappop 返回的并非当前最高优先级作业，take()/drain() 的顺序不可靠。
- **[logic/high]** [logic] scheduling/scheduler_eta.py:47-53 SchedulerEta.reprioritize 直接改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_eta.py:47-53`
  - 依据：reprioritize 直接修改堆中 _Item 的 priority 字段，但没有调用 heapq 的修复操作（如 _siftdown/_siftup 或重建堆）。修改后堆序不再成立，take() 弹出的不一定是当前最高优先级作业，调度顺序错误。触发条件：对已入队作业调用 reprioritize 后再 take()。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:47-53 SchedulerGamma.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:47-53`
  - 依据：同 SchedulerAlpha：reprioritize() 原地修改堆中元素的 priority 字段，未重建堆序，导致后续 heappop 返回的并非真正的最小优先级作业。
- **[logic/high]** [logic] scheduling/scheduler_theta.py:47-53 SchedulerTheta.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_theta.py:47-53`
  - 依据：同 SchedulerBeta/Epsilon：直接改堆内元素 priority 而不修复堆，导致 take() 顺序错误。
- **[logic/high]** [logic] wire/codec_alpha.py:33-35 CodecAlpha.decode 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_alpha.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version>=2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 键，因此解码结果 size 恒为 0，编码时写入的 size_bytes 被丢弃。触发条件：对 encode() 的输出调用 decode()。
- **[logic/high]** [logic] wire/codec_beta.py:33-35 CodecBeta.decode() 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_beta.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version>=2 分支读取 payload.get("size", 0)。v2 载荷没有 size 键，因此解码结果 size 恒为 0，total_size() 也随之恒为 0，往返编解码丢失数据。
- **[logic/high]** [logic] wire/codec_delta.py:33-35 CodecDelta.decode 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_delta.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version>=2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 字段，因此解码结果 size 恒为 0，编码时写入的 size_bytes 被丢弃。触发条件：对 encode() 产生的 v2 载荷调用 decode()。
- **[logic/high]** [logic] wire/codec_epsilon.py:33-35 CodecEpsilon.decode 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_epsilon.py:33-35`
  - 依据：与 CodecAlpha 相同：encode() 写入 size_bytes，decode() 的 v2 分支却读取 size，导致解码后 size 恒为 0，total_size() 也随之返回 0。
- **[logic/high]** [logic] wire/codec_eta.py:33-35 CodecEta.decode 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_eta.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version>=2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 字段，因此解码结果 size 恒为 0，往返不一致。触发条件：对 encode() 产生的 v2 载荷调用 decode()。
- **[logic/high]** [logic] wire/codec_gamma.py:33-35 CodecGamma.decode() 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_gamma.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 键，因此总是回退为 0，编码时写入的 size_bytes 被丢弃。触发条件：encode() 后 decode() 往返，或直接解码 v2 载荷。total_size() 依赖 decode()["size"]，也会全部返回 0。
- **[logic/high]** [logic] wire/codec_theta.py:33-35 CodecTheta.decode() 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_theta.py:33-35`
  - 依据：与 CodecBeta 相同：encode() 写 size_bytes，decode() 的 v2 分支读 size。触发条件：decode(encode(record)) 时 size 恒为 0，total_size() 结果错误。
- **[logic/high]** [logic] wire/codec_zeta.py:33-35 CodecZeta.decode() 对 v2 载荷读取 size 而非 size_bytes，丢失编码值（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_zeta.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，而 v2 线格式中并不存在 size 键，因此解码结果 size 恒为 0，encode/decode 往返丢失数据。
- **[concurrency/medium]** [concurrency] wiring/registry_alpha.py:25-28 RegistryAlpha.get 的检查-构造-缓存非原子，并发下可能构造多个实例（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wiring/registry_alpha.py:25-28`
  - 依据：get() 先检查 name 是否在 _instances 中，再调用 _build 构造并写回缓存，整个过程没有加锁。两个线程同时首次 get 同一名字时都会看到缓存缺失，各自构造一个实例，违反“同名组件进程内只应存在一个实例”的约定，且 build_count 会多计。触发条件：多线程并发首次访问同一未缓存组件。
- …另有 7 条未列出

## 待验证（孤证）

- **[error_handling/low]** [error_handling] persistence/journal_epsilon.py:24-28 JournalEpsilon._load() 对损坏行直接抛异常，无容错（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:24-28`
  - 依据：json.loads 对非空但格式错误的行会抛 JSONDecodeError，导致构造对象失败。但这是追加式日志的常见取舍，且文件由本类自身写入，正常路径不会产生坏行；没有证据表明这是被引入的缺陷，故不认定为缺陷。
- **[concurrency/low]** [concurrency] resources/pool_delta.py:33-37 acquire() 在持锁状态下调用工厂函数（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:33-37`
  - 依据：acquire() 在持有 _available（即 _lock）时调用 self._factory()。若工厂函数本身会回调池的 release()/acquire()，会因非重入锁而死锁；但工厂的契约是“新建一个资源”，正常实现不会回调池，且持锁构造可保证 _created 计数与资源创建的一致性。因此按现有契约不构成缺陷。
- **[resource_leak/low]** [resource_leak] resources/pool_delta.py:63-69 close() 未清理 _in_use，已借出资源仍被计入统计（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:63-69`
  - 依据：close() 只关闭并清空 _free 中的空闲资源，不触碰 _in_use。这是合理的：已借出的资源仍由调用方持有，池不应擅自关闭它们；_in_use 保留用于统计在借数量。因此不构成缺陷。
- **[logic/medium]** [logic] scheduling/scheduler_zeta.py:63-67 SchedulerZeta.cancel() 只删索引不删堆元素，pending() 与堆内容不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_zeta.py:63-67`
  - 依据：cancel() 从 _items 删除名字，堆中残留的 _Item 会在 take() 时通过 `if item.name in self._items` 被跳过，pending() 返回 len(self._items) 也正确。这是常见的惰性删除模式，行为正确，只是堆会暂时保留已取消元素。因此不构成缺陷。

## 争议（需裁决）

- **[logic/high]** [logic] scheduling/scheduler_zeta.py:47-53 SchedulerZeta.reprioritize() 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_zeta.py:47-53`
  - 依据：reprioritize() 直接对堆中已存在的 _Item 对象赋值 item.priority，但没有调用 heapq 的修复操作（如 _siftup/_siftdown 或重新 heapify）。堆的不变式被破坏后，take() 的 heappop 不再保证返回当前优先级最高的作业，调度顺序错误。触发条件：对队列中尚未出队的作业调用 reprioritize()。
  - 争议对手：2406a8d5f4b0, a3d41e09755d

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 6 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `resources` | 6 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| `scheduling` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 19%（单元格值 = 独立 Agent 数）
