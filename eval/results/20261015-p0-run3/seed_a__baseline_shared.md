# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 9 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 0 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：31

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 10 | 100% | 33% |

## 高置信结论

- **[boundary/medium]** [boundary] cache/ttl.py:28-33 TTLCache.put 容量淘汰判断在插入前执行导致超容（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:28-33`
  - 依据：淘汰检查 `len(self._store) > self.capacity` 在写入新键之前执行。当 store 大小恰好等于 capacity 时不会淘汰，随后插入新键使大小变为 capacity+1，缓存可长期超出容量上限。
- **[logic/low]** [logic] cache/ttl.py:29-31 更新已存在键时 _order 不更新导致淘汰顺序错误（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-31`
  - 依据：`if key not in self._store` 才 append，更新已有键时不会把 key 移到 _order 末尾。文档声称按写入顺序淘汰，但更新操作不改变顺序，导致最近写入的键可能先被淘汰，与声明的语义不符。
- **[logic/high]** [logic] config/loader.py:16-20 load 使用可变默认参数且浅拷贝 DEFAULTS（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:16-20`
  - 依据：`overrides: dict = {}` 是可变默认参数（虽未直接修改，但仍是隐患）；更关键的是 `dict(DEFAULTS)` 只做浅拷贝，嵌套的 `endpoints` dict 与 DEFAULTS 共享同一对象。任何对返回配置中 endpoints 的原地修改都会污染全局 DEFAULTS，影响后续所有 load 调用。
- **[concurrency/high]** [concurrency] runner/pool.py:31-33 TaskPool._next_id 未加锁，多线程并发下产生重复 task_id（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:31-33`
  - 依据：`self._seq += 1` 是非原子读-改-写操作，而 _run_one 在多个线程中并发调用 _next_id，没有使用 self._lock 保护。两个线程可能读到相同的 _seq 值，生成重复的 task-{n}，导致结果无法按 id 区分。
- **[concurrency/medium]** [concurrency] runner/pool.py:57-66 export 与 summary 读取 _results 未加锁存在数据竞争（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:57-66`
  - 依据：_run_one 在锁保护下追加 _results，但 export 和 summary 直接遍历 self._results 而未持锁。若在任务仍在执行时调用，可能读到不一致状态或触发 RuntimeError（迭代时列表被修改）。
- **[performance/medium]** [performance] runner/pool.py:35-43 run_all 忽略 concurrency 参数为每个任务创建线程（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:35-43`
  - 依据：构造函数接收 concurrency 并保存为 self.concurrency，但 run_all 对每个 job 都新建一个线程，完全没有使用该参数。任务数很大时会创建大量线程，导致资源耗尽或性能下降，与“固定线程数的任务池”文档不符。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:57-61 TaskPool.export 未使用 with 且异常时不会关闭文件句柄（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:57-61`
  - 依据：`handle = open(...)` 后若 json.dump 抛出异常（如序列化不可序列化的 value），`handle.close()` 不会执行，文件句柄泄漏。应使用 with 语句或 try/finally。
- **[boundary/low]** [boundary] runner/retry.py:28-37 attempts<=0 时 call 静默返回失败（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:28-37`
  - 依据：当 attempts<=0 时 for 循环体不执行，直接落到末尾 `return False, None`，fn 从未被调用。调用方无法区分“函数执行失败”与“配置错误导致根本没执行”，属于静默失败。
- **[error_handling/high]** [error_handling] runner/retry.py:29-31 RetryPolicy.call 将 ValueError 视为成功并返回 None（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:29-31`
  - 依据：捕获 ValueError 后直接 `return True, None`，把异常当作成功返回。调用方会误以为操作成功且得到 None 值，掩盖真实错误，且不会重试。

## 待验证（孤证）

（无）

## 争议（需裁决）

- **[logic/high]** [logic] config/loader.py:36-40 with_endpoint 浅拷贝后原地修改嵌套 endpoints 污染源配置（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 源：`config/loader.py:36-40`
  - 依据：`config.copy()` 是浅拷贝，`updated["endpoints"]` 与传入 config 的 endpoints 是同一对象。`updated["endpoints"][name] = url` 会原地修改调用方配置，甚至当 config 来自 load() 时会污染 DEFAULTS，违背文档“返回新配置、调用方保留原配置”的承诺。
  - 争议对手：848474ea31aa

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `config` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `runner` | 0 | 3 | 3 | 3 | 3 | 0 | 3 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
