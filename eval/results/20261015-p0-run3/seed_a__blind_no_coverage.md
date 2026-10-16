# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 11 | 单一来源孤证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：2 个（每轮全新身份）
- 账本条目：11

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 2 | 11 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] cache/ttl.py:29-34 TTLCache.put 容量检查在插入前执行且用 > 而非 >=，导致容量可被突破（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:29-34`
  - 依据：put 先判断 len(self._store) > self.capacity 再插入。当 store 大小恰好等于 capacity 时条件为假，不淘汰，随后插入使大小变为 capacity+1，超出上限。例如 capacity=8，已有 8 个键时 put 新键，最终 size()==9。正确做法是插入前用 >= 判断，或插入后再判断。
- **[logic/low]** [logic] cache/ttl.py:30-32 TTLCache 更新已存在键时 _order 不更新，淘汰顺序与写入顺序不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:30-32`
  - 依据：文档声明按写入顺序淘汰，但 put 对已存在的 key 不会把它移到 _order 末尾（key not in self._store 为假），因此一个被反复更新的热点键仍保留最初的顺序位置，会被优先淘汰，而真正久未写入的键反而留存。触发条件：对同一 key 多次 put 后触发淘汰。
- **[error_handling/low]** [error_handling] config/loader.py:42-44 describe 在 endpoints 为 None 时抛 AttributeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:42-44`
  - 依据：config.get("endpoints", {}) 只在键缺失时返回 {}；若配置中显式存在 "endpoints": None（例如来自 JSON 解析或调用方传入），则 .get("primary", "<none>") 会在 None 上调用而抛 AttributeError，而非返回默认值。触发条件：describe({"endpoints": None})。
- **[logic/high]** [logic] config/loader.py:17-21 load 使用可变默认参数且浅拷贝导致 DEFAULTS 被污染（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:17-21`
  - 依据：merged = dict(DEFAULTS) 是浅拷贝，merged["endpoints"] 与 DEFAULTS["endpoints"] 是同一个 dict。任何对返回配置的 endpoints 做就地修改（例如 with_endpoint 或调用方直接赋值）都会永久修改模块级 DEFAULTS，使后续 load() 返回被污染的默认值。同时 overrides: dict = {} 作为可变默认参数，虽然此处未就地修改 overrides，但仍是隐患。触发条件：load() 后修改返回值的 endpoints 子字典。
- **[logic/medium]** [logic] config/loader.py:24-32 load_from_env 将所有环境变量值作为字符串返回，未做类型转换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:24-32`
  - 依据：环境变量值始终是 str，overrides[key] = value 直接写入字符串。对于 timeout、retries 这类期望 int 的配置项，load_from_env 会返回 "30"、"3" 等字符串，与 DEFAULTS 中的 int 类型不一致，下游做数值比较/运算时会出错（如 "30" > 5 抛 TypeError 或字符串比较）。触发条件：设置 APP_TIMEOUT=60 后调用 load_from_env()。
- **[concurrency/high]** [concurrency] runner/pool.py:33-35 TaskPool._next_id 在无锁保护下自增，多线程并发时产生重复 task_id（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:33-35`
  - 依据：_next_id 由多个工作线程在 _run_one 中并发调用，但 self._seq += 1 未持有 self._lock。CPython 中该操作非原子（读-改-写），两个线程可能读到相同值并生成相同 task-{n}，导致结果中 task_id 重复、无法区分任务。触发条件：run_all 提交多个任务且线程并发执行。
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 TaskPool.summary 读取 _results 未加锁（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 遍历 self._results 时未持有 self._lock，而 _run_one 会在持锁下 append。若在任务仍在执行时调用 summary，可能读到部分结果或触发迭代期间列表被修改。触发条件：run_all 返回前或后台线程仍在运行时调用 summary。
- **[resource_leak/medium]** [resource_leak] runner/pool.py:60-64 TaskPool.export 读取 _results 未加锁，且文件句柄在异常时泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:60-64`
  - 依据：export 直接遍历 self._results 而不获取 self._lock，若与仍在运行的线程并发会读到不一致状态；同时 open 未使用 with，若 json.dump 抛出异常（如 value 不可序列化），handle.close() 不会执行，文件句柄泄漏。触发条件：导出包含不可 JSON 序列化 value 的结果，或导出时仍有线程在写结果。
- **[boundary/low]** [boundary] runner/retry.py:20-21 RetryPolicy.delay_for 使用 attempt 从 1 起算，首次退避即为 2 倍基准延迟（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:20-21`
  - 依据：call 中 attempt 从 1 开始，delay_for(1) = base_delay * 2^1 = 2*base_delay，首次重试等待时间就是基准的两倍，与通常的指数退避（首次为 base_delay）不符，整体退避被放大一倍。触发条件：任何发生重试的调用。
- **[error_handling/high]** [error_handling] runner/retry.py:31-33 RetryPolicy.call 把 ValueError 当作成功返回，吞掉真实失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:31-33`
  - 依据：except ValueError 分支返回 (True, None)，即把 ValueError 视为成功且不重试。这会让调用方误以为操作成功，且丢失异常信息。触发条件：fn 抛出任何 ValueError（例如解析失败、参数非法）时。
- **[logic/low]** [logic] runner/retry.py:34-38 RetryPolicy.call 的 for 循环后 return 为不可达代码（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`runner/retry.py:34-38`
  - 依据：循环内所有分支（成功 return、ValueError return、最后一次失败 return）都会返回，因此循环后的 return False, None 实际不可达。这只是冗余代码，不会造成错误行为，故不视为缺陷。

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `config` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `runner` | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 |

矩阵填充率 38%（单元格值 = 独立 Agent 数）
