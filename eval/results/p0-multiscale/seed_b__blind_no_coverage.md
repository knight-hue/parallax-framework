# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 25 | 单一来源孤证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：31

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 28 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/high]** [logic] analytics/window_alpha.py:22-26 滑动窗口均值在淘汰旧样本后仍使用累计总和，导致均值错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-26`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只增不减，从未减去被淘汰的值。因此一旦窗口满且继续 add，mean() 返回的 _total/len(_values) 会包含已被淘汰样本的贡献，均值随样本数增长而持续偏大，完全错误。触发条件：add 次数超过 size。
- **[logic/high]** [logic] analytics/window_beta.py:22-26 滑动窗口均值在淘汰旧样本后仍使用累计总和，导致均值错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`analytics/window_beta.py:22-26`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，窗口满后 mean() 会因包含已淘汰样本而偏大。触发条件：add 次数超过 size。
- **[logic/high]** [logic] analytics/window_gamma.py:22-26 滑动窗口均值在淘汰旧样本后仍使用累计总和，导致均值错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-26`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只累加不扣减，窗口满后 mean() 会因包含已淘汰样本而偏大。触发条件：add 次数超过 size。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-58 compact() 未同步内存中的 _records，导致重放与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-58`
  - 依据：compact() 只把截断后的 kept 写入磁盘，却没有更新 self._records。触发条件：先 append 若干条使 len(_records) > keep，再调用 compact()。此后 replay()/count() 仍返回全部旧记录（含已被丢弃的），而 disk_count() 返回 keep 条，二者不一致；后续 append() 调用 _flush() 会把内存中未截断的 _records 全量写回磁盘，使压缩结果被撤销。
- **[logic/high]** [logic] persistence/journal_beta.py:51-58 compact() 未同步内存中的 _records，导致重放与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-58`
  - 依据：compact() 只把裁剪后的 kept 写入磁盘，却没有更新 self._records。触发条件：先 append 超过 keep 条记录，再调用 compact()。此后 replay()/count() 仍返回全部旧记录（含已被丢弃的），而 disk_count() 返回裁剪后的条数，内存与磁盘状态永久分叉；后续 append() 还会用未裁剪的 _records 重写文件，把已丢弃的记录重新写回磁盘，使 compact 完全失效。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 compact() 未同步内存中的 _records，导致重放与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：与 journal_beta.py 相同：compact() 仅重写磁盘文件，未将 self._records 替换为 kept。触发条件：append 超过 keep 条后调用 compact()。结果 replay()/count() 与 disk_count() 不一致，且下一次 append() 会基于未裁剪的 _records 重写文件，把已丢弃记录恢复，压缩失效。
- **[concurrency/high]** [concurrency] resources/pool_alpha.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查它是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release()（或归还从未借出的资源）。此时 _free 中出现重复条目，两个线程可各自 pop 到同一个对象，破坏“同一资源同时只被一个持有者使用”的池语义；同时 _in_use 集合因从未删除而永久膨胀，stats() 的 in_use 计数失真。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:60-65 close() 只关闭空闲资源，已借出资源泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-65`
  - 依据：close() 仅遍历 self._free 调用 closer，对仍在 _in_use 中的资源不做任何处理，也不阻止后续 acquire()。触发条件：在仍有资源被借出时调用 close()，这些资源永远不会被关闭，造成句柄/连接泄漏；且 close() 后 acquire() 仍可继续新建资源，与“关闭”语义矛盾。
- **[concurrency/high]** [concurrency] resources/pool_beta.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：与 pool_alpha 相同：release() 无条件把 resource 追加到 _free 并 notify，不检查是否在 _in_use 中，也不从 _in_use 移除。重复归还同一资源会让 _free 出现重复条目，两个线程可同时借到同一对象，破坏池的互斥语义，并使 stats() 的 in_use 计数永久偏高。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:60-65 close() 只关闭空闲资源，已借出资源泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_beta.py:60-65`
  - 依据：close() 只对 self._free 中的资源调用 closer，_in_use 中的资源被忽略且不会被回收，close() 之后 acquire() 仍可新建资源。触发条件：存在未归还资源时调用 close()，这些资源永久泄漏。
- **[concurrency/high]** [concurrency] resources/pool_gamma.py:47-50 release() 未校验资源归属，重复归还会使同一资源被多次借出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：与 pool_alpha/pool_beta 相同：release() 无条件把 resource 追加到 _free 并 notify，不检查是否在 _in_use 中，也不从 _in_use 移除。重复归还同一资源会让 _free 出现重复条目，两个线程可同时借到同一对象，破坏池的互斥语义，并使 stats() 的 in_use 计数永久偏高。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:60-65 close() 只关闭空闲资源，已借出资源泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`resources/pool_gamma.py:60-65`
  - 依据：close() 只对 self._free 中的资源调用 closer，_in_use 中的资源被忽略且不会被回收，close() 之后 acquire() 仍可新建资源。触发条件：存在未归还资源时调用 close()，这些资源永久泄漏。
- **[logic/high]** [logic] scheduling/scheduler_alpha.py:44-51 reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:44-51`
  - 依据：item 是已放入 heapq 的对象，直接赋值 item.priority 改变了参与比较的字段，但没有调用 heapq.heapify 或重新 push，堆序被破坏。之后 take() 的 heappop 不再保证返回当前优先级最高的作业，可能返回错误顺序。触发条件：对队列中作业调用 reprioritize 后再 take。
- **[logic/low]** [logic] scheduling/scheduler_alpha.py:61-65 cancel 只从字典删除，堆中残留项导致 pending 与堆不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:61-65`
  - 依据：cancel 删除 _items 中的条目，堆中残留的 _Item 会在 take() 中因 name 不在 _items 而被跳过并丢弃，pending() 返回 len(_items) 也正确。这是常见的惰性删除模式，行为正确，不构成缺陷。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:44-51 reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:44-51`
  - 依据：与 scheduler_alpha 相同：直接修改堆内 _Item.priority 而不重建堆，堆序失效，take() 可能返回非最高优先级作业。触发条件：reprioritize 后再 take。
- **[logic/low]** [logic] scheduling/scheduler_beta.py:61-65 cancel 只从字典删除，堆中残留项导致 pending 与堆不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:61-65`
  - 依据：与 scheduler_alpha 相同，惰性删除模式行为正确，take() 会跳过已取消项，pending() 计数正确。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:44-51 reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:44-51`
  - 依据：与 scheduler_alpha 相同：直接修改堆内 _Item.priority 而不重建堆，堆序失效，take() 可能返回非最高优先级作业。触发条件：reprioritize 后再 take。
- **[logic/low]** [logic] scheduling/scheduler_gamma.py:61-65 cancel 只从字典删除，堆中残留项导致 pending 与堆不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:61-65`
  - 依据：与 scheduler_alpha 相同，惰性删除模式行为正确，take() 会跳过已取消项，pending() 计数正确。
- **[logic/medium]** [logic] wire/codec_alpha.py:45-46 total_size 依赖 decode 的 size 字段，在 v2 载荷上恒返回 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:45-46`
  - 依据：total_size 对每个载荷调用 decode 后取 ['size']。由于 decode 的 v2 分支错误地读取 'size'（见上一条），对 v2 载荷该值恒为 0，total_size 对 v2 数据总是返回 0，聚合结果错误。
- **[logic/medium]** [logic] wire/codec_beta.py:45-46 total_size 依赖 decode 的 size 字段，在 v2 载荷上恒返回 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:45-46`
  - 依据：同 codec_alpha：decode 的 v2 分支错误导致 total_size 对 v2 载荷恒为 0。
- **[logic/medium]** [logic] wire/codec_gamma.py:45-46 total_size 依赖 decode 的 size 字段，在 v2 载荷上恒返回 0（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:45-46`
  - 依据：同 codec_alpha：decode 的 v2 分支错误导致 total_size 对 v2 载荷恒为 0。
- **[concurrency/high]** [concurrency] wiring/registry_alpha.py:25-27 get() 的检查-构造-缓存非原子，并发下会重复构造实例（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`wiring/registry_alpha.py:25-27`
  - 依据：get() 先判断 name not in self._instances，再调用 _build(name) 并写回缓存，整个过程没有任何锁。触发条件：两个线程同时首次 get 同一个名字，二者都通过存在性检查，各自调用工厂构造实例，后写入者覆盖先写入者。这违反类文档“同名组件在进程内只应存在一个实例”的约定，且 build_count 会多计，先构造出的实例被丢弃（若持有资源则泄漏）。
- **[concurrency/high]** [concurrency] wiring/registry_beta.py:25-27 get() 的检查-构造-缓存非原子，并发下会重复构造实例（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`wiring/registry_beta.py:25-27`
  - 依据：与 registry_alpha 相同：get() 的存在性检查、工厂调用与缓存写入之间没有同步。两个线程并发首次获取同一名字时会各自构造实例，后写入者覆盖先写入者，违反“同名组件在进程内只应存在一个实例”的约定，并使 build_count 多计、被覆盖的实例泄漏。
- **[concurrency/medium]** [concurrency] wiring/registry_gamma.py:25-27 get() 的检查-构造-缓存非原子，并发下会重复构造实例（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`wiring/registry_gamma.py:25-27`
  - 依据：get() 先检查 name not in self._instances，再调用 _build 构造，最后写回缓存，整个过程没有加锁。触发条件：两个线程同时对同一未构造的名字调用 get()，二者都可能通过检查并各自构造一个实例，后写入者覆盖前者，导致同名组件在进程内出现多个实例，违反类文档中“同名组件在进程内只应存在一个实例”的约定，且 _build_count 会被多计。
- **[logic/low]** [logic] wiring/registry_gamma.py:43-44 clear() 只清空实例缓存，未重置 _build_count（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:43-44`
  - 依据：clear() 清空 _instances 后，build_count() 仍保留历史累计值。但 build_count 的语义是“累计构造次数”，clear 只负责丢弃缓存实例，并不声明要重置计数；文档字符串也未承诺重置。因此这是设计选择而非缺陷，仅在此记录以免误报。

## 争议（需裁决）

- **[logic/high]** [logic] wire/codec_alpha.py:33-35 decode 在 v2 分支读取 size 而非 size_bytes，导致 v2 记录 size 丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:33-35`
  - 依据：encode 把大小写入 'size_bytes' 字段（第 22 行），但 decode 的 v2 分支读取的是 payload.get('size', 0)，而 v2 线格式中并不存在 'size' 键。因此对任何由本类 encode 产生的 v2 载荷调用 decode，out['size'] 恒为 0，size 信息完全丢失。触发条件：encode 后 decode，或解码任何符合 v2 规范的载荷。
  - 争议对手：54e922100487
- **[logic/high]** [logic] wire/codec_beta.py:33-35 decode 在 v2 分支读取 size 而非 size_bytes，导致 v2 记录 size 丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:33-35`
  - 依据：与 codec_alpha 相同：encode 写入 'size_bytes'，decode 的 v2 分支却读取 'size'，v2 载荷解码后 size 恒为 0。
  - 争议对手：5dadac7dcf16
- **[logic/high]** [logic] wire/codec_gamma.py:33-35 decode 在 v2 分支读取 size 而非 size_bytes，导致 v2 记录 size 丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:33-35`
  - 依据：与 codec_alpha 相同：encode 写入 'size_bytes'，decode 的 v2 分支却读取 'size'，v2 载荷解码后 size 恒为 0。
  - 争议对手：21b0cac2ccea

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| `scheduling` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 17%（单元格值 = 独立 Agent 数）
