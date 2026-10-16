# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 10 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 1 | 单一来源孤证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：31

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 11 | 100% | 38% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量淘汰判断在插入前执行且用 > 而非 >=（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：淘汰检查发生在 `self._store[key] = ...` 之前，且条件是 `len(self._store) > self.capacity`。当 len 恰好等于 capacity 时不会淘汰，随后插入使 len 变为 capacity+1，容量被突破；只有下一次 put 才会纠正。
- **[logic/low]** [logic] cache/ttl.py:30-34 TTLCache 更新已存在 key 时 _order 不更新（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:30-34`
  - 依据：`if key not in self._store` 才 append，更新已有 key 时 _order 中位置不变，淘汰顺序不再反映最近写入顺序，与文档所述“按写入顺序淘汰”不符。
- **[api_misuse/low]** [api_misuse] config/loader.py:15-19 load 使用可变默认参数 overrides={}（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:15-19`
  - 依据：可变默认参数在函数定义时创建一次并被所有调用共享。虽然当前实现只读取 overrides 未修改它，但这是公认的反模式，一旦后续在函数内修改 overrides 就会跨调用泄漏状态。
- **[logic/high]** [logic] config/loader.py:36-40 with_endpoint 浅拷贝污染原配置的 endpoints（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:36-40`
  - 依据：`config.copy()` 只复制顶层字典，`updated["endpoints"]` 与 `config["endpoints"]` 指向同一嵌套字典。随后 `updated["endpoints"][name] = url` 会直接修改原配置的 endpoints，违反文档“返回一个新配置、调用方通常保留原配置”的约定。
- **[concurrency/medium]** [concurrency] runner/pool.py:31-33 TaskPool._next_id 未加锁，多线程下 _seq 自增存在竞态（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:31-33`
  - 依据：_run_one 在多个线程中并发执行，而 _next_id 对 self._seq 的 `+= 1` 没有加锁保护。`self._seq += 1` 是非原子操作（读-改-写），并发时可能产生重复的 task_id，导致结果无法区分。虽然 CPython 的 GIL 让单条字节码原子，但 += 涉及多条字节码，仍可能交错。
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 TaskPool.summary 未加锁读取 _results（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 在无锁情况下遍历 self._results，若与 _run_one 的 append 并发，可能读到部分更新或触发迭代期间列表变化，统计结果不准确。
- **[performance/medium]** [performance] runner/pool.py:36-44 TaskPool.run_all 忽略 concurrency 参数（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:36-44`
  - 依据：构造函数接收 concurrency 并保存为 self.concurrency，但 run_all 为每个 job 都创建一个线程，从未使用 self.concurrency 限制并发数。任务数很大时会创建大量线程，违背“固定线程数任务池”的设计。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:60-64 TaskPool.export 未加锁读取 _results 且文件句柄未用 with 保护（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：export 直接遍历 self._results 而未持有 self._lock，若与 _run_one 并发会读到不一致状态；同时 open 返回的句柄在 json.dump 抛异常时不会关闭，造成文件描述符泄漏。
- **[boundary/low]** [boundary] runner/retry.py:22-23 RetryPolicy.delay_for 首次退避为 base_delay*2（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:22-23`
  - 依据：call 中 attempt 从 1 开始，delay_for(1) = base_delay * 2**1 = 2*base_delay，首次退避翻倍，与通常期望的 base_delay 起步不符。
- **[error_handling/high]** [error_handling] runner/retry.py:30-32 RetryPolicy.call 对 ValueError 直接返回成功（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:30-32`
  - 依据：捕获 ValueError 后返回 `(True, None)`，把异常当作成功且丢弃返回值。调用方会误以为操作成功，且该异常既不被重试也不被上报，掩盖了真实失败。

## 待验证（孤证）

- **[logic/low]** [logic] runner/retry.py:34-38 RetryPolicy.call 的 for 循环后 return 为死代码（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`runner/retry.py:34-38`
  - 依据：循环内所有分支（成功 return、ValueError return、最后一次失败 return）都会返回，因此循环后的 `return False, None` 不可达。这只是冗余代码，不会导致错误行为，故不视为缺陷。

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `config` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| `runner` | 1 | 3 | 3 | 3 | 3 | 0 | 3 | 0 |

矩阵填充率 42%（单元格值 = 独立 Agent 数）
