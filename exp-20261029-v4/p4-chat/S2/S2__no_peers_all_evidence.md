# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 5 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 14 | 支持不足、相关性超限或尚待验证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：49
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：87 个节点 / 281 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 22 | 100% | 15% |

## 高置信结论

- **[boundary/medium]** [boundary] app/infrastructure/budget.py:55-59 charge 接受负数 token，可反向“充值”预算并绕过降级（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:55-59`
  - 依据：charge 只对 tokens == 0 提前返回，没有校验 tokens < 0。若上游用量统计出错（例如 usage 差值为负、或调用方传入负值做“回滚”），used 会减少，remaining 增大，remaining_ratio 上升，tier 从 minimal/fallback 回升到 main，导致预算控制被绕过、成本失控。同时 entries 会记录负消耗，事后审计失真。
- **[logic/medium]** [logic] app/infrastructure/budget.py:88-94 init_budget 对 total_limit=0 仍创建预算实例，与文档“0 表示不启用”矛盾（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:88-94`
  - 依据：模块文档与 init_budget 的 docstring 都声明 `total_limit <= 0` 表示不启用（默认 TOKEN_BUDGET_TOTAL=0 不启用），但代码只对 `total_limit < 0` 返回 None；当 total_limit == 0 时会创建一个 TokenBudget(total_limit=0) 并写入 ContextVar。此时 remaining_ratio 因 total_limit<=0 返回 1.0，tier 恒为 main，看似无害，但 get_budget() 不再返回 None，任何以 `get_budget() is not None` 判断“预算是否启用”的调用方会误判为已启用，并可能开始 charge/记录 entries，行为与“默认不启用”的契约不一致。
- **[boundary/medium]** [boundary] app/infrastructure/eventbus.py:158-168 会话淘汰时只清 _seq 不清 _subscribers，且淘汰后 seq 从 1 重新开始导致客户端去重误判（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:158-168`
  - 依据：_remember 在会话数超过 MAX_TRACKED_SESSIONS 时 popitem 淘汰最久未活跃会话并 self._seq.pop(evicted)。但该会话可能仍有活跃订阅者（_subscribers 未清理），且其 seq 被重置为 0。之后该会话再有事件时 seq 从 1 开始，而客户端持有 last_event_id（例如 300），replay 返回空、新事件 seq=1 小于客户端已见 seq，客户端按“seq 单调递增去重”会丢弃这些新事件，时间线永久卡死。这是有界缓存的淘汰策略与 seq 单调性契约冲突。
- **[concurrency/medium]** [concurrency] app/infrastructure/resilience.py:76-86 熔断半开状态可被并发请求同时放行，失去「只放一次探测」语义（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:76-86`
  - 依据：allow() 在冷却期满后无条件把 half_open_probing 置 True 并返回 True，没有检查是否已有探测在途。多个并发工具调用（同一工具在不同协程/Agent 实例中）在冷却期满后同时进入 allow()，会全部被放行，形成对已故障下游的并发冲击；且任一探测成功即 record_success 重置状态，其余仍在途的失败探测随后会重新计数，状态机在并发下不确定。文档明确写「放一次探测请求」，实现未保证互斥。
- **[resource_leak/medium]** [resource_leak] app/infrastructure/resilience.py:148-160 超时/异常路径下 next_handler 的异步生成器未被关闭，可能泄漏资源（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:148-160`
  - 依据：_collect 内部用 `async for chunk in next_handler(**input_kwargs)` 消费下游生成器；当 asyncio.wait_for 超时取消 _collect 任务时，async for 被取消，生成器不会收到 aclose()，其 finally/清理逻辑（如关闭 HTTP 连接、释放锁）可能不执行，取决于事件循环对异步生成器终结的处理时机。异常分支同理：next_handler 抛错后生成器状态未显式关闭。对长连接型工具（web_search_tool 等）会累积未释放连接。

## 待验证（孤证）

- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:27-30 ProductSearchSpec 未校验 top_k 与 price_max_major，注释称由调用方保证（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:27-30`
  - 依据：代码注释明确说明 top_k 由调用方保证为正，且 price_max_major 为 Optional 硬约束，检索链路会结构化过滤。值对象本身不校验并不构成可证实的缺陷，除非有调用方传入非法值；当前文件范围内无法证明存在这样的调用方。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-30 Sku.stock 为可变 dataclass 字段，注释称只读但未强制（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-30`
  - 依据：Sku 是普通 dataclass，stock 字段可被外部赋值修改，注释称其为“只读参考数据”。但模块刻意不提供 deduct_stock/restore_stock，且真正的库存扣减走 StockRepository 原子操作；直接改内存对象不会影响持久化库存，因此不构成超卖缺陷。属于设计取舍而非可证实的错误行为。
- **[error_handling/low]** [error_handling] app/infrastructure/context.py:33-35 ShoppingContext.reset 未校验 token 来源，跨上下文 reset 会抛错（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:33-35`
  - 依据：reset 直接透传 ContextVar.reset(token)，若 token 来自不同 Context 会抛 ValueError，这是 ContextVar 的标准语义，调用方应保证 set/reset 成对且在同一上下文。当前代码没有可证实的误用。
- **[logic/low]** [logic] app/infrastructure/eventbus.py:118-121 subscribe 未对同一 queue 去重，重复订阅导致事件重复投递（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:118-121`
  - 依据：subscribe 每次创建新 Queue，调用方不会传入已有 queue，因此不会重复。unsubscribe 用 in 判断并 remove 一次，若同一 queue 被 append 两次则只移除一个，但正常路径不会发生。属于调用方约束。
- **[resource_leak/low]** [resource_leak] app/infrastructure/eventbus.py:118-121 subscribe 未限制单会话订阅者数量，泄漏的 Queue 会无限累积（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:118-121`
  - 依据：subscribe 每次创建新 Queue 并 append 到列表，unsubscribe 负责移除。若调用方忘记 unsubscribe（如 WS 异常断开未走 finally），Queue 会累积。但这是调用方契约问题，bus 本身提供了 unsubscribe 接口。且 Queue 无 maxsize，put_nowait 不会阻塞。属于使用方责任，不构成 bus 实现缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/resilience.py:88-90 半开探测成功后 record_success 直接替换状态，但探测期间其他并发失败会被丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:88-90`
  - 依据：record_success 用 `self._states[tool_name] = _CircuitState()` 整体替换状态对象，而不是原地重置。若在探测请求进行期间有另一个并发请求（因 allow 的竞态被放行）失败并调用了 record_failure，它修改的是旧 state 对象；随后探测成功替换为新对象，这次失败被静默丢弃，熔断计数与真实故障视图不一致。
- **[error_handling/low]** [error_handling] app/infrastructure/resilience.py:168-176 超时/异常分支在 yield 前调用 _publish_circuit，若 publish 抛异常会击穿中间件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:168-176`
  - 依据：超时与异常处理分支中，`self._publish_circuit(...)` 位于 try/except 之外（except 块内部），且没有自身异常保护。若 TradeEventBus.publish 同步抛错（如序列化失败、连接断开），异常会从 except 块中抛出，绕过“不把异常抛穿到 Agent 循环”的设计目标，Agent 将收到未处理的异常而非结构化 error chunk。
- **[logic/low]** [logic] app/infrastructure/resilience.py:128-140 熔断短路与降级返回未计入失败/成功，熔断打开后永不自动恢复计数（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:128-140`
  - 依据：短路分支直接 return，不调用 record_failure，这是正确设计：熔断期间被拒绝的请求不应延长熔断或累加失败计数，否则熔断永不恢复。恢复依赖 allow() 在冷却期满后放行探测，由真实调用结果驱动 record_success/record_failure。因此不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/resilience.py:148-158 熔断短路分支不记录失败，持续熔断期间无法刷新冷却计时（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:148-158`
  - 依据：短路分支直接返回降级 chunk 而不调用 record_failure，这是熔断器的常规设计：打开期间不再累计失败，冷却期满后由 allow 转半开探测。若在短路时也记录失败，会不断重置 opened_at 导致永远无法进入半开。因此此处行为正确。
- **[logic/low]** [logic] app/infrastructure/resilience.py:88-99 record_failure 在半开探测失败时未累加 consecutive_failures，但会重置 opened_at，行为正确（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:88-99`
  - 依据：半开探测失败时重新打开并重置冷却计时，是标准熔断器行为；consecutive_failures 保持原值（>= threshold）不影响后续判断，因为 opened_at 非空即视为打开。record_success 用新 _CircuitState 覆盖，也正确闭合。此处无缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/settings.py:22-22 load_dotenv 在模块导入时执行，且不覆盖已有环境变量，测试间可能互相污染（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:22-22`
  - 依据：load_dotenv 默认 override=False，不会覆盖已存在的环境变量，这是标准用法。模块级执行是常见模式，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/settings.py:196-200 cors_origins 解析对空字符串返回空列表，可能导致 CORS 全关但无提示（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:196-200`
  - 依据：CORS_ORIGINS 为空时返回空列表，是『空值即关闭』设计的一致体现，注释也说明可选能力按空值关闭。不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/settings.py:175-176 load_settings 中 int()/float() 直接转换环境变量，非法值抛 ValueError 而非友好错误（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:175-176`
  - 依据：配置非法时启动失败并抛 ValueError 是合理行为，错误信息虽不友好但能定位到具体变量名（Python 的 int() 错误会带原始字符串）。不构成功能缺陷。
- **[logic/low]** [logic] app/infrastructure/settings.py:213-213 布尔配置解析只识别 '0'/'false'/'False'，'FALSE'/'no'/'off' 等被当作真值（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:213-213`
  - 依据：多处使用 os.getenv(...) not in ("0", "false", "False") 解析布尔。若运维设置 SEMANTIC_CACHE_ENABLED=FALSE 或 =no 或 =off，表达式为 True，功能被意外开启。这与常见的布尔环境变量约定不符，且同一文件内多处重复该模式，容易误配。

## 争议（需裁决）

- **[error_handling/medium]** [error_handling] app/infrastructure/eventbus.py:196-203 背板广播任务异常被静默吞掉，无日志无重试（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:196-203`
  - 依据：task.add_done_callback(self._pending.discard) 只从集合移除任务，从不检查 task.exception()。当 backplane.publish（Redis 发布）失败时，异常被 asyncio 记录为 'Task exception was never retrieved'，业务侧完全无感知，跨进程事件（worker 的 token.delta/tool.*）会静默丢失，前端时间线出现空洞且无任何告警。这与模块文档强调的“避免断线后时间线永久缺失”目标相悖。
  - 争议对手：4f2e96fb30ee, 4f2e96fb30ee, 76a59f5fed16, 76a59f5fed16, 79fddf980b8a
- **[logic/medium]** [logic] app/infrastructure/eventbus.py:128-137 deliver_local 对背板转发事件重新赋 seq，导致同一事件在 API 进程与 worker 进程 seq 不一致，且背板回环可能重复计数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:128-137`
  - 依据：publish 先调用 deliver_local 赋 seq 并写入本地历史，然后 _broadcast 把带 seq 的事件发到背板；远端进程收到后调用 deliver_local 又调用 _sequence 重新赋 seq 并写入自己的历史。同一逻辑事件在不同进程得到不同 seq，客户端跨进程重连时 last_event_id 语义错乱。此外若背板把本进程自己发布的事件也回传（Redis pub/sub 默认会回传给发布者所在订阅），deliver_local 会再次 _sequence，造成同一事件被投递两次且 seq 跳变。
  - 争议对手：23b79ad29580, 23b79ad29580, 8b62d8df467e, baaa2bd39308, baaa2bd39308
- **[boundary/low]** [boundary] app/infrastructure/settings.py:208-212 database_url 默认值使用 f-string 拼接 Path，Windows 路径反斜杠会破坏 SQLAlchemy URL（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:208-212`
  - 依据：在 Windows 上 data_dir 为 Path('C:\\...\\data')，f"sqlite+aiosqlite:///{data_dir / 'globex.db'}" 会得到 sqlite+aiosqlite:///C:\...\data\globex.db，反斜杠在 URL 中不是合法分隔符，SQLAlchemy 解析可能失败或指向错误路径。Linux 下无此问题。
  - 争议对手：89831e520a00

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：23｜覆盖正常：7｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 22，估计总体 22.0
- 待补检分组：app, app/application/usecases, app/infrastructure, app/application/agents, app/domain/catalog, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.0% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.0% |
| `54e94c349368` | 3 | 0 | `reader_miss` | 0.0% |
| `55804a11a232` | 3 | 0 | `reader_miss` | 0.0% |
| `5777be85cf0d` | 3 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.0% |
| `67641266b07e` | 3 | 0 | `reader_miss` | 0.0% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.0% |
| `817d1b432231` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 13 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 3 | 3 | 3 | 3 | 2 | 0 | 0 | 1 |

矩阵填充率 17%（单元格值 = 独立 Agent 数）
