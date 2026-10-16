# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 26 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 5 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：60

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 32 | 100% | 19% |

## 高置信结论

- **[boundary/medium]** [boundary] analytics/window_alpha.py:47-51 WindowAlpha.percentile 未校验 ratio 范围，越界索引可能抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_alpha.py:47-51`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 校验。当 ratio > 1 时 index 会超过 len(ordered)-1，ordered[index] 抛 IndexError；ratio 为负时 Python 负索引会静默返回错误元素（如 ratio=-0.1 返回最大值），属于静默错误。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_alpha.py:22-25 WindowAlpha._total 在 deque 自动淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动丢弃最旧样本，但 _total 只做累加、从不扣减被淘汰的值。一旦样本数超过 size，_total 会持续累积所有历史值，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度，分子却是全部历史之和，均值会随写入量单调膨胀，完全错误。触发条件：add() 调用次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_beta.py:47-51 WindowBeta.percentile 未校验 ratio 范围，越界索引可能抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_beta.py:47-51`
  - 依据：同 WindowAlpha：ratio 未做范围校验，ratio > 1 时 index 越界抛 IndexError，ratio < 0 时负索引静默返回错误元素。触发条件：传入越界 ratio。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 WindowBeta._total 在 deque 自动淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：与 WindowAlpha 相同：deque(maxlen=size) 在 append 时自动淘汰最旧元素，但 _total 只累加不扣减。样本数超过 size 后 mean() 的分子包含已淘汰样本，分母仅为当前窗口长度，结果偏大且随写入量增长。触发条件：add() 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:47-51 WindowGamma.percentile 未校验 ratio 范围，越界索引可能抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_gamma.py:47-51`
  - 依据：ratio 未做 [0,1] 校验，ratio > 1 时 index 越界抛 IndexError，ratio < 0 时负索引静默返回错误元素。触发条件：传入越界 ratio。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 WindowGamma 的 _total 在 deque 自动淘汰旧样本时未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：deque(maxlen=size) 在 append 超出容量时会自动丢弃最旧元素，但 add() 只做 self._total += value，从不减去被淘汰的值。因此一旦窗口内样本数达到 size 后继续 add，_total 会持续累加所有历史样本，而 mean() 用 self._total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，均值会随样本增多而单调膨胀，完全错误。触发条件：add 次数超过 size（默认 32）。
- **[logic/high]** [logic] persistence/journal_alpha.py:51-58 JournalAlpha.compact 只重写磁盘文件，未同步更新内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_alpha.py:51-58`
  - 依据：compact() 计算 surplus 后把 kept 写入磁盘，但没有把 self._records 更新为 kept。因此 compact() 之后：count()/replay() 仍返回全部旧记录（含已丢弃的），而 disk_count() 返回压缩后的条数，两者不一致；后续 append() 调用 _flush() 会把内存中未裁剪的 _records 全量写回磁盘，直接撤销压缩效果。触发条件：记录数超过 keep 后调用 compact()，再调用 append() 或 replay()。
- **[logic/high]** [logic] persistence/journal_beta.py:51-58 JournalBeta.compact 只重写磁盘文件，未同步更新内存 _records（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_beta.py:51-58`
  - 依据：compact() 计算 kept 并写入磁盘，但没有把 self._records 更新为 kept。触发条件：append 超过 keep 条后调用 compact()，随后 replay()/count() 仍返回全部旧记录，而 disk_count() 返回压缩后的条数，内存与磁盘不一致；再次 append 时 _flush 会把未压缩的完整 _records 写回磁盘，使压缩失效。
- **[logic/high]** [logic] persistence/journal_gamma.py:51-58 JournalGamma.compact 只重写磁盘文件，未同步更新内存 _records（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`persistence/journal_gamma.py:51-58`
  - 依据：compact() 计算 kept 并写入磁盘，但没有把 self._records 更新为 kept。触发条件：append 超过 keep 条后调用 compact()，随后 replay()/count() 仍返回全部旧记录，而 disk_count() 返回压缩后的条数，内存与磁盘不一致；再次 append 时 _flush 会把未压缩的完整 _records 写回磁盘，使压缩失效。
- **[logic/high]** [logic] resources/pool_alpha.py:47-50 PoolAlpha.release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：release() 无条件把 resource 追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除。触发条件：调用方对同一资源调用两次 release（或 release 一个从未 acquire 的对象）。结果 _free 中出现重复条目，后续两次 acquire 会返回同一个对象，破坏“池内资源总数不超过 size / 独占借出”的核心契约，且 _in_use 计数永远不减少，stats() 失真。
- **[resource_leak/medium]** [resource_leak] resources/pool_alpha.py:60-66 PoolAlpha.close 未关闭在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：close() 只遍历 _free 关闭空闲资源，_in_use 中的资源永远不会被关闭，造成资源泄漏；同时 close() 没有设置关闭标志，之后调用 acquire() 仍会从 _free 取（已关闭的）资源或通过 factory 新建资源，导致使用已关闭资源或关闭后继续泄漏。
- **[logic/high]** [logic] resources/pool_beta.py:47-50 PoolBeta.release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：与 PoolAlpha 相同：release() 无条件把 resource 追加到 _free 并 notify，不检查是否在 _in_use 中，也不从 _in_use 移除。重复 release 会让 _free 出现重复条目，后续 acquire 返回同一对象，破坏独占借出契约，_in_use 计数也永不减少。
- **[resource_leak/medium]** [resource_leak] resources/pool_beta.py:60-66 PoolBeta.close 未关闭在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_beta.py:60-66`
  - 依据：close() 只关闭 _free 中的空闲资源，_in_use 中的资源不会被关闭，造成泄漏；且没有关闭标志，close() 之后 acquire() 仍可返回已关闭资源或新建资源，行为不符合关闭语义。
- **[logic/high]** [logic] resources/pool_gamma.py:47-50 PoolGamma.release 未校验资源归属，重复归还会导致同一资源被多次借出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:47-50`
  - 依据：release() 无条件把资源追加到 _free 并 notify，既不检查该资源是否在 _in_use 中，也不从 _in_use 移除其 id。重复归还同一资源会使 _free 出现重复条目，后续 acquire 可能把同一对象同时交给两个调用者，破坏池的互斥语义。
- **[resource_leak/medium]** [resource_leak] resources/pool_gamma.py:60-66 PoolGamma.close 未关闭在用资源且未阻止后续 acquire（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`resources/pool_gamma.py:60-66`
  - 依据：close() 只关闭 _free 中的空闲资源，_in_use 中的资源不会被关闭，造成泄漏；且没有关闭标志，close() 之后 acquire() 仍可返回已关闭资源或新建资源，行为不符合关闭语义。
- **[logic/high]** [logic] scheduling/scheduler_beta.py:45-50 SchedulerBeta.reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`scheduling/scheduler_beta.py:45-50`
  - 依据：同 SchedulerAlpha：直接赋值 item.priority 而不重建堆，堆序被破坏，take() 可能返回非最高优先级作业。
- **[logic/high]** [logic] scheduling/scheduler_gamma.py:45-50 SchedulerGamma.reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`scheduling/scheduler_gamma.py:45-50`
  - 依据：同 SchedulerAlpha/Beta：直接赋值 item.priority 而不重建堆，堆序被破坏，take() 可能返回非最高优先级作业。
- **[error_handling/medium]** [error_handling] wire/codec_alpha.py:44-45 CodecAlpha.total_size 对缺失 size 的记录抛 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:44-45`
  - 依据：total_size 使用 self.decode(payload)["size"] 直接下标取值。decode 对 v1 记录会设置 out["size"]，但对 v2 记录同样设置 size（值为 0），因此对合法 v2 记录不会抛 KeyError；然而若 payload 的 v 字段为 0 或负数（version<1），decode 不会写入 size 键，此时 total_size 抛 KeyError。触发条件：传入 v<=0 的 payload。
- **[logic/high]** [logic] wire/codec_alpha.py:31-38 CodecAlpha.decode 对 v2 记录读取 size 而非 size_bytes（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_alpha.py:31-38`
  - 依据：encode() 把字节数写入 size_bytes 字段，但 decode() 在 version>=2 分支读取 payload.get("size", 0)，而 v2 线格式中并不存在 size 字段，因此解码结果 size 恒为 0，丢失编码时写入的字节数。触发条件：encode 后 decode 同一记录。
- **[error_handling/medium]** [error_handling] wire/codec_beta.py:44-45 CodecBeta.total_size 对缺失 size 的记录会抛 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:44-45`
  - 依据：decode() 在 version<1 时不会写入 'size' 键（只有 version>=1 分支才设置 out['size']），但 total_size() 无条件访问 self.decode(payload)['size']。当传入 v=0 或负版本的 payload 时，decode 返回的字典没有 'size'，total_size 抛 KeyError 而非返回合理值。触发条件：payload 的 v 字段小于 1。
- **[logic/high]** [logic] wire/codec_beta.py:31-38 CodecBeta.decode 对 v2 记录读取 size 而非 size_bytes，丢失编码时写入的字节数（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_beta.py:31-38`
  - 依据：encode() 把 record['size'] 写入 'size_bytes' 字段，但 decode() 在 version>=2 分支读取的是 payload.get('size', 0)，而线格式中并不存在 'size' 键，因此解码结果 size 恒为 0，编码时写入的字节数被丢弃，round-trip 不一致。
- **[error_handling/medium]** [error_handling] wire/codec_gamma.py:44-45 CodecGamma.total_size 对缺失 size 的记录抛 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:44-45`
  - 依据：total_size 使用 self.decode(payload)["size"] 直接下标取值。decode 对 v1 记录会设置 out["size"]，但对 v2 记录同样设置 size（值为 0），因此对合法 v2 记录不会抛 KeyError；然而若 payload 的 v 字段为 0 或负数（version<1），decode 不会写入 size 键，此时 total_size 抛 KeyError。触发条件：传入 v<=0 的 payload。
- **[logic/high]** [logic] wire/codec_gamma.py:31-38 CodecGamma.decode 对 v2 记录读取 size 而非 size_bytes（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`wire/codec_gamma.py:31-38`
  - 依据：encode() 把字节数写入 size_bytes 字段，但 decode() 在 version>=2 分支读取 payload.get("size", 0)，而 v2 线格式中并不存在 size 字段，因此解码结果 size 恒为 0，丢失编码时写入的字节数。触发条件：encode 后 decode 同一记录。
- **[concurrency/medium]** [concurrency] wiring/registry_alpha.py:24-26 RegistryAlpha.get 非线程安全，并发首次取用会构造多个实例（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_alpha.py:24-26`
  - 依据：get() 采用 check-then-act：先判断 name 不在 _instances，再调用 _build 并写入。没有加锁，两个线程同时首次 get 同一名字时会各自构造实例，后写入者覆盖前者，违反“同名组件在进程内只应存在一个实例”的约定，且 _build_count 也会多计。
- **[concurrency/medium]** [concurrency] wiring/registry_beta.py:24-26 RegistryBeta.get 非线程安全，并发首次取用会构造多个实例（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_beta.py:24-26`
  - 依据：get() 采用 check-then-act：先判断 name 不在 _instances，再调用 _build 并写入。没有加锁，两个线程同时首次 get 同一名字时会各自构造实例，后写入者覆盖前者，违反“同名组件在进程内只应存在一个实例”的约定，且 _build_count 也会多计。
- **[concurrency/medium]** [concurrency] wiring/registry_gamma.py:24-26 RegistryGamma.get 非线程安全，并发首次取用会构造多个实例（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`wiring/registry_gamma.py:24-26`
  - 依据：get() 先检查 name not in self._instances，再调用 _build 并写回缓存，检查与写入之间没有锁。触发条件：两个线程同时首次 get 同一 name，二者都通过存在性检查，各自调用工厂构造实例，_build_count 变为 2，违反“同名组件在进程内只应存在一个实例”的约定，且其中一个实例被丢弃。

## 待验证（孤证）

- **[error_handling/low]** [error_handling] persistence/journal_alpha.py:25-29 JournalAlpha._load 对损坏行直接抛异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_alpha.py:25-29`
  - 依据：json.loads 对非空行解析失败会抛 JSONDecodeError，但这是文件损坏时的合理失败方式，且调用方在 __init__ 中同步感知，不属于静默错误。未发现需要吞掉异常的契约要求，因此不认定为缺陷。
- **[performance/low]** [performance] persistence/journal_alpha.py:46-48 JournalAlpha.append 每次全量重写文件（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_alpha.py:46-48`
  - 依据：append 调用 _flush 全量重写文件，在记录数很大时是 O(n) 写放大，但类文档明确说明“append() 追加一条并重写文件”，这是设计选择而非缺陷；keep 默认 200 也限制了规模。
- **[error_handling/low]** [error_handling] wiring/registry_beta.py:28-30 RegistryBeta.get 对未注册名字抛 KeyError 而非明确错误（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:28-30`
  - 依据：get() 对未注册名字会在 _build 中通过 self._factories[name] 抛 KeyError。虽然错误信息不够友好，但 has() 提供了显式检查手段，且 KeyError 是合理的失败语义，不构成行为缺陷。
- **[logic/low]** [logic] wiring/registry_beta.py:41-42 RegistryBeta.clear 清空实例但不清零 build_count，计数语义不一致（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_beta.py:41-42`
  - 依据：clear() 只清空 _instances，_build_count 保留累计值。build_count() 的语义是“累计构造次数”，clear 后重新 get 会再次构造并递增，属于可接受的累计统计，不构成缺陷。
- **[logic/low]** [logic] wiring/registry_gamma.py:41-42 RegistryGamma.clear 清空实例缓存但保留工厂，语义上可接受（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`wiring/registry_gamma.py:41-42`
  - 依据：clear() 只清空 _instances，_factories 保留，因此之后 get() 会重新构造实例。这是“重置缓存”的合理实现，没有与文档约定冲突（约定只要求同一时刻单实例）。不构成缺陷。

## 争议（需裁决）

- **[logic/high]** [logic] scheduling/scheduler_alpha.py:45-50 SchedulerAlpha.reprioritize 直接修改堆内元素优先级，破坏堆不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`scheduling/scheduler_alpha.py:45-50`
  - 依据：reprioritize() 直接对已入堆的 _Item 赋值 item.priority，没有调用 heapq 的修复操作（如 _siftup/_siftdown 或先删后插）。触发条件：对堆中非根元素提权或降权后，堆序不再成立，take() 返回的“当前优先级最高作业”可能不是真正的最小优先级元素，饥饿缓解逻辑失效。
  - 争议对手：3792417ca829

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 2 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| `resources` | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| `scheduling` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `wiring` | 1 | 2 | 0 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 27%（单元格值 = 独立 Agent 数）
