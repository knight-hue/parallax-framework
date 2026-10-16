# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 7 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 4 | 单一来源孤证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：32

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 13 | 100% | 33% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量淘汰时机错误，且淘汰后未清理 _order 中的重复键（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：容量检查在写入之前用 len(self._store) > self.capacity 判断，导致缓存实际可容纳 capacity+1 个条目（例如 capacity=8 时能存 9 个）。此外 get 中 pop 掉过期条目时没有从 _order 移除对应键，_order 会残留已删除的键，_evict_one 可能弹出这些陈旧键而不淘汰真正的旧条目，使容量上限进一步失效。
- **[logic/high]** [logic] config/loader.py:16-20 load 使用可变默认参数且浅拷贝 DEFAULTS，嵌套 dict 被共享修改（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:16-20`
  - 依据：merged = dict(DEFAULTS) 是浅拷贝，merged['endpoints'] 与 DEFAULTS['endpoints'] 指向同一 dict。配合 with_endpoint 中的 updated['endpoints'][name] = url，会直接污染模块级 DEFAULTS，使后续所有 load() 调用都带上被改写的 endpoint。触发条件：调用 with_endpoint(load(), ...) 或任何对返回配置 endpoints 的原地修改。
- **[logic/high]** [logic] config/loader.py:36-40 with_endpoint 原地修改共享的 endpoints 字典，污染源配置与 DEFAULTS（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:36-40`
  - 依据：config.copy() 只复制顶层，updated['endpoints'] 仍与传入 config 的 endpoints 是同一对象，赋值会同时改写调用方原配置以及（当 config 来自 load() 时）模块级 DEFAULTS。文档声称“返回新配置、调用方通常保留原配置”，实际行为与之相反。触发条件：任何 with_endpoint 调用。
- **[concurrency/medium]** [concurrency] runner/pool.py:29-31 _next_id 在无锁情况下自增，存在竞态导致重复 task_id（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:29-31`
  - 依据：多个工作线程并发调用 _run_one，其中调用 _next_id 执行 `self._seq += 1`，该读-改-写未受 self._lock 保护。触发条件：并发提交多个 job 时，两个线程可能读到相同 _seq 值，产生重复的 task-{n} id，破坏结果标识唯一性。
- **[performance/medium]** [performance] runner/pool.py:35-43 TaskPool.run_all 忽略 concurrency 参数，为每个任务创建线程（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:35-43`
  - 依据：类文档与构造参数声明“固定线程数”，但 run_all 对 jobs 中每个元素都新建一个线程，concurrency 从未被使用。提交大量任务时会创建等量线程，导致资源耗尽/性能退化。触发条件：jobs 数量远大于 concurrency。
- **[boundary/low]** [boundary] runner/retry.py:29-38 RetryPolicy.call 在 attempts<=0 时静默返回失败（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:29-38`
  - 依据：当 attempts 为 0 或负数时，for 循环不执行，函数直接落到末尾 return False, None，fn 从未被调用。调用方可能误以为操作被尝试过并失败，而实际根本没执行。触发条件：构造 RetryPolicy(attempts=0)。
- **[error_handling/high]** [error_handling] runner/retry.py:29-33 RetryPolicy.call 对 ValueError 直接返回成功，吞掉异常（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:29-33`
  - 依据：捕获 ValueError 后返回 (True, None)，把失败伪装成成功且丢弃异常信息。调用方按 (ok, value) 判断会误认为操作成功，得到 None 值。触发条件：被调用函数抛出 ValueError（常见于解析/校验失败）。

## 待验证（孤证）

- **[api_misuse/medium]** [api_misuse] config/loader.py:23-31 load_from_env 把所有环境变量值当字符串，未做类型转换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:23-31`
  - 依据：DEFAULTS 中 timeout/retries 是 int，但环境变量覆盖后变成 str（如 '30'）。后续若做数值比较或算术会抛 TypeError，或与默认值类型不一致导致下游逻辑分支错误。触发条件：设置 APP_TIMEOUT=30 后调用 load_from_env()。
- **[concurrency/medium]** [concurrency] runner/pool.py:60-64 TaskPool.export 未加锁读取 _results，且文件句柄未用 with 保护（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：export 直接遍历 self._results 而不获取 self._lock，若与仍在运行的工作线程并发（例如 run_all 尚未 join 完成时调用），会读到不一致的列表甚至触发 RuntimeError。同时 open 后若 json.dump 抛异常，handle.close() 不会执行，造成文件句柄泄漏。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:58-62 TaskPool.export 未使用 with 且异常时句柄泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:58-62`
  - 依据：open 后若 json.dump 抛异常（如 value 不可序列化），handle.close() 不会执行，文件句柄泄漏且文件内容不完整。触发条件：结果中包含不可 JSON 序列化的 value。
- **[resource_leak/low]** [resource_leak] runner/pool.py:60-64 export 未使用 with 且异常时句柄泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：open 后若 json.dump 抛出异常（如 value 不可序列化），handle.close() 不会执行，文件句柄泄漏。触发条件：结果中包含不可 JSON 序列化的 value 时。应使用 with 语句或 try/finally。

## 争议（需裁决）

- **[logic/critical]** [logic] cache/ttl.py:24-24 TTLCache.get 的 TTL 比较方向（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:24-24`
  - 依据：与第一条相同问题的定位行，确认该比较方向确为缺陷而非有意设计：注释与类文档均声明“超过 TTL 后视为失效”，而代码在未超过 TTL 时删除条目。
  - 争议对手：918f067abd50, f72c1eddbe62
- **[concurrency/low]** [concurrency] runner/pool.py:58-66 TaskPool.export 与 summary 读取 _results 未加锁（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:58-66`
  - 依据：export 和 summary 直接遍历 self._results，而 _run_one 在持锁状态下 append。若在任务仍在执行时调用（例如另一线程调用 export），list 迭代与 append 并发可能读到不一致快照或抛 RuntimeError。触发条件：run_all 未返回时并发调用 export/summary。
  - 争议对手：126ca65854b1

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `config` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `runner` | 0 | 3 | 3 | 3 | 2 | 0 | 3 | 0 |

矩阵填充率 38%（单元格值 = 独立 Agent 数）
