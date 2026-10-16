# Parallax 运行报告 `9d3e85392fc8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 9 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 4 | 单一来源孤证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：3｜停止原因：`max_rounds_reached`
- 参与 Reader：9 个（每轮全新身份）
- 账本条目：60

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 14 | 100% | 33% |
| 1 | 3 | 3 | 100% | 46% |
| 2 | 3 | 1 | 100% | 50% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量淘汰时机错误，容量上限被突破（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：淘汰检查 `if len(self._store) > self.capacity` 在写入新键之前执行，且用的是严格大于。当 store 大小恰好等于 capacity 时不会淘汰，随后写入新键使大小变为 capacity+1，超出容量上限。例如 capacity=8、已有 8 个键时 put 第 9 个键，store 变为 9 个元素。正确做法是在插入前判断 len >= capacity 或插入后再判断。
- **[logic/critical]** [logic] cache/ttl.py:24-24 TTLCache.get 的 TTL 判断（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:24-24`
  - 依据：与第一条相同问题的精确行定位：`if time.time() - created < self.ttl:` 条件方向错误，新鲜条目被删除、过期条目被返回。
- **[api_misuse/low]** [api_misuse] config/loader.py:23-31 load_from_env 把所有环境变量值当字符串，未做类型转换（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r2-0｜置信度 0.5
  - 源：`config/loader.py:23-31`
  - 依据：DEFAULTS 中 timeout/retries 是 int，但环境变量覆盖后变成 str（如 '30'）。describe 会输出字符串，下游若做数值比较或算术会抛 TypeError 或产生错误结果。触发条件：设置 APP_TIMEOUT=30 后调用 load_from_env。
- **[logic/medium]** [logic] config/loader.py:23-31 load_from_env 把所有环境变量值当字符串，未做类型转换（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`config/loader.py:23-31`
  - 依据：DEFAULTS 中 timeout/retries 是 int，但环境变量读出的 value 始终是 str，overrides[key] = value 直接覆盖后，config['timeout'] 变成字符串。下游若做数值比较或算术（如 timeout > 0、retries - 1）会抛 TypeError 或产生错误比较结果。触发条件：设置 APP_TIMEOUT=60 后调用 load_from_env()。
- **[api_misuse/medium]** [api_misuse] runner/pool.py:37-45 TaskPool.run_all 忽略 concurrency 参数，为每个任务创建线程（确认存在缺陷）
  - 独立来源 2 个：reader-r1-1, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:37-45`
  - 依据：类文档与构造参数声明为固定线程数的任务池（concurrency 默认 4），但 run_all 对 jobs 中每个任务都新建一个线程，完全没有使用 self.concurrency。当 jobs 很大时会创建大量线程，既违背 API 契约又可能耗尽资源。触发条件：提交的任务数超过 concurrency。
- **[concurrency/medium]** [concurrency] runner/pool.py:31-33 TaskPool._next_id 非线程安全，并发下可能产生重复 task_id（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:31-33`
  - 依据：run_all 为每个 job 启动独立线程，_run_one 在线程内调用 _next_id，而 _next_id 对 self._seq 的读-改-写没有加锁。多个线程可能读到相同的 _seq 值并写回，导致生成重复的 task-{n} id，结果列表中 task_id 冲突。触发条件：并发提交多个任务。
- **[performance/medium]** [performance] runner/pool.py:36-44 TaskPool 未限制并发数，concurrency 参数被忽略（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r1-0, reader-r2-1｜置信度 0.5
  - 源：`runner/pool.py:36-44`
  - 依据：类文档与 __init__ 声明『固定线程数』并接收 concurrency，但 run_all 对每个 job 都新建一个线程，完全没有使用 self.concurrency 做限流。提交 N 个任务就会创建 N 个线程，任务量大时线程数失控，可能耗尽资源。触发条件：run_all 传入远大于 concurrency 的任务列表。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:57-61 TaskPool.export 未使用 with 且异常时文件句柄泄漏（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:57-61`
  - 依据：open 后若 json.dump 抛异常（如 value 不可序列化），handle.close() 不会执行，文件句柄泄漏。应使用 with open(...) as handle。触发条件：结果中包含不可 JSON 序列化的 value。
- **[error_handling/high]** [error_handling] runner/retry.py:30-33 RetryPolicy.call 把 ValueError 当作成功返回，掩盖真实失败（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-2, reader-r1-0, reader-r2-1｜置信度 0.5
  - 源：`runner/retry.py:30-33`
  - 依据：`except ValueError: return True, None` 将 ValueError 异常吞掉并报告成功，调用方无法区分“函数正常返回 None”和“函数抛出 ValueError 失败”。触发条件：被调用函数因参数非法或解析失败抛出 ValueError 时，call 返回 (True, None)，重试逻辑被绕过且错误被静默。

## 待验证（孤证）

- **[error_handling/low]** [error_handling] config/loader.py:42-44 describe 对 endpoints 非 dict 时调用 .get 会抛异常（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`config/loader.py:42-44`
  - 依据：config.get("endpoints", {}) 在 endpoints 缺失时返回 {}，可安全调用 .get。仅当调用方显式传入 endpoints 为非 dict（如字符串）时才会 AttributeError，但这属于调用方违反约定，且函数签名未承诺容错。因此不认定为缺陷。
- **[concurrency/low]** [concurrency] runner/pool.py:57-66 TaskPool.export 与 summary 读取 _results 未加锁（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`runner/pool.py:57-66`
  - 依据：export 和 summary 直接遍历 self._results，而 _run_one 在其它线程中会 append 到该列表。若在任务仍在运行时调用 export/summary，会与 append 竞争，可能读到不一致状态或触发 RuntimeError。触发条件：run_all 返回前（或其它线程仍在写）调用 export/summary。
- **[logic/low]** [logic] runner/pool.py:38-46 run_all 返回 snapshot 而非直接返回结果（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`runner/pool.py:38-46`
  - 依据：run_all 在 join 所有线程后调用 snapshot()，此时所有写入已完成，加锁读取能拿到完整结果。虽然 _results 会跨多次 run_all 累积，但这是设计选择而非并发缺陷。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:60-64 export 未加锁读取 _results，且文件句柄未用 with 保护（确认存在缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：export 直接遍历 self._results 而没有获取 self._lock，若与仍在运行的线程并发会读到不一致状态；同时 open 后若 json.dump 抛异常（如 value 不可序列化），handle.close() 不会执行，文件句柄泄漏。触发条件：任务结果含不可 JSON 序列化对象，或导出与执行并发。

## 争议（需裁决）

- **[api_misuse/low]** [api_misuse] config/loader.py:16-16 load 使用可变默认参数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`config/loader.py:16-16`
  - 依据：def load(overrides: dict = {}) 使用可变对象作为默认参数。虽然当前函数体只读取 overrides（merged.update(overrides)）而不修改它，因此不会立即产生跨调用状态泄漏，但这是公认的反模式，一旦后续在函数内修改 overrides 就会引入难以排查的共享状态缺陷。触发条件：未来在 load 内对 overrides 做原地写入。
  - 争议对手：62bd19496d2b, b0fb7b47cfe9
- **[logic/high]** [logic] config/loader.py:16-20 load 使用可变默认参数且浅合并导致 DEFAULTS 被污染（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-2, reader-r2-0, reader-r2-1｜置信度 0.5
  - 源：`config/loader.py:16-20`
  - 依据：merged = dict(DEFAULTS) 是浅拷贝，merged["endpoints"] 与 DEFAULTS["endpoints"] 是同一对象。任何对返回结果中 endpoints 的修改（例如 with_endpoint）都会写回模块级 DEFAULTS，使后续 load() 返回被污染的默认值。同时 overrides: dict = {} 是可变默认参数，虽然此处未就地修改 overrides，但配合浅合并语义仍构成隐患。触发条件：load() 后对结果 endpoints 做任何嵌套修改。
  - 争议对手：3e89e4625439
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 summary 未加锁读取 _results（确认存在缺陷）
  - 独立来源 4 个：reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 在无锁情况下多次读取 self._results（len 与生成器遍历），若与 _run_one 的 append 并发，total 与 ok/failed 可能基于不同快照，导致 failed 为负数或统计不一致。触发条件：任务仍在执行时调用 summary。
  - 争议对手：cea8e19eeb25
- **[boundary/low]** [boundary] runner/retry.py:20-21 RetryPolicy.call 退避延迟从 attempt=1 起算，首次重试等待翻倍（确认存在缺陷）
  - 独立来源 5 个：reader-r0-0, reader-r1-0, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：delay_for(attempt) 返回 base_delay * 2**attempt，而 call 在第一次失败（attempt=1）后调用 delay_for(1)，得到 2*base_delay 而非 base_delay，整体退避序列偏移一档。若期望首次重试等待 base_delay，则实际等待时间翻倍。触发条件：任何发生重试的调用。
  - 争议对手：7ee5421a957a, 9033bb64a964
- **[logic/low]** [logic] runner/retry.py:20-21 RetryPolicy.call 退避延迟从 attempt=1 开始，首次重试即等待 2*base_delay（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r1-1, reader-r2-2｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：delay_for(attempt) = base_delay * 2**attempt，而 call 中首次失败后调用 delay_for(1)，得到 2*base_delay 而非 base_delay。若期望首次退避为 base_delay，则指数偏移了一位。触发条件：任何一次重试。
  - 争议对手：ae9b11a99d41

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `config` | 6 | 0 | 0 | 2 | 0 | 0 | 0 | 5 |
| `runner` | 5 | 6 | 5 | 4 | 3 | 0 | 3 | 2 |

矩阵填充率 50%（单元格值 = 独立 Agent 数）
