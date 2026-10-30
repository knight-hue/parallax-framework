# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 43 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：45
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：81 个节点 / 124 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 44 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **43** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[error_handling/low]** [error_handling] app/application/agents/context_policy.py:44-58 summary_template 占位符与 summary_schema 字段一致性仅靠注释保证，无运行时校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:44-58`
  - 依据：模板占位符与文档描述的五个字段一致（task_overview/current_state/important_discoveries/next_steps/context_to_preserve），当前代码本身没有不一致。缺少校验属于健壮性建议，不是已存在的缺陷。
- **[logic/low]** [logic] app/application/agents/context_policy.py:66-73 context_policy 中 trigger_ratio 0.15 与 reserve_ratio 0.75 组合可能导致压缩后仍超阈值或频繁压缩（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:66-73`
  - 依据：trigger_ratio=0.15 表示上下文占用 15% 即触发压缩，reserve_ratio=0.75 表示保留末段 75% 原始消息。两者语义由 AgentScope 内部定义，无法仅凭本文件断定冲突；且这是配置取舍而非代码缺陷。
- **[logic/low]** [logic] app/application/agents/permissions.py:44-52 allow_business_tools 幂等判断只检查 source，可能跳过用户自定义规则（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/permissions.py:44-52`
  - 依据：判断 any(rule.source == "projectSettings") 用于幂等，若已有同 source 但 behavior 为 DENY 的规则，会跳过追加 ALLOW，导致工具被拒。但该函数只由本模块写入 projectSettings 规则，正常流程下不会出现 DENY 的 projectSettings 规则，且注释说明兼容恢复的持久化状态。属于理论边界，不构成确认缺陷。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:178-181 价格上限使用严格小于，等于上限的商品被误判为超预算（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:178-181`
  - 依据：`_within_price_cap` 使用 `<` 比较，当商品价格恰好等于 price_max_major 时返回 False，被标记为 over_price_cap 过滤掉。通常“预算上限”语义应包含等于上限（<=）。这属于边界条件处理错误，会让恰好等于预算的商品被错误过滤。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:196-205 rerank 返回分数数量与候选数不一致时索引越界（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-205`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的索引取值，未校验 rerank_scores 长度是否等于 scored 长度。若 Reranker 实现返回的分数少于候选数（例如内部截断或异常），会抛 IndexError；虽然外层 try/except 会捕获并降级，但降级后 scored 仍是原向量分列表，行为可接受——不过异常被吞掉会掩盖 reranker 的契约违约。更关键的是若返回多于候选数则多余分数被忽略，属静默不一致。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-137 向量召回成功但结果为空时不会走关键词兜底，导致空结果（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-137`
  - 依据：当 embedder 与 vector_index 均配置且 _vector_recall 正常返回空列表时，recall_strategy 被置为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 因 scored 为空而跳过精排；`elif not scored:` 分支会执行关键词召回——但注意该 elif 与第一个 if 是同一 if/elif 链，第一个 if 条件为 False（scored 空）时确实会进入 elif，因此这里实际会兜底。需要重新核对：第一个 if 条件 `recall_strategy == "embedding_only" and scored` 为 False，进入 elif `not scored` 为 True，执行关键词召回。所以此路径是安全的。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:148-152 注释声称按 product_id 兜底排序但实际只按分数排序，并列分数顺序不稳定（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:148-152`
  - 依据：注释明确说明分数相同时应按 product_id 兜底排序以保证结果可复现，但实际代码 `filtered.sort(key=lambda item: -item[0])` 只按分数排序，没有 product_id 作为次级键。Python 的 sort 是稳定的，但输入顺序来自向量检索后端（Qdrant 分片/版本不同顺序可能变），因此并列分数时输出顺序仍不稳定，与注释承诺的可复现性相悖，会导致同问句答案不稳定及评测指标不可复现。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:213-220 关键词召回中 _keyword_score 对无匹配返回 0.0 但调用方用 score >= 0 过滤，导致所有商品都被纳入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-220`
  - 依据：_keyword_score 在无任何词匹配时返回 0.0，而 _keyword_recall 用 `if score >= 0` 作为纳入条件，0.0 >= 0 为真，因此所有商品（包括完全不相关的）都会被加入候选。这使关键词兜底召回退化为“返回全库”，再靠 top_k 截断，可能把不相关商品排进结果（尤其当相关商品分数也为 0 时）。正确做法应是 `score > 0`。
- **[concurrency/low]** [concurrency] app/application/usecases/order_usecases.py:100-118 PlaceOrder 中 next_order_id 与 save 之间无幂等保护，重投可能生成多张订单（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:100-118`
  - 依据：当 idempotency_key 为空时确实没有幂等保护，但这是调用方显式选择不传键的语义，模块文档也说明幂等由“任务号+买家”提供。传了键时由 record 的原子 claim 兜底。因此不构成缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:196-202 取消订单先释放库存再保存，保存失败导致库存与订单状态不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-202`
  - 依据：CancelOrderUseCase 先对每行 release 库存，再 save 订单。若 save 抛异常（DB 故障），库存已回补但订单仍是未取消状态，买家可再次取消并再次回补库存，造成库存虚增。缺少补偿或事务边界。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:118-130 幂等键冲突回滚后未删除已保存的订单，产生孤儿订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：execute 在 save(order) 之后才调用 idempotency.record。若 record 返回 False（并发下另一路先登记了同一键），代码只回滚库存并返回赢家结果，但本路已经 save 的订单仍留在 OrderRepository 中，成为一张库存已释放、却真实存在的孤儿订单。买家后续查询/取消该订单会看到一张库存未扣减的订单，且取消时还会再次 release 库存，造成库存虚增。
- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:133-143 幂等键在写单前崩溃时 _replay 返回 None 导致重复下单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:133-143`
  - 依据：_replay 在键已登记但订单查不到时返回 None，注释说“让调用方继续新建”。但键已登记意味着另一路可能正在写单或已写单但读不到（最终一致/主从延迟），继续新建会绕过幂等保护产生第二张订单，与模块文档“队列重投不会产生第二张订单”的承诺矛盾。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:46-47 convert 使用 round() 对最小单位金额做银行家舍入，可能产生 1 分偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:46-47`
  - 依据：converted_minor = round(...) 使用 Python 内置 round，对 .5 采用银行家舍入（round-half-to-even），且浮点乘法本身有精度误差。例如 5 分 JPY 转 USD：5 * (0.048/7.10) ≈ 0.0338 → 0；而某些恰好落在 .5 附近的金额会因浮点表示误差被舍入到与预期相反的方向，导致金额换算出现 1 分偏差。金额换算应使用 Decimal 或显式 half-up 舍入。
- **[logic/medium]** [logic] app/domain/catalog/exchange_rate.py:41-47 ExchangeRateTable.convert 未校验源币种是否在 SUPPORTED_CURRENCIES 中，且 rate() 与 SUPPORTED_CURRENCIES 校验口径不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:41-47`
  - 依据：convert 只校验目标币种 to_currency 是否在 SUPPORTED_CURRENCIES 中，源币种 money.currency 仅通过 self.rate() 检查是否在 rates_to_cny 中。rates_to_cny 与 SUPPORTED_CURRENCIES 是两个独立集合：若 Money 的 currency 是 rates_to_cny 有但 SUPPORTED_CURRENCIES 没有的币种（或反之），行为不一致。更关键的是，rate() 的检查只覆盖 rates_to_cny，而 convert 对目标币种用 SUPPORTED_CURRENCIES 检查，两处校验来源不同，一旦两个集合漂移（例如新增币种只加进 SUPPORTED_CURRENCIES 而忘记加进 _RATES_TO_CNY），convert 会在 rate() 中抛出未预期的 ValueError，而不是给出清晰的币种不支持错误。此外，当 to_currency == money.currency 时直接返回 money，完全跳过 SUPPORTED_CURRENCIES 校验，导致非法币种（如 'XYZ'）的同币种转换被静默接受，与后续分支的校验语义不一致。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:27-30 from_major_units 用 round() 做银行家舍入，浮点主单位换算可能产生 1 分偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:27-30`
  - 依据：major 是 float，major*100 会引入二进制浮点误差；round() 采用银行家舍入（round-half-to-even），例如 round(2.675*100)=267 但 round(0.125*100)=12（因 12.5 舍到偶数 12），与业务通常期望的四舍五入不一致，且 1.005*100=100.49999... 会舍成 100。金额换算出现 1 分偏差在价格场景是可观测错误。
- **[logic/medium]** [logic] app/domain/catalog/money.py:14-17 Money 构造器绕过不变量校验（直接实例化可产生负金额/非法币种）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:14-17`
  - 依据：Money 是 frozen dataclass，但校验只写在 Money.of 静态工厂里，__post_init__ 没有校验。add/multiply 内部直接用 Money(...) 构造，虽然它们自身输入受控，但任何外部代码（如反序列化、测试、其他模块）都可以 Money(-100, 'XXX') 直接构造出违反文档声明不变量（非负、受支持币种）的对象，随后 add/multiply/__str__ 都会在非法状态上继续运算，且 _assert_same_currency 只比较币种不校验合法性。文档明确把非负整数与受支持币种列为不变量，因此不变量未被类型本身强制。
- **[logic/low]** [logic] app/domain/catalog/money.py:32-40 Money.add/multiply 直接调用构造器而非 of，但输入受控，不构成缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:32-40`
  - 依据：add 先 _assert_same_currency 且两个操作数若都经 of 构造则币种合法、金额非负，和仍非负；multiply 显式校验 quantity 为非负 int 且排除 bool，乘积非负。因此在“所有 Money 都经 of 构造”的前提下不会产生非法状态，不单独算缺陷（根因是构造器缺 __post_init__，已在另一条 finding 记录）。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:12-12 retrieval_ports 从 app.domain.catalog.product 导入 Product，但该文件不在给定文件列表中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:12-12`
  - 依据：该 import 指向 app.domain.catalog.product.Product，虽然本次审查文件列表未包含 product.py，但这是同包内正常依赖，无法据此断定模块缺失或循环导入；仅凭给定文件不能确认缺陷，故记为非缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/stock_repository.py:27-30 StockRepository 端口缺少对 quantity 正数/非零的契约约束（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:27-30`
  - 依据：端口是抽象接口，quantity 的合法性校验责任在实现方与调用方；文档已说明 reserve 原子性与失败语义。仅凭接口签名无法断定存在缺陷，属于契约设计而非可复现错误。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:47-53 searchable_text 对空 detail 的 highlight 产生多余空格，且未处理 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-53`
  - 依据：ProductHighlight.detail 默认空字符串，f"{h.label} {h.detail}" 会产生尾部空格，但最终文本用于召回分词，多余空格不影响检索语义；且 dataclass 类型标注为 str，None 不在契约内。因此不构成真实缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-33 Product 为可变 dataclass，frozen 的 ProductHighlight 与可变 skus 列表共享引用（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-33`
  - 依据：Product 非 frozen 且 skus/highlights 使用 default_factory，每个实例获得独立列表，不存在类级共享可变默认值问题。虽然外部可修改列表内容，但这是聚合根的可变设计选择，未观察到由此导致的错误行为。
- **[logic/medium]** [logic] app/domain/catalog/product.py:40-41 primary_sku 返回 skus[-1] 而非首个 SKU，语义与命名不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:40-41`
  - 依据：primary_sku 命名为“主 SKU”，但实现返回 self.skus[-1]（最后一个）。在商品卡展示、默认加购、下单默认规格等场景中，调用方期望得到的是列表首个/标记为主的首选 SKU。返回最后一个会导致默认展示/结算的是列表中最后一个规格（通常是价格最高或最不常用的变体），属于可观察的错误行为。若约定“最后一个即主 SKU”，则应在文档中明确，但当前无任何说明，且与常见约定相反。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:24-27 ProductSearchSpec 未校验 top_k 为正，注释把校验责任外推给调用方（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:24-27`
  - 依据：__post_init__ 只校验 normalized_query，对 top_k 仅留注释“由调用方保证为正”。但 top_k 会直接传给 ProductVectorIndex.search(embedding, top_n) 与关键词召回，top_k<=0 时下游可能返回空结果或抛底层异常（如 Qdrant limit 必须 >0），错误在远离构造点处才暴露，且 frozen 值对象一旦构造就无法修正。值对象本应在构造时守住自身不变量。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:27-31 Sku.stock 未校验类型，bool/float 可通过非负检查（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:27-31`
  - 依据：__post_init__ 只判断 self.stock < 0。传入 True（bool 是 int 子类）或 1.5 都能通过，stock 被当作初始库存播种到 StockRepository 时可能写入非整数库存，后续原子扣减按整数处理会产生类型不一致或截断。Money 的 of/multiply 都显式排除了 bool，这里没有，属于同类校验缺失。
- **[boundary/low]** [boundary] app/infrastructure/budget.py:70-74 remaining_ratio 在 used 超过 total_limit 时返回负值，tier 仍能正确落到 fallback，但 ratio 语义被破坏（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:70-74`
  - 依据：当 used > total_limit 时 remaining 为负，remaining_ratio 返回负值。tier 遍历 TIER_THRESHOLDS，负值不满足任何 >= 下界，最终 return "fallback"，行为正确。exhausted 也正确为 True。虽然 ratio 为负在语义上不美观，但没有导致错误行为，故不判为缺陷。
- **[logic/medium]** [logic] app/infrastructure/budget.py:88-94 init_budget 对 total_limit == 0 的处理与文档约定不一致（0 应表示不启用，但实际创建了预算实例）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:88-94`
  - 依据：模块文档与 settings 都约定 TOKEN_BUDGET_TOTAL=0 表示不启用预算（默认关闭）。但 init_budget 只在 total_limit < 0 时返回 None，total_limit == 0 时会创建一个 total_limit=0 的 TokenBudget 并写入 ContextVar。此时 remaining_ratio 因 total_limit<=0 恒为 1.0，tier 恒为 main，看似无害；但 exhausted 恒为 False、charge 仍会累计 used 与 entries，且 get_budget() 返回非 None，调用方若以 `get_budget() is not None` 判断是否启用预算，就会误判为已启用。更关键的是：一旦调用方按文档传入 0 期望关闭，实际却进入了预算记账路径，与“默认不启用”的契约相悖。
- **[api_misuse/low]** [api_misuse] app/infrastructure/context.py:36-38 ShoppingContext.reset 未校验 token 来源，跨上下文 reset 会抛 ValueError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:36-38`
  - 依据：ContextVar.reset 在 token 不属于当前上下文时会抛 ValueError，这是标准库行为。reset 是薄封装，调用方需自行保证 set/reset 配对。未发现本文件内误用，不判为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/eventbus.py:130-140 replay 在缓冲被淘汰后返回空列表，但 last_seq 仍返回旧值导致客户端无法判断缺口（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:130-140`
  - 依据：会话被淘汰时 _seq 也被 pop，last_seq 返回 0。replay 返回空列表。客户端带 last_event_id 请求补发时，若会话已被淘汰，服务端返回空且 last_seq=0，客户端可据此判断缺口（seq 不连续）。注释已说明此语义。不构成缺陷。
- **[logic/medium]** [logic] app/infrastructure/eventbus.py:118-128 deliver_local 对同一事件重复投递时 seq 会重复递增，背板回环导致 seq 跳变（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:118-128`
  - 依据：publish 先 deliver_local(event) 给本地订阅者并分配 seq，然后 _broadcast 把已带 seq 的事件发到背板。背板收到远端事件后调用 deliver_local 再次 _sequence，会重新分配一个新的 seq（覆盖原 seq）。若背板把本进程发布的事件也回环回来（Redis pub/sub 默认会回送给发布者所在的所有订阅者，除非用独立连接或过滤），同一事件会被投递两次且 seq 不同，客户端看到重复事件。代码注释声称 deliver_local 用于背板收到远端事件以避免回环，但 publish 路径本身也调用 deliver_local，若背板实现未过滤自身消息则回环。
- **[resource_leak/low]** [resource_leak] app/infrastructure/eventbus.py:148-158 _remember 淘汰会话时只清理 _seq 不清理 _subscribers，订阅者队列可能残留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:148-158`
  - 依据：_remember 淘汰最久未活跃会话时 pop 掉 _history 和 _seq，但 _subscribers 由 unsubscribe 显式管理，与历史缓冲生命周期不同。订阅者队列由 WS 连接持有，连接关闭时调用 unsubscribe 清理。淘汰历史不影响活跃订阅者，不构成泄漏。
- **[error_handling/medium]** [error_handling] app/infrastructure/llm.py:155-175 重试循环捕获 BaseException 会把 CancelledError 当作瞬时故障重试，延迟取消（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:155-175`
  - 依据：_call_with_fallback 用 `except BaseException as err` 捕获，随后 is_transient_error(err) 判断。asyncio.CancelledError 在 Python 3.8+ 继承自 BaseException，其 str 通常为空或不含标记，一般会被 is_transient_error 判为 False 并 raise，看似安全。但若取消发生在 await asyncio.sleep(delay) 期间，sleep 抛出的 CancelledError 会被外层 except 捕获，str 为空 → 非瞬时 → raise，行为正确。真正的问题在于：若上游异常消息恰好包含 'timeout' 等标记且同时是取消场景（如 httpx 超时被包装），会进入重试分支并 await sleep，从而在取消后仍继续等待。更直接的问题是 `raise last_error` 在 last_error 为 None 时（理论上循环至少执行一次，不会为 None）——此处不成立。综合看，捕获 BaseException 而非 Exception 是明确的反模式，会吞掉 KeyboardInterrupt/SystemExit 并进入重试逻辑。
- **[error_handling/low]** [error_handling] app/infrastructure/llm.py:176-180 重试用尽后回退到备用模型时，若备用模型也失败，异常直接抛出但未再重试（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:176-180`
  - 依据：回退调用 `return await self._fallback(...)` 在重试循环之外，备用模型失败会直接抛出。这是设计选择（回退只做一次），且备用模型失败时再重试主模型意义不大。不构成明确缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/llm.py:92-100 流式分支异常退出时 _release_after_stream 用 (None,None,None) 退出 slot，掩盖异常且未传递异常信息（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:92-100`
  - 依据：finally 中调用 slot.__aexit__(None, None, None) 而非传入异常信息。GatewayThrottle.slot 是 @asynccontextmanager，其 __aexit__ 在收到 None 时正常退出，不会吞掉异常——异常仍会从 async for 循环向外传播。此处不传异常只影响上下文管理器内部的异常感知，而 GatewayThrottle 不依赖该信息，因此不构成实际缺陷。
- **[logic/low]** [logic] app/infrastructure/llm.py:118-128 预算降级分支调用 self._fallback(...) 时未经过 _call_with_fallback，备用模型失败无重试（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:118-128`
  - 依据：_invoke_upstream 在 tier != main 时直接 await self._fallback(...)，而 _call_with_fallback 的重试循环包裹的是 _invoke_upstream，因此备用模型调用本身也在重试循环内（每次重试都会重新走 _invoke_upstream → fallback）。所以备用模型失败仍会被重试，不构成缺陷。
- **[resource_leak/high]** [resource_leak] app/infrastructure/llm.py:88-100 流式分支中 _release_after_stream 的 finally 在生成器未被消费时不会执行，导致闸门名额泄漏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:88-100`
  - 依据：ThrottledChatModel.__call__ 在流式分支返回 self._release_after_stream(slot, result) 这个异步生成器，但此时 slot.__aexit__ 尚未调用，名额由生成器 finally 释放。若调用方拿到生成器后从未迭代（例如上层在拿到响应后因其他条件提前 return/抛错、或把生成器丢弃），生成器的 finally 永远不会执行，slot 的 __aexit__ 不会被调用，Semaphore 名额永久泄漏。多次发生后 GatewayThrottle 的并发名额被耗尽，所有后续模型调用在 slot.__aenter__ 处永久阻塞。这是手动管理上下文（而非 async with）的典型风险。
- **[concurrency/low]** [concurrency] app/infrastructure/resilience.py:101-113 半开探测成功后 record_success 重置状态，但探测期间其他并发请求的失败会误判为半开失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:101-113`
  - 依据：由于 allow() 可能放行多个并发探测（见上一条），当其中一个探测失败时 record_failure 看到 half_open_probing=True，会重新打开熔断并重置冷却；而另一个探测成功时 record_success 又会把状态整体重置为 closed。两个并发探测的结果互相覆盖，最终状态取决于完成顺序，可能把真实故障掩盖为 closed，或把成功误判为 open。
- **[concurrency/medium]** [concurrency] app/infrastructure/resilience.py:88-99 熔断半开探测状态在并发调用下可能被多个请求同时放行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:88-99`
  - 依据：allow() 在冷却期满后无条件设置 half_open_probing=True 并返回 True。若多个协程在冷却期满后几乎同时调用 allow()，每个都会看到 opened_at 非 None、elapsed >= reset_seconds，于是都返回 True，导致半开状态下放行多次探测请求，违背“只放一次探测”的设计。此外 half_open_probing 一旦置 True，后续 allow() 调用仍会走 elapsed 判断并再次返回 True（因为 opened_at 未变），半开期间并不限制并发。
- **[error_handling/low]** [error_handling] app/infrastructure/resilience.py:168-178 超时/异常分支中 _publish_circuit 在 yield 前调用，但 bus.publish 若抛异常会中断降级返回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:168-178`
  - 依据：_publish_circuit 直接调用 self._bus.publish(...)，未做异常保护。在超时或工具异常分支中，若事件总线 publish 抛出异常（如 Redis 断连），该异常会从 on_tool_call 生成器抛出，导致本应返回的结构化 ERROR chunk 无法 yield，异常穿透到 Agent 循环，违背“不把异常抛穿到 Agent 循环”的设计目标。
- **[boundary/low]** [boundary] app/infrastructure/settings.py:175-176 settings 中布尔解析对 'FALSE'/'False ' 等大小写与空白变体处理不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:175-176`
  - 依据：布尔解析使用 `not in ("0", "false", "False")`，对 'FALSE'、' false' 等变体会被当作 True。这是常见的宽松解析取舍，且环境变量通常由运维按文档填写；未构成明确错误行为，不判为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/settings.py:196-200 database_url 默认值在 data_dir 创建后拼接，但 MYSQL_URL 兼容分支未校验驱动可用性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:196-200`
  - 依据：注释已明确说明换服务型数据库需自行装驱动且本仓未验证，属于已知限制而非隐藏缺陷。默认 SQLite 路径在 data_dir.mkdir 之后拼接，顺序正确。不判为缺陷。
- …另有 3 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/resilience.py:190-195 只检查最后一个 chunk 的 ERROR 状态，中间 chunk 为 ERROR 时被忽略（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:190-195`
  - 依据：代码仅用 chunks[-1].state 判断整体成败。若工具流式返回多个 chunk，其中间某个 chunk 为 ERROR 而最后一个为 SUCCESS（或反之），熔断统计会与实际故障不符。例如工具先报错后补发一个成功 chunk，会被记为成功，连续失败计数被清零，熔断永远无法打开；反之最后一个 ERROR 但前面成功也会被记为失败。这与“工具自身返回 ERROR 也计入连续失败”的注释意图不完全一致。
  - 争议对手：c7a7ed8ae3f2

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

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
| `2cc7c376f2fe` | 1 | 2 | `partition_gap` | — |
| `31d1e54cf47c` | 1 | 3 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| …另有 20 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
