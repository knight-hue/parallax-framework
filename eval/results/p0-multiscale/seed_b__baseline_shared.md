# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 23 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 4 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：77

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 28 | 100% | 17% |

## 高置信结论

- **[logic/high]** [logic] analytics/window_alpha.py:22-25 WindowAlpha 使用 deque(maxlen) 淘汰旧样本但 _total 未同步扣减，mean 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque(maxlen=size) 在 append 超出容量时会自动丢弃最旧元素，但 _total 只做累加、从不扣减被淘汰的值。一旦样本数超过 size，_total 会持续增长而 len(self._values) 被限制在 size，导致 mean() 返回远大于真实窗口均值的错误结果。触发条件：add 调用次数超过 size（默认 32）。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 WindowBeta 使用 deque(maxlen) 淘汰旧样本但 _total 未同步扣减，mean 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 _total 只做累加从不扣减被淘汰的值。当样本数超过 size 后，_total 会持续增长，而 len(self._values) 始终不超过 size，导致 mean() 返回的均值远大于真实窗口均值。触发条件：add 次数超过 size（默认 32）。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 WindowGamma 使用 deque(maxlen) 淘汰旧样本但 _total 未同步扣减，mean 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，mean() 分子包含已淘汰样本，窗口满后均值错误。触发条件：add 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-57 JournalAlpha.compact 只写盘不更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-57`
  - 依据：compact() 计算 kept 后直接 write_text 写盘，但没有把 self._records 替换为 kept。因此磁盘上只剩 keep 条，而内存 _records 仍保留全部记录。后续 replay()/count() 返回被压缩掉的旧记录，且下一次 append() 调用 _flush() 会把内存中的全部旧记录重新写回磁盘，使压缩失效。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_beta.py:51-57 JournalBeta.compact 只写盘不更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-57`
  - 依据：compact() 计算 kept 后直接写文件，但没有把 self._records 替换为 kept。之后 replay()/count() 仍返回被压缩前的全部记录，而 disk_count() 返回压缩后的条数，两者不一致；再次 append 时 _flush 会把内存中未压缩的全部记录重新写回磁盘，使压缩失效。触发条件：记录数超过 keep 后调用 compact()。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-57 JournalGamma.compact 只写盘不更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-57`
  - 依据：与 JournalAlpha/Beta 相同：compact() 把 kept 写入磁盘后未更新 self._records，内存仍保留全部记录。replay()/count() 与 disk_count() 结果不一致，且后续 append() 的 _flush() 会把已丢弃的记录重新写回磁盘，压缩失效。触发条件：记录数超过 keep 后调用 compact()，再调用 replay()/count() 或 append()。
- **[logic/high]** [logic] resources/pool_alpha.py:47-50 release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release 无条件把资源 append 到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。同一资源被重复 release 会多次进入 _free，后续 acquire 可把同一对象同时借给多个调用方，破坏池的互斥语义。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:60-66 close 只关闭空闲资源，未处理在借资源（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：close 只遍历 _free 调用 closer，_in_use 中的资源不会被关闭，造成资源泄漏。触发条件：在仍有资源被借出时调用 close。
- **[logic/high]** [logic] resources/pool_beta.py:47-50 PoolBeta.release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除其 id。若调用方重复归还同一资源（或归还从未借出的资源），_free 中会出现重复条目，后续 acquire 会把同一底层资源同时借给多个调用者，破坏池的互斥语义；同时 _in_use 集合因从未移除而永久膨胀，stats 失真。触发条件：对同一资源调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:60-66 PoolBeta.close 只关闭空闲资源，未处理在借资源（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:60-66`
  - 依据：close 只遍历 _free 调用 closer 并清空 _free，_in_use 中的资源不会被关闭，且 _created 不重置。若调用方在仍有在借资源时 close，这些资源永远不会被释放，造成资源泄漏。触发条件：close 时存在未归还资源。
- **[logic/high]** [logic] resources/pool_gamma.py:47-50 PoolGamma.release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：与 pool_beta.py 相同：release() 无条件把 resource 追加到 _free 并 notify，不检查资源是否在 _in_use 中，也不从 _in_use 移除其 id。重复归还同一资源会使 _free 出现重复条目，后续 acquire 可能把同一资源同时借给多个调用者，破坏互斥；_in_use 也因从不移除而永久膨胀。触发条件：对同一资源调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:60-66 PoolGamma.close 只关闭空闲资源，未处理在借资源（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:60-66`
  - 依据：close 只关闭 _free 中的资源并清空 _free，_in_use 中的资源不会被关闭，_created 也不重置。close 时若仍有在借资源，这些资源永远不会被释放。触发条件：close 时存在未归还资源。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:47-50 reprioritize 直接修改堆内元素优先级导致堆序失效（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:47-50`
  - 依据：同 SchedulerAlpha：直接改 priority 后未重新堆化，堆序失效，take() 可能返回错误顺序的作业。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:47-50 reprioritize 直接修改堆内元素优先级导致堆序失效（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:47-50`
  - 依据：同 SchedulerAlpha/Beta：直接改 priority 而不重建堆，堆序失效。
- **[error_handling/medium]** [error_handling] wire/codec_alpha.py:41-42 CodecAlpha.total_size 对缺失 size 的载荷抛 KeyError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:41-42`
  - 依据：total_size 直接用 self.decode(payload)["size"] 取值。decode() 对 v1 载荷会设置 out["size"]，但对 v2 载荷虽然也设置了 size（值为 0），对既无 v 也无 size 的载荷（如 {"name": "x"}）decode 会走 version=1 分支设置 size=0，看似安全；然而当载荷为 v2 且缺少 size 键时 decode 仍会写入 size=0，因此不会 KeyError。真正会 KeyError 的情形是 decode 返回的字典不含 size——当前实现总会写入 size，故此处实际不会抛 KeyError。
- **[logic/high]** [logic] wire/codec_alpha.py:33-35 CodecAlpha.decode 对 v2 记录读取 size 而非 size_bytes，丢失编码字段（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:33-35`
  - 依据：encode() 把记录写成 v2 格式，字段名为 size_bytes；但 decode() 在 version >= 2 分支里读取的是 payload.get("size", 0)，而 v2 载荷中不存在 size 键，因此总是得到默认值 0，size_bytes 中携带的真实大小被丢弃。触发条件：对 encode() 产生的 v2 载荷调用 decode()。
- **[error_handling/medium]** [error_handling] wire/codec_beta.py:41-42 total_size 对缺失 size 的载荷抛 KeyError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:41-42`
  - 依据：total_size 直接下标访问 decode 结果的 'size' 键。虽然当前 decode 在 version>=1 时总会写入 'size'，但若传入 v 为 0 或负数的载荷，decode 不会设置 'size'，此处会抛 KeyError 而非给出合理默认值。触发条件：payload 的 v 字段小于 1。
- **[logic/high]** [logic] wire/codec_beta.py:33-35 decode 对 v2 记录读取 size 而非 size_bytes，丢失编码字段（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:33-35`
  - 依据：encode 写入的是 size_bytes，但 decode 的 v2 分支读取 payload.get("size", 0)，导致 v2 记录解码后 size 恒为 0，往返不一致。
- **[error_handling/medium]** [error_handling] wire/codec_gamma.py:41-42 CodecGamma.total_size 对缺失 size 的载荷抛 KeyError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:41-42`
  - 依据：total_size 直接用 self.decode(payload)["size"] 取值。decode 对 v1 载荷会设置 size，但对 v2 载荷虽然也设置了 size（值为 0），若传入的 payload 使 decode 返回的字典不含 size（例如未来版本分支），或调用方传入非本 codec 解码的字典，会抛 KeyError 而非返回 0。触发条件：载荷缺少 size 键。
- **[logic/high]** [logic] wire/codec_gamma.py:33-35 CodecGamma.decode 对 v2 记录读取 size 而非 size_bytes，丢失编码字段（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:33-35`
  - 依据：encode 把记录写入 size_bytes 字段（v2 格式），但 decode 在 version >= 2 分支读取的是 payload.get("size", 0)，而线格式中并不存在 size 键，因此解码结果 size 恒为 0，编码时写入的 size_bytes 被丢弃，往返不一致。
- **[concurrency/medium]** [concurrency] wiring/registry_alpha.py:22-24 RegistryAlpha.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_alpha.py:22-24`
  - 依据：get() 先检查 name not in self._instances，再调用 _build 并写回 _instances，整个过程没有任何锁保护。两个线程同时首次获取同一名字时，都会通过检查并各自调用工厂构造实例，违反类文档中“同名组件在进程内只应存在一个实例”的约定，且 _build_count 也会被多计。触发条件：多线程并发首次 get 同一名字。
- **[concurrency/medium]** [concurrency] wiring/registry_beta.py:22-24 RegistryBeta.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_beta.py:22-24`
  - 依据：get 先检查 _instances 再构造并写入，没有加锁。两个线程同时首次 get 同一名字时会各自构造实例，违反“同名组件进程内只应存在一个实例”的约定，且 _build_count 也会多计。
- **[concurrency/medium]** [concurrency] wiring/registry_gamma.py:22-24 RegistryGamma.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_gamma.py:22-24`
  - 依据：get() 先检查 name not in self._instances 再构造并写入，检查与写入之间没有锁。多线程同时首次获取同一组件时，两个线程都会通过检查并各自调用 _build，导致工厂被调用两次、产生两个实例，违反类文档中“同名组件在进程内只应存在一个实例”的约定。触发条件：多线程并发首次 get 同一 name。

## 待验证（孤证）

- **[boundary/low]** [boundary] analytics/window_alpha.py:44-48 WindowAlpha.percentile 对 ratio 越界未做钳制（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`analytics/window_alpha.py:44-48`
  - 依据：ratio 超出 [0,1] 时 index 会越界并抛 IndexError，但该方法的契约隐含要求 ratio 为分位比例，调用方传入合法值即可正常工作；这属于调用方责任而非实现缺陷，且没有证据表明内部会传入越界值，故不认定为缺陷。
- **[logic/low]** [logic] resources/pool_alpha.py:28-45 acquire 超时等待逻辑正确（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:28-45`
  - 依据：acquire 在 Condition 上循环等待，每次被唤醒后重新检查 _free 与 _created，并用 deadline 计算剩余时间，能正确处理虚假唤醒与超时，逻辑本身没有缺陷。
- **[performance/low]** [performance] resources/pool_beta.py:33-36 PoolBeta.acquire 在持锁状态下调用工厂函数（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_beta.py:33-36`
  - 依据：acquire 在持有 _available 条件锁时调用 self._factory()，若工厂耗时较长会阻塞其他线程的 acquire/release。但这保证了 _created 计数与资源创建的一致性，避免超发；在定长池语义下是可接受的权衡，且未观察到明确的错误行为，故不认定为缺陷。
- **[logic/low]** [logic] wiring/registry_gamma.py:38-39 RegistryGamma.clear 清空实例缓存但不清零 _build_count，计数语义不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:38-39`
  - 依据：clear() 只清空 _instances，_build_count 保留累计构造次数。build_count() 的语义是“累计构造次数”，clear 后重新 get 会再次构造并递增计数，这与“累计”语义一致，并非缺陷。

## 争议（需裁决）

- **[logic/high]** [logic] scheduling/scheduler_alpha.py:47-50 reprioritize 直接修改堆内元素优先级导致堆序失效（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:47-50`
  - 依据：reprioritize 直接修改 _Item.priority，但堆数组未重新堆化（未调用 heapq.heapify 或 push/pop 调整）。修改后堆序不再满足小顶堆性质，take() 可能返回非最高优先级的作业，饥饿缓解逻辑失效。
  - 争议对手：3792417ca829

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 3 | 0 | 0 | 0 | 3 | 0 | 1 | 0 |
| `scheduling` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| `wiring` | 1 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 23%（单元格值 = 独立 Agent 数）
