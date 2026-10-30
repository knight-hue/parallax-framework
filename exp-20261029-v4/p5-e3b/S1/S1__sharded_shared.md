# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 67 | 支持不足、相关性超限或尚待验证 |
| 争议 | 7 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：120
- 独立性画像：有效通道 2.45 / 3，归一化 81.7%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：164 个节点 / 430 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 74 | 100% | 48% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **67** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:232-240 _vector_recall 中 by_id[hit.product_id] 在 hit.product_id 不在 by_id 时被 if 过滤，安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:232-240`
  - 依据：列表推导带 `if hit.product_id in by_id` 守卫，不会 KeyError。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:250-258 _rerank 中 rerank_scores 长度与 scored 不一致时索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:250-258`
  - 依据：代码用 `rerank_scores[i]` 按 scored 的索引取值，假设 Reranker 返回的分数列表长度与输入 documents 完全一致。若 Reranker 实现返回较短列表（例如过滤了空文档、或 API 返回部分结果），会抛 IndexError。该异常会被 execute 中的 except 捕获并降级为按向量分排序，因此不会导致请求失败，但会静默丢失精排结果且日志只记录'rerank 不可用'，掩盖真实原因。属于边界处理不严谨。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:137-152 向量召回成功但结果为空时被误判为召回失败并覆盖策略标注（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:137-152`
  - 依据：向量召回成功返回空列表时 recall_strategy 已被置为 embedding_only，但 scored 为空，于是进入 elif not scored 分支执行关键词召回并把 recall_strategy 覆盖为 keyword_2gram。这本身是合理的兜底，但 rerank_applied 与 recall_strategy 的语义被混淆：当向量召回返回空（例如索引为空）时，实际并未发生 embedding 失败，却对外报告 keyword_2gram，掩盖了索引为空这一运维问题。更关键的是，若向量召回返回空但关键词召回也返回空，最终 recall_strategy 仍标为 keyword_2gram，调用方无法区分“embedding 服务异常”与“索引无数据”。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:196-210 _to_rejected 与 _within_price_cap 使用 primary_sku 价格做币种换算，但 _to_card 展示的 price_major 用原币种，导致 filtered_out 与 hits 的价格口径不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-210`
  - 依据：_to_rejected 明确把价格换算到 target_currency 并标注 currency=spec.target_currency，而 _to_card 展示原币种 price_major/currency。两者口径不同但各自字段自洽（filtered_out 带 currency 字段说明换算后币种），并非缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:78-86 tokenize 对 CJK chunk 生成 2-gram 但单字符 chunk 不生成，且空格切词对中文整句无效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:78-86`
  - 依据：这是极简分词的设计取舍，对中文整句（无空格）会作为一个 chunk 生成 2-gram，能工作。单字符 chunk 不生成 2-gram 是合理的（无法生成）。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:262-270 关键词召回未应用 top_k 截断前的候选上限，全表扫描后排序（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:262-270`
  - 依据：_keyword_recall 对 list_all() 全量商品逐个 tokenize 并打分，复杂度 O(N * 文档长度)。在商品量级较大时确实较慢，但这是兜底路径，且 tokenize 结果未缓存。不过该实现没有正确性问题，且商品目录规模通常有限，属于可接受的降级实现，不构成缺陷。
- **[boundary/low]** [boundary] app/application/usecases/order_usecases.py:88-90 PlaceOrderUseCase 校验 quantity 在 find_sku 之后，但 quantity<=0 的校验位置不影响正确性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:88-90`
  - 依据：quantity<=0 的校验在 find_sku 之后，但仍在 reserve 之前，不会造成扣减错误。顺序问题不影响正确性。
- **[concurrency/low]** [concurrency] app/application/usecases/order_usecases.py:108-116 PlaceOrderUseCase 对同一 SKU 出现在多个 items 时分别 reserve，可能一个成功一个失败导致部分回滚，但回滚逻辑正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-116`
  - 依据：reserved 列表记录每次成功的 reserve，异常时 _rollback 逐条 release，能正确回滚。同一 SKU 多次 reserve 各自独立，回滚也各自独立，无缺陷。
- **[concurrency/low]** [concurrency] app/application/usecases/order_usecases.py:88-118 PlaceOrder 先校验全部商品再扣减，但校验与扣减之间无锁，SKU 可能被并发删除（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:88-118`
  - 依据：resolved 阶段读取 product 与 sku 后，扣减阶段只依赖 sku_id 与 quantity，不依赖 product 对象是否仍存在。即使商品在两步之间被删除，reserve 仍按 sku_id 扣减，订单行已保存了 title/unit_price 快照，不会出现空引用。库存扣减走条件 UPDATE 保证原子性。不构成缺陷。
- **[error_handling/high]** [error_handling] app/application/usecases/order_usecases.py:136-140 PlaceOrderUseCase 幂等键冲突路径中 _replay 抛 OrderAccessDenied 时，本次已 save 的订单未清理（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:136-140`
  - 依据：record 冲突后调用 _replay，_replay 内部若 order.buyer_id != buyer_id 抛 OrderAccessDenied。此时 _rollback 已执行（库存回补），但本次 order 已 save 且未删除，异常向上传播。系统留下'库存未扣减但订单存在'的订单，后续查询/取消会再次 release 造成库存虚增。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:199-202 CancelOrderUseCase 未校验订单当前状态是否可取消，依赖 order.cancel 内部状态机，但 release 在 save 之前执行，若 cancel 抛异常则不会 release（正确），若 release 中途失败则部分回补（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:199-202`
  - 依据：循环 release 无 try/except，若第 2 个 SKU release 抛异常，第 1 个已回补、订单状态已在内存改为取消但未 save。调用方重试时 order.cancel 可能因状态已是取消而抛异常（取决于状态机实现），导致第 2 个 SKU 永远不回补；或状态机允许重复 cancel 则第 1 个 SKU 被重复回补。缺少补偿/幂等保护。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:133-133 PlaceOrderUseCase 幂等键 record 与 find 的键格式不一致（record 传裸 key，find 传 buyer_id:key）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:133-133`
  - 依据：record 调用为 `self._idempotency.record(idempotency_key, order.order_id)`，传入的是裸 idempotency_key；而 _replay 中 find 调用为 `self._idempotency.find(f"{buyer_id}:{idempotency_key}")`，传入的是拼接键。若 OrderIdempotencyStore 实现按传入字符串原样存取（端口未规定内部拼接），则 record 写入的键与 find 查询的键永远不匹配：幂等重投时 _replay 永远返回 None，幂等完全失效；且 record 冲突路径的 _replay 也永远找不到赢家订单，必然抛 ValueError。这是幂等机制的核心缺陷。
- **[security/low]** [security] app/application/usecases/order_usecases.py:168-172 QueryOrderUseCase 对空 buyer_id 抛 OrderAccessDenied 而非参数错误，但这是安全设计（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:168-172`
  - 依据：空 buyer_id 视为无权访问，映射为 404，符合防枚举设计。
- **[security/low]** [security] app/application/usecases/order_usecases.py:190-195 取消订单未校验 buyer_id 为空时仍可能通过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:190-195`
  - 依据：CancelOrderUseCase 与 QueryOrderUseCase 均使用 `if not buyer_id or order.buyer_id != buyer_id` 校验，空 buyer_id 会被拒绝，逻辑正确。OrderAccessDenied 映射为 404 的设计也合理。不构成缺陷。
- **[logic/low]** [logic] app/domain/catalog/exchange_rate.py:33-38 ExchangeRateTable.rate 未校验 from/to 是否在 SUPPORTED_CURRENCIES，仅依赖 rates_to_cny 字典（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:33-38`
  - 依据：rate() 只检查 rates_to_cny 是否包含币种，而 _RATES_TO_CNY 的键集合与 SUPPORTED_CURRENCIES 当前完全一致（CNY/USD/EUR/GBP/JPY/HKD/AUD/CAD/SGD）。convert() 在调用 rate 前已校验 to_currency 属于 SUPPORTED_CURRENCIES，money.currency 由 Money.of 保证受支持。因此当前不会出现不一致；仅当两处常量未来漂移时才可能出问题，属于维护风险而非现存缺陷。
- **[logic/low]** [logic] app/domain/catalog/exchange_rate.py:44-50 ExchangeRateTable.convert 对同币种直接返回原对象，跳过 SUPPORTED_CURRENCIES 校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:44-50`
  - 依据：convert 在 to_currency == money.currency 时提前返回，不再校验 to_currency 是否在 SUPPORTED_CURRENCIES 中。但 Money 本身在构造时已保证 currency 属于 SUPPORTED_CURRENCIES（Money.of 校验），因此同币种分支下 to_currency 必然合法，提前返回不会放过非法币种。rate() 也会对 from/to 做汇率表校验。此处不构成缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 Money 对 JPY 按 100 倍换算，与 ISO-4217 最小单位不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的 ISO-4217 最小单位是 1 日元（无小数位），不是 1/100。from_major_units 和 to_major_units 对所有币种统一除以/乘以 100，导致 JPY 金额被放大 100 倍：from_major_units(1000, 'JPY') 得到 100000 minor units，to_major_units 再除 100 得 1000，往返看似自洽，但与外部系统（支付网关、订单落库的 total_amount_minor）对接时口径错误。注释自承「demo 暂统一」，但这是跨境业务的核心不变量，属于真实缺陷而非风格问题。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/product_repository.py:1-1 ProductRepository 端口缺少按 SKU 查询或批量存在性校验，但这不是缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/product_repository.py:1-1`
  - 依据：端口定义完整，find_by_id/find_by_ids/list_all 满足用例需求。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:51-54 Reranker.rerank 契约要求返回等长分数但无运行时保证（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:51-54`
  - 依据：docstring 已明确契约“返回与 documents 等长的精排分数”，调用方需自行校验；抽象端口无法强制。属于契约文档而非缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:40-42 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:40-42`
  - 依据：这是抽象端口声明，契约由实现方保证；端口层不做参数校验是常见设计，缺陷应落在具体实现。仅凭该抽象方法无法证明存在错误行为。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/stock_repository.py:30-32 StockRepository.release 端口未规定对未登记 SKU 的行为，调用方 CancelOrder 可能对已删除 SKU 回补（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:30-32`
  - 依据：端口契约未明确 release 对未登记 SKU 的行为，但这是契约模糊而非代码缺陷；实现层已有其他审查者指出问题。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-38 Product 未校验 title/brand 等必填字段，searchable_text 可能返回空串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：__post_init__ 只校验 product_id 与 skus 非空，title/brand 等允许为空。但这是聚合根对字段的宽松契约，是否算缺陷取决于上层是否依赖非空；仅凭本文件无法证明会导致错误行为，且 searchable_text 对空串仍可工作（embedding 空文本可能报错，但那是 EmbeddingClient 实现的问题）。因此不判定为确认缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 中 origin_country 被拼入召回文本但文档未声明，且空 highlights 产生多余空格（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：docstring 写的是'标题 + 品牌 + 品类 + 描述 + 亮点'，但实现还拼入了 origin_country。这是文档与实现不一致，但 origin_country 作为召回特征本身合理，且不会导致错误行为。空 highlights 时 highlight_text 为空串，join 会产生连续空格，对分词/embedding 无实质影响。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:30-34 ProductSearchSpec 未校验 price_max_major 与 top_k 的边界（负数/NaN）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:30-34`
  - 依据：__post_init__ 只校验了 normalized_query 非空和 top_k > 0，没有校验 price_max_major。若调用方传入负数或 NaN，price_max_major 作为'价格硬约束'会在检索链路做结构化过滤：负数会导致所有商品被过滤（空结果），NaN 的比较恒为 False 也会导致过滤行为异常（取决于实现是 `price <= max` 还是 `max is not None and price > max`）。由于该字段被声明为硬约束，缺少边界校验会让非法输入静默传播到检索层。
- **[logic/low]** [logic] app/domain/catalog/sku.py:1-1 Sku.stock 只读但 dataclass 未冻结，仍可被外部修改（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:1-1`
  - 依据：文档说明 stock 是初始库存只读参考，但 dataclass 非 frozen，外部仍可赋值。不过这是设计取舍，未直接导致错误行为；真正的扣减走 StockRepository。
- **[logic/low]** [logic] app/domain/catalog/sku.py:20-21 Sku.stock 为初始库存但 dataclass 非 frozen，可被就地修改（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:20-21`
  - 依据：文档明确说明 stock 是只读参考数据，且刻意不提供 deduct_stock/restore_stock。dataclass 未 frozen 确实允许赋值，但这是设计取舍（与 OrderLine 不同），且没有代码路径依赖其不可变性来保证正确性。不构成可复现缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-25 Address.__post_init__ 未校验 state/postal_code/phone，one_line 可能输出空字段（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-25`
  - 依据：校验字段列表刻意排除了 state/postal_code/phone，one_line 对缺失字段只会输出空串，不会抛异常或产生错误金额。是否必填属于业务规则选择，代码本身行为一致，不构成可复现缺陷。
- **[boundary/high]** [boundary] app/domain/order/order.py:47-53 Order.__post_init__ 只检查 lines 是否为 None，空列表可通过校验，导致 total_amount 索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：文档声明不变量为“至少一条订单行”，但校验只写了 `if self.lines is None`。传入空列表 [] 时校验通过，currencies 为空集合，len 为 0 不大于 1，构造成功。随后调用 total_amount() 时执行 `self.lines[0].subtotal()` 直接抛 IndexError；snapshot() 也会调用 total_amount()。Order.place 同样不做非空校验，因此空行订单可被创建并在快照/金额计算时崩溃。
- **[logic/low]** [logic] app/domain/order/order.py:76-82 Order.cancel 未 strip 就保存 reason，仅空白字符被拒绝但前后空白被保留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:76-82`
  - 依据：cancel 用 not reason.strip() 拒绝纯空白，但保存的是原始 reason。这属于数据规范化取舍，不会导致错误行为：状态机与不变量（取消必须带 reason）均被满足。不构成缺陷。
- **[performance/low]** [performance] app/domain/order/order.py:92-96 Order.snapshot 重复调用 total_amount，且未包含 confirmed_at（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:92-96`
  - 依据：total_amount 被调用两次，但订单行数量很小，开销可忽略；缺少 confirmed_at 是快照字段选择，不影响正确性。不构成缺陷。
- **[logic/critical]** [logic] app/domain/order/order_line.py:27-28 OrderLine.subtotal 使用 quantity - 1 计算小计，少算一件（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:27-28`
  - 依据：subtotal 应为 unit_price * quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0，quantity=3 时只算 2 件，导致订单金额系统性偏低，直接影响支付金额、到手价（landed_total 依赖 subtotal）与关税计算。
- **[concurrency/medium]** [concurrency] app/domain/order/ports/order_idempotency_store.py:20-27 OrderIdempotencyStore 端口未定义键的构造规则，find/record 分离导致调用方需自行保证原子性（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:20-27`
  - 依据：该文件只是抽象端口，find 与 record 分离是接口设计；真正的原子性由实现方（如 InMemoryOrderIdempotencyStore）负责，其他审查者已在实现文件中报告了非原子问题。端口本身没有可执行代码，不构成独立缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/order/ports/order_repository.py:22-24 OrderRepository.next_order_id 作为端口方法语义模糊（生成 vs 查询）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_repository.py:22-24`
  - 依据：next_order_id 命名暗示生成下一个单号，但放在仓储端口上语义可接受（由持久层分配 ID）。其他审查者已在具体实现（in_memory/sql）中指出并发与驱动问题，端口本身不构成缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:1-1 freight 计算使用 round 对浮点乘积取整（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:1-1`
  - 依据：0.4*(quantity-1) 为浮点，round 后为 int；对分单位取整误差最多 1 分，属简化口径。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:97-98 关税计算对 taxable_minor_cny * tariff_rate 使用 round 后转 Money，浮点乘法可能产生分位误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:97-98`
  - 依据：taxable_minor_cny 是整数分，tariff_rate 是有限小数（0.13/0.09 等），乘积经 round 取整到分。虽然 0.13 在二进制浮点下不精确，但 round 到整数分后误差远小于 0.5 分，不会造成可观察的错误。属于可接受的实现方式。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:1-1 de_minimis_applied 语义与字段注释不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:1-1`
  - 依据：字段注释为“是否命中免税额度（关税为 0）”，代码用 taxable_minor_cny == 0 判断，即小计未超额度，语义一致。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:36-42 免税额度判断用 CNY 折算小计，但 US/EU 额度按固定汇率硬编码，汇率表变动后口径不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:36-42`
  - 依据：免税额度以 CNY 分为单位硬编码（如 US 800*710），而 subtotal_cny 通过 rates.convert 实时折算。若汇率表与硬编码汇率不同，免税判断会与真实 USD 额度有偏差。但这是文档中明确声明的“简化口径”，且 quote 内部自洽（都用 CNY 口径比较），不构成代码缺陷。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:88-90 运费按 quantity 线性递增但未按件数乘基础运费，多件运费可能低于单件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:88-90`
  - 依据：注释明确说明“首件全价 + 续件 40%”，公式 base*(1+0.4*(q-1)) 与注释一致，是刻意的续重简化逻辑，不是缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:66-77 InMemoryOrderIdempotencyStore 的 find+record 非原子，并发同键请求可双双通过（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:66-77`
  - 依据：find 与 record 各自加锁，但二者之间没有锁保护。两个并发请求用同一幂等键：都先 find 返回 None，然后都调用 record；record 内部虽有锁，但第一个 record 成功后第二个 record 返回 False——若调用方忽略 record 的返回值（或先 save 订单再 record），就会产生两笔订单。端口契约要求 find+record 组合具备原子性，当前实现无法保证。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/in_memory_repositories.py:33-34 InMemoryProductRepository.find_by_ids 静默丢弃不存在的 product_id，调用方无法区分缺失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:33-34`
  - 依据：find_by_ids 用 `if pid in self._products` 过滤掉不存在的 id，返回的列表长度可能小于入参。这是仓储接口的常见约定（批量查询返回命中的子集），调用方若需要严格校验应自行比对。该行为与 SQL 实现的 `WHERE id IN (...)` 语义一致，不构成缺陷。
- …另有 27 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:296-305 库存覆盖使用 get_many 返回的 Mapping，未登记 SKU 的语义依赖实现（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-305`
  - 依据：_overlay_authoritative_stock 用 `if sku["sku_id"] in current` 判断是否覆盖，这依赖 get_many 对未登记 SKU 返回“缺失”而非 0。若某个 StockRepository 实现（如 InMemoryStockRepository）对未登记 SKU 返回 0，则 `in current` 为 True，会把未登记 SKU 的库存覆盖为 0，商品卡显示“无货”，与 Sku.stock 初始库存矛盾，误导买家。端口未定义该语义，调用方却按“缺失”假设编写，属于契约误用。
  - 争议对手：346f156eb49f
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:41-45 ExchangeRateTable.convert 用 round() 做银行家舍入，且对 JPY 等零小数币种仍按分口径取整（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:41-45`
  - 依据：convert 使用 Python 内置 round()，对 .5 采用银行家舍入（round-half-to-even），例如 0.5→0、1.5→2、2.5→2，导致金额换算结果依赖奇偶而非统一进位规则，跨币种结算会出现不可预期的 1 分偏差。同时 Money 全币种按 100 分口径（见 money.py 注释），JPY 换算后仍被当作“分”处理，与 ISO-4217 最小单位不一致。
  - 争议对手：12cf0f8c0af4
- **[logic/low]** [logic] app/domain/catalog/money.py:38-46 Money.add/multiply 绕过 of() 校验直接构造实例（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 是唯一做不变量校验（非负整数、受支持币种）的入口，但 add 和 multiply 直接调用 Money(...) 构造器，跳过校验。虽然当前输入来自已校验的实例，结果仍非负且币种合法，但 multiply 的 quantity 校验与 of 的 amount 校验是两套逻辑；一旦未来有人用 dataclass 直接构造非法 Money（frozen 不阻止构造），或 add 的 other 来自反序列化未校验的数据，不变量就会被破坏。更直接的问题是：Money 的 dataclass 构造器本身不校验，任何代码都可以 Money(-5, 'XXX') 绕过所有不变量，of() 的校验形同虚设。
  - 争议对手：247a99dcc820
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:47-48 InMemoryOrderRepository.next_order_id 非原子，并发下单可能产生重复单号（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:47-48`
  - 依据：next_order_id 直接调用 next(self._counter) 生成单号，但生成单号与 save 之间没有任何锁或原子性保证。itertools.count 的 next 本身在 CPython 下是原子的，所以不会出现两个协程拿到同一个数字；但问题在于调用方（下单用例）通常是 await next_order_id() 后再 await save()，两个并发请求会交错：A 拿到 GBX-000001，B 拿到 GBX-000002，这本身没问题。真正的风险是：如果调用方在拿到单号后、save 之前失败或重试，单号被消耗但订单未落库，导致单号空洞——这属于可接受行为。更关键的是，若调用方把 next_order_id 与 save 组合成'先查后写'的幂等流程，进程内无锁会导致同一幂等键并发时两个请求都通过 find 检查。不过该缺陷的根因在调用方而非本方法。就本方法本身而言，next(self._counter) 在单进程内是安全的。
  - 争议对手：cfad3d7abbb5
- **[logic/medium]** [logic] app/infrastructure/persistence/seed_products.py:88-90 P1023 SilentBuds 价格以 USD 计价但数值 189 与同类 CNY 产品混排，跨币种价格比较失真（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:88-90`
  - 依据：P1023 的 SKU 价格是 189.0 USD，而同类竞品 P1022（299 CNY）、P1024（89 CNY）等均为 CNY。若检索/排序层按 price 数值直接比较（如价格区间过滤、按价格排序、价格梯度打分），189 USD 会被当作 189 单位与 CNY 数值同尺度比较，实际约合 1350 CNY，导致排序与价格过滤结果错误。种子数据是评测语料，这种混币种会污染 Recall/排序指标。
  - 争议对手：810f28da72a6, 810f28da72a6, fd84ffdd3ab5
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:1-1 next_order_id 依赖 inserted_primary_key，部分驱动可能返回 None（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：SQLAlchemy 的 inserted_primary_key 仅在单行 INSERT 且驱动支持 RETURNING/自增回填时可用；批量插入、部分异步驱动或使用 ON CONFLICT 时可能为 None 或抛 InvalidRequestError。代码未做判空，直接取 [0] 会抛异常或得到错误单号。
  - 争议对手：287e4396a040
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:1-1 release 未登记 SKU 时先 commit 再 log，若 log 失败库存已增加但无流水（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：未登记 SKU 分支中，先 db.add(SkuStockRow) 并 commit，再 _log_movement 并第二次 commit。若第二次 commit 失败，库存已增加但流水缺失，破坏审计一致性。应放在同一事务内。
  - 争议对手：c1d692844ce5

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.7%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：8｜覆盖正常：24｜无法判定：0
- 单 Reader 检出率：61.7%（重捕对 3，已观测 74，估计总体 120.0
- 待补检分组：app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/domain/catalog, app/domain/order

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `36316f1e43cb` | 2 | 0 | `reader_miss` | 14.7% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 14.7% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 14.7% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 14.7% |
| `87535cbc08cd` | 2 | 0 | `reader_miss` | 14.7% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 14.7% |
| `a97afbf9a0c4` | 2 | 0 | `reader_miss` | 14.7% |
| `bbc63879339e` | 2 | 0 | `reader_miss` | 14.7% |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app/application/usecases` | 2 | 2 | 2 | 2 | 0 | 2 | 1 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 2 | 2 | 2 | 0 | 0 | 0 | 2 | 1 |
| `app/domain/shipping` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 2 | 2 | 2 | 2 | 0 | 0 | 2 | 2 |

矩阵填充率 55%（单元格值 = 独立 Agent 数）
