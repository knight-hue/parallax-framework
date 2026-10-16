# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 23 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 12 | 单一来源孤证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：96

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 40 | 100% | 23% |

## 高置信结论

- **[logic/high]** [logic] analytics/window_alpha.py:22-25 WindowAlpha 淘汰旧样本时未从 _total 中扣除，mean() 结果错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 add() 只做 self._total += value，从不减去被淘汰的值。因此一旦窗口写满并继续 add，_total 会持续累加所有历史样本，而 mean() 用 _total / len(self._values)（分母是当前窗口长度），导致均值随写入次数单调膨胀，完全错误。触发条件：add 次数超过 size。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 WindowBeta 滑动窗口淘汰旧样本时未同步扣减 _total，导致 mean 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只增不减。因此当样本数超过 size 后，mean() 返回 _total / len(self._values)，分子包含已被淘汰的样本，分母只是当前窗口大小，均值被系统性高估。触发条件：add 次数超过 size（默认 32）。
- **[boundary/low]** [boundary] analytics/window_gamma.py:43-47 WindowGamma.percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_gamma.py:43-47`
  - 依据：与 WindowAlpha 相同：percentile 未校验 ratio 范围，ratio 超出 [0,1] 时 index 越界，抛出 IndexError。触发条件：传入超出 [0,1] 的 ratio。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 WindowGamma 滑动窗口淘汰旧样本时未同步扣减 _total，导致 mean 计算错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 在 append 时自动淘汰最旧元素，但 _total 只增不减。窗口满后 mean() 返回的是全部历史样本总和除以窗口长度，结果偏大且随运行时间单调增长。触发条件：add 次数超过 size 后调用 mean()。
- **[logic/high]** [logic] persistence/journal_alpha.py:47-53 JournalAlpha.compact 只写盘不更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_alpha.py:47-53`
  - 依据：compact() 计算 kept 后直接 write_text 写盘，但没有把 self._records 替换为 kept。于是 compact 之后：count()/replay() 仍返回全部旧记录，而 disk_count() 返回压缩后的条数，两者不一致；后续 append() 调用 _flush() 会把仍含全部旧记录的 self._records 重新写回磁盘，使压缩结果被撤销。触发条件：记录数超过 keep 后调用 compact()，再调用 append() 或 replay()。
- **[logic/high]** [logic] persistence/journal_beta.py:47-53 JournalBeta.compact 只重写磁盘文件，未同步内存 _records，导致 replay/count 与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_beta.py:47-53`
  - 依据：与 JournalAlpha 相同：compact() 写入 kept 到磁盘但未更新 self._records，内存与磁盘状态分叉，replay() 仍返回已丢弃记录，后续 append 会把旧记录重新写回。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 JournalGamma.compact 未更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：与 JournalAlpha 相同：compact() 只写磁盘不更新 self._records，replay()/count() 与 disk_count() 不一致，且后续 append() 会把未裁剪记录重新写回磁盘，撤销 compact 效果。
- **[logic/medium]** [logic] resources/pool_alpha.py:47-50 release 未校验资源归属，重复归还会使池内资源数超过 size（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若同一资源被 release 两次（或 release 一个从未借出的对象），_free 中会出现重复条目，后续 acquire 会把同一对象同时借给多个调用方，破坏“池内资源总数不超过 size”的约定。触发条件：调用方重复归还或归还非池内对象。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:60-66 close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：close 仅遍历 _free 关闭空闲资源并清空，不关闭 _in_use 中的资源，也不设置关闭标志。调用 close 后若仍有在借资源，这些资源永远不会被关闭；同时 close 之后 acquire 仍可继续新建资源（_created 未重置），造成资源泄漏。触发条件：存在在借资源时调用 close，或 close 后继续 acquire。
- **[logic/high]** [logic] resources/pool_beta.py:47-50 PoolBeta.release 未校验资源归属，重复归还会使池内资源数超过 size（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除其 id。因此同一资源被 release 两次（或 release 一个从未借出的资源）会向 _free 注入重复条目，_free 长度可超过 _size，破坏“池内资源总数不超过 size”的约定；同时 _in_use 永不缩减，stats() 的 in_use 计数也会失真。触发条件：对同一资源调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:60-66 PoolBeta.close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:60-66`
  - 依据：close() 仅遍历 _free 关闭空闲资源并清空，对 _in_use 中的资源不做任何处理，也不设置关闭标志。关闭后调用 acquire() 仍会从 _free（已空）或工厂新建资源，导致资源在池关闭后继续被创建/借出，已借出的资源永远不会被关闭，造成资源泄漏。触发条件：close() 之后仍有在借资源或再次 acquire()。
- **[logic/high]** [logic] resources/pool_gamma.py:47-50 PoolGamma.release 未校验资源归属，重复归还会使池内资源数超过 size（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：与 PoolBeta 相同：release() 不检查资源是否处于借出状态，也不从 _in_use 中移除 id，重复归还会向 _free 追加重复条目，使空闲资源数超过 _size，并让 _in_use 计数永久偏高。触发条件：对同一资源调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:60-66 PoolGamma.close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:60-66`
  - 依据：与 PoolBeta 相同：close() 只关闭 _free 中的资源，忽略 _in_use 中的在借资源，且没有关闭状态标记。关闭后 acquire() 仍可新建或借出资源，导致资源无法被回收，形成泄漏。触发条件：close() 时存在在借资源，或 close() 后再次 acquire()。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:47-51 reprioritize 修改堆内元素优先级后未重新堆化，导致调度顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:47-51`
  - 依据：与 scheduler_alpha.py 相同：直接改写堆中 _Item.priority 而不重建堆，破坏 heapq 不变量。take() 依据失效的堆序弹出，返回的作业可能不是当前最高优先级，饥饿缓解逻辑失效。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:47-51 reprioritize 修改堆内元素优先级后未重新堆化，导致调度顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:47-51`
  - 依据：与 scheduler_alpha.py 相同：_Item 的 priority 参与排序，reprioritize 原地修改后未重新堆化，堆不变式被破坏，take() 返回顺序不再按优先级。触发条件为对已入队作业调用 reprioritize 后再 take。
- **[logic/high]** [logic] wire/codec_alpha.py:33-35 CodecAlpha.decode 对 v2 记录读取 size 而非 size_bytes，丢失编码字段（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:33-35`
  - 依据：encode() 把大小写入 "size_bytes" 字段，但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，而线格式中并不存在 "size" 键，因此解码 v2 记录时 size 恒为 0，编码时写入的 size_bytes 被丢弃。触发条件：对 encode() 产生的 v2 payload 调用 decode()。
- **[logic/high]** [logic] wire/codec_alpha.py:43-44 CodecAlpha.total_size 对 v2 记录求和恒为 0（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:43-44`
  - 依据：total_size 依赖 decode 返回的 size，而 decode 对 v2 记录因读取错误字段使 size 恒为 0，因此对 v2 载荷求和结果恒为 0，统计完全失效。
- **[logic/high]** [logic] wire/codec_beta.py:33-35 decode 对 v2 记录读取 size 而非 size_bytes，导致 size 丢失（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:33-35`
  - 依据：encode 把大小写入 'size_bytes' 字段（v2 格式），但 decode 在 version >= 2 分支读取的是 payload.get('size', 0)，而线格式中并不存在 'size' 键。因此对 v2 编码结果解码时 out['size'] 恒为 0，原始大小信息丢失。触发条件：encode 后 decode 任意带 size 的记录。
- **[logic/medium]** [logic] wire/codec_beta.py:43-44 total_size 对 v2 记录求和得到 0（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:43-44`
  - 依据：total_size 依赖 decode 返回的 "size" 字段。由于 decode 的 v2 分支错误地读取 "size" 而非 "size_bytes"，对 v2 线格式记录 total_size 恒为 0，统计结果错误。触发条件：传入由 encode 生成的 v2 payload 列表。
- **[logic/high]** [logic] wire/codec_gamma.py:43-44 CodecGamma.total_size 对 v2 记录求和得到 0（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:43-44`
  - 依据：total_size 依赖 decode(payload)["size"]，而 decode 对 v2 记录因读取了不存在的 "size" 键而返回 0，导致对 v2 线格式记录求和恒为 0，统计结果错误。触发条件：传入 v2 编码的 payload 列表。
- **[concurrency/medium]** [concurrency] wiring/registry_alpha.py:22-25 RegistryAlpha.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_alpha.py:22-25`
  - 依据：get() 先检查 name not in self._instances，再调用 _build 并写回，整个过程没有任何锁。两个线程同时首次 get 同一名字时都会通过检查并各自调用工厂，导致同名组件被构造两次，违反类文档中“同名组件在进程内只应存在一个实例”的约定，且 _build_count 也会多计。触发条件：多线程并发首次 get 同一未构造的名字。
- **[concurrency/medium]** [concurrency] wiring/registry_beta.py:22-25 RegistryBeta.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_beta.py:22-25`
  - 依据：get 采用 check-then-act：先判断 name 不在 _instances，再调用 _build 并写入。多线程并发首次 get 同一名字时，两个线程都可能通过判断并各自构造实例，违反类文档“同名组件在进程内只应存在一个实例”的约定，且 _build_count 会被多计。触发条件：多线程并发首次获取同一组件。
- **[concurrency/medium]** [concurrency] wiring/registry_gamma.py:22-25 RegistryGamma.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_gamma.py:22-25`
  - 依据：get 先检查 name not in self._instances 再构造并写入，检查与写入之间没有锁。两个线程同时首次 get 同一名字时都会通过检查并各自调用 _build，导致工厂被调用两次、产生两个实例，违反类文档中“同名组件在进程内只应存在一个实例”的约定，同时 _build_count 也会多计。

## 待验证（孤证）

- **[error_handling/low]** [error_handling] persistence/journal_alpha.py:26-30 JournalAlpha._load 对损坏行未做容错，json.loads 会抛异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_alpha.py:26-30`
  - 依据：文件由本类自身以合法 JSON Lines 写入，正常流程下不会产生损坏行。对损坏行直接抛异常属于可接受的失败模式，不构成明确缺陷。
- **[logic/low]** [logic] resources/pool_alpha.py:28-45 acquire 超时等待逻辑正确（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:28-45`
  - 依据：acquire 在 Condition 上循环等待，每次用 deadline 计算剩余时间，超时抛 TimeoutError，被唤醒后重新检查 _free 与 _created，逻辑正确，未发现缺陷。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:57-63 close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_alpha.py:57-63`
  - 依据：close 仅遍历 _free 调用 closer 并清空，_in_use 中的资源不会被关闭，且 close 后没有设置关闭标志，acquire 仍可继续新建或借出资源，导致资源泄漏与关闭后仍可使用的语义错误。触发条件：在仍有资源被借出时调用 close，或 close 后再次 acquire。
- **[logic/low]** [logic] resources/pool_beta.py:31-32 PoolBeta 使用 id(resource) 作为在借标识，存在 id 复用风险（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_beta.py:31-32`
  - 依据：_in_use 以 id(resource) 记录在借资源。理论上对象被回收后 id 可能被新对象复用，但池中资源在借出期间由调用方持有引用，不会被回收，因此 id 在借出生命周期内稳定，不会发生冲突。仅用于计数，不构成实际缺陷。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:57-63 PoolBeta.close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_beta.py:57-63`
  - 依据：close() 仅遍历 _free 关闭空闲资源并清空，对 _in_use 中的资源不做任何处理，也没有设置关闭标志。关闭后调用 acquire() 仍会从 _free 取（已空）或新建资源，导致资源在池关闭后继续被创建/泄漏，且已借出的资源永远不会被关闭。
- **[performance/low]** [performance] resources/pool_gamma.py:31-34 PoolGamma.acquire 在持锁状态下调用工厂函数，可能阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:31-34`
  - 依据：与 PoolBeta 相同：acquire() 在持有 _lock 的临界区内调用工厂函数，工厂耗时会导致锁被长时间占用，阻塞其他线程的池操作。触发条件：工厂函数耗时且存在并发访问。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:57-63 PoolGamma.close 只关闭空闲资源，未处理在借资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_gamma.py:57-63`
  - 依据：与 PoolBeta 相同：close() 只关闭 _free 中的资源，忽略 _in_use 中的资源，且未设置关闭状态，关闭后 acquire() 仍可新建资源，造成资源泄漏。
- **[logic/medium]** [logic] scheduling/scheduler_alpha.py:61-65 cancel 后堆中残留条目，drain 仍会返回已取消作业（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:61-65`
  - 依据：cancel 只从 _items 删除名字，不从 _heap 移除对应 _Item。take 通过 `if item.name in self._items` 过滤已取消项，因此 take 本身安全；但 drain 调用 take，take 会跳过已取消项，所以 drain 不会返回已取消作业。经核对，cancel 与 take 的配合是正确的惰性删除，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_alpha.py:40-41 RegistryAlpha.clear 清空实例缓存但保留工厂，build_count 语义与实例状态不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_alpha.py:40-41`
  - 依据：clear() 只清空 _instances，_factories 保留，_build_count 也不重置。这看起来可能不一致，但 clear 的语义就是“丢弃缓存实例以便下次重新构造”，保留工厂和累计构造计数是合理设计，不会导致错误行为。因此不认定为缺陷。
- **[logic/low]** [logic] wiring/registry_beta.py:39-40 clear 只清实例不清工厂，build_count 语义与实例缓存不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:39-40`
  - 依据：clear 清空 _instances 后再次 get 会重新构造实例，_build_count 继续累加，这是“累计构造次数”的合理语义，并未违反任何约定；工厂注册信息保留也是预期行为。因此不构成缺陷。
- **[logic/low]** [logic] wiring/registry_beta.py:40-41 clear 清空实例缓存但保留工厂，build_count 语义与实例状态不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:40-41`
  - 依据：clear 只清 _instances，_factories 保留，这是合理的“重置缓存”语义；build_count 作为累计构造次数不清零也符合其命名。未发现会导致错误行为的缺陷，故记录为非缺陷。
- **[error_handling/low]** [error_handling] wiring/registry_gamma.py:22-25 RegistryGamma.get 对未注册名字抛出 KeyError 而非明确错误（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:22-25`
  - 依据：get() 对未注册名字会在 _build 中通过 self._factories[name] 抛出 KeyError，这是可预期的失败方式，且 has() 提供了预检查手段，不构成缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] analytics/window_alpha.py:41-45 WindowAlpha.percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_alpha.py:41-45`
  - 依据：percentile 直接用 int(round(ratio * (len(ordered) - 1))) 作为索引，未对 ratio 做 [0,1] 约束。当 ratio > 1（如 1.5）时 index 会超出列表范围，ordered[index] 抛出 IndexError；ratio < 0 时 Python 负索引会静默返回错误元素。触发条件：传入超出 [0,1] 的 ratio。
  - 争议对手：c08cb472f515
- **[boundary/medium]** [boundary] analytics/window_beta.py:41-45 WindowBeta.percentile 未校验 ratio 范围，越界索引抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`analytics/window_beta.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1（如 1.5）或 ratio < 0（如 -0.1）时，index 会超出 [0, len-1] 范围，ordered[index] 抛出 IndexError。ratio 是外部传入参数，未做任何范围校验。
  - 争议对手：94a091aa21f8
- **[performance/low]** [performance] resources/pool_beta.py:31-34 PoolBeta.acquire 在持锁状态下调用工厂函数，可能阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:31-34`
  - 依据：acquire() 在 with self._available（即持有 _lock）的临界区内直接调用 self._factory()。若工厂构造耗时较长（如建立网络连接），会长时间持有锁，阻塞其他线程的 acquire/release/stats，降低并发吞吐。触发条件：工厂函数耗时且存在并发访问。
  - 争议对手：446e82ac0bed, 6b66453016df
- **[logic/high]** [logic] scheduling/scheduler_alpha.py:47-51 reprioritize 修改堆内元素优先级后未重新堆化，导致调度顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:47-51`
  - 依据：heapq 的堆不变量依赖于元素在插入时的比较键。reprioritize 直接修改 _Item.priority 字段，但没有调用 heapq.heapify 或删除后重新 push。修改后堆结构不再满足小顶堆性质，take() 会按旧的堆序弹出元素，可能返回优先级并非最高的作业，甚至让被提权的作业长期滞留在堆底。触发条件：任何在 add 之后、take 之前调用 reprioritize 的场景（正是文档所述饥饿缓解用途）。
  - 争议对手：f7cfc3e404b5
- **[logic/high]** [logic] wire/codec_gamma.py:33-35 CodecGamma.decode 对 v2 记录读取 size 而非 size_bytes，丢失编码字段（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:33-35`
  - 依据：encode() 把 v2 记录的大小写入 "size_bytes" 字段，但 decode() 在 version >= 2 分支读取的是 payload.get("size", 0)，而线格式中并不存在 "size" 键，因此解码结果 size 恒为 0，编码时写入的 size_bytes 被丢弃。触发条件：对任意 v2 编码结果调用 decode。
  - 争议对手：21b0cac2ccea, f2e861f20475

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 3 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `resources` | 3 | 0 | 0 | 0 | 3 | 0 | 3 | 0 |
| `scheduling` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 3 | 3 | 0 | 2 | 0 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
