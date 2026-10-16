# Parallax 运行报告 `4b4940197cd8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 84 | 单一来源孤证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：5 个（每轮全新身份）
- 账本条目：84

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 5 | 84 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] analytics/window_alpha.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_alpha.py:44-48`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1（如 1.5）或 ratio < 0（如 -0.1）时，index 会超出 [0, len-1] 范围，ordered[index] 抛出 IndexError。方法未对 ratio 做任何范围校验或钳制，调用方传入越界值即崩溃。
- **[logic/high]** [logic] analytics/window_alpha.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，当窗口已满时 append 会自动淘汰最旧样本，但 add() 只做 self._total += value，从不减去被淘汰的值。因此一旦样本数超过 size，_total 会持续累加所有历史样本，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史样本之和，均值会随样本增多而单调膨胀，结果完全错误。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_beta.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_beta.py:44-48`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 范围校验。当 ratio > 1 时 index 会超过 len(ordered)-1，当 ratio < 0 时 index 为负且可能超出负向边界，ordered[index] 会抛出 IndexError。触发条件：调用 percentile(1.5) 或 percentile(-0.1) 等越界值。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此当添加样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<= size），分子却是全部历史之和，结果被严重高估。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_delta.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_delta.py:44-48`
  - 依据：同 window_alpha：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无校验。
- **[logic/high]** [logic] analytics/window_delta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_delta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧元素，但 _total 只增不减，mean() 分子包含已淘汰样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。
- **[boundary/medium]** [boundary] analytics/window_epsilon.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_epsilon.py:44-48`
  - 依据：同 window_alpha：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无校验。
- **[logic/high]** [logic] analytics/window_epsilon.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_epsilon.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧元素，但 _total 只增不减，mean() 分子包含已淘汰样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。
- **[boundary/medium]** [boundary] analytics/window_eta.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_eta.py:44-48`
  - 依据：同 window_alpha：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无校验。
- **[logic/high]** [logic] analytics/window_eta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_eta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧元素，但 _total 只增不减，mean() 分子包含已淘汰样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_gamma.py:44-48`
  - 依据：同 window_alpha：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无校验。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧元素，但 _total 只增不减，mean() 分子包含已淘汰样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。
- **[boundary/medium]** [boundary] analytics/window_theta.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_theta.py:44-48`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 范围校验。ratio > 1 或 ratio < 0 时 index 越界，ordered[index] 抛出 IndexError。触发条件：调用 percentile(1.5) 或 percentile(-0.1) 等越界值。
- **[logic/high]** [logic] analytics/window_theta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_theta.py:22-25`
  - 依据：与 window_beta.py 相同：deque(maxlen=size) 在 append 时自动淘汰最旧样本，但 _total 只累加不扣减。样本数超过 size 后 mean() 的分子包含全部历史样本之和，分母仅为当前窗口长度，均值被高估。触发条件：add 次数超过 size（默认 32）。
- **[boundary/medium]** [boundary] analytics/window_zeta.py:44-48 percentile 未校验 ratio 范围，越界 ratio 会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_zeta.py:44-48`
  - 依据：同 window_alpha：ratio 超出 [0,1] 时 index 越界，ordered[index] 抛 IndexError，无校验。
- **[logic/high]** [logic] analytics/window_zeta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-3｜置信度 0.5
  - 源：`analytics/window_zeta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧元素，但 _total 只增不减，mean() 分子包含已淘汰样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。
- **[logic/high]** [logic] persistence/journal_alpha.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_alpha.py:47-53`
  - 依据：compact() 计算 surplus 后把 kept 写入磁盘，但没有更新 self._records。因此 compact() 之后 self._records 仍保留全部旧记录，而磁盘只剩 keep 条。后续 replay()/count() 返回的是未压缩的内存数据，disk_count() 返回磁盘数据，两者不一致；再次 append() 时 _flush() 会把内存中的全部旧记录重新写回磁盘，使压缩完全失效。
- **[logic/high]** [logic] persistence/journal_beta.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_beta.py:47-53`
  - 依据：compact() 计算 surplus 后把 kept 写入磁盘，但没有更新 self._records。因此 compact() 之后 self._records 仍保留全部旧记录，而磁盘只剩 keep 条。后续 replay()/count() 返回的是未压缩的内存数据，disk_count() 返回磁盘数据，两者不一致；再次 append() 时 _flush() 会把内存中的全部旧记录重新写回磁盘，使压缩完全失效。
- **[logic/high]** [logic] persistence/journal_delta.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_delta.py:47-53`
  - 依据：compact() 计算 surplus 后只把 kept 写回磁盘，但没有更新 self._records。调用 compact() 后，replay()/count() 仍返回压缩前的全部记录，而 disk_count() 返回压缩后的条数，内存与磁盘状态永久不一致；后续 append() 会基于未压缩的 _records 重新 _flush()，把已被压缩掉的旧记录又写回磁盘，使压缩失效。
- **[boundary/low]** [boundary] persistence/journal_epsilon.py:47-52 compact() 的 surplus 计算与切片在 keep 为负时行为异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:47-52`
  - 依据：keep 为负时 surplus 会大于 len(_records)，kept 为空列表，写盘为空文件，语义上等价于“保留最近负数条”即全部丢弃，属于调用方传入非法参数，不构成代码缺陷。
- **[error_handling/low]** [error_handling] persistence/journal_epsilon.py:62-66 disk_count() 在文件不存在时抛异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:62-66`
  - 依据：若从未 append 过且文件不存在，disk_count() 会因 read_text 抛 FileNotFoundError。但 __init__ 仅在文件存在时加载，且 append 会创建文件；对未写入的日志调用 disk_count 属于调用方使用前提，且异常是显式失败而非静默错误，不认定为缺陷。
- **[logic/high]** [logic] persistence/journal_epsilon.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_epsilon.py:47-53`
  - 依据：compact() 计算 surplus 后把 kept 写入磁盘，但没有更新 self._records。触发条件：append 若干条使 len(_records) > keep，调用 compact()。此后 replay()/count() 仍返回全部旧记录（含已被压缩掉的），而 disk_count() 返回压缩后的条数，两者不一致；再次 append 时 _flush() 会把内存中的全部旧记录重新写回磁盘，使压缩完全失效。
- **[logic/high]** [logic] persistence/journal_eta.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_eta.py:47-53`
  - 依据：与 journal_epsilon.py 相同：compact() 只把 kept 写入磁盘，未更新 self._records。触发条件：记录数超过 keep 后调用 compact()。replay()/count() 仍返回未压缩的全部记录，后续 append 触发的 _flush() 会把旧记录重新写回，压缩失效。
- **[logic/high]** [logic] persistence/journal_gamma.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_gamma.py:47-53`
  - 依据：compact() 计算 surplus 后把 kept 写入磁盘，但没有更新 self._records。因此 compact() 之后 self._records 仍保留全部旧记录，而磁盘只剩 keep 条。后续 replay()/count() 返回的是未压缩的内存数据，disk_count() 返回磁盘数据，两者不一致；再次 append() 时 _flush() 会把内存中的全部旧记录重新写回磁盘，使压缩完全失效。
- **[logic/high]** [logic] persistence/journal_theta.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_theta.py:47-53`
  - 依据：与 journal_delta.py 相同：compact() 只写磁盘，未更新 self._records，导致 replay()/count() 与 disk_count() 不一致，且后续 append() 会把已丢弃的记录重新写回。
- **[logic/high]** [logic] persistence/journal_zeta.py:47-53 compact() 只重写磁盘文件，未同步内存 _records，导致内存与磁盘不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`persistence/journal_zeta.py:47-53`
  - 依据：与 journal_delta.py 相同：compact() 只写磁盘，未更新 self._records，导致 replay()/count() 与 disk_count() 不一致，且后续 append() 会把已丢弃的记录重新写回。
- **[api_misuse/medium]** [api_misuse] resources/pool_alpha.py:60-66 close() 用 getattr(self._factory, "close") 取工厂的 close 方法，而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:60-66`
  - 依据：closer 取自 self._factory（工厂函数/对象），随后却以 closer(resource) 调用，把资源当作参数传给工厂的 close。触发条件：工厂对象恰好有 close 方法（如工厂是某个带 close 的类实例）时，会以错误语义调用；而资源本身若需要关闭则完全不会被关闭。正确做法应是 getattr(resource, "close", None)。
- **[concurrency/low]** [concurrency] resources/pool_alpha.py:33-37 acquire() 在持锁状态下调用工厂函数，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:33-37`
  - 依据：self._factory() 在 with self._available 临界区内执行。触发条件：工厂创建资源较慢（如建立网络连接）时，所有其他 acquire/release 线程都会被阻塞在锁上，即使池中已有空闲资源也无法取用，放大延迟。
- **[logic/low]** [logic] resources/pool_alpha.py:30-31 acquire() 使用 id(resource) 跟踪占用，对象被回收后 id 可能复用（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`resources/pool_alpha.py:30-31`
  - 依据：虽然 _in_use 用 id() 跟踪，但池中资源在 _free 或调用方手中始终被强引用，不会在仍被跟踪时被回收，因此 id 复用不会造成误判。真正的问题是 release() 未移除 id（已单独报告），而非 id 本身。
- **[logic/medium]** [logic] resources/pool_alpha.py:47-50 release() 未从 _in_use 移除资源，导致 in_use 计数只增不减（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_alpha.py:47-50`
  - 依据：acquire() 会把 id(resource) 加入 _in_use，但 release() 只把资源放回 _free 并 notify，从未 discard 对应的 id。触发条件：任意一次 acquire/release 循环后调用 stats()，in_use 会持续累加，永远不回落，stats 报告失真。
- **[api_misuse/medium]** [api_misuse] resources/pool_beta.py:60-66 close() 取的是工厂的 close 方法而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:60-66`
  - 依据：close() 用 getattr(self._factory, "close", None) 获取工厂对象的 close，然后对每个空闲资源调用 closer(resource)。若工厂本身没有 close（常见情况），则资源永远不会被关闭，造成资源泄漏；若工厂恰好有 close，其签名通常也不接受 resource 参数，会抛 TypeError。正确做法是对每个 resource 调用 getattr(resource, "close", None)。
- **[concurrency/medium]** [concurrency] resources/pool_beta.py:33-37 acquire() 在持锁状态下调用工厂函数，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:33-37`
  - 依据：acquire() 在 with self._available 持锁期间调用 self._factory()。若工厂创建资源耗时（如建立网络连接），所有其他 acquire()/release()/stats() 调用都会被阻塞，且 release() 无法归还资源来唤醒等待者，可能造成整体吞吐骤降甚至超时。
- **[logic/high]** [logic] resources/pool_beta.py:47-50 release() 未从 _in_use 移除资源，导致 in_use 计数只增不减（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_beta.py:47-50`
  - 依据：acquire() 会把 id(resource) 加入 _in_use，但 release() 只把资源放回 _free 并 notify，从未执行 self._in_use.discard(id(resource))。因此 stats()['in_use'] 单调递增，永远反映历史借出次数而非当前在用数量，监控/容量判断会失真。
- **[api_misuse/medium]** [api_misuse] resources/pool_delta.py:60-66 close() 用 getattr(self._factory, "close") 取工厂的 close 方法，而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:60-66`
  - 依据：同 pool_alpha.py：closer 取自工厂而非资源，close() 无法正确关闭池内资源，且当工厂带 close 时会以错误参数调用。
- **[concurrency/low]** [concurrency] resources/pool_delta.py:33-37 acquire() 在持锁状态下调用工厂函数，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:33-37`
  - 依据：同 pool_alpha.py：工厂调用位于临界区内，慢工厂会阻塞所有并发 acquire/release。
- **[logic/medium]** [logic] resources/pool_delta.py:47-50 release() 未从 _in_use 移除资源，导致 in_use 计数只增不减（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_delta.py:47-50`
  - 依据：同 pool_alpha.py：release() 只归还到 _free，未从 _in_use 删除 id(resource)，stats() 的 in_use 会单调增长，无法反映真实占用数。
- **[api_misuse/medium]** [api_misuse] resources/pool_epsilon.py:60-66 close() 用 getattr(self._factory, "close") 取工厂的 close 方法，而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:60-66`
  - 依据：同 pool_alpha.py：closer 取自工厂而非资源，close() 无法正确关闭池内资源，且当工厂带 close 时会以错误参数调用。
- **[concurrency/low]** [concurrency] resources/pool_epsilon.py:33-37 acquire() 在持锁状态下调用工厂函数，可能长时间阻塞其他线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:33-37`
  - 依据：同 pool_alpha.py：工厂调用位于临界区内，慢工厂会阻塞所有并发 acquire/release。
- **[logic/medium]** [logic] resources/pool_epsilon.py:47-50 release() 未从 _in_use 移除资源，导致 in_use 计数只增不减（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_epsilon.py:47-50`
  - 依据：同 pool_alpha.py：release() 只归还到 _free，未从 _in_use 删除 id(resource)，stats() 的 in_use 会单调增长，无法反映真实占用数。
- **[api_misuse/medium]** [api_misuse] resources/pool_eta.py:60-66 close() 用 getattr(self._factory, "close") 取工厂的 close 方法，而非资源自身的 close（确认存在缺陷）
  - 独立来源 1 个：reader-r0-4｜置信度 0.5
  - 源：`resources/pool_eta.py:60-66`
  - 依据：同 pool_alpha.py：closer 取自工厂而非资源，close() 无法正确关闭池内资源，且当工厂带 close 时会以错误参数调用。
- …另有 44 条未列出

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `resources` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| `scheduling` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
