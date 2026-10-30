# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 49 | 支持不足、相关性超限或尚待验证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：85
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：123 个节点 / 302 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 52 | 100% | 29% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **49** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[logic/medium]** [logic] app/application/agents/context_policy.py:66-76 build_context_config 丢弃 context_size，压缩阈值与模型窗口脱钩（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/context_policy.py:66-76`
  - 依据：函数签名接收 context_size 并在 docstring 中声明“与 create_chat_model 保持一致”，但函数体第一行 `del context_size` 直接丢弃该参数，ContextConfig 只使用固定的 trigger_ratio=0.15 / reserve_ratio=0.75。压缩触发点因此变成模型窗口的固定比例，而不是按实际窗口大小计算；当调用方传入不同窗口（例如 8k 与 128k）时，压缩阈值不会随之调整，长对话在小窗口模型上仍可能爆 token，在大窗口模型上则过早压缩、丢失原始消息。docstring 明确说明该参数用于配套关系，实现却未使用，属于实现与契约不一致的逻辑缺陷。
- **[api_misuse/low]** [api_misuse] app/application/agents/search_agent.py:62-84 build_tools 返回类型标注为 list[FunctionTool]，但 web_search_tool 分支追加的也是 FunctionTool，类型一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:62-84`
  - 依据：两个分支构造的都是 FunctionTool，返回类型与标注一致；web_search_tool 按 tavily_api_key 条件注册是文档声明的设计，未配置时 Agent 看不到该工具属于预期行为，不是缺陷。
- **[api_misuse/medium]** [api_misuse] app/application/agents/search_agent.py:88-103 build() 中 Toolkit 与 middlewares 参数可能不符合 AgentScope 2.0 Agent 构造签名（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:88-103`
  - 依据：无法从给定文件确认 AgentScope 2.0 的 Agent 构造签名是否接受 toolkit/middlewares/context_config/react_config 这些关键字。代码内部一致（build_agent_middlewares 返回列表、Toolkit(tools=...) 用法），且其他工厂文件未在审查范围内，无法证实签名不匹配。按纪律不报告为缺陷。
- **[logic/low]** [logic] app/application/agents/search_agent.py:55-60 build_tools 每次调用都新建中间件与工具实例，MainAgent 与 SearchAgent 各自持有独立熔断中间件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:55-60`
  - 依据：文档明确说明 build_tools() 同时供 MainAgent 复用，且每次调用返回新列表。ToolResilienceMiddleware 共享同一个 circuit_registry（构造时注入），因此熔断状态是共享的，新建中间件实例不会导致熔断失效。工具实例本身无状态，重复构建不构成缺陷。
- **[logic/low]** [logic] app/application/agents/search_agent.py:78-85 web_search_tool 仅在 tavily_api_key 存在时注册，但 build_tools 文档声称 MainAgent 复用同一批工具，主 Agent 单干时缺少兜底能力（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/search_agent.py:78-85`
  - 依据：这是有意的条件注册设计，文档已明确说明未配置时 Agent 看不到该工具。MainAgent 复用 build_tools 时同样受此条件约束，行为一致，不构成缺陷。
- **[logic/low]** [logic] app/application/agents/trade_agent.py:55-76 TradeAgentFactory.build_tools 每次调用新建中间件实例，MainAgent 与子 Agent 不共享熔断状态（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:55-76`
  - 依据：`_resilience()` 每次返回新的 `ToolResilienceMiddleware` 列表，但中间件内部持有的是共享的 `self._circuit_registry`，熔断状态在 registry 中，不在中间件实例中。因此 MainAgent 与子 Agent 共享同一 registry，熔断状态一致。此条不构成缺陷。
- **[logic/low]** [logic] app/application/agents/trade_agent.py:66-84 TradeAgentFactory.build_tools 每次调用新建中间件实例，MainAgent 与 TradeAgent 各自持有独立熔断中间件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/trade_agent.py:66-84`
  - 依据：build_tools 每次调用都通过 self._resilience() 新建 ToolResilienceMiddleware 列表，但熔断状态存放在共享的 self._circuit_registry 中，中间件本身无状态，因此 MainAgent 与 TradeAgent 复用同一 registry 时熔断计数仍然共享，不构成缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:196-199 价格上限过滤使用严格小于，等于上限的商品被误判为超预算（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-199`
  - 依据：price_max_major 语义是“价格硬约束上限”，通常应包含等于上限的商品（<=）。但 _within_price_cap 使用 primary_in_target.to_major_units() < spec.price_max_major，恰好等于上限的商品会被 _reject_reason 判为 over_price_cap 并从结果中剔除，同时出现在 filtered_out 中，向模型传达“超预算”的错误结论。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:218-228 rerank 返回分数数量与候选数不一致时索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:218-228`
  - 依据：_rerank 用 `rerank_scores[i]` 按候选索引取值，但未校验 rerank_scores 长度是否等于 scored 长度。若 Reranker 实现返回的分数少于候选数（例如上游截断或返回空列表），会抛 IndexError；该异常被 execute 的 except 捕获后降级为按向量分排序，看似安全，但若返回分数多于候选数则多余分数被静默丢弃，且 rerank_applied 仍为 True，结果与标注不符。更关键的是，若 rerank_scores 为 None 或非序列，异常同样被吞掉，掩盖了 Reranker 契约违约。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:130-145 向量召回成功但结果为空时不回退关键词召回（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:130-145`
  - 依据：当 embedder 与 vector_index 均存在且 _vector_recall 未抛异常但返回空列表时，recall_strategy 被置为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支——该分支确实会调用 _keyword_recall。但注意：若向量召回返回非空，rerank 抛异常时 scored 保持向量结果，逻辑正常；真正的问题在于向量召回返回空时虽然会走关键词召回，但 recall_strategy 在关键词召回后仍被覆盖为 'keyword_2gram'，这本身没问题。重新审视：`elif not scored` 分支确实覆盖了空结果场景，因此该路径实际是安全的。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:168-175 分数并列时按 product_id 兜底排序的注释与实现不符，排序不稳定（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:168-175`
  - 依据：注释明确说明“分数相同时按 product_id 兜底排序”，理由是向量检索在分数并列时返回顺序由后端决定，不固定会导致同一 query 结果不稳定、评测指标不可复现。但实际代码 filtered.sort(key=lambda item: -item[0]) 只按分数排序，Python 的 sort 是稳定排序，并列项会保留 scored 中的原始顺序（即向量后端返回顺序），完全没有 product_id 兜底。因此注释承诺的确定性并未实现，同一 query 在不同次运行仍可能给出不同 top_k 结果。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:236-244 关键词召回无匹配时返回 0.0 分候选，无关商品进入结果（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:236-244`
  - 依据：_keyword_score 在 `matched` 为空时返回 0.0，而 _keyword_recall 的过滤条件是 `if score >= 0`，因此所有与查询毫无交集的商品都会以 0.0 分进入候选列表。随后 execute 只按分数排序并截断 top_k，导致完全无关的商品被当作召回结果返回给模型，模型可能据此给出误导性推荐。注释声称“关键词降级召回”，但实际行为是“全量返回”。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:78-88 tokenize 对 CJK chunk 生成 2-gram 但保留整词，短 chunk 与长 chunk 权重失衡（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:78-88`
  - 依据：tokenize 对每个 chunk 既加入整词又加入所有 2-gram，长中文 chunk 会产生大量 2-gram，使 _keyword_score 的 len(matched) 被长文本主导。但这是关键词降级召回的启发式设计，且 _keyword_score 对品类命中额外加权，未构成明确错误行为；记录为 not_a_defect。
- **[concurrency/medium]** [concurrency] app/application/usecases/order_usecases.py:96-104 PlaceOrderUseCase 幂等键冲突分支回滚后仍可能返回赢家订单，但自身订单已保存造成重复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:96-104`
  - 依据：_replay 在键已登记但订单尚未写入（record 成功、save 之前崩溃）时返回 None，调用方继续新建订单。但 record 是在 save 之后调用的，因此正常路径下不会出现“键已登记但订单不存在”。真正的问题是：_replay 返回 None 时（find 返回空 order_id 或 find_by_id 返回 None），代码会继续走完整下单流程，而幂等键可能已被另一路占用，最终在 record 处失败并回滚库存——但此时已 save 的订单未撤销（见上一条）。此外 _replay 中 order 为 None 时静默返回 None，掩盖了“键已登记但订单丢失”的不一致状态。
- **[error_handling/low]** [error_handling] app/application/usecases/order_usecases.py:148-154 QueryOrderUseCase 对空 buyer_id 抛 OrderAccessDenied 而非参数错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:148-154`
  - 依据：`if not buyer_id or order.buyer_id != buyer_id` 对空 buyer_id 抛 `OrderAccessDenied`，映射为 404。这是有意的安全设计（不泄露订单存在性），与类文档一致。不构成缺陷。
- **[error_handling/high]** [error_handling] app/application/usecases/order_usecases.py:178-184 取消订单先回补库存再保存，保存失败导致库存重复回补（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:178-184`
  - 依据：`order.cancel(reason)` 修改内存状态后，先 `release` 库存，再 `save`。若 `save` 抛异常，库存已回补但订单状态未持久化（仍为未取消）。调用方重试取消时，`order.cancel` 会再次通过状态机（因为持久化状态仍是未取消），再次 `release`，造成库存重复回补。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:118-126 PlaceOrderUseCase 幂等键冲突回滚时未删除已保存的订单，留下孤儿订单（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-126`
  - 依据：在 idempotency_key 分支中，代码先 await self._order_repo.save(order) 把订单持久化，然后才调用 self._idempotency.record(...)。当 record 返回 False（并发下另一路先登记了同一个键）时，代码只回滚库存（_rollback(reserved)）并返回赢家的结果，却没有删除/作废自己刚保存的订单。结果是：库存被释放，但订单仍然存在于 order_repo 中，形成一张库存未扣减的孤儿订单；若后续对该订单执行取消，还会再次 release 库存，造成库存虚增。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:49-50 convert 使用 round() 的银行家舍入，跨币种换算结果与业务预期（四舍五入）不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:49-50`
  - 依据：Python 内置 round() 对 .5 采用银行家舍入（round-half-to-even），而金额换算通常期望四舍五入（half-up）。例如 0.5 分会被舍入为 0，1.5 分舍入为 2，2.5 分舍入为 2。在最小单位（分）口径下，这会造成换算金额系统性偏差，且对同一金额的不同换算方向可能不对称（A→B 与 B→A 往返后金额漂移）。
- **[logic/medium]** [logic] app/domain/catalog/exchange_rate.py:44-50 ExchangeRateTable.convert 未校验源币种是否在 SUPPORTED_CURRENCIES，且 rate() 与 SUPPORTED_CURRENCIES 校验口径不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:44-50`
  - 依据：convert 只校验目标币种 to_currency 是否在 SUPPORTED_CURRENCIES 中，源币种 money.currency 仅由 rate() 检查是否在 rates_to_cny 中。若 Money 允许构造出不在 SUPPORTED_CURRENCIES 但恰好在 _RATES_TO_CNY 中的币种（或反之），两条校验路径会给出不一致的结果：rate() 通过而 convert 的语义边界被绕过。更关键的是，rate() 的校验集合是 rates_to_cny（可被注入替换），而 convert 的校验集合是模块级 SUPPORTED_CURRENCIES，二者可能不同步——例如注入一个只含部分币种的 rates_to_cny 时，convert 对目标币种的校验会通过 SUPPORTED_CURRENCIES 却在 rate() 中抛 ValueError，错误信息指向'汇率表不支持'而非'不受支持'，调用方难以区分。
- **[logic/high]** [logic] app/domain/catalog/money.py:33-36 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的最小单位就是 1 日元（无小数位）。from_major_units 对所有币种统一 round(major*100)，于是 from_major_units(1000, 'JPY') 得到 100000 minor units，即 1000 日元被当成 100000 日元。to_major_units 与 __str__ 同样固定除以 100，导致 JPY 金额展示与结算都放大 100 倍。注释承认是简化，但这是跨境价格核心不变量，属于真实金额错误而非风格问题。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/product_repository.py:17-25 ProductRepository 抽象方法使用 list[str] 但未从 typing 导入，Python<3.9 下运行期报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/product_repository.py:17-25`
  - 依据：文件有 from __future__ import annotations，注解在运行期不求值，list[str] 不会在定义时求值；且项目若运行在 3.9+ 则内置泛型本就可用。因此不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:20-24 retrieval_ports 抽象方法使用 ... 而非 raise NotImplementedError，子类漏实现时静默返回 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:20-24`
  - 依据：ABC + @abstractmethod 已经保证未实现抽象方法的子类无法实例化，方法体用 ... 是合法的占位写法，不会导致静默返回 None 的运行时问题。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/stock_repository.py:30-33 StockRepository 端口缺少幂等/并发语义的运行时约束，仅靠文档约定（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:30-33`
  - 依据：reserve 的原子性只写在 docstring 里，ABC 无法强制实现方遵守。这是端口设计的常见做法，缺陷应落在具体实现而非端口定义。端口本身没有可执行逻辑，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/stock_repository.py:30-40 StockRepository 端口缺少对 quantity<=0 的契约约束，reserve/release 语义在非正数量下未定义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:30-40`
  - 依据：这是抽象端口（ABC），方法体为空，quantity 的合法性校验属于实现方职责。端口文档已明确 reserve 的原子性与库存不足返回 False 的语义，未对 quantity<=0 作约定属于契约留白而非实现缺陷；在端口层无法引用具体错误代码。
- **[logic/medium]** [logic] app/domain/catalog/product.py:38-39 Product.primary_sku 返回 skus[-1]（最后一个）而非主 SKU（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:38-39`
  - 依据：方法名为 primary_sku，语义上应返回主推 SKU（通常是第一个或显式标记的），实现却取 skus[-1]。若 skus 顺序按录入顺序排列，主 SKU 在首位时该方法返回的是最后一个（可能是配件/最便宜变体），下游展示与下单会选错 SKU。这是可复现的语义错误。
- **[logic/low]** [logic] app/domain/catalog/sku.py:24-31 Sku.stock 校验非负但未校验 price 币种/金额，且 stock 为可变字段可被外部改写（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:24-31`
  - 依据：Sku 是 @dataclass（非 frozen），stock 字段可被外部赋值绕过 __post_init__ 校验，但文档明确说明 stock 是只读参考数据、扣减必须走 StockRepository，且 __post_init__ 已校验初始值非负。这是设计取舍而非缺陷；记录以澄清。
- **[boundary/low]** [boundary] app/infrastructure/budget.py:66-72 charge 允许负 token 与超支，remaining_ratio 在 total_limit<=0 时恒为 1.0 掩盖超支（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:66-72`
  - 依据：charge 只对 tokens == 0 提前返回，负值会被累加使 used 减少（相当于返还预算），且没有上限校验。remaining_ratio 在 total_limit<=0 时直接返回 1.0，即使 used 已远超 total_limit 也不会进入 fallback 档。当 total_limit 为正但 used 超过 total_limit 时，remaining 为负，ratio 为负，tier 落到 fallback，这是正确的；但 total_limit<=0 的分支会让“0 预算”永远 main，与 init_budget 的 0 处理叠加后，预算护栏在默认配置下完全失效。
- **[logic/high]** [logic] app/infrastructure/budget.py:88-94 init_budget 对 total_limit=0 仍创建预算实例，与“0=不启用”语义冲突（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/budget.py:88-94`
  - 依据：模块文档与 settings 都声明 TOKEN_BUDGET_TOTAL=0 表示不启用预算（默认值即 0）。但 init_budget 只在 total_limit < 0 时返回 None，total_limit == 0 时会创建一个 total_limit=0 的 TokenBudget 并写入 ContextVar。此后 current_tier() 返回该预算的 tier：remaining_ratio 在 total_limit<=0 时返回 1.0，于是 tier 恒为 main，看似无害；但一旦发生任何 charge（tokens>0），used>0，remaining 变负，remaining_ratio 仍因 total_limit<=0 返回 1.0，tier 仍为 main——预算完全不生效，却让 get_budget() 返回非 None，使所有依赖“budget is not None 即启用”的调用方误判预算已开启（例如注入 minimal hint、发布预算事件、按预算分支选模型）。这是默认配置下就会触发的语义错误。
- **[error_handling/low]** [error_handling] app/infrastructure/context.py:40-42 ShoppingContext.reset 未校验 token 来源，跨上下文 reset 会抛 ValueError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/context.py:40-42`
  - 依据：ContextVar.reset 在 token 不属于当前上下文时会抛 ValueError，这是标准行为。ShoppingContext.reset 直接透传，调用方需保证 set/reset 配对。属于正常 API 契约，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/eventbus.py:158-168 replay 返回的事件列表未按 seq 排序保证，且 buffer 被淘汰时返回空列表但 last_seq 仍返回旧值，客户端可能误判（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:158-168`
  - 依据：replay 中 buffer 是 deque，append 顺序即 seq 递增顺序，列表推导保持顺序，返回的列表天然按 seq 升序。buffer 被淘汰时 _history.get 返回 None，replay 返回 []，而 last_seq 从 _seq 取——但 _remember 淘汰时会 `self._seq.pop(evicted, None)`，所以被淘汰会话的 last_seq 返回 0，与 replay 返回 [] 一致，客户端可据此判断缺口。设计自洽，不是缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/eventbus.py:148-156 deliver_local 中 queue.put_nowait 在队列满时抛 QueueFull，会中断后续订阅者投递（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:148-156`
  - 依据：deliver_local 遍历订阅者队列并 `queue.put_nowait(sequenced)`。asyncio.Queue 默认 maxsize=0（无界），但 subscribe 创建的是 `asyncio.Queue()` 无界队列，put_nowait 不会抛 QueueFull。然而若未来 subscribe 改为有界队列，或调用方传入有界队列，put_nowait 会抛 QueueFull 并中断循环，导致后续订阅者收不到事件。当前代码 subscribe 用无界队列，所以实际不会触发——但这是脆弱点。更现实的问题：若某个订阅者队列的消费者已停止（WS 断开但未 unsubscribe），无界队列会无限增长导致内存泄漏，且 put_nowait 永不失败，问题被掩盖。
- **[logic/low]** [logic] app/infrastructure/eventbus.py:192-201 publish 中 _broadcast 的 create_task 在无运行循环时被吞掉但本地投递已完成（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:192-201`
  - 依据：_broadcast 捕获 RuntimeError 并跳过广播，注释说明同步测试场景下本地投递已完成。这是有意的降级设计，不构成缺陷。
- **[resource_leak/medium]** [resource_leak] app/infrastructure/eventbus.py:178-190 eventbus._remember 淘汰会话时未清理 _subscribers，且淘汰仅在新建 buffer 分支触发（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/eventbus.py:178-190`
  - 依据：_remember 在 buffer 为 None 时执行淘汰：`self._history.popitem(last=False)` 并 `self._seq.pop(evicted, None)`，但没有清理 `self._subscribers[evicted]`。若被淘汰会话仍有订阅者（例如 WS 连接未正常 unsubscribe），其队列会永久留在 _subscribers 中，造成内存泄漏。此外淘汰逻辑只在新会话首次写入时触发，已存在会话持续写入不会触发淘汰，MAX_TRACKED_SESSIONS 上限对活跃会话集合不生效。
- **[concurrency/high]** [concurrency] app/infrastructure/llm.py:168-186 _call_with_fallback 捕获 BaseException 重试，吞掉 CancelledError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:168-186`
  - 依据：`except BaseException as err` 会捕获 `asyncio.CancelledError`。若 `is_transient_error(err)` 对取消异常返回 True（例如取消消息中含 'timeout' 等标记），则进入重试循环并 `await asyncio.sleep(delay)`，取消无法传播，任务无法及时终止。即便 `is_transient_error` 返回 False 而 `raise`，也应在捕获 CancelledError 时立即重新抛出，而不是依赖字符串匹配。
- **[error_handling/low]** [error_handling] app/infrastructure/llm.py:218-236 _charge_budget 中 total 为 None 时 int(total) 抛 TypeError 被 except 捕获，但若 total 为字符串数字则 int 成功而 budget.charge 可能因类型不符出错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:218-236`
  - 依据：_charge_budget 整体被 try/except Exception 包裹，任何异常都被记录 debug 日志并跳过，不影响主链路。total 为 None 时 `int(total)` 抛 TypeError 被捕获；total 为字符串数字时 int 成功；total 为负数时 budget.charge 内部行为取决于 budget.py（其他审查者已指出 budget.py 允许负 token 的缺陷，但那是 budget.py 的问题，不是此处）。此处代码的容错设计是正确的，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/llm.py:76-90 ThrottledChatModel.__call__ 中 slot.__aenter__ 抛异常时未处理，且非流式分支 _charge_budget 在 __aexit__ 之后调用，若 _charge_budget 抛异常则异常传播但名额已释放（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:76-90`
  - 依据：__call__ 中 `await slot.__aenter__()` 若抛异常，此时尚未进入 try 块，异常直接传播，slot 未获取，无需释放——正确。非流式分支 `await slot.__aexit__(None, None, None)` 先释放名额，再 `_charge_budget(result)`，_charge_budget 内部有 try/except 不会抛异常，即使抛也是名额已释放，不会泄漏。设计正确。
- **[error_handling/high]** [error_handling] app/infrastructure/llm.py:96-106 finally 中先记账后释放名额，记账异常导致名额永不释放（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:96-106`
  - 依据：`_release_after_stream` 的 finally 块中先调用 `_charge_budget(last)`，再 `await slot.__aexit__`。虽然 `_charge_budget` 内部有 try/except 包裹，但 `_safe_field` 与 `int(total)` 之外的路径（如 `budget.charge` 抛 BaseException 子类、或 `_charge_budget` 本身被替换/异常）仍可能中断 finally，使 `slot.__aexit__` 不执行，信号量名额泄漏。更关键的是顺序问题：释放资源应放在记账之前或独立 try 中，当前顺序把非关键路径（记账）放在关键路径（释放名额）之前。
- **[logic/medium]** [logic] app/infrastructure/llm.py:246-268 create_chat_model 中 fallback 与主模型共用 credential 且未传 throttle/bus（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:246-268`
  - 依据：`common` 字典包含 `credential`，fallback 与主模型共用同一 `OpenAICredential` 实例。若 credential 内部持有可变状态（如 token 刷新、连接池），共享实例可能导致并发问题。更明确的是 fallback 是裸 `OpenAIChatModel`，没有 throttle，`_call_with_fallback` 与 `_invoke_upstream` 中的回退调用都不经过配额闸门，与模块文档“限流回退”的意图不符。
- **[resource_leak/high]** [resource_leak] app/infrastructure/llm.py:140-152 预算降级分支直接调用 fallback 模型，绕过闸门与流包装（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:140-152`
  - 依据：`_invoke_upstream` 在 tier != 'main' 时直接 `return await self._fallback(...)`。`self._fallback` 是普通 `OpenAIChatModel`，其流式返回的生成器不会被 `_release_after_stream` 包装，也不会经过 `_charge_budget`。同时该分支在 `__call__` 已获取 slot 之后执行，返回的流式生成器由 `__call__` 的 `hasattr(result, '__aiter__')` 分支包装——但包装的是 fallback 的流，slot 仍由主模型持有，语义上尚可；真正的问题是 fallback 调用本身不再经过 `_call_with_fallback` 的重试与 `_publish_fallback` 事件，且 fallback 模型没有 throttle，回退调用完全绕过配额闸门。
- **[resource_leak/high]** [resource_leak] app/infrastructure/llm.py:88-90 流式分支中 _release_after_stream 是 async generator，调用后未迭代即返回，闸门名额与记账都不会执行（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/llm.py:88-90`
  - 依据：ThrottledChatModel.__call__ 在流式分支执行 `return self._release_after_stream(slot, result)`。_release_after_stream 被声明为 `async def` 且函数体内含 `yield`，因此它是一个异步生成器函数：调用它只创建生成器对象，函数体（包括 try/finally 中的 `_charge_budget(last)` 与 `await slot.__aexit__(...)`）在首次迭代前不会执行。__call__ 返回的是这个生成器对象，调用方（AgentScope 框架）会 `async for` 迭代它，此时 finally 才会执行——但关键在于：如果调用方拿到返回值后没有迭代（例如异常路径、或框架对返回值做了类型判断后丢弃），名额永不释放。更严重的是，`_release_after_stream` 的 finally 中 `await slot.__aexit__(None, None, None)` 只在生成器被关闭/耗尽时执行；若调用方提前 break 且未调用 `aclose()`，名额泄漏。此外 `_charge_budget(last)` 在流为空（last 为 None）时被调用，_charge_budget 内部对 response is None 有保护，这点安全。真正缺陷在于：__call__ 的返回类型标注为 `ChatResponse | AsyncGenerator`，但流式分支返回的是「未启动的生成器」，与 `_invoke_upstream` 中 `return await self._fallback(...)` 返回的可能是已启动的生成器语义不一致，且名额释放完全依赖调用方正确迭代/关闭。
- …另有 9 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/agents/permissions.py:40-52 allow_business_tools 的幂等判断只检查 source，会跳过用户自定义的 projectSettings 规则并阻止追加 ALLOW（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/agents/permissions.py:40-52`
  - 依据：幂等判断 `any(rule.source == "projectSettings" for rule in rules)` 只按 source 判断，不检查 behavior 或 rule_content。如果持久化状态里该工具已存在一条 source=projectSettings 但 behavior=DENY/ASK 的规则（例如用户或上层配置显式拒绝该工具），函数会直接 continue，不再追加 ALLOW 规则，导致业务写工具被意外拒绝或仍触发确认卡，与函数文档声明的“显式配置 allow 规则”目标相反。触发条件是恢复的持久化 permission_context 中已存在同 source 的非 ALLOW 规则。
  - 争议对手：a1b9a699a2d1
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:38-46 Money.add/multiply 直接构造实例绕过 of() 校验，可产生负金额（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 强制 amount 非负，但 add/multiply 用 Money(...) 直接构造，未走校验。虽然 add 的两个操作数若都来自 of() 则和必非负，但 dataclass 本身不校验，任何直接 Money(-1, 'USD') 或 Money(1.5, 'USD') 都能构造出违反不变量（非负整数）的实例，且 add/multiply 会继续传播这些非法值。不变量只在工厂方法上成立，值对象本身不成立，属于边界校验缺口。
  - 争议对手：69217fef01ae
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:27-30 ProductSearchSpec 未校验 top_k 为正，负值导致切片语义错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:27-30`
  - 依据：__post_init__ 只校验 normalized_query，注释写“top_k 由调用方保证为正”，但 dataclass 是公开值对象，调用方传入 top_k=0 或负数时不会报错。在 catalog_search 中 filtered[: spec.top_k] 对负数会变成“去掉末尾 N 个”，返回非预期数量的结果；top_k=0 返回空。缺少校验使错误输入静默产生错误行为。
  - 争议对手：c8c5675c09ee

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：7｜覆盖正常：23｜无法判定：0
- 单 Reader 检出率：68.6%（重捕对 3，已观测 52，估计总体 75.8
- 待补检分组：app, app/application/usecases, app/infrastructure, app/application/agents, app/domain/catalog, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 9.9% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 9.9% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 9.9% |
| `54e94c349368` | 2 | 0 | `reader_miss` | 9.9% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 9.9% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 9.9% |
| `f9c039a1b907` | 2 | 0 | `reader_miss` | 9.9% |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `app/application/usecases` | 2 | 1 | 2 | 2 | 0 | 0 | 1 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| `app/infrastructure` | 2 | 2 | 2 | 2 | 2 | 0 | 2 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
