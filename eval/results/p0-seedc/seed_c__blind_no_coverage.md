# Parallax 运行报告 `4b4940197cd8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 87 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：5 个（每轮全新身份）
- 账本条目：89

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 5 | 88 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] analytics/window_alpha.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_alpha.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 约束。当 ratio > 1（如 1.5）或 ratio < 0（如 -0.1）时，index 会超出 ordered 的有效下标范围，ordered[index] 抛出 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_alpha.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，当窗口已满时 append 会自动淘汰最旧样本，但 _total 只做累加、从不减去被淘汰的值。因此一旦样本数超过 size，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，均值会随样本增多而单调膨胀，结果完全错误。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_beta.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_beta.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 范围校验。当 ratio > 1 时 index 会超过 len(ordered)-1，当 ratio < 0 时 index 为负（且绝对值可能超过长度），ordered[index] 会抛出 IndexError。触发条件：调用 percentile(1.5) 或 percentile(-0.1) 等越界值。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此当添加样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<= size），分子却是全部历史之和，结果被严重高估。触发条件：add 调用次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_delta.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_delta.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验，ratio 超出 [0,1] 时 ordered[index] 会抛 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_delta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_delta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 在满窗后 append 会丢弃最旧元素，但 _total 只累加不扣减，mean() 用 _total/len(_values) 会得到错误结果。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_epsilon.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_epsilon.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验，ratio 超出 [0,1] 时 ordered[index] 会抛 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_epsilon.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_epsilon.py:22-25`
  - 依据：deque(maxlen=size) 满窗后 append 自动淘汰最旧样本，_total 只累加不扣减，mean() 用 _total/len(_values) 会随历史样本累积而错误膨胀。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_eta.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_eta.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验，ratio 超出 [0,1] 时 ordered[index] 会抛 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_eta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_eta.py:22-25`
  - 依据：deque(maxlen=size) 满窗后 append 自动淘汰最旧样本，_total 只累加不扣减，mean() 用 _total/len(_values) 会随历史样本累积而错误膨胀。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_gamma.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验，ratio 超出 [0,1] 时 ordered[index] 会抛 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：deque(maxlen=size) 满窗后 append 自动淘汰最旧样本，_total 只累加不扣减，mean() 用 _total/len(_values) 会随历史样本累积而错误膨胀。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_theta.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_theta.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验。ratio > 1 或 ratio < 0 时 index 越界，ordered[index] 抛出 IndexError。触发条件：传入超出 [0,1] 的 ratio。
- **[logic/high]** [logic] analytics/window_theta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_theta.py:22-25`
  - 依据：与 window_beta.py 相同：deque(maxlen=size) 在 append 时自动淘汰最旧样本，但 _total 只累加不扣减。样本数超过 size 后 mean() 的分子包含全部历史样本之和，分母仅为当前窗口长度，导致均值错误。触发条件：add 调用次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_zeta.py:41-45 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_zeta.py:41-45`
  - 依据：index 由 ratio 直接计算且未做范围校验，ratio 超出 [0,1] 时 ordered[index] 会抛 IndexError。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_zeta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_zeta.py:22-25`
  - 依据：deque(maxlen=size) 满窗后 append 自动淘汰最旧样本，_total 只累加不扣减，mean() 用 _total/len(_values) 会随历史样本累积而错误膨胀。触发条件：add 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_alpha.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：先 append 若干条使 len(_records) > keep，再调用 compact()。此后 replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，内存与磁盘状态永久不一致；后续 append() 还会用未截断的 _records 重写文件，把已丢弃的旧记录重新写回磁盘，使 compact() 的保留语义失效。
- **[logic/high]** [logic] persistence/journal_beta.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_beta.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：先 append 若干条使 len(_records) > keep，再调用 compact()。此后 replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，内存与磁盘状态永久不一致；后续 append() 还会用未截断的 _records 重写文件，把已丢弃的旧记录重新写回磁盘，使 compact() 的保留语义失效。
- **[logic/high]** [logic] persistence/journal_delta.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_delta.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：append 若干条超过 keep 后调用 compact()，磁盘只剩 keep 条，但内存 _records 仍是全部记录，随后 replay()/count() 返回被丢弃的记录，与 disk_count() 不一致。
- **[logic/high]** [logic] persistence/journal_epsilon.py:47-53 compact() 未同步内存中的 _records，导致重放与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:47-53`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。触发条件：append 若干条使 len(_records) > keep，调用 compact() 后，磁盘只剩 keep 条，但 replay()/count() 仍返回全部旧记录。后续 append() 调用 _flush() 会把未裁剪的 self._records 全量写回磁盘，使 compact 的效果被完全撤销，保留量约束失效。
- **[logic/high]** [logic] persistence/journal_eta.py:47-53 compact() 未同步内存中的 _records，导致重放与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_eta.py:47-53`
  - 依据：与 journal_epsilon.py 相同：compact() 仅重写磁盘文件，未更新 self._records。compact 后 replay()/count() 仍返回被丢弃的记录，且下一次 append() 的 _flush() 会把全部记录写回，撤销压缩结果。
- **[logic/high]** [logic] persistence/journal_gamma.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_gamma.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：先 append 若干条使 len(_records) > keep，再调用 compact()。此后 replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，内存与磁盘状态永久不一致；后续 append() 还会用未截断的 _records 重写文件，把已丢弃的旧记录重新写回磁盘，使 compact() 的保留语义失效。
- **[logic/high]** [logic] persistence/journal_theta.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_theta.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：append 若干条超过 keep 后调用 compact()，磁盘只剩 keep 条，但内存 _records 仍是全部记录，随后 replay()/count() 返回被丢弃的记录，与 disk_count() 不一致。
- **[logic/high]** [logic] persistence/journal_zeta.py:47-53 compact() 未同步内存中的 _records，导致 replay() 与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_zeta.py:47-53`
  - 依据：compact() 只把截断后的 kept 写回磁盘，却没有更新 self._records。触发条件：append 若干条超过 keep 后调用 compact()，磁盘只剩 keep 条，但内存 _records 仍是全部记录，随后 replay()/count() 返回被丢弃的记录，与 disk_count() 不一致。
- **[api_misuse/medium]** [api_misuse] resources/pool_alpha.py:58-64 close() 对 factory 调用 closer(resource) 属 API 误用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:58-64`
  - 依据：closer 取自 self._factory（工厂函数）的 close 属性，却以单个 resource 作为参数调用。工厂的 close 语义通常是关闭工厂自身（无参），而资源对象的关闭方法在 resource 上。触发条件：factory 恰好带有 close 方法时，close() 会以错误的对象和参数调用它，可能抛 TypeError 或关闭错误的实体；而真正需要关闭的 resource 从未被关闭，造成资源泄漏。
- **[concurrency/high]** [concurrency] resources/pool_alpha.py:45-48 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:45-48`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release（或归还一个从未借出的对象），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏“借出资源互斥”的池语义；同时 _in_use 集合因从未删除而持续增长，stats() 的 in_use 计数永久偏高。
- **[logic/low]** [logic] resources/pool_alpha.py:30-37 acquire() 使用 id(resource) 作为 _in_use 键，对象被回收后 id 可复用（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:30-37`
  - 依据：虽然 id() 在对象被 GC 后可能被复用，但池在资源借出期间通过 _free/_in_use 持有引用，借出对象不会被回收，因此 id 冲突在正常使用下不会发生。仅在调用方错误地丢弃资源引用并触发回收时才可能出问题，属于调用方误用，不构成本代码的缺陷。
- **[performance/low]** [performance] resources/pool_alpha.py:33-37 acquire() 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:33-37`
  - 依据：factory() 在 with self._available 临界区内执行，若工厂创建资源耗时（如建立网络连接），所有其他 acquire/release 线程都会被阻塞在锁上，即使池中已有空闲资源也无法取用。触发条件：并发场景下工厂较慢。
- **[api_misuse/medium]** [api_misuse] resources/pool_beta.py:58-64 close() 对 factory 调用 closer(resource) 属 API 误用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:58-64`
  - 依据：closer 取自 self._factory（工厂函数）的 close 属性，却以 resource 为参数调用。工厂函数通常没有 close 属性，因此 callable(closer) 为假，资源永远不会被真正关闭；即便工厂恰好有 close，其签名也不是接收单个 resource，调用语义错误。
- **[concurrency/low]** [concurrency] resources/pool_beta.py:38-41 acquire() 超时等待使用 wait(remaining) 但未处理虚假唤醒（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_beta.py:38-41`
  - 依据：wait 被包在 while True 循环中，每次唤醒后重新检查 _free 与 _created 并重算 remaining，虚假唤醒或 notify 后条件不满足都会继续等待，逻辑正确。
- **[concurrency/high]** [concurrency] resources/pool_beta.py:45-48 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:45-48`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：同一资源被 release 两次（或 release 一个从未借出的资源），_free 中会出现重复条目，后续两次 acquire() 会返回同一个对象，破坏池的互斥语义。
- **[performance/medium]** [performance] resources/pool_beta.py:33-37 acquire() 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:33-37`
  - 依据：factory() 在 with self._available 临界区内被调用，若工厂创建资源耗时（如建立连接），所有其他 acquire/release 线程都会被阻塞在锁上，即使池中已有空闲资源也无法取用。
- **[api_misuse/medium]** [api_misuse] resources/pool_delta.py:58-64 close() 对 factory 调用 closer(resource) 属 API 误用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:58-64`
  - 依据：同 pool_alpha.py：closer 来自 factory 而非 resource，却以 resource 为参数调用，语义与参数均错误，可能导致 TypeError 或未关闭真正的资源。
- **[concurrency/high]** [concurrency] resources/pool_delta.py:45-48 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:45-48`
  - 依据：同 pool_alpha.py：release() 不检查资源是否在 _in_use 中、也不从 _in_use 删除，重复归还会在 _free 中产生重复条目，导致同一资源被并发借出，且 in_use 统计只增不减。
- **[logic/low]** [logic] resources/pool_delta.py:30-37 acquire() 使用 id(resource) 作为 _in_use 键，对象被回收后 id 可复用（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_delta.py:30-37`
  - 依据：同 pool_alpha.py：借出期间池持有引用，id 复用不会在正常使用下发生，不构成本代码缺陷。
- **[performance/low]** [performance] resources/pool_delta.py:33-37 acquire() 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:33-37`
  - 依据：同 pool_alpha.py：factory() 在临界区内执行，慢工厂会阻塞所有其他池操作。
- **[api_misuse/medium]** [api_misuse] resources/pool_epsilon.py:58-64 close() 对 factory 调用 closer(resource) 属 API 误用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:58-64`
  - 依据：同 pool_alpha.py：closer 来自 factory 而非 resource，却以 resource 为参数调用，语义与参数均错误，可能导致 TypeError 或未关闭真正的资源。
- **[concurrency/high]** [concurrency] resources/pool_epsilon.py:45-48 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:45-48`
  - 依据：同 pool_alpha.py：release() 不检查资源是否在 _in_use 中、也不从 _in_use 删除，重复归还会在 _free 中产生重复条目，导致同一资源被并发借出，且 in_use 统计只增不减。
- **[logic/low]** [logic] resources/pool_epsilon.py:30-37 acquire() 使用 id(resource) 作为 _in_use 键，对象被回收后 id 可复用（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_epsilon.py:30-37`
  - 依据：同 pool_alpha.py：借出期间池持有引用，id 复用不会在正常使用下发生，不构成本代码缺陷。
- **[performance/low]** [performance] resources/pool_epsilon.py:33-37 acquire() 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:33-37`
  - 依据：同 pool_alpha.py：factory() 在临界区内执行，慢工厂会阻塞所有其他池操作。
- …另有 47 条未列出

## 争议（需裁决）

- **[logic/high]** [logic] wire/codec_beta.py:20-36 encode 写入 size_bytes，decode 却读取 size，导致 v2 往返丢失 size（确认存在缺陷）
  - 独立来源 1 个：reader-r0-5｜置信度 0.5
  - 源：`wire/codec_beta.py:20-36`
  - 依据：encode 把记录的大小写入键 "size_bytes"（第 24 行），但 decode 在 version>=1 和 version>=2 两个分支里都读取 payload.get("size", 0)（第 33、37 行），从不读取 "size_bytes"。因此对 encode 产生的 v2 载荷调用 decode 时，size 永远回退为默认值 0，往返（round-trip）丢失数据。触发条件：任何 encode 后 decode 的正常使用路径。
  - 争议对手：ebcc8dd3938d

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 1 |
| `scheduling` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `wiring` | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
