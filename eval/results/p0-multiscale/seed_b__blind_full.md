# Parallax 运行报告 `9d3e85392fc8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 25 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 21 | 单一来源孤证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：3｜停止原因：`max_rounds_reached`
- 参与 Reader：9 个（每轮全新身份）
- 账本条目：151

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 41 | 100% | 15% |
| 1 | 3 | 1 | 100% | 23% |
| 2 | 3 | 8 | 100% | 25% |

## 高置信结论

- **[logic/high]** [logic] analytics/window_alpha.py:22-25 WindowAlpha 的 _total 在 deque 淘汰最旧样本时未同步扣减，导致 mean() 错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧元素，但 _total 只做累加、从不减去被淘汰的值。因此当样本数超过 size 后，mean() 返回的 _total/len(_values) 会持续偏大，且偏差随写入量单调增长。触发条件：add() 调用次数 > size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_beta.py:41-45 percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_beta.py:41-45`
  - 依据：同 window_alpha.py：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无范围校验。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 add() 累加 _total 但 deque 满时淘汰旧值未从 _total 扣除，导致 mean() 错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只增不减，窗口写满后 mean() 计算错误。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:41-45 percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_gamma.py:41-45`
  - 依据：同 window_alpha.py：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无范围校验。
- **[logic/high]** [logic] analytics/window_gamma.py:22-26 滑动窗口均值使用累计总和，淘汰旧样本后计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-26`
  - 依据：add() 将每个值累加到 self._total，但 deque 设置了 maxlen=size，超出容量时最旧样本会被自动丢弃，而 self._total 从未减去被淘汰的值。因此当样本数超过 size 后，mean() 返回 self._total / len(self._values)，分子包含所有历史样本之和，分母只是当前窗口长度，结果被严重放大。触发条件：连续 add 超过 size 个样本后调用 mean()。
- **[logic/high]** [logic] persistence/journal_alpha.py:47-53 JournalAlpha.compact 只重写磁盘文件，未同步内存 _records，导致后续 append 复活已丢弃记录（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_alpha.py:47-53`
  - 依据：compact() 计算 kept = self._records[surplus:] 并只把 kept 写入磁盘，但没有更新 self._records。于是内存中仍保留全部旧记录，下一次 append() 调用 _flush() 时会用完整的 self._records 重写文件，被压缩掉的记录全部复活；replay()/count() 也仍返回未压缩的数据。触发条件：先 append 超过 keep 条，再 compact()，再 append 任意一条。
- **[logic/high]** [logic] persistence/journal_beta.py:51-58 compact() 未更新内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-58`
  - 依据：与 journal_alpha 相同：compact() 仅写盘，未同步 self._records。压缩后 replay()/count() 仍返回被丢弃的记录，后续 append 触发的 _flush() 会把旧记录重新写回，压缩失效。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 compact() 未更新内存中的 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：与 journal_alpha 相同：compact() 只写盘未更新 self._records，导致 replay()/count() 与 disk_count() 不一致，且后续 append 会把被压缩的记录重新写回磁盘。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:60-66 close 只关闭空闲资源，未处理在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：close 仅遍历 _free 关闭空闲资源，_in_use 中的资源永远不会被关闭，造成资源泄漏；同时 close 后没有设置关闭标志，acquire 仍可继续创建/借出资源，close 语义不完整。触发条件：在存在已借出资源时调用 close。
- **[logic/medium]** [logic] resources/pool_beta.py:47-50 release 未校验资源归属，可重复归还导致资源泄漏与计数错误（确认存在缺陷）
  - 独立来源 5 个：reader-r0-1, reader-r0-2, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：与 pool_alpha 相同：release 不检查资源是否在 _in_use 中、也不从 _in_use 删除，重复归还会让同一资源被多次借出，且 in_use 统计失真。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:61-66 close 只关闭空闲资源，借出中的资源永不关闭（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_beta.py:61-66`
  - 依据：与 pool_alpha 相同：close 不处理 _in_use 中的资源，也不阻止后续 release 把资源放回已关闭的池，导致借出资源泄漏。
- **[logic/high]** [logic] resources/pool_gamma.py:47-50 release 未校验资源归属，可重复归还导致资源泄漏与计数错误（确认存在缺陷）
  - 独立来源 5 个：reader-r0-1, reader-r0-2, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：release 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。同一资源被 release 两次会进入 _free 两次，后续 acquire 会把同一对象发给两个调用者；同时 _in_use 集合永不缩小，stats 的 in_use 计数错误。触发条件：调用方重复归还或归还非本池资源。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:61-66 close 只关闭空闲资源，借出中的资源永不关闭（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_gamma.py:61-66`
  - 依据：close 只遍历 _free 调用 closer，_in_use 中的资源不会被关闭，也没有标记池已关闭。若调用方在 close 前借出资源且不再归还，这些资源（如连接/文件句柄）会泄漏。触发条件：存在未归还资源时调用 close。
- **[logic/high]** [logic] scheduling/scheduler_alpha.py:47-53 reprioritize 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:47-53`
  - 依据：堆内元素的排序键 priority 被就地修改后没有调用 heapq.heapify 或重新入堆，堆不变式被破坏。此后 take() 弹出的不一定是当前优先级最高的作业，饥饿缓解逻辑失效。触发条件：对已入队作业调用 reprioritize 后再 take。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:47-53 reprioritize 直接修改堆内元素优先级，破坏堆序（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:47-53`
  - 依据：与 SchedulerAlpha 相同：就地修改 priority 后未重建堆，堆序失效，take() 返回顺序不再按优先级。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:47-50 reprioritize 直接修改堆内元素优先级导致堆序失效（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:47-50`
  - 依据：与 scheduler_alpha/beta 相同：直接修改堆中 _Item 的 priority 字段而不重建堆，破坏堆不变式，take() 返回顺序不再保证按优先级。触发条件：入队后调用 reprioritize 再 take。
- **[error_handling/medium]** [error_handling] wire/codec_alpha.py:46-47 total_size 对缺失 size 的记录抛 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r1-0｜置信度 0.5
  - 源：`wire/codec_alpha.py:46-47`
  - 依据：decode 在 version<1 时不会写入 size 键（只有 name），而 total_size 直接用 self.decode(payload)["size"] 取值，遇到 v=0 或缺失 v 且无 size 的 payload 会抛 KeyError 而非返回 0。触发条件：传入 version<1 的 payload。
- **[logic/high]** [logic] wire/codec_alpha.py:30-38 decode 对 v1 载荷读取 size 字段，与 encode 写入的 size_bytes 不匹配（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:30-38`
  - 依据：encode() 写入的字段是 size_bytes，而 decode() 在 version>=1 和 version>=2 分支都读取 payload.get("size", 0)，字段名不一致。对任何由本编解码器产生的载荷（v=2），decode 得到的 size 恒为 0，round-trip 丢失 size 信息；total_size 也因此恒为 0。
- **[error_handling/medium]** [error_handling] wire/codec_beta.py:44-45 total_size 对缺失 size 的载荷会抛 KeyError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-2, reader-r1-0, reader-r1-2｜置信度 0.5
  - 源：`wire/codec_beta.py:44-45`
  - 依据：decode 在 version<1 时不会写入 out["size"]（只有 name），而 total_size 直接用 self.decode(payload)["size"] 取值。对 v=0 或缺失 v 且无 size 的载荷，会抛出 KeyError 而非返回合理默认值。触发条件：传入 version 小于 1 的载荷。
- **[logic/high]** [logic] wire/codec_beta.py:33-40 decode 对 v2 记录读取 size 而非 size_bytes，导致 size 恒为 0（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-2｜置信度 0.5
  - 源：`wire/codec_beta.py:33-40`
  - 依据：encode() 把大小写入键 'size_bytes'（v2 字段），但 decode() 在 version >= 1 和 version >= 2 两个分支都读取 payload.get('size', 0)。对于 v2 线格式，'size' 键不存在，因此 out['size'] 恒为 0，total_size() 也恒返回 0。触发条件：encode 后再 decode 任意记录即可复现。
- **[error_handling/medium]** [error_handling] wire/codec_gamma.py:46-47 total_size 对缺失 size 的 payload 抛 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r1-0｜置信度 0.5
  - 源：`wire/codec_gamma.py:46-47`
  - 依据：与 codec_alpha 相同：当 payload 的 v<1 时 decode 不写入 size，total_size 下标访问抛 KeyError。
- **[logic/high]** [logic] wire/codec_gamma.py:30-38 decode 对 v1 载荷读取 size 字段，与 encode 写入的 size_bytes 不匹配（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:30-38`
  - 依据：与 codec_alpha 相同：encode 写入 size_bytes，decode 读取 size，字段名不匹配导致解码后 size 恒为 0，round-trip 丢失数据。
- **[concurrency/medium]** [concurrency] wiring/registry_alpha.py:22-25 get 的惰性构造非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r1-2｜置信度 0.5
  - 源：`wiring/registry_alpha.py:22-25`
  - 依据：get() 先检查 name not in self._instances 再调用 _build 并写回，整个过程没有加锁。多线程并发首次获取同一名字时，两个线程都可能通过检查并各自构造一个实例，违反“同名组件在进程内只应存在一个实例”的约定，且 _build_count 也会被多计。
- **[concurrency/medium]** [concurrency] wiring/registry_beta.py:24-26 RegistryBeta.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r1-2｜置信度 0.5
  - 源：`wiring/registry_beta.py:24-26`
  - 依据：与 RegistryAlpha 相同：get() 的检查-构造-写入无锁保护，多线程并发首次取用同一 name 时可能重复构造实例，违反“同名组件只应存在一个实例”的约定，并使 _build_count 偏大。
- **[concurrency/medium]** [concurrency] wiring/registry_gamma.py:24-26 RegistryGamma.get 非线程安全，可能重复构造实例（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r1-2｜置信度 0.5
  - 源：`wiring/registry_gamma.py:24-26`
  - 依据：get() 采用 check-then-act：先判断 name 不在 _instances，再调用 _build 并写入。两个线程同时首次获取同一名字时都会通过判断，各自构造一个实例，后写入者覆盖前者，违反类文档中“同名组件在进程内只应存在一个实例”的约定，且 build_count 会多计。

## 待验证（孤证）

- **[api_misuse/medium]** [api_misuse] resources/pool_alpha.py:61-67 close() 调用 factory.close 而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:61-67`
  - 依据：closer = getattr(self._factory, 'close', None) 取的是工厂函数的 close 属性，而循环里却调用 closer(resource)，把资源对象当作参数传给工厂的 close。若工厂本身没有 close 属性（常见情况），则资源永远不会被关闭，造成资源泄漏；若工厂恰好有 close，则语义也完全错误（应调用 resource.close()）。正确写法应为 getattr(resource, 'close', None)。
- **[boundary/low]** [boundary] resources/pool_alpha.py:38-41 acquire 超时计算使用 monotonic，逻辑正确（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:38-41`
  - 依据：deadline 基于 time.monotonic() 计算，remaining <= 0 时抛 TimeoutError，wait(remaining) 使用剩余时间，能正确处理虚假唤醒与超时边界，未发现缺陷。
- **[concurrency/high]** [concurrency] resources/pool_alpha.py:47-50 release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release() 直接把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复 release 同一资源（或 release 从未 acquire 的资源），_free 中会出现重复条目，后续两次 acquire 会返回同一个对象，破坏“池内资源总数不超过 size”和互斥借出的约定，导致并发使用同一资源。触发条件：对同一 resource 调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:59-64 close 未清理 _in_use，且关闭后仍可继续借出资源（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:59-64`
  - 依据：close() 只关闭并清空 _free 中的空闲资源，_in_use 中的资源既不关闭也不清空，_created 也不重置。关闭后调用 acquire() 时，由于 _created 仍等于已创建数量，若 _created < size 会继续通过 factory 新建资源，池在“已关闭”状态下仍可借出资源，且这些新资源永远不会被 close 回收。触发条件：close() 之后再次 acquire()。
- **[api_misuse/medium]** [api_misuse] resources/pool_beta.py:61-67 close() 调用 factory.close 而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:61-67`
  - 依据：同 pool_alpha：closer 取自 self._factory 的 close 属性，却以 resource 为参数调用，导致资源无法被正确关闭（工厂通常没有 close 属性），造成资源泄漏。
- **[concurrency/high]** [concurrency] resources/pool_beta.py:47-50 release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：与 pool_alpha 相同：release() 直接把 resource 追加到 _free 并 notify，不检查是否在 _in_use 中，也不从 _in_use 移除。重复 release 同一资源会使 _free 出现重复条目，后续 acquire 返回同一对象，破坏互斥借出约定。触发条件：对同一 resource 调用 release 两次。
- **[performance/low]** [performance] resources/pool_beta.py:33-36 acquire 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:33-36`
  - 依据：同 pool_alpha：在条件变量临界区内调用工厂函数，工厂慢时会阻塞其他线程的 acquire/release。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:59-64 close 未清理 _in_use，且关闭后仍可继续借出资源（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_beta.py:59-64`
  - 依据：close() 只关闭并清空 _free 中的空闲资源，_in_use 中的资源既不关闭也不清空，_created 也不重置。关闭后 acquire() 仍可能新建资源，池在已关闭状态下继续借出且新资源无法被回收。触发条件：close() 之后再次 acquire()。
- **[api_misuse/medium]** [api_misuse] resources/pool_gamma.py:61-67 close() 调用 factory.close 而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:61-67`
  - 依据：同 pool_alpha/pool_beta：closer 取自 self._factory 的 close 属性，却以 resource 为参数调用，导致资源无法被正确关闭（工厂通常没有 close 属性），造成资源泄漏。
- **[concurrency/high]** [concurrency] resources/pool_gamma.py:47-50 release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：与 pool_alpha/pool_beta 相同：release() 直接把 resource 追加到 _free 并 notify，不检查是否在 _in_use 中，也不从 _in_use 移除。重复 release 同一资源会使 _free 出现重复条目，后续 acquire 返回同一对象，破坏互斥借出约定。触发条件：对同一 resource 调用 release 两次。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:59-64 close 未清理 _in_use，且关闭后仍可继续借出资源（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:59-64`
  - 依据：close() 只关闭并清空 _free 中的空闲资源，_in_use 中的资源既不关闭也不清空，_created 也不重置。关闭后 acquire() 仍可能新建资源，池在已关闭状态下继续借出且新资源无法被回收。触发条件：close() 之后再次 acquire()。
- **[logic/low]** [logic] scheduling/scheduler_alpha.py:62-66 cancel 后堆中残留项使 pending 与 take 行为不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:62-66`
  - 依据：cancel 只从 _items 删除，堆中残留项由 take 的惰性删除逻辑（item.name in self._items 检查）跳过，pending() 返回 len(self._items) 也正确。这是常见的惰性删除设计，不构成缺陷。
- **[resource_leak/low]** [resource_leak] scheduling/scheduler_alpha.py:60-64 SchedulerAlpha/Beta/Gamma 的 cancel 只删字典不删堆，堆中残留项被 take 跳过（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:60-64`
  - 依据：cancel 仅从 _items 删除，堆中仍保留该 _Item；take() 通过 `if item.name in self._items` 判断并跳过已取消项，因此不会返回已取消作业，pending() 也基于 _items 计数正确。残留项会在后续 take 循环中被弹出清理，属于惰性删除的常见实现，不构成功能缺陷（仅内存短暂占用）。
- **[logic/medium]** [logic] wire/codec_alpha.py:41-42 CodecAlpha.total_size 依赖 decode 的 size，v2 记录会全部计为 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`wire/codec_alpha.py:41-42`
  - 依据：total_size 通过 self.decode(payload)['size'] 求和。由于 decode 对 v2 记录读取的是不存在的 'size' 键而返回 0（见上一条），对 v2 payload 调用 total_size 会恒返回 0，与 encode 写入的 size_bytes 不符。触发条件：传入由 encode() 生成的 v2 payload 列表。
- **[error_handling/low]** [error_handling] wiring/registry_alpha.py:24-26 get 未校验名称是否已注册，未注册名称抛出 KeyError 而非明确错误（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_alpha.py:24-26`
  - 依据：get() 对未注册名称会经 _build 访问 self._factories[name] 抛出 KeyError。虽然错误信息不如显式检查友好，但行为是确定且可预期的（KeyError 是字典访问未注册键的自然结果），不构成错误行为，因此不算缺陷。
- **[logic/low]** [logic] wiring/registry_alpha.py:43-44 RegistryAlpha.clear 只清实例不清 build_count，属预期行为（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_alpha.py:43-44`
  - 依据：clear() 仅清空 _instances，保留 _factories 与 _build_count。build_count 作为累计构造次数指标，clear 后不清零是合理语义，未发现错误行为。
- **[error_handling/low]** [error_handling] wiring/registry_beta.py:24-26 get 未校验名称是否已注册，未注册名称抛出 KeyError 而非明确错误（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:24-26`
  - 依据：与 registry_alpha 相同：get() 对未注册名称经 _build 访问 self._factories[name] 抛出 KeyError，行为确定且可预期，不构成错误行为。
- **[logic/low]** [logic] wiring/registry_beta.py:40-41 clear 只清实例缓存，build_count 不重置（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:40-41`
  - 依据：clear 清空 _instances 后再次 get 会重新构造，_build_count 继续累加。这是累计构造次数的语义，并非错误；build_count 作为累计计数器保留历史值是合理设计，不构成缺陷。
- **[error_handling/low]** [error_handling] wiring/registry_gamma.py:28-30 RegistryGamma.get 对未注册名字抛出 KeyError 而非明确错误，且 _build_count 已自增（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:28-30`
  - 依据：_build 先自增 _build_count 再访问 self._factories[name]，若 name 未注册会抛 KeyError，且 _build_count 已被错误地加一。但 get() 只在 name 不在 _instances 时调用 _build，未注册名字必然不在 _instances，因此 KeyError 是预期行为；_build_count 在失败路径上偏大属于统计口径问题，不影响实例复用语义，不构成真实缺陷。
- **[logic/low]** [logic] wiring/registry_gamma.py:39-40 clear 只清实例不清工厂，build_count 持续累加（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:39-40`
  - 依据：clear() 仅清空 _instances 而保留 _factories，符合“重置缓存”的语义；build_count 作为累计构造次数持续累加也是合理设计，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_gamma.py:43-44 clear() 只清实例缓存，_build_count 不重置（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:43-44`
  - 依据：同 registry_alpha.py：build_count 表示累计构造次数，clear 后继续累加符合语义，不是缺陷。

## 争议（需裁决）

- **[boundary/medium]** [boundary] analytics/window_alpha.py:41-45 percentile 未校验 ratio 范围，越界索引会抛 IndexError（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r1-1, reader-r2-0, reader-r2-2｜置信度 0.5
  - 源：`analytics/window_alpha.py:41-45`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1（如 1.5）或 ratio < 0（如 -0.1）时，index 会超出 [0, len-1] 范围，ordered[index] 抛出 IndexError。函数没有对 ratio 做任何范围校验或钳制。触发条件：调用方传入超出 [0,1] 的 ratio。
  - 争议对手：1885b4112aca
- **[logic/high]** [logic] resources/pool_alpha.py:51-54 release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 5 个：reader-r0-1, reader-r0-2, reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 源：`resources/pool_alpha.py:51-54`
  - 依据：release 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。若调用方重复 release 同一资源（或 release 一个从未借出的资源），_free 中会出现重复条目，后续 acquire 会把同一对象同时交给多个调用方，破坏池的互斥语义；同时 _in_use 集合永远不缩小，stats 的 in_use 计数失真。触发条件：对同一资源调用 release 两次。
  - 争议对手：c1d57ee1a5b8
- **[performance/low]** [performance] resources/pool_alpha.py:33-36 acquire 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:33-36`
  - 依据：acquire() 在 with self._available 临界区内直接调用 self._factory()。若工厂构造耗时较长（如建立网络连接），会长时间持有条件变量锁，阻塞所有其他 acquire/release/stats 调用，降低并发吞吐。触发条件：工厂构造慢且并发访问。
  - 争议对手：9174805ee232, bfcb0c888dcc, f1925661634c
- **[performance/low]** [performance] resources/pool_gamma.py:33-36 acquire 在持锁状态下调用 factory()，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:33-36`
  - 依据：同 pool_alpha/pool_beta：在条件变量临界区内调用工厂函数，工厂慢时会阻塞其他线程的 acquire/release。
  - 争议对手：7a785f42bf78

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 6 | 0 | 5 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 5 | 1 | 1 | 0 | 5 | 0 | 4 | 1 |
| `scheduling` | 6 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `wire` | 4 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| `wiring` | 4 | 4 | 0 | 3 | 0 | 0 | 0 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
