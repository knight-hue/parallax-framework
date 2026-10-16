# Parallax 运行报告 `4e7863205788`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 53 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 26 | 单一来源孤证 |
| 争议 | 12 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：6 个（每轮全新身份）
- 账本条目：370

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 6 | 91 | 100% | 25% |

## 高置信结论

- **[logic/high]** [logic] analytics/window_alpha.py:24-27 WindowAlpha._total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 add() 只做 self._total += value，从不扣减被淘汰的值。因此当样本数超过 size 后，_total 会持续累加所有历史值，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口大小，分子却是全部历史之和，均值会随写入次数单调膨胀，完全错误。触发条件：向窗口写入超过 size 个样本后调用 mean()。
- **[logic/high]** [logic] analytics/window_beta.py:24-27 WindowBeta._total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:24-27`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 自动淘汰旧样本，但 _total 只增不减，mean() 用 _total 除以当前窗口长度，窗口满后均值被高估。
- **[logic/high]** [logic] analytics/window_delta.py:24-27 WindowDelta._total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:24-27`
  - 依据：deque(maxlen=size) 淘汰旧样本时 _total 未扣减，mean() 分子包含已淘汰样本，窗口满后均值错误。
- **[logic/high]** [logic] analytics/window_epsilon.py:24-27 WindowEpsilon._total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:24-27`
  - 依据：deque(maxlen=size) 在 append 超出容量时会自动丢弃最旧样本，但 add() 只做 self._total += value，从不扣减被淘汰样本的值。因此当样本数超过 size 后，_total 会持续累加所有历史样本，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，均值会随写入次数单调膨胀，完全错误。触发条件：add() 调用次数超过 size（默认 32）。
- **[logic/high]** [logic] analytics/window_eta.py:24-27 WindowEta 的 _total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:24-27`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 add() 只做 self._total += value，从不减去被淘汰的值。因此一旦样本数超过 size，_total 会持续累加所有历史样本，而 mean() 用 _total / len(self._values)（分母是当前窗口长度），结果被系统性放大。触发条件：add() 调用次数超过 size（默认 32）。
- **[logic/high]** [logic] analytics/window_gamma.py:24-27 WindowGamma 的 _total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:24-27`
  - 依据：add() 使用 deque(maxlen=size) 追加样本，当窗口已满时 append 会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此一旦样本数超过 size，mean() 返回的 _total/len(_values) 会包含已被淘汰的旧样本之和，均值随样本增多而持续偏大，与窗口语义不符。触发条件：连续 add 超过 size 个样本后调用 mean()。
- **[logic/high]** [logic] analytics/window_theta.py:22-25 WindowTheta.mean() 在 deque 淘汰旧样本后仍使用累计总和，均值计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:22-25`
  - 依据：add() 每次把 value 累加到 self._total，但 deque 设置了 maxlen=size，当样本数超过 size 时最旧样本被自动丢弃，而 _total 并未相应扣减。因此一旦窗口满，mean() 返回的 _total/len(_values) 会包含已被淘汰样本的贡献，结果偏大且随写入次数持续漂移。触发条件：连续 add 超过 size 个样本后调用 mean()。
- **[logic/high]** [logic] analytics/window_zeta.py:24-27 WindowZeta._total 在 deque 淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:24-27`
  - 依据：与 WindowGamma 相同：deque(maxlen=size) 在 append 时自动淘汰最旧样本，但 add() 只累加 _total，不扣减被淘汰的值。窗口满后 mean() 的分子包含全部历史样本之和，分母仅为当前窗口长度，结果错误。触发条件：add 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-58 JournalAlpha.compact() 未更新内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有把 self._records 更新为 kept。因此压缩后内存中仍保留全部旧记录，而磁盘只剩最近 keep 条。后续 append() 调用 _flush() 会用未裁剪的 self._records 重写文件，把已丢弃的旧记录重新写回磁盘，压缩失效；replay()/count() 返回的也是未压缩的数据。触发条件：记录数超过 keep 后调用 compact()，再调用 append() 或 replay()。
- **[logic/high]** [logic] persistence/journal_beta.py:55-62 JournalBeta.compact() 未同步内存 _records，导致 replay 与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_beta.py:55-62`
  - 依据：compact() 只把截断后的 kept 写入磁盘，却没有更新 self._records。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是截断后的文件，二者不一致；后续 append() 还会用未截断的 _records 重写文件，把已丢弃的记录重新写回磁盘。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_delta.py:51-58 JournalDelta.compact() 未更新内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_delta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写回磁盘，却没有把 self._records 替换为 kept。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的文件，二者不一致；再次 append() 时 _flush() 会把内存中未裁剪的全部记录重新写回磁盘，使 compact 的效果被撤销。触发条件：len(_records) > keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_epsilon.py:51-58 compact() 未更新内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:51-58`
  - 依据：compact() 只把截断后的 kept 写入磁盘，却没有把 self._records 替换为 kept。触发条件：append 若干条使 len(_records) > keep，调用 compact()。此后 replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，两者不一致；再次 append() 时 _flush() 会把内存中未截断的旧记录全部写回磁盘，使压缩结果被撤销。
- **[logic/high]** [logic] persistence/journal_eta.py:51-58 compact() 未更新内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_eta.py:51-58`
  - 依据：与 journal_epsilon.py 相同：compact() 只写磁盘不更新 self._records。触发条件：append 超过 keep 条后调用 compact()，replay()/count() 仍返回全部记录，且下一次 append() 的 _flush() 会把未截断的记录全部写回，撤销压缩效果。
- **[logic/high]** [logic] persistence/journal_gamma.py:55-62 JournalGamma.compact() 未同步内存 _records，导致 replay 与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_gamma.py:55-62`
  - 依据：与 JournalBeta 相同：compact() 只写磁盘不更新 self._records，replay()/count() 与 disk_count() 不一致，且后续 append() 会把已丢弃记录重新写回。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_theta.py:51-58 JournalTheta.compact() 未更新内存 _records，内存与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_theta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有把 self._records 替换为 kept。之后 replay()/count() 仍返回被丢弃的旧记录，而 disk_count() 反映的是裁剪后的数量，二者不一致；后续 append() 调用 _flush() 时还会把内存中未裁剪的全部记录重新写回磁盘，使 compact 的效果被撤销。触发条件：记录数超过 keep 后调用 compact()，再调用 replay()/count() 或 append()。
- **[logic/high]** [logic] persistence/journal_zeta.py:55-62 JournalZeta.compact() 未同步内存 _records，导致 replay 与磁盘不一致（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`persistence/journal_zeta.py:55-62`
  - 依据：与 JournalDelta 相同：compact() 仅重写磁盘文件，未更新 self._records。replay()/count() 返回未裁剪的记录，disk_count() 返回裁剪后的数量，二者不一致；后续 append() 会用未裁剪的 _records 重写文件，把已丢弃记录恢复，使压缩无效。触发条件：len(_records) > keep 后调用 compact()。
- **[concurrency/high]** [concurrency] resources/pool_alpha.py:51-54 release() 不校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release()（或归还一个从未借出的对象），_free 中会出现同一对象的两个引用，后续两次 acquire() 会返回同一个资源实例，导致资源被并发重复使用；同时 _in_use 集合永远不缩小，stats() 的 in_use 计数失真。
- **[logic/high]** [logic] resources/pool_alpha.py:51-54 release 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_alpha.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire() 会把同一对象同时交给多个调用者，破坏池的互斥语义；同时 _in_use 集合永不缩小，stats() 的 in_use 计数失真。触发条件：对同一资源调用 release 两次。
- **[concurrency/high]** [concurrency] resources/pool_beta.py:51-54 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:51-54`
  - 依据：release() 无条件把资源追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire() 会把同一资源同时借给多个调用方，破坏池的互斥语义。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] resources/pool_beta.py:51-54 release() 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_beta.py:51-54`
  - 依据：release() 无条件把资源 append 到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。调用方重复归还同一资源时，_free 中会出现同一对象的多个副本，后续 acquire 会把同一资源同时借给多个调用方，破坏池的互斥语义。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:64-70 close() 未清理 _in_use 且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:64-70`
  - 依据：close() 只关闭并清空 _free，不清理 _in_use，也不设置关闭标志。关闭后 _created 仍为原值，若 _created 已达 size，后续 acquire 会因 _created < _size 为假而永久等待直至超时；同时 _in_use 中残留的 id 使 stats() 报告错误的在用数量，已借出资源也不会被关闭。
- **[concurrency/high]** [concurrency] resources/pool_delta.py:51-54 release() 不校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release()（或归还从未借出的资源），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏“池内资源总数不超过 size”的互斥保证，导致并发使用同一资源。
- **[logic/high]** [logic] resources/pool_delta.py:51-54 release() 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_delta.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release()（或归还一个从未借出的对象）。此时 _free 中出现重复条目，后续两次 acquire() 会返回同一个对象，破坏“借出资源互斥”的池语义；同时 _in_use 集合因从未移除而持续增长，stats() 的 in_use 计数失真。
- **[resource_leak/medium]** [resource_leak] resources/pool_delta.py:64-70 close() 未清理 _in_use，且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:64-70`
  - 依据：close() 只关闭并清空 _free 中的空闲资源，不处理 _in_use 中已借出的资源，也不设置关闭标志。触发条件：在仍有资源被借出时调用 close()，之后调用方归还这些资源，它们会被重新放入 _free 并可被再次 acquire，而底层资源可能已被关闭；同时 _created 计数不变，池无法真正释放。
- **[concurrency/high]** [concurrency] resources/pool_epsilon.py:51-54 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:51-54`
  - 依据：与 pool_beta.py 相同：release() 无条件把资源放回 _free，不校验资源是否在 _in_use 中，也不从 _in_use 移除。重复归还同一资源会导致该资源被多次借出，破坏池的互斥语义。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] resources/pool_epsilon.py:52-55 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_epsilon.py:52-55`
  - 依据：与 pool_beta.py 相同：release() 不校验资源是否属于本池、是否处于借出状态，也不从 _in_use 中移除 id。重复归还会让 _free 出现重复条目，导致同一资源被并发借出，且 _in_use 永不减少。
- **[resource_leak/medium]** [resource_leak] resources/pool_epsilon.py:63-69 close() 未清理 _in_use，且不阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:63-69`
  - 依据：与 pool_beta.py 相同：close() 未清理 _in_use，也未阻止后续 acquire，关闭后池仍可继续借出资源，状态泄漏。触发条件：调用 close() 后再调用 acquire()。
- **[concurrency/high]** [concurrency] resources/pool_eta.py:51-54 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:51-54`
  - 依据：与 pool_alpha.py 相同：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。重复归还或归还未借出的资源会让 _free 中出现同一对象的多个引用，后续 acquire() 可能把同一资源同时借给多个调用方；_in_use 集合也因从不删除而永久膨胀。
- **[logic/high]** [logic] resources/pool_eta.py:51-54 release 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_eta.py:51-54`
  - 依据：与 pool_alpha.py 相同：release() 无条件把 resource 追加到 _free 并 notify，不检查归属、不从 _in_use 移除。重复归还会使 _free 出现重复条目，acquire() 可能把同一对象同时借给多个调用者，且 _in_use 计数失真。触发条件：对同一资源调用 release 两次。
- **[concurrency/high]** [concurrency] resources/pool_gamma.py:51-54 PoolGamma.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_gamma.py:51-54`
  - 依据：release() 无条件把资源追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不检查是否已归还。若调用方重复 release 同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire() 会把同一对象同时交给多个调用者，破坏池的互斥语义。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] resources/pool_gamma.py:51-54 PoolGamma.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_gamma.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire() 会把同一对象同时借给多个调用者，破坏池的互斥语义；同时 _in_use 集合因从未删除而持续膨胀，stats() 的 in_use 永远不下降。触发条件：对同一资源调用 release() 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:64-70 PoolGamma.close() 未清理 _in_use 且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_gamma.py:64-70`
  - 依据：close() 只关闭并清空 _free，不重置 _created、不清空 _in_use，也没有设置关闭标志。关闭后调用 acquire() 时，由于 _created 仍等于 size 且 _free 为空，会一直等待直到超时抛 TimeoutError；而 _in_use 中残留的 id 使 stats() 永远显示有资源在用，已借出的资源归还后还会被放回已关闭的池。触发条件：close() 之后再调用 acquire()/release()/stats()。
- **[concurrency/high]** [concurrency] resources/pool_theta.py:51-54 PoolTheta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_theta.py:51-54`
  - 依据：release() 无条件把资源 append 回 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏池的独占语义；同时 _in_use 集合因从未移除而永久膨胀，stats() 的 in_use 计数失真。触发条件：同一资源被 release 两次。
- **[logic/high]** [logic] resources/pool_theta.py:51-54 PoolTheta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_theta.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若同一资源被 release 两次，_free 中会出现两个相同引用，后续两次 acquire 会返回同一个对象，破坏池的互斥语义；同时 _in_use 集合永远不缩小，stats() 的 in_use 计数失真。
- **[resource_leak/medium]** [resource_leak] resources/pool_theta.py:63-69 PoolTheta.close() 未清理 _in_use，且不阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_theta.py:63-69`
  - 依据：close() 只关闭并清空 _free，没有清空 _in_use，也没有设置关闭标志。关闭后 _created 仍等于原值，若 _created < _size 则 acquire() 仍会通过 factory() 新建资源并成功返回，池在“已关闭”后继续工作；同时 _in_use 中残留的 id 使 stats() 长期虚高，已借出资源永远不会被回收。触发条件：调用 close() 后再调用 acquire()。
- **[concurrency/high]** [concurrency] resources/pool_zeta.py:51-54 PoolZeta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_zeta.py:51-54`
  - 依据：与 PoolGamma 相同：release() 无条件将 resource 放入 _free，不校验其是否属于 _in_use，也不从 _in_use 中移除。重复归还同一资源会让 _free 出现重复条目，acquire() 可能把同一资源同时分配给多个调用者，且 _in_use 计数永久泄漏。触发条件：对同一资源调用 release() 两次。
- **[logic/high]** [logic] resources/pool_zeta.py:51-54 PoolZeta.release() 未校验资源归属，重复归还导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r0-3｜置信度 0.5
  - 源：`resources/pool_zeta.py:51-54`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。重复归还同一资源会使 _free 出现重复条目，后续 acquire() 可能把同一对象同时借给多个调用者；_in_use 集合因从不删除而持续膨胀，stats() 的 in_use 永不下降。触发条件：对同一资源调用 release() 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_zeta.py:65-71 PoolZeta.close() 只关闭空闲资源，未关闭在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_zeta.py:65-71`
  - 依据：close() 仅关闭 _free 中的资源，_in_use 中的资源不会被关闭而泄漏；且没有 closed 状态，close() 之后 acquire() 仍可新建/借出资源，池无法真正关闭。触发条件：存在在用资源时调用 close()，或 close() 后继续 acquire()。
- **[logic/high]** [logic] scheduling/scheduler_eta.py:47-53 SchedulerEta.reprioritize() 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_eta.py:47-53`
  - 依据：reprioritize() 通过 self._items[name] 拿到堆中 _Item 对象并直接赋值 item.priority。该对象同时存在于 self._heap 列表中，原地修改其排序键不会触发 heapq 的 sift 操作，堆不变量被破坏。此后 take() 的 heapq.heappop 不再保证返回当前优先级最高的作业，可能返回优先级较低者。触发条件：对已入队作业调用 reprioritize() 后再 take()。
- **[logic/high]** [logic] wire/codec_alpha.py:33-35 CodecAlpha.decode 对 v2 载荷读取 size 而非 size_bytes，丢失实际大小（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_alpha.py:33-35`
  - 依据：encode() 把大小写入 size_bytes 字段，v2 线格式中并不存在 size 键。decode() 在 version >= 2 分支却读取 payload.get("size", 0)，因此对任何由本编解码器产生的 v2 载荷都会得到默认值 0，实际大小丢失。total_size() 依赖 decode()["size"]，会恒返回 0。触发条件：decode 一个 v2 载荷（含 size_bytes）。
- …另有 13 条未列出

## 待验证（孤证）

- **[boundary/low]** [boundary] analytics/window_gamma.py:47-51 WindowGamma.percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`analytics/window_gamma.py:47-51`
  - 依据：ratio 若大于 1 或小于 0，index 会越界导致 IndexError。但该函数签名未声明 ratio 的合法范围，且调用方按分位语义通常传入 [0,1] 内的值；在给定代码范围内没有证据表明存在越界调用，因此不认定为缺陷，仅记录边界行为。
- **[boundary/low]** [boundary] persistence/journal_epsilon.py:55-61 compact() 的 keep 为负时切片行为异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:55-61`
  - 依据：若 keep 为负数，surplus 会大于 len(_records)，kept = self._records[surplus:] 得到空列表，磁盘被清空，返回值 surplus 大于实际记录数。但 keep 由构造参数给出，负值属于调用方误用，且不会引发异常或数据损坏之外的行为，故不判为缺陷。
- **[performance/low]** [performance] persistence/journal_epsilon.py:71-75 disk_count() 每次调用都重新读取整个文件（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:71-75`
  - 依据：disk_count() 重新读盘是为了反映磁盘真实状态（与内存 _records 可能不一致），这是有意的设计选择而非缺陷；在记录量不大时开销可接受。
- **[api_misuse/low]** [api_misuse] resources/pool_alpha.py:66-72 close() 通过工厂的 close 属性关闭资源，语义可疑但非缺陷（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:66-72`
  - 依据：close() 用 getattr(self._factory, "close", None) 取工厂自身的 close 方法，再对每个空闲资源调用 closer(resource)。虽然把“关闭资源”的职责挂在工厂对象上略显奇怪，但这是该 API 的既定约定（工厂可提供 close(resource) 钩子），且 callable 检查保证工厂没有 close 时不会报错。未发现会导致错误行为的路径，故不认定为缺陷。
- **[logic/medium]** [logic] resources/pool_alpha.py:36-40 acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:36-40`
  - 依据：_in_use 保存的是 id(resource)。CPython 中 id 是对象存活期间的内存地址，一旦对象被回收，同一 id 可能被新对象复用。触发条件：借出的资源在未归还前被外部释放（引用计数归零），随后 factory 新建的对象恰好分配到同一地址，_in_use.add(id(resource)) 会与残留条目冲突，使 in_use 计数错误、无法区分两个不同资源。
- **[api_misuse/low]** [api_misuse] resources/pool_beta.py:66-72 close() 通过工厂的 close 属性关闭资源，语义可疑但非必然缺陷（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_beta.py:66-72`
  - 依据：close() 从 self._factory 上取 close 属性并逐个调用 closer(resource)。虽然把工厂的 close 当作资源关闭器在语义上有些奇怪，但代码本身逻辑自洽：若工厂没有 close 属性则 callable(closer) 为 False，不会抛错；若工厂提供了 close(resource) 接口则行为正确。没有可引用的证据表明它必然导致错误行为，故不判定为缺陷。
- **[logic/medium]** [logic] resources/pool_beta.py:36-40 acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_beta.py:36-40`
  - 依据：acquire() 用 id(resource) 记录在用资源，但 _in_use 只保存整数 id 而不持有对象引用。若资源在借出期间被释放（例如调用方丢弃引用），其 id 可能被新对象复用，导致 _in_use 中出现错误的 id，stats() 的 in_use 计数失真，且无法正确判断资源归属。触发条件：借出的资源被回收后新对象复用同一 id。
- **[boundary/low]** [boundary] resources/pool_delta.py:36-38 acquire() 在等待期间不检查池是否已关闭（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:36-38`
  - 依据：close() 只清理 _free 中的空闲资源，不改变 _created 或设置关闭标志，因此等待中的 acquire() 在超时前仍可能通过 _created < _size 新建资源。这属于 close() 语义不完整，但当前代码并未承诺 close() 后禁止 acquire，且不会造成崩溃或资源泄漏（新建资源由调用方持有），因此不单独判为缺陷。
- **[concurrency/low]** [concurrency] resources/pool_delta.py:33-37 acquire() 在持锁状态下调用工厂函数（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:33-37`
  - 依据：工厂在 _available 条件锁内被调用，若工厂阻塞会拖住其他等待者。但这是定长池的常见实现取舍，且代码本身没有引入死锁（工厂不回调池方法），不构成可确证的缺陷，故记录为非缺陷。
- **[error_handling/low]** [error_handling] resources/pool_delta.py:28-42 acquire() 在等待期间不检查池是否已关闭（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:28-42`
  - 依据：close() 只清理空闲资源，并不改变 _created 或设置关闭标志，因此等待中的 acquire() 在超时后仍会抛 TimeoutError，不会永久阻塞或返回已关闭资源。虽然缺少“池已关闭”的显式错误，但这是设计取舍而非可证实的错误行为，故不认定为缺陷。
- **[logic/medium]** [logic] resources/pool_delta.py:36-40 acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_delta.py:36-40`
  - 依据：_in_use 保存的是 id(resource)。当资源对象被释放后其 id 可能被新对象复用，导致 _in_use 中出现碰撞，stats() 的 in_use 计数错误；且由于 release() 从不从 _in_use 中删除，该集合只增不减，长期运行会持续泄漏内存。
- **[logic/medium]** [logic] resources/pool_epsilon.py:36-40 acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_epsilon.py:36-40`
  - 依据：与 pool_beta.py 相同：_in_use 只保存 id(resource) 整数而不持有对象引用，id 可被回收复用，导致在用集合失真。触发条件：借出的资源被回收后新对象复用同一 id。
- **[logic/medium]** [logic] resources/pool_eta.py:36-40 acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:36-40`
  - 依据：与 pool_alpha.py 相同：_in_use 保存 id(resource)，对象被回收后 id 可被新对象复用，导致 _in_use 集合无法正确区分不同资源，in_use 计数与归属判断失真。
- **[logic/medium]** [logic] resources/pool_gamma.py:36-40 PoolGamma.acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_gamma.py:36-40`
  - 依据：acquire() 用 id(resource) 记录在用资源。id 只在对象存活期间唯一，若某资源被释放/回收后新对象复用了同一内存地址，_in_use 中会残留旧 id 或与新对象冲突，导致 stats() 的 in_use 计数错误，并使基于 id 的归属判断失效。触发条件：资源对象被回收且新对象复用其地址。
- **[logic/medium]** [logic] resources/pool_theta.py:36-40 PoolTheta.acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_theta.py:36-40`
  - 依据：_in_use 保存的是 id(resource) 而非资源本身或稳定标识。CPython 中对象被回收后其 id 可被新对象复用，若某资源在借出期间被外部释放并回收，新创建的对象可能获得相同 id，导致 _in_use 误判、stats() 计数错误，并使归属校验（若实现）失效。触发条件：借出对象被回收且新对象复用同一内存地址。
- **[logic/medium]** [logic] resources/pool_zeta.py:36-40 PoolZeta.acquire() 用 id(resource) 跟踪在用资源，id 可被回收复用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`resources/pool_zeta.py:36-40`
  - 依据：acquire() 用 id(resource) 记录在用资源。id 仅在对象存活期间唯一，对象被回收后地址可被新对象复用，导致 _in_use 计数错误或归属判断失效。触发条件：资源对象被回收且新对象复用其地址。
- **[logic/low]** [logic] scheduling/scheduler_alpha.py:61-64 cancel() 只从 _items 删除，堆中残留项由 take() 惰性跳过（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:61-64`
  - 依据：cancel() 删除 _items 中的条目后，堆中对应的 _Item 成为孤儿，但 take() 在弹出时会检查 item.name in self._items，孤儿项被直接丢弃，pending() 也基于 _items 计数，因此取消语义正确，只是堆可能暂时占用额外内存，不构成功能缺陷。
- **[logic/low]** [logic] scheduling/scheduler_eta.py:62-65 SchedulerEta.cancel 仅从 _items 删除，堆中残留项由 take 惰性跳过（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_eta.py:62-65`
  - 依据：cancel() 只删除 _items 中的条目，堆中仍保留对应 _Item，但 take() 在弹出时会检查 item.name in self._items，不在则丢弃并继续循环，因此被取消的作业不会被返回。该惰性删除策略是正确的，只是堆内存会暂时保留已取消项，不构成功能缺陷。
- **[logic/low]** [logic] scheduling/scheduler_zeta.py:62-66 SchedulerZeta.cancel() 只从 _items 删除，堆中残留项依赖 take() 惰性清理（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_zeta.py:62-66`
  - 依据：cancel() 仅从 _items 删除而不从堆中移除，看似泄漏，但 take() 在弹出时会检查 item.name in self._items，已取消的项会被跳过并丢弃，pending() 也基于 _items 计数，因此行为正确。堆中残留项会在后续 take() 时被清理，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_alpha.py:41-42 RegistryAlpha.clear 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_alpha.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保持原值。调用 clear() 后再次 get 会重新构造实例并继续累加计数，build_count() 返回的是历史累计构造次数而非当前缓存中的实例数，与“清空后重新开始”的语义不符，容易误导调用方。触发条件：clear() 后再次 get 并读取 build_count()。
- **[logic/low]** [logic] wiring/registry_beta.py:41-42 clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_beta.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保持累加。清空后再次 get 会重新构造实例并继续累加计数，build_count() 返回的是历史累计构造次数而非当前缓存中的实例数，调用方若用它判断缓存状态会得到错误结果。
- **[logic/low]** [logic] wiring/registry_delta.py:41-42 clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_delta.py:41-42`
  - 依据：clear() 只清空 _instances，不重置 _build_count。清空后再次 get 会重新构造实例并继续累加 _build_count，使 build_count() 反映的是历史累计构造次数而非当前缓存状态，调用方若用它判断“是否已构造/构造了几次”会得到与缓存不一致的结果。触发条件：clear() 后再次 get()。
- **[logic/low]** [logic] wiring/registry_epsilon.py:41-42 RegistryEpsilon.clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_epsilon.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保持累加。clear 后再次 get 会重新构造实例并继续累加计数，使 build_count() 无法反映当前缓存状态下的构造次数，调用方若依赖该计数判断是否重建会得到错误结论。
- **[logic/low]** [logic] wiring/registry_eta.py:41-42 RegistryEta.clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_eta.py:41-42`
  - 依据：clear() 仅清空 _instances，未重置 _build_count，导致 clear 后重新构造实例时计数继续累加，build_count() 不再准确反映构造次数。
- **[logic/low]** [logic] wiring/registry_gamma.py:41-42 RegistryGamma.clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_gamma.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保持累加。clear 的语义是重置注册表状态，但 build_count() 在 clear 后仍返回历史累计值，调用方无法据此判断当前缓存状态，统计与实例缓存不一致。
- **[logic/low]** [logic] wiring/registry_theta.py:41-42 RegistryTheta.clear 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_theta.py:41-42`
  - 依据：clear() 仅清空 _instances，未重置 _build_count，导致 build_count() 在 clear 后仍保留历史累计值，无法反映当前缓存状态。触发条件：clear() 后再次 get 并读取 build_count()。

## 争议（需裁决）

- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:65-71 close() 只关闭空闲资源，未关闭在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_alpha.py:65-71`
  - 依据：close() 仅遍历 self._free 关闭空闲资源并清空，未处理 self._in_use 中的在用资源，也没有设置关闭标志。调用 close() 后池仍可被 acquire() 使用：若 _free 为空且 _created < _size，acquire() 会继续调用 factory() 新建资源，导致 close() 之后仍产生新资源，且这些资源永远不会被关闭，造成资源泄漏。触发条件：close() 之后再次 acquire()。
  - 争议对手：6908c4f4d37c, a8464e3a5aa0
- **[resource_leak/medium]** [resource_leak] resources/pool_eta.py:64-70 close() 未清理 _in_use 且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-3, reader-r0-5｜置信度 0.5
  - 源：`resources/pool_eta.py:64-70`
  - 依据：与 pool_alpha.py 相同：close() 只关闭并清空 _free，不处理 _in_use，也不阻止后续 acquire()，导致关闭后仍可新建/借出资源，已借出资源无法回收关闭，造成泄漏。触发条件：close() 之后再次 acquire()。
  - 争议对手：a10f2e0b6dc4, b22f4fa4a0a7
- **[logic/high]** [logic] scheduling/scheduler_alpha.py:47-53 reprioritize 直接修改堆内元素优先级，破坏堆序导致调度顺序错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:47-53`
  - 依据：reprioritize() 直接对堆中已存在的 _Item 对象赋值 item.priority，但没有调用 heapq 的修复操作（如 _siftdown/_siftup 或重新 heappush）。堆的排序不变量依赖元素在插入时确定的位置，原地修改优先级后堆序被破坏，后续 take() 会按错误的顺序弹出作业。触发条件：先 add 多个作业，再对某个作业调用 reprioritize 提升/降低优先级，然后 take()。
  - 争议对手：cdc2f73cbda8, f7cfc3e404b5
- **[logic/high]** [logic] scheduling/scheduler_beta.py:47-52 reprioritize() 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:47-52`
  - 依据：reprioritize() 通过 self._items[name] 拿到 _Item 对象后直接赋值 item.priority，但该对象仍位于 self._heap 中。heapq 的堆序依赖元素比较结果，原地修改已入堆元素的排序键不会触发任何上浮/下沉调整，堆不变量被破坏。触发条件：对队列中任意作业调用 reprioritize() 后，take() 不再保证返回当前优先级最高的作业（例如把某作业优先级从 10 改为 1，它仍可能排在堆底，直到其它元素被弹出后才可能浮上来）。正确做法是标记旧条目失效并 push 一个新条目，或调用 heapq.heapify 重建。
  - 争议对手：0357111a04ff, c064a02e93a6, c8d29cbf9ab0, ca47aee93de7
- **[logic/high]** [logic] scheduling/scheduler_delta.py:47-51 SchedulerDelta.reprioritize() 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_delta.py:47-51`
  - 依据：reprioritize() 直接对已入堆的 _Item 赋值 item.priority，而没有做 heapify 或 push/pop 修复。堆是按 priority 排序的，就地修改会使堆序失效，之后 take() 的 heappop 不再保证返回当前优先级最高的作业，可能返回错误顺序甚至漏掉被提权的作业。触发条件：对队列中已有作业调用 reprioritize() 后再 take()。
  - 争议对手：c842d543010c
- **[logic/high]** [logic] scheduling/scheduler_epsilon.py:47-52 reprioritize() 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_epsilon.py:47-52`
  - 依据：与 scheduler_beta.py 相同：reprioritize() 原地修改仍在 self._heap 中的 _Item.priority，不重建堆也不重新入堆，堆序失效。触发条件：对已入队作业调用 reprioritize() 后，take()/drain() 返回的顺序不再按最新优先级，饥饿缓解逻辑失效。
  - 争议对手：317a3241ac22, 45a22e0b4e5e, 95e6cbac8bbf
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:47-53 reprioritize() 直接修改堆内元素优先级，破坏堆序导致调度顺序错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:47-53`
  - 依据：与 scheduler_alpha.py 相同：reprioritize() 原地修改堆内 _Item.priority，未做堆修复，破坏小顶堆不变式。调用方用它做饥饿缓解后，take() 返回的顺序不再按真实优先级，调度结果错误。
  - 争议对手：47824ad05509
- **[logic/high]** [logic] scheduling/scheduler_theta.py:47-53 reprioritize() 直接修改堆内元素优先级，破坏堆序导致调度顺序错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_theta.py:47-53`
  - 依据：与 scheduler_beta.py / scheduler_epsilon.py 相同：reprioritize() 直接赋值 item.priority，未修复堆结构，导致 heappop 不再返回最高优先级作业。触发条件：任何一次 reprioritize 调用之后。
  - 争议对手：a82cdf2f85cd, ab84103658bb, faaf4fe89c92
- **[logic/high]** [logic] scheduling/scheduler_zeta.py:47-52 SchedulerZeta.reprioritize() 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`scheduling/scheduler_zeta.py:47-52`
  - 依据：reprioritize() 直接对堆中已存在的 _Item 对象赋值 item.priority，而没有执行 heapq 的 sift 操作（如 heapify 或先删除再重新 push）。修改堆内元素的排序键会破坏小顶堆不变量，之后 take() 的 heappop 不再保证返回当前优先级最高的作业，可能返回错误顺序甚至漏取。触发条件：对队列中尚未出队的作业调用 reprioritize() 后继续 take()。
  - 争议对手：b10dfb943ffb, e67f68968722
- **[logic/high]** [logic] wire/codec_beta.py:33-35 decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_beta.py:33-35`
  - 依据：encode() 把大小写入 "size_bytes" 字段，但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)。触发条件：对 encode() 的输出调用 decode()，v2 载荷中没有 "size" 键，因此 out["size"] 恒为 0，total_size() 对所有 v2 载荷都返回 0，往返编解码丢失大小。
  - 争议对手：e3d8bf7fb647, ebcc8dd3938d
- **[logic/high]** [logic] wire/codec_zeta.py:33-35 decode() 对 v2 载荷读取 size 而非 size_bytes，丢失大小信息（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`wire/codec_zeta.py:33-35`
  - 依据：encode() 写入的 v2 字段是 size_bytes（见 encode 中 "size_bytes": int(record.get("size", 0))），但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，而 v2 载荷中并不存在 size 键，因此解码结果 size 恒为 0，原始大小信息丢失。触发条件：对任何由本 codec encode 出的 v2 载荷调用 decode()。
  - 争议对手：50d5c54d21fb, 57d77f18ff8f, 993507837e91
- **[logic/low]** [logic] wiring/registry_zeta.py:41-42 clear() 清空实例缓存但不重置 build_count（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`wiring/registry_zeta.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保持累计值。触发条件：clear() 后再次 get() 会重新构造实例，build_count 继续累加。若调用方用 build_count 判断“是否已构造过/构造了几次”，clear() 后该计数不再反映当前缓存状态，语义不一致。
  - 争议对手：d2a8da499f6b, e11c7e17ff0a

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 6 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 6 | 0 | 2 | 0 | 0 | 0 | 1 | 0 |
| `resources` | 3 | 5 | 2 | 1 | 5 | 0 | 0 | 2 |
| `scheduling` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 3 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 31%（单元格值 = 独立 Agent 数）
