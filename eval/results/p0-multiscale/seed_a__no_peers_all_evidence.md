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
- 账本条目：30

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 13 | 100% | 33% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:30-35 TTLCache.put 容量检查在插入前执行，导致实际容量超出上限（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:30-35`
  - 依据：put 先判断 len(self._store) > self.capacity 再插入。当 store 大小恰好等于 capacity 时不会淘汰，插入后大小变为 capacity+1，缓存长期可容纳 capacity+1 个条目，容量上限被突破。正确做法是插入后检查或使用 >=。
- **[logic/high]** [logic] config/loader.py:16-20 load 使用可变默认参数且浅拷贝 DEFAULTS，嵌套 dict 被共享修改（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:16-20`
  - 依据：merged = dict(DEFAULTS) 是浅拷贝，merged['endpoints'] 与 DEFAULTS['endpoints'] 指向同一对象。配合 with_endpoint 中的 updated['endpoints'][name] = url，会直接污染全局 DEFAULTS，使后续所有 load() 调用都带上被修改的 endpoint。此外 overrides: dict = {} 作为可变默认参数虽未在函数内修改，但仍是隐患。
- **[logic/high]** [logic] config/loader.py:36-40 with_endpoint 浅拷贝后原地修改嵌套 dict，污染调用方与全局默认配置（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:36-40`
  - 依据：config.copy() 只复制顶层，updated['endpoints'] 仍与传入 config 的 endpoints 是同一对象。执行 updated['endpoints'][name] = url 会同时修改调用方传入的 config，违背文档“调用方通常保留原配置”的承诺；若 config 来自 load()，还会连带修改 DEFAULTS。
- **[concurrency/medium]** [concurrency] runner/pool.py:30-32 TaskPool._next_id 在无锁情况下自增，存在竞态（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:30-32`
  - 依据：_next_id 由多个工作线程并发调用，但 self._seq += 1 未加锁。CPython 下该操作非原子，可能产生重复 task_id，破坏结果标识的唯一性。触发条件：run_all 并发执行多个任务。
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 TaskPool.summary 未加锁读取 _results（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 遍历 self._results 时未获取 self._lock，而 _run_one 会在持锁状态下 append。若在任务仍在执行时调用 summary，可能读到部分结果或触发迭代期间列表被修改。触发条件：run_all 返回前或并发调用 summary。
- **[performance/medium]** [performance] runner/pool.py:35-43 TaskPool.run_all 忽略 concurrency 参数，为每个任务创建线程（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 源：`runner/pool.py:35-43`
  - 依据：构造函数接收 concurrency 并作为“固定线程数”的语义，但 run_all 对 jobs 中每个任务都新建一个线程，完全没有使用 self.concurrency。当 jobs 数量很大时会创建大量线程，既违背 API 契约又可能耗尽资源。
- **[error_handling/high]** [error_handling] runner/retry.py:29-31 RetryPolicy.call 把 ValueError 当作成功返回，掩盖真实失败（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:29-31`
  - 依据：捕获 ValueError 后直接 return True, None，把异常当作成功。调用方会认为操作成功但拿到 None，无法区分“成功返回 None”和“因 ValueError 失败”，导致错误被静默吞掉。

## 待验证（孤证）

- **[concurrency/low]** [concurrency] runner/pool.py:57-66 TaskPool.export 与 summary 读取 _results 时未加锁（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`runner/pool.py:57-66`
  - 依据：export 和 summary 直接遍历 self._results，而 _run_one 会在其他线程持锁 append。虽然 run_all 在 join 后才返回，但 export/summary 是公开方法，若在任务运行期间被调用，会与 append 并发，可能读到不一致的列表状态或触发迭代期间修改。snapshot 已正确加锁，这两个方法却没有。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:57-61 TaskPool.export 未使用 with 且异常时不会关闭文件句柄（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 源：`runner/pool.py:57-61`
  - 依据：handle = open(...) 后若 json.dump 抛出异常（例如结果对象不可序列化），handle.close() 不会被执行，文件句柄泄漏。应使用 with open(...) as handle 保证释放。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:60-64 TaskPool.export 未加锁读取 _results，且文件句柄未用 with 保护（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：export 直接遍历 self._results 而未持有 self._lock，若与运行中的任务并发会读到不一致状态；同时 open 后若 json.dump 抛异常（如序列化不可序列化的 value），handle.close() 不会执行，造成文件句柄泄漏。触发条件：value 含不可 JSON 序列化对象时调用 export。
- **[logic/low]** [logic] runner/retry.py:33-38 RetryPolicy.call 的 for 循环后 return 为不可达代码（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`runner/retry.py:33-38`
  - 依据：循环内所有分支（成功 return、ValueError return、最后一次失败 return）都会返回，因此循环后的 return False, None 实际不可达。这只是冗余代码，不会产生错误行为，故不视为缺陷。

## 争议（需裁决）

- **[logic/low]** [logic] cache/ttl.py:30-35 TTLCache.put 更新已存在 key 时 _order 与 _store 不同步，淘汰顺序错乱（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:30-35`
  - 依据：当 key 已存在时不会重复 append 到 _order，但 _store[key] 的时间戳被刷新。_order 仍保留该 key 的旧位置，导致按写入顺序淘汰的语义失效：一个刚被更新的 key 可能因为处于 _order 前部而被优先淘汰，而真正最旧的 key 反而保留。
  - 争议对手：918f067abd50
- **[boundary/low]** [boundary] runner/retry.py:20-21 RetryPolicy.delay_for 首次重试使用 2**1 倍退避，且 attempt 从 1 起算（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：call 中 attempt 从 1 开始，delay_for(1) = base_delay * 2，首次重试就跳过了 base_delay，退避序列为 2x、4x…而非通常的 1x、2x…。若这是有意设计则无碍，但与“base_delay”命名暗示的基准间隔不一致，容易造成等待时间翻倍。
  - 争议对手：555e73a76dd4, 555e73a76dd4, c69cce55216c

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `config` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `runner` | 1 | 3 | 3 | 3 | 2 | 0 | 2 | 0 |

矩阵填充率 38%（单元格值 = 独立 Agent 数）
