# Parallax 运行报告 `9d3e85392fc8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 9 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 3 | 单一来源孤证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：3｜停止原因：`max_rounds_reached`
- 参与 Reader：9 个（每轮全新身份）
- 账本条目：65

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 14 | 100% | 25% |
| 1 | 3 | 3 | 100% | 46% |
| 2 | 3 | 0 | 100% | 46% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量检查在插入前执行，实际容量可超出 capacity（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-1, reader-r1-2, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：len(self._store) > self.capacity 在写入新键之前判断，因此当 store 大小恰好等于 capacity 时不会淘汰，随后插入使大小变为 capacity+1，缓存长期可容纳 capacity+1 个条目。触发条件：连续 put 到容量上限后再 put 一个新键。
- **[logic/medium]** [logic] config/loader.py:16-19 load 使用可变默认参数且浅合并，嵌套 DEFAULTS 被共享/污染（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`config/loader.py:16-19`
  - 依据：`def load(overrides: dict = {})` 使用可变默认参数（虽未在函数内修改 overrides，但仍是隐患）；更实质的问题是 `merged = dict(DEFAULTS)` 为浅拷贝，merged['endpoints'] 与 DEFAULTS['endpoints'] 是同一对象。任何对返回配置的 endpoints 的修改（例如经 with_endpoint 派生）都会永久污染模块级 DEFAULTS，使后续所有 load 调用返回被篡改的默认值。触发条件：load() 后修改返回值的 endpoints。
- **[logic/high]** [logic] config/loader.py:36-41 with_endpoint 的浅拷贝导致修改共享的 endpoints 字典，污染原配置与 DEFAULTS（确认存在缺陷）
  - 独立来源 5 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`config/loader.py:36-41`
  - 依据：config.copy() 只复制顶层，updated['endpoints'] 与 config['endpoints'] 指向同一 dict，因此 updated['endpoints'][name] = url 会同时修改传入的 config，违背文档“调用方通常保留原配置”的承诺；若 config 来自 load()，还会连带污染 DEFAULTS['endpoints']。触发条件：调用 with_endpoint 后继续使用原 config。
- **[concurrency/high]** [concurrency] runner/pool.py:31-33 TaskPool._next_id 未加锁，并发下产生重复 task_id（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:31-33`
  - 依据：self._seq += 1 是非原子操作，而 _next_id 在多个工作线程中并发调用（run_all 为每个 job 启动一个线程），存在竞态，可能生成重复的 task-{n}，使结果无法按 id 区分。触发条件：并发提交多个任务。
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 summary 读取 _results 未加锁（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 直接遍历 self._results 而不获取 self._lock，而 _run_one 在持锁状态下 append。若在任务仍在执行时调用 summary，可能读到部分结果或触发迭代期间列表被修改的异常。触发条件：run_all 尚未 join 完成时调用 summary。
- **[performance/high]** [performance] runner/pool.py:36-44 TaskPool 未限制并发数，concurrency 参数被忽略（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r1-0｜置信度 0.5
  - 源：`runner/pool.py:36-44`
  - 依据：类文档与 __init__ 声称是"固定线程数的任务池"，但 run_all 对每个 job 都新建一个线程并立即 start，完全没有使用 self.concurrency。提交 N 个任务就会创建 N 个线程，任务量大时可能耗尽线程资源或压垮下游。触发条件：jobs 数量远大于 concurrency 时。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:60-64 export 未加锁且未使用 with，异常时泄漏文件句柄（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r1-0｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：handle = open(...) 后若 json.dump 抛异常（例如 result.__dict__ 含不可序列化对象），handle.close() 不会执行，文件句柄泄漏。同时读取 self._results 未持锁，若与仍在运行的任务并发会读到不一致状态。触发条件：序列化失败或 export 与 run_all 并发调用。
- **[boundary/low]** [boundary] runner/retry.py:20-21 RetryPolicy.delay_for 的 attempt 从 1 开始，首次退避即为 2 倍 base_delay（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r2-1｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：call 中 attempt 从 1 开始，delay_for(1) = base_delay * 2，首次重试等待时间就是基准的两倍，指数退避整体偏移一档，与通常“首次退避为 base_delay”的预期不符。触发条件：任何一次重试。
- **[error_handling/high]** [error_handling] runner/retry.py:30-31 RetryPolicy.call 将 ValueError 当作成功返回，掩盖真实失败（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/retry.py:30-31`
  - 依据：捕获 ValueError 后直接 return True, None，把异常当作成功。调用方会认为操作成功但拿到 None，导致静默的数据错误；且该分支不重试，与重试策略语义矛盾。触发条件：fn 抛出 ValueError（如解析失败、参数非法）时。

## 待验证（孤证）

- **[api_misuse/low]** [api_misuse] config/loader.py:22-29 load_from_env 将所有环境变量值作为字符串覆盖，未做类型转换（确认存在缺陷）
  - 独立来源 1 个：reader-r1-2｜置信度 0.5
  - 源：`config/loader.py:22-29`
  - 依据：环境变量值始终是 str，overrides[key] = value 会把 timeout/retries 等本应为 int 的配置替换成字符串（如 '30'），后续若进行数值比较或算术会出错。触发条件：设置 APP_TIMEOUT=30 后调用 load_from_env，返回的 timeout 为字符串而非 int。
- **[logic/high]** [logic] config/loader.py:41-44 with_endpoint 浅拷贝导致修改污染原配置的嵌套 endpoints（确认存在缺陷）
  - 独立来源 1 个：reader-r1-2｜置信度 0.5
  - 源：`config/loader.py:41-44`
  - 依据：config.copy() 只做浅拷贝，updated['endpoints'] 与 config['endpoints'] 指向同一个 dict。随后 `updated['endpoints'][name] = url` 会直接修改原配置对象，违反文档字符串中“返回一个把 endpoints[name] 指向 url 的新配置 / 调用方通常保留原配置”的约定。触发条件：调用 with_endpoint 后原 config 的 endpoints 被意外改写。
- **[boundary/low]** [boundary] runner/retry.py:18-19 RetryPolicy.call 退避延迟从 attempt=1 开始，首次重试即等待 2 倍基础延迟（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`runner/retry.py:18-19`
  - 依据：delay_for(attempt) = base_delay * 2**attempt，而循环中 attempt 从 1 开始，因此第一次重试等待 2*base_delay 而非 base_delay，整体退避比预期翻倍。触发条件：任何一次重试。

## 争议（需裁决）

- **[logic/critical]** [logic] cache/ttl.py:22-26 TTLCache.get 的过期判断条件写反，未过期条目被删除、过期条目被返回（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-1, reader-r1-2, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`cache/ttl.py:22-26`
  - 依据：判断条件应为 time.time() - created >= self.ttl 才算过期。当前写成 < self.ttl 时删除并返回 None，导致刚写入、尚未过期的条目被立即当作失效删除；而真正过期的条目（age >= ttl）反而跳过该分支，直接返回陈旧 value。触发条件：任何一次 get 调用都会命中错误分支，缓存完全失效且会返回过期数据。
  - 争议对手：918f067abd50
- **[api_misuse/low]** [api_misuse] config/loader.py:17-17 load 使用可变默认参数（确认存在缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 源：`config/loader.py:17-17`
  - 依据：def load(overrides: dict = {}) 使用可变对象作为默认参数。虽然当前实现只读取 overrides（merged.update(overrides)）而不修改它，因此不会立即产生跨调用状态泄漏，但这是公认的反模式，一旦后续在函数内对 overrides 做任何写入就会造成难以排查的共享状态 bug。属于可修复的 API 设计缺陷。
  - 争议对手：62bd19496d2b
- **[error_handling/low]** [error_handling] config/loader.py:42-44 describe 对 endpoints 为 None 时抛 AttributeError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r2-0｜置信度 0.5
  - 源：`config/loader.py:42-44`
  - 依据：config.get("endpoints", {}) 只在键缺失时返回 {}；若配置中显式存在 "endpoints": None（例如来自外部 JSON/YAML 或调用方传入），则 .get("primary", "<none>") 会在 None 上调用而抛 AttributeError。触发条件：config 含 endpoints=None。
  - 争议对手：96cbb555a8cc
- **[concurrency/medium]** [concurrency] runner/pool.py:55-59 TaskPool.export 未加锁读取 _results，且文件句柄未用 with 保护（确认存在缺陷）
  - 独立来源 2 个：reader-r0-2, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:55-59`
  - 依据：export 直接遍历 self._results 而不获取 self._lock，若与仍在运行的线程并发调用会读到不一致状态或触发 RuntimeError；同时 open 后若 json.dump 抛异常，handle.close() 不会执行，造成文件句柄泄漏。触发条件：任务执行期间调用 export，或序列化过程中出现不可序列化对象。
  - 争议对手：fc41abc6b106
- **[logic/low]** [logic] runner/retry.py:22-23 RetryPolicy.call 的退避延迟从 attempt=1 开始，首次重试即等待 2 倍基础延迟（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:22-23`
  - 依据：delay_for(attempt) 使用 2 ** attempt，而循环中 attempt 从 1 开始，因此第一次重试等待 base_delay*2 而非 base_delay，整体退避比预期翻倍。触发条件：attempts >= 2 且首次调用失败。
  - 争议对手：968ae76e94cf, 9890f5f4abc2, f72179629f1d

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| `config` | 6 | 0 | 0 | 3 | 0 | 0 | 0 | 3 |
| `runner` | 4 | 6 | 4 | 6 | 2 | 0 | 2 | 0 |

矩阵填充率 46%（单元格值 = 独立 Agent 数）
