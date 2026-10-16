# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 9 | 单一来源孤证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：2 个（每轮全新身份）
- 账本条目：11

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 2 | 10 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] cache/ttl.py:28-33 TTLCache.put 容量检查在插入前执行，实际容量可超出 capacity（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:28-33`
  - 依据：len(self._store) > self.capacity 在写入新键之前判断，因此当 store 大小恰好等于 capacity 时不会淘汰，随后插入使大小变为 capacity+1，缓存长期可容纳 capacity+1 个条目，违反容量上限语义。触发条件：连续 put 到 store 大小达到 capacity 后再 put 一个新键。
- **[error_handling/low]** [error_handling] config/loader.py:42-44 describe 在 endpoints 为 None 时抛 AttributeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:42-44`
  - 依据：config.get("endpoints", {}) 只在键缺失时返回 {}；若配置中显式存在 "endpoints": None（例如来自外部 JSON 或调用方传入），则 .get("primary", "<none>") 会在 None 上调用而抛出 AttributeError，而非返回 "<none>"。触发条件：describe({"endpoints": None})。
- **[logic/medium]** [logic] config/loader.py:15-19 load 使用可变默认参数且浅合并导致 DEFAULTS 被污染（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:15-19`
  - 依据：merged = dict(DEFAULTS) 是浅拷贝，merged["endpoints"] 与 DEFAULTS["endpoints"] 是同一对象。若调用方对返回结果的 endpoints 做就地修改（例如通过 with_endpoint），会永久改变模块级 DEFAULTS，使后续 load() 返回被污染的默认值。同时 overrides: dict = {} 作为可变默认参数虽未在函数内被修改，但属于易被误用的模式；核心缺陷是浅拷贝共享嵌套可变对象。触发条件：load() 返回后其 endpoints 被就地修改。
- **[logic/low]** [logic] config/loader.py:22-30 load_from_env 将所有环境变量值作为字符串返回，未做类型转换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 源：`config/loader.py:22-30`
  - 依据：环境变量值始终是 str，overrides[key] = value 直接存入字符串。对于 timeout、retries 这类 DEFAULTS 中为 int 的键，load_from_env 返回的配置类型与默认值不一致（如 timeout 变成 "30"），下游若做数值比较或算术会出错。触发条件：设置 APP_TIMEOUT=60 后调用 load_from_env()。
- **[concurrency/high]** [concurrency] runner/pool.py:33-35 TaskPool._next_id 未加锁，多线程并发调用产生重复 task_id（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:33-35`
  - 依据：_run_one 在每个工作线程中调用 _next_id，而 _next_id 对 self._seq 的读-改-写没有加锁。多个线程同时执行 self._seq += 1 会丢失更新，导致不同任务得到相同 task_id，结果无法区分。触发条件：run_all 提交多个任务并发执行。
- **[concurrency/low]** [concurrency] runner/pool.py:66-68 TaskPool.summary 未加锁读取 _results（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:66-68`
  - 依据：summary 在无锁情况下多次读取 self._results（len 与生成器遍历），若与 _run_one 的 append 并发，可能得到 total 与 ok/failed 不一致的结果。触发条件：任务仍在执行时调用 summary。
- **[performance/medium]** [performance] runner/pool.py:37-45 TaskPool.run_all 忽略 concurrency 参数，为每个任务创建线程（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/pool.py:37-45`
  - 依据：构造函数接收 concurrency 并声明为“固定线程数的任务池”，但 run_all 对 jobs 中每个任务都新建一个线程，完全没有使用 self.concurrency。当 jobs 数量很大时会创建大量线程，可能耗尽资源或触发线程创建失败。触发条件：提交的任务数远大于 concurrency。
- **[error_handling/high]** [error_handling] runner/retry.py:30-31 RetryPolicy.call 将 ValueError 视为成功并返回 None（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`runner/retry.py:30-31`
  - 依据：捕获 ValueError 后直接 return True, None，把异常当作成功结果上报，调用方无法区分“函数返回 None”和“函数抛出 ValueError”。这掩盖了真实错误，且与文档中“失败时按退避重试”的语义矛盾。触发条件：被调用函数抛出 ValueError。
- **[logic/low]** [logic] runner/retry.py:21-22 RetryPolicy.delay_for 的 attempt 从 1 开始，首次退避即为 2 倍 base_delay（确认并非缺陷）
  - 独立来源 0 个：—｜置信度 0.5
  - 源：`runner/retry.py:21-22`
  - 依据：call 中 attempt 从 1 开始，delay_for(1) = base_delay * 2。这只是退避序列的起点选择（首次重试等待 2*base_delay），并非错误行为，属于设计选择，不构成缺陷。

## 争议（需裁决）

- **[logic/critical]** [logic] cache/ttl.py:22-26 TTLCache.get 的过期判断条件写反，未过期条目被删除、过期条目被返回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 源：`cache/ttl.py:22-26`
  - 依据：判断应为 time.time() - created >= self.ttl 才算过期。当前代码在 age < ttl（即条目仍然新鲜）时执行 pop 并返回 None，导致所有未过期缓存永远命中失败；而当 age >= ttl（已过期）时反而返回 value，缓存永不失效。触发条件：任何一次 get 调用。
  - 争议对手：f72c1eddbe62

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cache` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `config` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `runner` | 1 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
