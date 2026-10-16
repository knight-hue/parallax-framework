# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 6 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 1 | 单一来源孤证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：19

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 9 | 100% | 29% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量淘汰判断在插入前执行且用 > 而非 >=，导致容量可被突破（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：put 先检查 `len(self._store) > self.capacity` 再插入。当 len == capacity 时不会淘汰，插入后 len 变为 capacity+1，超过上限；只有下一次 put 才会触发淘汰。因此缓存实际可容纳 capacity+1 个条目，容量上限被突破一个。正确做法是插入前判断 len >= capacity（或插入后判断 > capacity）。
- **[logic/low]** [logic] cache/ttl.py:29-34 TTLCache 更新已存在 key 时 _order 与 _store 不同步，淘汰顺序错乱（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：当 key 已存在时不会重复 append 到 _order，但 _store[key] 的时间戳被刷新。_order 中该 key 仍处于旧位置，淘汰时按 _order 顺序 pop(0) 会优先淘汰这个刚被更新的“新”条目，而真正更早写入的条目反而保留，LRU/写入顺序淘汰语义被破坏。
- **[api_misuse/low]** [api_misuse] config/loader.py:16-20 load 使用可变默认参数 overrides={}（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`config/loader.py:16-20`
  - 依据：函数签名 def load(overrides: dict = {}) 使用可变对象作为默认参数。虽然当前实现只读取 overrides（merged.update(overrides)）而不修改它，因此不会立即产生跨调用污染，但这是公认的反模式：任何后续在函数内对 overrides 的写入都会在多次调用间持久化，且调用方若把该默认对象当作可写对象也会污染全局。属于 API 误用。
- **[concurrency/high]** [concurrency] runner/pool.py:31-33 TaskPool._next_id 未加锁，多线程并发下产生重复 task_id（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:31-33`
  - 依据：_next_id 在多个工作线程中并发调用（run_all 为每个 job 启动一个线程，_run_one 内调用 _next_id），但 `self._seq += 1` 不是原子操作，且未持有 self._lock。两个线程可能读到相同的 _seq 值，生成重复的 task_id，破坏结果标识的唯一性。
- **[concurrency/low]** [concurrency] runner/pool.py:68-70 TaskPool.summary 未加锁读取 _results（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:68-70`
  - 依据：summary 遍历 self._results 时未持有 self._lock，与 _run_one 的 append 并发时可能读到部分结果，导致 total/ok/failed 计数不一致。虽然 run_all 返回前会 join 所有线程，但 summary 是公开方法，可被其他线程在任务运行期间调用。
- **[error_handling/high]** [error_handling] runner/retry.py:28-30 RetryPolicy.call 把 ValueError 当作成功返回 (True, None)（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:28-30`
  - 依据：捕获 ValueError 后直接 `return True, None`，把异常吞掉并谎报成功，调用方无法感知失败，也不会重试。触发条件：fn 抛出 ValueError（例如参数校验失败）时。

## 待验证（孤证）

- **[performance/medium]** [performance] runner/pool.py:35-42 TaskPool.run_all 未使用 concurrency 限制并发数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:35-42`
  - 依据：构造函数接收 concurrency 参数并保存为 self.concurrency，但 run_all 对每个 job 都无条件创建一个线程，完全没有使用该上限。触发条件：jobs 数量远大于 concurrency 时，会创建大量线程，违背“固定线程数任务池”的契约并可能耗尽资源。

## 争议（需裁决）

- **[logic/high]** [logic] config/loader.py:37-40 with_endpoint 浅拷贝导致修改共享的 endpoints 字典，污染原配置（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`config/loader.py:37-40`
  - 依据：config.copy() 是浅拷贝，updated['endpoints'] 与 config['endpoints'] 指向同一个 dict。随后 `updated['endpoints'][name] = url` 会直接修改原配置的 endpoints。文档字符串明确说“调用方通常保留原配置，只把派生结果传给需要覆盖的目标”，但实际会污染原配置，导致后续使用原配置的代码看到被覆盖的 endpoint。需要深拷贝 endpoints（如 dict(config['endpoints'])）。
  - 争议对手：822d88f740a6
- **[boundary/low]** [boundary] runner/retry.py:20-21 RetryPolicy.call 首次重试即等待 base_delay*2（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：delay_for(attempt) 使用 2**attempt，而循环中 attempt 从 1 开始，因此第一次重试等待 base_delay*2 而非 base_delay，退避序列整体偏移一档。触发条件：任何一次重试。
  - 争议对手：b139e65a433b

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `config` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `runner` | 0 | 2 | 2 | 2 | 0 | 0 | 1 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
