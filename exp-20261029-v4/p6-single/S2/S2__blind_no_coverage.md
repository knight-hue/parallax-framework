# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 52 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：54
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：88 个节点 / 142 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 53 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **52** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/medium]** [boundary] app/application/agents/context_policy.py:62-70 context_policy 中 trigger_ratio=0.15 与 reserve_ratio=0.75 组合导致压缩后仍可能超窗（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:62-70`
  - 依据：trigger_ratio=0.15 表示上下文占用达 15% 就触发压缩，reserve_ratio=0.75 表示保留末段 75% 的原始消息。压缩后保留 75% 原始消息 + 摘要，占用仍可能接近或超过触发阈值，导致频繁重复压缩（每次刚压缩完又立刻触发），甚至压缩后占用不降反升（摘要本身占 token）。更关键的是：reserve_ratio 0.75 意味着只压缩前 25% 的消息，压缩收益极小，而触发阈值仅 15%，压缩后保留部分（75%）已远超触发阈值，会立即再次触发压缩，形成压缩抖动。这是配置参数组合的边界缺陷。
- **[logic/low]** [logic] app/application/agents/context_policy.py:62-70 build_context_config 丢弃 context_size 参数，无法校验 trigger/reserve 与窗口的配套关系（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:62-70`
  - 依据：函数用 `del context_size` 显式丢弃参数，注释说明窗口由 model 侧提供。这是有意的设计取舍，不是缺陷。虽然丢弃参数使得无法在此处校验 trigger_ratio * context_size 是否合理，但 ContextConfig 的 ratio 是相对值，由框架按实际窗口计算，不需要 context_size。不构成缺陷。
- **[logic/low]** [logic] app/application/agents/permissions.py:40-52 allow_business_tools 幂等判断只认 source，恢复的持久化规则若 source 不同会重复追加（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/permissions.py:40-52`
  - 依据：幂等性依赖 rule.source == 'projectSettings'。若持久化恢复的规则 source 为其他值（如 'userSettings'），会再追加一条 ALLOW 规则。但重复 ALLOW 规则不会改变行为（仍为放行），只是列表膨胀，不构成功能缺陷。记录为 not_a_defect。
- **[api_misuse/medium]** [api_misuse] app/application/agents/search_agent.py:94-108 build() 中 Toolkit 与 middlewares 参数可能不符合 AgentScope 2.0 Agent 构造签名（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:94-108`
  - 依据：无法从给定文件确认 AgentScope 2.0 的 Agent 构造签名是否接受 toolkit/middlewares/context_config/react_config 这些关键字。仅凭本文件无法判定为缺陷，且其他工厂（如 MainAgent）若使用相同签名则说明是项目约定。
- **[logic/low]** [logic] app/application/agents/search_agent.py:78-91 web_search_tool 仅在 tavily_api_key 非空时注册，但 build_tools 文档称 MainAgent 复用同一批工具，主 Agent 单干时缺少 web 兜底（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:78-91`
  - 依据：这是设计上的条件注册：未配置 key 时工具不可用是预期行为，文档也明确说明“未配置时 Agent 看不到它”。不构成缺陷。
- **[concurrency/low]** [concurrency] app/application/agents/trade_agent.py:62-80 TradeAgentFactory.build_tools 每次调用都新建 middlewares 列表，但 ToolResilienceMiddleware 实例共享 circuit_registry，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:62-80`
  - 依据：_resilience() 每次返回新的 ToolResilienceMiddleware 实例，但都传入同一个 self._circuit_registry，熔断状态在 registry 中共享，因此不同工具/不同 Agent 实例的熔断计数是统一的。这是有意的设计（按工具名区分熔断器）。不构成缺陷。
- **[performance/low]** [performance] app/application/agents/trade_agent.py:82-100 TradeAgentFactory.build 中 build_tools 被调用两次（Toolkit 内一次，MainAgent 复用一次），每次新建 FunctionTool 实例（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:82-100`
  - 依据：build() 中 Toolkit(tools=list(self.build_tools())) 调用一次 build_tools，MainAgent 复用时会再调用一次。每次新建 FunctionTool 和 middleware 实例，但底层 usecase 和 registry 是共享的，无状态泄漏。开销可忽略。不构成缺陷。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:196-200 价格上限比较使用严格小于，等于上限的商品被误判为超预算（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-200`
  - 依据：_within_price_cap 用 `primary_in_target.to_major_units() < spec.price_max_major`，即价格恰好等于 price_max_major 时返回 False，被标记为 over_price_cap 过滤掉。语义上“预算上限”通常包含等于（<=）。买家说“预算 500 以内”，500 元的商品应被接受，实际却被过滤并回传 filtered_out，模型会告诉买家“没有符合预算的商品”。这是边界条件缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:236-244 向量召回成功但结果为空时，仍会走关键词兜底并覆盖 recall_strategy，但 embedding_only 分支下 rerank 未配置时降级逻辑正确；真正缺陷是 rerank 返回长度不足时索引越界（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:236-244`
  - 依据：_rerank 假设 reranker.rerank 返回与 documents 等长的分数列表（端口文档也这么写），但代码用 rerank_scores[i] 按 scored 的索引直接取值。若实现返回的列表比 documents 短（HTTP reranker 截断、部分失败、返回空列表），会抛 IndexError。该异常被 execute 中的 except Exception 捕获并降级为按向量分排序，因此不会崩溃——但降级路径本身是安全的。真正的问题是：如果 rerank_scores 比 documents 长，多余分数被静默丢弃，不会报错；如果短，则 IndexError 被吞掉，rerank_applied 保持 False，行为可接受。因此这里不构成真实缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:253-257 关键词召回入选条件 score >= 0 使零分商品全部入选（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:253-257`
  - 依据：_keyword_recall 用 `if score >= 0` 过滤候选，但 _keyword_score 的最小返回值就是 0.0（无匹配时），因此该条件永远成立，等于没有过滤。结合上一条，无匹配商品会以 0 分进入 filtered，再经 top_k 截断后返回给模型。这是边界条件写错（应为 > 0）。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:78-86 tokenize 对中文 chunk 生成 2-gram 但保留原 chunk，导致单字中文查询无法匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:78-86`
  - 依据：tokenize 对含 CJK 且长度 >= 2 的 chunk 补 2-gram，同时保留原 chunk。单字中文查询（如“鞋”）长度 1，不生成 2-gram，但原 chunk “鞋” 被加入 terms，仍可与文档中的“鞋”匹配（文档中“鞋”作为独立 chunk 或 2-gram 的一部分）。实际上文档侧“运动鞋”会生成 2-gram {运动, 动鞋} 和原 chunk 运动鞋，不含单字“鞋”，因此单字查询“鞋”无法命中“运动鞋”。这是分词粒度的局限，但属于已知的极简分词设计取舍，且注释已说明“极简分词”，不构成需要报告的缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:188-196 _to_rejected 中 spec.target_currency 可能为 None 导致 convert 异常（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:188-196`
  - 依据：_to_rejected 和 _within_price_cap 都调用 self._tariff.rates.convert(price, spec.target_currency)。若 spec.target_currency 为 None（ProductSearchSpec 未强制该字段，且其他审查者已指出 ProductSearchSpec 缺少校验），convert 可能抛异常。_within_price_cap 在 _reject_reason 中被调用，异常会从 execute 中未捕获地抛出（execute 的 try 只包住 _vector_recall），导致整个检索失败而非降级。_to_rejected 同理。这是错误处理缺失：价格换算失败应降级为不过滤或标注不可用，而不是让整个 execute 崩溃。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:300-312 _to_card 中 landed_price 异常只捕获 ValueError，其他异常（如 KeyError）会中断整个检索（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:300-312`
  - 依据：_to_card 中 tariff.quote 只捕获 ValueError，注释说“目的国不在规则表内”。但 TariffSchedule.quote 在规则表缺字段、汇率缺失等情况下可能抛 KeyError 或其他异常，这些不会被捕获，会从 execute 中未捕获地抛出（execute 的 try 只包住 _vector_recall），导致整个检索失败。到手价是附加信息，其计算失败不应让整个检索崩溃。这是错误处理范围过窄的缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:148-158 rerank 分支条件 recall_strategy == 'embedding_only' and scored 在向量召回成功但为空时走关键词兜底，逻辑正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:148-158`
  - 依据：当向量召回成功但返回空列表时，recall_strategy 被设为 embedding_only 但 scored 为空，第一个 if 条件 `recall_strategy == 'embedding_only' and scored` 为假，进入 elif not scored 分支走关键词召回并把 recall_strategy 改为 keyword_2gram。这是合理的降级：向量库为空时用关键词兜底。虽然 recall_strategy 从 embedding_only 被覆盖为 keyword_2gram 可能让调用方误以为向量召回失败，但语义上“最终采用的召回策略”确实是关键词，标注如实。不构成缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:168-172 filtered.sort 注释声称按 product_id 兜底排序但实际只按分数排序，同分顺序不稳定（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:168-172`
  - 依据：注释明确说明“分数相同时按 product_id 兜底排序”，并解释了不固定顺序会导致同问句答案不稳定、评测指标不可复现。但实际代码 `filtered.sort(key=lambda item: -item[0])` 只按分数排序，没有 product_id 作为次级键。Python 的 sort 是稳定排序，但输入顺序来自向量检索后端（注释自己说后端顺序不固定）或关键词召回（list_all 顺序），因此同分商品的相对顺序仍不稳定，注释承诺的确定性没有实现。这是注释与实现不一致导致的真实行为缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:258-266 关键词召回在无匹配时返回 0.0 分候选，导致无关商品进入结果（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:258-266`
  - 依据：_keyword_score 在 matched 为空时返回 0.0，而 _keyword_recall 用 `if score >= 0` 作为入选条件。0.0 >= 0 恒为真，因此**所有**商品（包括与查询毫无词面重叠的商品）都会以 0.0 分进入候选列表。当查询词与任何商品都不匹配时，本应返回空结果，实际却返回按 product_id 排序的任意 top_k 商品，模型会把这些无关商品当作检索结果推荐给买家。这是明确的逻辑缺陷：入选阈值应为 `score > 0`。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:340-356 _overlay_authoritative_stock 中 sku_ids 可能包含重复项，get_many 结果按 sku_id 覆盖正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:340-356`
  - 依据：sku_ids 由所有卡片的 sku 拼接，不同商品可能有相同 sku_id 的概率极低（sku_id 应全局唯一），即使重复，get_many 返回的 dict 按 sku_id 覆盖，结果仍正确。异常被捕获并降级为初始库存，符合设计。不构成缺陷。
- **[boundary/low]** [boundary] app/application/usecases/order_usecases.py:76-82 PlaceOrder 中 quantity 校验在 find_sku 之后，但顺序不影响正确性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:76-82`
  - 依据：quantity <= 0 的校验放在 find_sku 之后，只是多做一次查询，不会导致错误行为（负数量不会进入 reserve）。不构成缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:106-118 PlaceOrder 在 save 之后 record 之前崩溃会留下无幂等记录的订单，重投时重复下单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:106-118`
  - 依据：order_repo.save(order) 与 idempotency.record 之间不是原子操作。若进程在两者之间崩溃，订单已落库但幂等键未登记；队列重投时 _replay 返回 None，会再次扣库存并创建第二张订单，违背“重投不会产生第二张订单”的承诺。_replay 的 docstring 也承认“登记后写单前崩溃”场景，但实际顺序是写单在前、登记在后，注释与实现相反。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:175-182 CancelOrder 先回补库存再 save，save 失败会导致库存已回补但订单未取消（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:175-182`
  - 依据：order.cancel(reason) 修改内存状态后，先循环 release 库存，再 order_repo.save(order)。若 save 抛异常（DB 故障/乐观锁冲突），库存已回补但订单状态未持久化仍为已支付；重试取消会再次 release，造成库存多回补。库存回补与状态持久化缺乏原子性/补偿。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:108-118 PlaceOrder 幂等键冲突回滚后未删除已保存的订单，产生孤儿订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-118`
  - 依据：流程为：reserve 库存 → Order.place → order_repo.save(order) → idempotency.record。若 record 返回 False（并发下另一路先登记同键），代码回滚库存并回放赢家订单，但**没有删除自己刚 save 的订单**。该订单已持久化，库存却已释放，形成“有订单无库存占用”的孤儿订单；后续该订单可被查询/取消，取消时还会再次 release 库存，导致库存被多回补。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:33-37 rate() 未校验 from_currency 是否在 SUPPORTED_CURRENCIES，仅校验汇率表（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:33-37`
  - 依据：rate() 只检查两个币种是否在 rates_to_cny 中，而 convert() 只校验 to_currency 是否在 SUPPORTED_CURRENCIES。若 money.currency 在汇率表中但不在 SUPPORTED_CURRENCIES，或反之，行为不一致。但当前 _RATES_TO_CNY 的键集合与 SUPPORTED_CURRENCIES 看起来一致（CNY/USD/EUR/GBP/JPY/HKD/AUD/CAD/SGD），且 Money 构造时已限制币种，因此实际不会触发。记录为 not_a_defect 以说明已核查。
- **[logic/high]** [logic] app/domain/catalog/exchange_rate.py:41-46 ExchangeRateTable.convert 对零小数币种（JPY）按分单位换算导致金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:41-46`
  - 依据：convert 直接用 money.amount_in_minor_units 乘以汇率再 round，然后调用 Money.of(converted_minor, to_currency)。amount_in_minor_units 是“最小单位”口径：对 CNY/USD 是分（×100），对 JPY 是元（×1）。当目标币种为 JPY 时，源金额的最小单位是分，而 JPY 的最小单位是元，两者量纲不同，直接相乘会把结果放大 100 倍。例如 100 CNY（10000 分）按 1 CNY = 1/0.048 ≈ 20.83 JPY 应得约 2083 JPY，实际得到 round(10000 * 20.83) = 208333 JPY。这与模块 docstring 声称的“最小单位口径一致均为分级换算后再取整”相矛盾，因为 JPY 并不存在分级。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:35-43 Money.add/multiply 直接构造实例绕过 of 的校验，但输入已受约束，不构成缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：add 与 multiply 用 Money(...) 直接构造而非 Money.of，但两者输入都来自已校验的 Money 实例（非负整数）与已校验的 quantity（非负整数），结果必然非负整数，currency 也来自已校验实例。因此不会产生非法 Money。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：from_major_units 对所有币种统一 round(major*100)，但 JPY 的最小单位就是 1 日元（无小数），SUPPORTED_CURRENCIES 明确包含 JPY。传入 1000 JPY 会得到 100000 minor units，to_major_units 再除以 100 得 1000，看似自洽，但 Money 的不变量声明 amount_in_minor_units 是“最小货币单位（分）”，对 JPY 而言最小单位是 1，因此 100000 表示 100000 日元，与 1000 日元相差 100 倍。任何跨币种比较/结算都会出错。注释承认是简化，但这是真实金额错误而非风格问题。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:47-50 retrieval_ports 中 Reranker.rerank 文档承诺等长返回但无运行时校验，调用方直接索引（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:47-50`
  - 依据：端口文档明确要求“返回与 documents 等长的精排分数；失败抛异常，由调用方降级”。这是端口契约，实现方负责遵守。调用方 catalog_search._rerank 直接索引，若实现违约会 IndexError 并被 execute 捕获降级。契约清晰，不构成端口本身的缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:40-41 primary_sku 返回 skus[-1] 而非首个 SKU，语义与命名不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:40-41`
  - 依据：primary_sku 返回列表最后一个元素。若 seed 数据把主 SKU 放在首位，则返回的是非主 SKU，可能导致展示价格/默认下单 SKU 错误。但这是数据约定问题，无法从本文件确认 seed 顺序；且方法名 primary 与实现无强制契约。记录为 not_a_defect 但提示需核对 seed 顺序。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:27-30 ProductSearchSpec 未校验 top_k 与 price_max_major，负值可流入检索链路（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:27-30`
  - 依据：__post_init__ 只校验 normalized_query，注释写“top_k 由调用方保证为正”，但该值对象是 SearchAgent 从自然语言改写产出的边界对象，正是最需要防御的地方。top_k <= 0 会导致召回为空或下游 LIMIT 负数报错；price_max_major 为负数会生成恒假的价格过滤条件，静默返回空结果而非报错，买家侧表现为“搜不到商品”且无任何错误信号。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-33 Sku.stock 为可变 dataclass 字段，与“只读初始库存”的契约不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-33`
  - 依据：文档明确说明 stock 是只读参考数据、刻意不提供 deduct_stock/restore_stock，真正的扣减走 StockRepository 原子操作。dataclass 非 frozen 只是允许属性赋值，但没有任何业务代码路径依赖在 Sku 上改库存；__post_init__ 也校验了非负。这属于设计取舍而非可复现缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/budget.py:57-61 charge 接受负数 token，可反向“充值”预算并绕过降级（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:57-61`
  - 依据：charge 只对 tokens == 0 提前返回，没有校验 tokens < 0。若上游用量统计出错（例如 usage 字段缺失被算成负数、或某处用 charge 做“退还”），used 会被减小，remaining 增大，remaining_ratio 上升，tier 从 minimal/fallback 回升到 main，导致本应降级的意图继续调用主模型，预算控制失效。账本类对象对负消耗应显式拒绝或钳制。
- **[logic/medium]** [logic] app/infrastructure/budget.py:88-94 init_budget 对 total_limit == 0 仍创建预算实例，与文档“0 表示不启用”矛盾（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:88-94`
  - 依据：模块文档与 init_budget 的 docstring 都声明 total_limit <= 0 表示不启用（默认 TOKEN_BUDGET_TOTAL=0 不启用），但代码只对 total_limit < 0 返回 None；total_limit == 0 时会创建一个 TokenBudget(total_limit=0) 并写入 ContextVar。此时 remaining_ratio 因 total_limit <= 0 返回 1.0，tier 恒为 main，看似无害，但 get_budget() 不再返回 None，任何以 `get_budget() is not None` 判断“预算是否启用”的调用方会误判为已启用，并可能开始记录 entries、上报预算指标或走预算相关分支。这与“默认不启用”的契约直接冲突。
- **[api_misuse/low]** [api_misuse] app/infrastructure/context.py:33-35 ShoppingContext.reset 未校验 token 来源，跨 Task 重置会抛 ValueError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:33-35`
  - 依据：ContextVar.reset 要求 token 由同一 Context 中的 set 产生，跨 Task 使用会抛 ValueError。这是 ContextVar 的标准语义，调用方应在同一协程内成对 set/reset；模块文档也说明依赖 Task 级隔离。当前代码只是薄封装，没有引入额外错误行为，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/eventbus.py:130-140 replay 在会话被淘汰后返回空列表，但 last_seq 仍可能返回旧值导致客户端误判（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:130-140`
  - 依据：_remember 淘汰会话时同步 pop 了 _seq，因此 last_seq 对已淘汰会话返回 0，与 replay 返回空列表一致，客户端可据此判断缺口。逻辑自洽。
- **[logic/medium]** [logic] app/infrastructure/eventbus.py:118-128 deliver_local 对同一事件重复投递时 seq 会再次自增，背板回环导致 seq 跳号（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:118-128`
  - 依据：publish 先 deliver_local 给本地订阅者并赋 seq，然后 _broadcast 把带 seq 的事件发到背板。若背板把本进程自己发布的事件也回传（Redis pub/sub 默认行为，除非按进程 ID 过滤），接收端会再次调用 deliver_local，_sequence 会再 +1 并覆盖 seq，导致同一事件在历史缓冲中出现两次且 seq 不同，客户端补发时收到重复事件。注释声称 deliver_local 用于背板远端事件以避免回环，但代码未对来源做任何去重/过滤。
- **[resource_leak/low]** [resource_leak] app/infrastructure/eventbus.py:108-112 subscribe 未限制单会话订阅者数量，泄漏的 Queue 会无界增长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:108-112`
  - 依据：subscribe/unsubscribe 成对使用由调用方负责；Queue 无界但订阅者列表本身不会自动增长，除非调用方忘记 unsubscribe。这属于调用方契约问题，本文件内无证据表明存在泄漏路径。
- **[concurrency/medium]** [concurrency] app/infrastructure/llm.py:168-186 重试循环捕获 BaseException 会把 CancelledError 当作瞬时错误重试（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:168-186`
  - 依据：_call_with_fallback 用 `except BaseException as err` 捕获，随后仅用 is_transient_error(err) 判断。asyncio.CancelledError 在 Python 3.8+ 继承自 BaseException，其 str 通常为空，不会被 transient 标记命中，因此会走 `if not is_transient_error(err): raise` 重新抛出——这一路径尚可。但若取消发生在 asyncio.sleep 期间，sleep 抛出的 CancelledError 同样被外层 except 捕获并重新抛出，行为正确。真正的问题在于：若上游把取消包装成带 'timeout'/'connection error' 文案的异常（网关超时取消），则会被判定为瞬时错误并进入 asyncio.sleep 重试，吞掉取消信号，导致任务无法及时终止。
- **[error_handling/medium]** [error_handling] app/infrastructure/llm.py:103-113 流式分支 finally 中 _charge_budget 抛异常会掩盖原始异常并跳过闸门释放（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:103-113`
  - 依据：_release_after_stream 的 finally 中先调用 _charge_budget(last) 再 await slot.__aexit__。_charge_budget 内部虽有 try/except 包裹，但若 _charge_budget 之外的 slot.__aexit__ 抛异常，或 _charge_budget 的 except 分支本身（logger.debug）抛异常，则 finally 中抛出的新异常会覆盖流迭代过程中的原始异常，且 slot.__aexit__ 可能未执行导致名额泄漏。顺序上应先释放闸门再记账，或把记账放在独立 try 中。
- **[logic/low]** [logic] app/infrastructure/llm.py:143-152 预算降级分支调用 self._fallback(...) 时未经过闸门，且 fallback 是裸 OpenAIChatModel 无重试（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:143-152`
  - 依据：预算降级时直接 await self._fallback(...)，fallback 是普通 OpenAIChatModel，不经过 ThrottledChatModel 的重试/闸门。但外层 __call__ 已持有 slot，且降级本身是预算不足时的主动选择，不再重试是合理设计（避免在预算紧张时继续消耗）。此处不构成缺陷。
- **[resource_leak/high]** [resource_leak] app/infrastructure/llm.py:88-100 流式分支的闸门释放与预算记账在生成器未被消费时永不执行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:88-100`
  - 依据：ThrottledChatModel.__call__ 在流式分支把 slot 移交给 _release_after_stream 生成器，只有生成器被 async for 消费（或显式 aclose）时 finally 才会执行 slot.__aexit__。若调用方拿到 AsyncGenerator 后未迭代就丢弃（例如上层在拿到流后因参数校验失败/取消/异常提前返回，或把返回值存起来但没消费），生成器不会被启动，finally 不执行，闸门名额永久泄漏。多次发生后 GatewayThrottle 名额耗尽，所有模型调用阻塞。这是把资源释放责任交给调用方消费行为的典型泄漏。
- **[concurrency/medium]** [concurrency] app/infrastructure/resilience.py:76-86 熔断半开状态可被并发请求同时放行，失去“只放一次探测”的语义（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:76-86`
  - 依据：allow() 在冷却期满后无条件把 half_open_probing 置 True 并返回 True，没有检查该标志是否已为 True。多个并发工具调用（同一工具在不同协程/Task 中）在冷却期满后同时进入 allow()，会全部被放行，形成对已故障下游的并发探测风暴，与文档“放一次探测请求”的设计相悖。此外 half_open_probing 一旦置 True 后，若探测请求既未成功也未失败（例如被取消），状态会永久停留在 half_open，后续 allow() 仍会持续放行。
- …另有 12 条未列出

## 争议（需裁决）

- **[error_handling/medium]** [error_handling] app/infrastructure/eventbus.py:172-180 _broadcast 中 create_task 成功但 backplane.publish 协程抛异常时异常被吞掉且无日志（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:172-180`
  - 依据：task.add_done_callback(self._pending.discard) 只从集合移除任务，从不调用 task.exception()。若 backplane.publish 协程内部抛异常（如 Redis 连接失败），asyncio 会在任务被 GC 时打印 'Task exception was never retrieved'，但业务层完全无感知，跨进程事件静默丢失，前端 WS 时间线出现缺口且无任何告警。
  - 争议对手：33fb473fc09f

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：30｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain/catalog, app, app/infrastructure, app/application/usecases, app/application/agents, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 1 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `13e4eea2c850` | 1 | 1 | `partition_gap` | — |
| `195131b30098` | 1 | 4 | `partition_gap` | — |
| `24481c1442d8` | 1 | 1 | `partition_gap` | — |
| `27d90514a9b4` | 1 | 2 | `partition_gap` | — |
| `2cc7c376f2fe` | 1 | 4 | `partition_gap` | — |
| `31d1e54cf47c` | 1 | 4 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| …另有 20 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| `app/application/usecases` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 |

矩阵填充率 40%（单元格值 = 独立 Agent 数）
