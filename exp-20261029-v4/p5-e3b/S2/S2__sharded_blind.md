# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 6 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 60 | 支持不足、相关性超限或尚待验证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：85
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：125 个节点 / 274 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 71 | 100% | 27% |

## 高置信结论

- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:118-130 幂等键冲突回滚后未删除已保存的订单，留下孤儿订单（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：claimed=False 分支只调用 _rollback(reserved) 回补库存，没有删除此前 save(order) 写入的订单。该订单在 order_repo 中永久存在，但库存已释放，形成“有订单无库存占用”的不一致状态；买家若查询该 order_id 会看到一张实际未成立的订单。注释说“本次的扣减与订单都要撤销”，但代码只撤销了扣减。
- **[boundary/medium]** [boundary] app/domain/catalog/exchange_rate.py:44-49 convert 使用 round() 对负数金额做银行家舍入，且未校验 Money 币种是否在汇率表中（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:44-49`
  - 依据：convert 先检查 to_currency 是否在 SUPPORTED_CURRENCIES，但 money.currency 只通过 self.rate() 间接校验（rate 会检查 from_currency 是否在 rates_to_cny 中）。问题在于：SUPPORTED_CURRENCIES 与 _RATES_TO_CNY 的键集合可能不一致——若 SUPPORTED_CURRENCIES 含某币种而 _RATES_TO_CNY 不含，则 to_currency 通过校验后 rate() 抛 ValueError，错误信息是“汇率表不支持币种”而非“不受支持”，语义混乱但仍是异常。更实质的缺陷是 round() 对 .5 采用银行家舍入（round-half-to-even），例如 2.5 分→2、3.5 分→4，导致同一批换算金额出现系统性偏差，且与业务上通常期望的四舍五入不一致。触发条件：换算结果恰为 x.5 分。
- **[boundary/low]** [boundary] app/infrastructure/budget.py:76-80 remaining_ratio 在 total_limit<=0 时恒为 1.0，导致超支后档位永不降级（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:76-80`
  - 依据：remaining_ratio 对 total_limit<=0 直接返回 1.0，这是把“未启用”的语义塞进了比例计算。若 total_limit 为 0 的实例被创建（见上一条），无论 used 多大，ratio 都是 1.0，tier 恒为 main，exhausted 恒为 False。这使“预算耗尽”这一安全兜底在边界值 0 上完全失效。
- **[logic/medium]** [logic] app/infrastructure/budget.py:88-95 init_budget 对 total_limit=0 仍创建预算实例，与文档“0 表示不启用”矛盾（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:88-95`
  - 依据：模块文档与 settings 都声明 TOKEN_BUDGET_TOTAL=0 表示不启用预算（默认关闭）。但 init_budget 只在 total_limit < 0 时返回 None，total_limit == 0 时会创建一个 TokenBudget(total_limit=0) 并写入 ContextVar。此时 remaining_ratio 因 total_limit<=0 返回 1.0，tier 恒为 main，看似无害；但 get_budget() 不再返回 None，任何以 `get_budget() is not None` 判断“预算是否启用”的调用方会误判为已启用，并且 charge() 会持续累加 used 与 entries（无上限增长），与“默认不启用”的契约不一致。
- **[error_handling/medium]** [error_handling] app/infrastructure/llm.py:168-180 重试循环捕获 BaseException 会把 CancelledError 当作瞬时错误重试（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:168-180`
  - 依据：_call_with_fallback 用 except BaseException 捕获，随后 is_transient_error(err) 判断。若 is_transient_error 对 asyncio.CancelledError 返回 True（或实现宽松），任务取消会被吞掉并进入 asyncio.sleep 重试，导致取消无法及时生效、请求被延长。即便 is_transient_error 返回 False，用 BaseException 捕获也会把 KeyboardInterrupt/SystemExit 纳入判断路径，语义不当。正确做法是只捕获 Exception 并显式放行 CancelledError。
- **[resource_leak/high]** [resource_leak] app/infrastructure/llm.py:88-100 流式分支的闸门释放依赖调用方消费生成器，未消费则名额永久泄漏（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:88-100`
  - 依据：__call__ 在流式分支把 slot 交给 _release_after_stream 包装生成器，只有生成器被 async for 消费（或 aclose）时 finally 才会执行 slot.__aexit__。若调用方拿到生成器后未迭代、或仅部分迭代后丢弃引用，asyncio 生成器被 GC 时 finally 虽可能执行，但依赖 GC 时机；更关键的是若调用方把生成器存起来不消费，闸门名额一直不释放，GatewayThrottle 并发额度被永久占用，后续请求全部阻塞。这是把资源生命周期交给调用方的典型泄漏点。

## 待验证（孤证）

> ⚠️ 本节共 **60** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[api_misuse/low]** [api_misuse] app/application/agents/context_policy.py:55-68 build_context_config 丢弃 context_size 参数，无法校验窗口一致性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:55-68`
  - 依据：del context_size 只是显式声明该参数未使用，注释说明窗口由 model 侧提供。这不会导致错误行为，属于设计取舍而非缺陷。
- **[boundary/high]** [boundary] app/application/agents/context_policy.py:62-68 context_policy 的 trigger_ratio 与 reserve_ratio 之和超过 1，压缩后仍超窗口（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:62-68`
  - 依据：trigger_ratio=0.15 表示上下文占用达 15% 即触发压缩，reserve_ratio=0.75 表示压缩后保留末段 75% 的原始消息。二者之和 0.90 虽小于 1，但语义上压缩触发点（15%）远低于保留量（75%）：一旦占用达到 15% 就触发压缩，而压缩策略要求保留 75% 的原始消息，压缩后占用仍约为 75%，远超触发阈值，导致每次请求都再次触发压缩，形成压缩抖动/死循环，且压缩几乎无法把占用降到阈值以下。此外 reserve_ratio 通常应小于 1 - trigger_ratio 才能保证压缩有效。
- **[logic/low]** [logic] app/application/agents/context_policy.py:62-72 context_policy 忽略 context_size 参数，trigger_ratio 固定 0.15 可能对小窗口过早压缩（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:62-72`
  - 依据：del context_size 有注释说明窗口由 model 侧提供，参数仅用于标明配套关系。trigger_ratio/reserve_ratio 是固定策略，是否合理取决于产品取舍而非代码错误。不构成可引用的缺陷。
- **[api_misuse/low]** [api_misuse] app/application/agents/search_agent.py:61-84 web_search_tool 仅在配置 key 时注册，但 build_tools 返回类型标注为 list[FunctionTool] 且 MainAgent 复用同一批工具，未配置时行为差异未在调用方处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:61-84`
  - 依据：条件注册是文档明确声明的设计（“未配置时 Agent 看不到它”），调用方通过 Toolkit 动态获取工具列表，不存在硬编码索引或数量假设。未发现引用具体代码证明调用方依赖固定工具数量。
- **[error_handling/low]** [error_handling] app/application/agents/search_agent.py:83-91 web_search_tool 仅在配置 tavily_api_key 时注册，但系统提示词可能仍指示使用该工具（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:83-91`
  - 依据：代码注释明确说明该工具按“有 TAVILY_API_KEY 才注册”设计，未配置时 Agent 看不到它，属于有意的可选能力降级。是否与提示词冲突取决于 prompts 内容，本文件无法证实存在缺陷。
- **[logic/low]** [logic] app/application/agents/search_agent.py:55-60 build_tools 每次调用都新建中间件与工具实例，MainAgent 与 SearchAgent 不共享熔断状态（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:55-60`
  - 依据：`_resilience()` 每次返回新的 ToolResilienceMiddleware 列表，但熔断状态存放在构造时传入的共享 `self._circuit_registry` 中，中间件本身无状态，因此多次调用 build_tools 不会导致熔断计数分裂。工具实例重复创建只是对象开销，不构成行为缺陷。
- **[logic/low]** [logic] app/application/agents/search_agent.py:60-92 build_tools 每次调用都新建中间件与工具实例，MainAgent 与 SearchAgent 各自持有独立熔断中间件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:60-92`
  - 依据：build_tools() 每次调用都会重新构造 FunctionTool 与 ToolResilienceMiddleware，但熔断状态保存在共享的 self._circuit_registry 中，因此即使中间件实例不同，熔断计数仍然共享，不会出现“各限一份等于没限”的问题。工具本身是无状态包装，重复构造不产生错误行为。
- **[concurrency/low]** [concurrency] app/application/agents/trade_agent.py:60-78 TradeAgent 每次 build_tools 都新建中间件实例，但无共享状态问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:60-78`
  - 依据：_resilience() 每次返回新的 ToolResilienceMiddleware 列表，但熔断状态存放在共享的 circuit_registry 中，中间件本身无状态，因此 MainAgent 与 TradeAgent 各自持有实例不会导致熔断状态分裂。不构成缺陷。
- **[logic/low]** [logic] app/application/agents/trade_agent.py:60-78 TradeAgentFactory.build_tools 每次调用新建中间件实例，MainAgent 与子 Agent 共享工具时熔断状态不共享（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:60-78`
  - 依据：ToolResilienceMiddleware 持有的是同一个 circuit_registry（构造注入），熔断状态在 registry 中共享，中间件实例本身无状态，因此新建实例不影响熔断语义。不是缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:1-1 价格上限过滤使用严格小于，导致恰好等于预算的商品被拒绝（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:1-1`
  - 依据：在 _within_price_cap 中，判断条件是 `primary_in_target.to_major_units() < spec.price_max_major`。当商品价格恰好等于用户给出的 price_max_major（例如用户说“预算 500 元以内”，商品正好 500 元）时，该商品会被判为 over_price_cap 并进入 filtered_out，而不是作为命中返回。通常“价格上限”语义应包含边界（<=），这里用严格小于造成边界商品被错误过滤，属于边界缺陷。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:213-216 价格上限比较使用严格小于，等于上限的商品被误判为超预算（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-216`
  - 依据：price_max_major 语义是“预算上限”，通常应包含等于上限的商品。代码用 < 而非 <=，恰好等于上限的商品会被 _reject_reason 判为 over_price_cap 并进入 filtered_out，模型会告知买家“超预算”，与用户预期（上限内可买）不符。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:1-1 rerank 分数与召回分数长度不匹配时索引越界（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:1-1`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标取值，但没有校验 rerank_scores 的长度是否等于 scored 的长度。如果 Reranker 实现返回的分数数量少于文档数（例如截断、过滤或实现缺陷），会抛出 IndexError；该异常会被 execute 中的 except 捕获并降级为按向量分排序，但此时 rerank 已经部分执行，且错误被静默吞掉，掩盖了 Reranker 的真实缺陷。更严重的是若返回多于文档数则多余分数被忽略。缺少长度一致性校验。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:253-262 rerank 分数数量与候选数不一致时索引越界或静默丢候选（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:253-262`
  - 依据：_rerank 直接用 rerank_scores[i] 按 scored 的下标取值，未校验 rerank_scores 长度是否等于 len(scored)。若 Reranker 实现返回的分数少于候选数（例如内部截断、过滤空文档），会抛 IndexError；该异常被 execute 的 except 捕获后降级为“按向量分排序”，但此时 scored 已被部分覆盖/异常中断，且 rerank_applied 仍为 False——行为虽不崩溃，但错误被吞掉且日志只显示“rerank 不可用”，掩盖了真实的数据契约问题。若返回多于候选数则多余分数被静默丢弃。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:168-172 排序注释声称按 product_id 兜底但实际只按分数排序，并列分数顺序不稳定（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:168-172`
  - 依据：注释明确说明“分数相同时按 product_id 兜底排序”，理由是向量检索在分数并列时返回顺序由后端决定，不固定会导致同一 query 结果不稳定、评测指标不可复现。但实际代码 filtered.sort(key=lambda item: -item[0]) 只按分数排序，Python 的 sort 是稳定排序，因此并列项保持 scored 中的原始顺序——而该顺序正是来自 Qdrant 返回顺序（_vector_recall 直接按 vector_hits 顺序构造列表）。所以注释承诺的确定性并未实现，缺陷真实存在。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:236-244 关键词召回在无匹配时返回 0 分候选，导致无关商品被当作命中返回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:236-244`
  - 依据：_keyword_score 在没有任何词命中时返回 0.0，而 _keyword_recall 的过滤条件是 score >= 0，因此所有商品（包括与查询毫无关系的）都会进入候选列表。降级到 keyword_2gram 时（embedding 服务异常），结果会包含大量完全不相关的商品，且 total_candidates 被虚高，模型会误以为库里有这些商品。若意图是“无匹配则排除”，阈值应为 > 0。
- **[concurrency/high]** [concurrency] app/application/usecases/order_usecases.py:96-130 幂等键在订单保存后才登记，并发重投会重复扣库存并产生第二张订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:96-130`
  - 依据：execute 先 reserve 库存、再 Order.place、再 save(order)，最后才调用 idempotency.record 抢占幂等键。两个并发请求携带同一 idempotency_key 时，二者都会在 _replay 阶段查不到键（record 尚未发生），于是各自 reserve 库存、各自 next_order_id、各自 save 一张订单。随后只有一路 record 成功，另一路 claimed=False 时执行 _rollback(reserved) 并回放赢家订单——但此时输家已经 save 的订单仍留在 order_repo 中，成为一张孤儿订单（库存已回补但订单存在），且 next_order_id 已被消耗。注释声称“队列重投不会产生第二张订单”，与实现不符：幂等键的抢占发生在副作用之后，无法阻止并发下的重复下单。
- **[error_handling/low]** [error_handling] app/application/usecases/order_usecases.py:108-116 库存预留循环中部分成功后异常回滚正确，但 release 失败会掩盖原始异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-116`
  - 依据：except Exception 中 await self._rollback(reserved) 若 release 抛异常，会替换原始异常向上传播，丢失根因；但这是常见的补偿逻辑取舍，且 _rollback 内部无 try 保护。严格说属于可改进点，未达到确认缺陷的强度，因为主流程仍会失败并触发上层重试。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:168-176 取消订单时先回补库存再 save，save 失败会导致库存被重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:168-176`
  - 依据：CancelOrderUseCase.execute 先 order.cancel(reason)（内存状态变更），随后逐行 release 库存，最后才 save(order)。若 save 抛异常（DB 故障、乐观锁冲突等），订单在持久层仍是未取消状态，但库存已经被回补。调用方重试取消时，order.cancel 在内存对象上再次成功（因为重新从 repo 读出的订单仍是未取消状态），于是再次 release，造成库存被重复回补、超卖。注释“重复取消会被状态机挡在上一步，因此不会重复回补”只在 save 成功的前提下成立。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:196-202 取消订单先回补库存再保存订单，保存失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-202`
  - 依据：execute 中先 order.cancel(reason) 修改内存状态，然后循环 release 回补库存，最后才 await self._order_repo.save(order)。若 save 抛异常（DB 故障/乐观锁冲突），订单在持久层仍是未取消状态，但库存已经回补。调用方重试取消时，状态机允许再次 cancel（因为持久层未变），于是库存被第二次回补，造成库存虚增。注释“重复取消会被状态机挡在上一步”只在 save 成功时成立。
- **[security/medium]** [security] app/application/usecases/order_usecases.py:133-141 幂等回放命中他人订单时抛 OrderAccessDenied 而非继续新建（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:133-141`
  - 依据：幂等键若被其他买家占用，_replay 抛 OrderAccessDenied 阻止本次下单，避免把他人订单快照返回给当前买家，这是正确的安全行为；虽然会拒绝合法下单，但属于保守失败，不构成信息泄露或越权。
- **[logic/low]** [logic] app/domain/catalog/exchange_rate.py:36-40 rate() 未校验 from_currency 是否在 SUPPORTED_CURRENCIES，与 convert 的校验口径不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:36-40`
  - 依据：convert 只校验 to_currency 在 SUPPORTED_CURRENCIES 中，from_currency（即 money.currency）仅由 rate() 检查是否在 rates_to_cny 中。若 SUPPORTED_CURRENCIES 是 rates_to_cny 的子集（例如 SUPPORTED_CURRENCIES 不含某币种但 rates_to_cny 含），则 Money 可以持有该币种并通过 convert 的 from 侧校验，产生一个“不受支持”的 Money 参与换算，破坏 Money 的币种不变量。反之若 rates_to_cny 缺某 SUPPORTED 币种，to 侧通过后 rate() 抛错。两处校验集合不一致是真实缺陷。
- **[security/low]** [security] app/domain/catalog/exchange_rate.py:28-30 ExchangeRateTable 为 frozen dataclass 但 rates_to_cny 是可变 dict，可被外部修改破坏汇率快照（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:28-30`
  - 依据：frozen=True 只阻止属性重新赋值，不阻止对 rates_to_cny 这个 dict 的原地修改。default_factory 返回的是 dict(_RATES_TO_CNY) 的浅拷贝，实例间不共享，但实例自身的 dict 仍可被调用方通过 table.rates_to_cny['USD']=1.0 篡改，且该对象被当作不可变值对象在领域内传递，篡改会静默影响后续所有换算。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-32 Money.from_major_units 对 JPY 按 100 倍换算，与最小单位口径不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-32`
  - 依据：JPY 没有小数位（最小单位就是 1 日元），但 from_major_units 对所有币种统一乘 100。传入 1000 JPY 会得到 100000 minor units，to_major_units 再除 100 得 1000，看似自洽，但与真实 JPY 最小单位口径不一致；一旦与外部支付/汇率服务（按真实最小单位）对接，金额会放大 100 倍。注释也承认这是简化。
- **[error_handling/low]** [error_handling] app/domain/catalog/money.py:33-36 Money.from_major_units 对非数值输入抛出 TypeError 而非 ValueError，且未校验 currency 前先做乘法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：from_major_units 直接调用 round(major * 100)，若 major 为 None 或字符串会抛 TypeError；但这是 Python 常规行为，且最终仍会经 Money.of 校验 currency 与 amount。round 返回 int，amount 校验通过。不构成真实缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/product_repository.py:14-25 ProductRepository 抽象方法使用 list[str] 注解，在 Python 3.8 下运行期求值会报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/product_repository.py:14-25`
  - 依据：文件顶部有 from __future__ import annotations，注解被延迟为字符串，不会在运行期求值，因此 list[str] 在 3.8 下也不会报错。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:44-46 retrieval_ports 的 upsert_products 未校验 products 与 embeddings 等长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:44-46`
  - 依据：这是抽象端口定义，契约由实现方保证；端口层不做参数校验是常见做法，且没有具体代码表明会越界。不构成可引用的缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/stock_repository.py:42-44 get_many 返回 Mapping[str,int] 但未约定未登记 SKU 的表示，与 get 返回 None 不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:42-44`
  - 依据：get 明确“未登记的 SKU 返回 None”，而 get_many 返回 Mapping[str,int]，无法表达 None。调用方若用 get_many 批量查库存，未登记 SKU 要么被省略（KeyError/缺键）要么被填 0，两种实现都符合当前文档，但语义不同：填 0 会让“未登记”与“库存为 0”混淆，导致商品卡显示售罄而非未知。端口契约不自洽。
- **[boundary/low]** [boundary] app/domain/catalog/ports/stock_repository.py:30-40 StockRepository 端口缺少对 quantity<=0 的契约约束，reserve/release 语义未定义（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:30-40`
  - 依据：reserve 文档只说明“库存不足返回 False”，未规定 quantity<=0 的行为。若实现直接执行 stock -= quantity，传入负数 quantity 会变成加库存（reserve(-5) 反而增加库存），release(-5) 会扣库存。端口作为契约未约束边界，实现者极易写出可被负数绕过的原子扣减，属于真实的可利用边界缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:45-51 searchable_text 对 highlight.detail 为空时产生多余空格，但不影响召回（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:45-51`
  - 依据：detail 默认空串时 f"{h.label} {h.detail}" 会带尾随空格，join 后出现连续空格。这只是文本格式瑕疵，不影响分词/召回正确性，不构成真实缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:1-1 ProductSearchSpec 未校验 top_k 为正，注释把责任推给调用方（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:1-1`
  - 依据：值对象在 __post_init__ 中校验了 normalized_query，却对 top_k 只留注释“由调用方保证为正”。若调用方传入 top_k=0 或负数，execute 中 `filtered[: spec.top_k]` 会返回空列表或意外切片（负数会从尾部截取），产生静默错误结果而非明确报错。值对象既然承担校验职责，应在此处校验 top_k > 0。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:27-30 ProductSearchSpec 未校验 top_k 为正，注释称由调用方保证但无强制（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:27-30`
  - 依据：注释明确说明 top_k 由调用方保证为正，且该值对象是内部构造，未校验不构成可复现的错误行为；若调用方传入 0 或负数，检索链路会自行处理。属于设计取舍，不报告为缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/context.py:36-38 ShoppingContext.reset 未校验 token 归属，跨任务 reset 会抛错或串台（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:36-38`
  - 依据：ContextVar.reset(token) 本身会校验 token 是否属于当前上下文，跨上下文使用会抛 ValueError，这是 Python 的保护而非本模块缺陷。set/reset 成对使用是调用方责任，模块只是薄封装，未引入额外错误行为。
- **[error_handling/low]** [error_handling] app/infrastructure/context.py:38-40 ShoppingContext.reset 未校验 token 来源，跨上下文 reset 会抛 ValueError 而非静默（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:38-40`
  - 依据：ContextVar.reset 在 token 不属于当前上下文时抛 ValueError，这是标准库行为，调用方应保证 set/reset 配对。不构成缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/eventbus.py:148-158 会话淘汰时只清 _seq 不清 _history 之外的订阅者，且淘汰后 seq 从 1 重新开始导致客户端补发错乱（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:148-158`
  - 依据：_remember 在会话数超限时 popitem 淘汰最久未活跃会话并 self._seq.pop(evicted)。但该会话的 _subscribers 队列并未清理（若仍有活跃订阅者，其队列继续存在但历史被清空）。更严重的是被淘汰会话若之后再次 publish，_seq 从 0 重新计数，新事件 seq=1，而客户端此前已收到 seq 到 N，重连时带 last_event_id=N 请求补发，replay 返回空且新事件 seq=1 < N，客户端按 seq 去重会丢弃这些新事件，时间线永久缺失。
- **[concurrency/medium]** [concurrency] app/infrastructure/eventbus.py:118-130 deliver_local 对同一事件重复投递时 seq 会重复递增，背板回环导致客户端 seq 不单调（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:118-130`
  - 依据：publish 先 deliver_local 赋 seq 并广播到背板；背板把事件转发回本进程时又调用 deliver_local，_sequence 再次 +1 生成新 seq 并再次 _remember。若背板把本进程自己发布的事件也回传（Redis pub/sub 默认会回传给发布者所在订阅），同一逻辑事件会被投递两次、占用两个 seq，客户端时间线出现重复事件且 seq 跳号。代码注释声称'避免回环广播'，但 deliver_local 本身没有任何去重/来源标记机制，仅靠调用方约定。
- **[concurrency/medium]** [concurrency] app/infrastructure/eventbus.py:148-156 deliver_local 对背板转发事件重新赋 seq，可能与本地已发 seq 冲突（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:148-156`
  - 依据：注释说明 seq 在 deliver_local 赋值，因为 WS 客户端只连一个进程，无论事件来自本进程还是背板转发都经由此处进入订阅者，因此对客户端单调。_sequence 用 _seq[session_id]+1 递增，同一进程内不会重复。背板转发的事件若已带 seq 会被 replace 覆盖，但客户端只看到本进程的 seq 序列，仍单调。除非同一事件既本地投递又被背板回环转发（注释称 deliver_local 用于避免回环），否则无缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/eventbus.py:175-185 publish 在无运行事件循环时静默跳过广播，跨进程事件丢失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:175-185`
  - 依据：_broadcast 捕获 RuntimeError 并跳过广播，注释说明这是同步测试场景的兜底，本地投递已完成。生产环境 publish 都在事件循环内调用，不会触发。这是有意的降级设计，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/eventbus.py:196-205 publish 在无运行事件循环时静默跳过背板广播，跨进程事件丢失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:196-205`
  - 依据：注释已明确说明该分支用于同步测试场景，此时本地投递已完成，跳过广播是预期行为。生产环境 publish 均在事件循环内调用，不会触发 RuntimeError。因此不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/llm.py:246-262 create_chat_model 中 fallback 与主模型共用同一 credential 对象（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:246-262`
  - 依据：fallback 与主模型共用 credential 是合理的——同一网关同一 api_key，只是 model 名不同。OpenAICredential 是不可变配置对象，共享无副作用。不是缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/llm.py:137-143 预算降级分支直接 await 备用模型，绕过闸门与流式名额移交（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:137-143`
  - 依据：_invoke_upstream 在 tier != main 且存在 fallback 时直接 `return await self._fallback(...)`。若 fallback 是流式模型，返回的是异步生成器，外层 __call__ 会把它交给 _release_after_stream 持有名额——这部分尚可；但 fallback 模型自身是普通 OpenAIChatModel，不经过 GatewayThrottle，因此降级期间对备用模型的并发/速率完全不受闸门约束，与模块文档“配额闸门”目标矛盾，网关配额紧张时降级流量会再次触发 429。
- …另有 20 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/agents/permissions.py:40-52 allow_business_tools 幂等判断只检查 source，会跳过用户自定义的 projectSettings 规则并重复追加（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/permissions.py:40-52`
  - 依据：幂等判断 `any(rule.source == "projectSettings" for rule in rules)` 只按 source 判断，不检查 rule_content/behavior。若持久化状态里已存在同 source 但不同内容（例如用户或项目配置的 DENY/ASK 规则，或 rule_content 非空的规则），函数会认为已配置而跳过追加 ALLOW，导致业务写工具仍被默认策略拦截（RequireUserConfirmEvent 挂起），与模块文档声明的“显式配置 allow 规则”目标不符。反之，若已有同 source 的 ALLOW 规则但 tool_name 不同（rules 是按 tool_name 分桶的，所以这点不成立），则不会重复。核心缺陷是 source 不足以唯一标识本函数追加的规则。
  - 争议对手：a1b9a699a2d1
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:1-1 关键词召回在无匹配时返回 0.0 而非负分，导致所有商品都被当作候选（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:1-1`
  - 依据：_keyword_recall 用 `if score >= 0` 过滤候选，而 _keyword_score 在没有任何词命中时返回 0.0（不是负数）。因此 `score >= 0` 恒为真，所有商品都会进入候选列表，包括与查询完全无关的商品。这会让关键词降级召回退化为“返回全库”，再靠 top_k 截断，可能把无关商品排进结果（尤其当所有商品都 0 分时，顺序取决于 list_all 顺序）。过滤条件与打分函数的约定不一致。
  - 争议对手：e7260e09e372, e7260e09e372
- **[logic/medium]** [logic] app/domain/catalog/money.py:33-36 JPY 等零小数位币种按 100 倍换算导致金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的最小货币单位就是 1 日元（无小数位）。from_major_units 对所有币种统一乘 100，to_major_units 统一除 100，因此 1000 JPY 会被存成 100000 minor units，再显示为 1000.00 JPY，语义上把 1000 日元当成了 1000 分。注释承认是简化，但代码对外暴露的 to_major_units/__str__ 会给出错误金额，属于真实逻辑缺陷（跨境结算场景）。
  - 争议对手：e43fdf0c37f2
- **[logic/medium]** [logic] app/domain/catalog/product.py:38-39 primary_sku 返回 skus[-1] 而非首个 SKU，与“主 SKU”语义相反（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:38-39`
  - 依据：方法名为 primary_sku，但返回列表最后一个元素。若 SKU 列表按默认/主推顺序排列（常见约定首个为主 SKU），则返回的是最次要的 SKU，导致展示价、加购默认项错误。代码中没有任何排序或标记说明最后一个才是主 SKU，语义与实现不一致。
  - 争议对手：0dce63d15651
- **[logic/low]** [logic] app/infrastructure/settings.py:175-176 settings 中布尔解析对 'FALSE'/'False ' 等大小写与空白变体处理不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:175-176`
  - 依据：多处使用 `os.getenv(..., "1") not in ("0", "false", "False")` 解析布尔。若环境变量设为 "FALSE"、"False "（带空格）或 "no"，会被当作 True，与运维预期相反。例如 SEMANTIC_CACHE_ENABLED=FALSE 仍会开启语义缓存。这是可复现的配置解析缺陷。
  - 争议对手：b84ebef15759

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.82% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：8｜覆盖正常：22｜无法判定：0
- 单 Reader 检出率：37.2%（重捕对 3，已观测 71，估计总体 191.0
- 待补检分组：app/domain/catalog, app, app/application/usecases, app/infrastructure, app/application/agents, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 2 | 0 | `reader_miss` | 39.5% |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 39.5% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 39.5% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 39.5% |
| `54e94c349368` | 2 | 0 | `reader_miss` | 39.5% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 39.5% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 39.5% |
| `f9c039a1b907` | 2 | 0 | `reader_miss` | 39.5% |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 2 | 1 | 1 | 1 | 0 | 0 | 0 | 2 |
| `app/application/usecases` | 2 | 1 | 2 | 2 | 0 | 1 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 1 | 0 | 1 | 0 | 1 |
| `app/infrastructure` | 2 | 2 | 2 | 2 | 2 | 0 | 2 | 1 |

矩阵填充率 46%（单元格值 = 独立 Agent 数）
