# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 44 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：48
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：85 个节点 / 136 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 46 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **44** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:196-205 _rerank 未校验 rerank_scores 长度，索引越界会抛 IndexError 并被静默降级（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-205`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标取值，但未校验 rerank_scores 的长度是否等于 scored 的长度。若 Reranker 实现返回的分数数量少于文档数（例如截断、过滤或实现 bug），会抛 IndexError；该异常被上层 `except Exception` 捕获后静默降级为按向量分排序，rerank_applied 保持 False。这掩盖了 Reranker 的真实缺陷，且部分商品被丢弃/错配分数时不会报错。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-130 向量召回成功但结果为空时，仍会走关键词召回，且 recall_strategy 被错误标注为 keyword_2gram（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-130`
  - 依据：当 embedder 与 vector_index 均可用、_vector_recall 正常返回空列表时，recall_strategy 被置为 'embedding_only'，但 scored 为空。随后 `if recall_strategy == 'embedding_only' and scored:` 为假，进入 `elif not scored:` 分支执行关键词召回并把 recall_strategy 覆盖为 'keyword_2gram'。这本身是合理的兜底，但问题在于：向量召回成功返回空（即向量库确实没有匹配）与向量召回异常降级，被混为一谈，recall_strategy 无法区分。更关键的是，若向量召回返回空但关键词召回也返回空，最终 recall_strategy 仍标为 keyword_2gram，掩盖了向量链路实际可用的事实，影响可观测性与评测归因。
- **[concurrency/high]** [concurrency] app/application/usecases/order_usecases.py:118-130 幂等键登记与订单保存顺序导致并发下重复扣减/订单丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：execute 先 save(order) 再 record(idempotency_key)。若 record 返回 False（另一路并发先登记了同一键），代码回滚本次库存并返回赢家订单，但本次已 save 的订单并未删除，仓库中残留一张孤儿订单（库存已回补但订单存在）。此外 _replay 使用 f"{buyer_id}:{idempotency_key}" 作为键，而 record 直接使用 idempotency_key，两处键格式不一致：若 OrderIdempotencyStore 实现按原样存储，record 写入的是裸 key，_replay 查询的是 buyer:key，永远查不到，导致幂等完全失效（每次重投都新建订单并重复扣库存）。
- **[error_handling/low]** [error_handling] app/application/usecases/order_usecases.py:108-116 库存回滚 _rollback 自身异常会掩盖原始错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-116`
  - 依据：except 块中 await self._rollback(reserved) 若 release 抛异常，会替换掉原始异常（库存不足等），调用方看到的是回滚错误而非根因，且部分已扣减库存无法回补。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:196-201 取消订单先回补库存再保存，保存失败导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-201`
  - 依据：CancelOrderUseCase.execute 先对每行 release 库存，再 save(order)。若 save 抛异常（DB 故障等），订单状态仍是未取消，但库存已被回补；调用方重试取消会再次 release，库存被重复回补。注释声称“重复取消会被状态机挡在上一步”，但状态机只在内存对象上生效，未持久化的取消不会阻止重试。
- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:118-130 幂等键冲突回滚后未删除已保存订单，产生孤儿订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：在 record 返回 False 的分支里只回滚了库存（_rollback），没有删除第 118 行已 save 的 order。结果是库存被回补但订单仍留在 OrderRepository 中，形成一张库存未扣减的幽灵订单，后续可被查询/取消，取消时还会再次 release 库存，造成库存虚增。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/product_repository.py:18-20 ProductRepository.find_by_ids 未约定返回顺序，_vector_recall 依赖 by_id 映射而非顺序，安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/product_repository.py:18-20`
  - 依据：_vector_recall 用 `by_id = {product.product_id: product ...}` 再按 vector_hits 顺序重建，不依赖 find_by_ids 的返回顺序，因此端口未约定顺序不会导致错误。
- **[logic/low]** [logic] app/domain/catalog/ports/retrieval_ports.py:26-29 VectorHit 与端口定义本身无缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:26-29`
  - 依据：VectorHit 为 frozen dataclass，字段完整；抽象方法签名与文档一致，未发现可复现缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/stock_repository.py:30-38 StockRepository 端口未约束 quantity 正负，release 可被负值滥用（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/stock_repository.py:30-38`
  - 依据：端口只声明契约，quantity 的正负由调用方（PlaceOrderUseCase 已校验 quantity>0，CancelOrder 使用订单行数量）保证。端口层不校验属于设计选择，不构成可复现缺陷。
- **[error_handling/medium]** [error_handling] app/domain/catalog/product.py:47-52 Product.searchable_text 未包含 SKU 信息，且对 None 字段做 join 会抛 TypeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 用 " ".join([...]) 拼接 title/brand/category/origin_country/description/highlight_text。这些字段在 dataclass 中声明为 str 且无默认值，但 __post_init__ 只校验 product_id 和 skus，不校验这些字段非空/非 None。若调用方传入 None（例如从 JSON/DB 反序列化时缺失字段），join 会抛 TypeError: sequence item N: expected str instance, NoneType found，导致召回链路崩溃。此外 highlight_text 在 highlights 为空时是空字符串，join 会产生多余空格，但这只是格式问题。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:27-31 ProductSearchSpec 未校验 price_max_major 非负/有限（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:27-31`
  - 依据：__post_init__ 只校验 normalized_query 和 top_k，未校验 price_max_major。若传入负数或 NaN/inf，下游结构化过滤会得到空结果或异常行为（NaN 比较恒为 False，导致所有商品被过滤）。作为值对象，应在构造时拒绝非法价格约束。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-33 Sku.stock 为初始库存只读，但 dataclass 非 frozen 可被外部改写（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-33`
  - 依据：docstring 声明 stock 是只读参考数据，但 dataclass 未设 frozen=True，外部仍可 sku.stock = -1 绕过 __post_init__ 校验。不过这只是防御性问题，实际扣减走 StockRepository，不构成运行时缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-27 Address.__post_init__ 未校验 state/postal_code/phone，one_line 可能输出 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-27`
  - 依据：只校验 recipient_name/country/city/address_line 是有意为之（state/postal_code 在某些国家可空）。one_line 对 None 会输出 'None' 字符串，属于展示瑕疵而非数据错误，且 dataclass 类型标注为 str，正常调用方不会传 None。
- **[logic/high]** [logic] app/domain/order/order.py:47-53 Order.__post_init__ 允许空订单行列表，违反“至少一条订单行”不变量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：文档声明不变量为“至少一条订单行”，但校验只判断 self.lines is None，空列表 [] 能通过。随后 total_amount() 访问 self.lines[0] 会抛 IndexError，snapshot() 也会调用 total_amount()，导致空订单在创建时不被拒绝、在读取金额时崩溃。
- **[performance/low]** [performance] app/domain/order/order.py:88-90 Order.snapshot 重复调用 total_amount 两次，且未包含 confirmed_at/cancelled_at（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-90`
  - 依据：total_amount 被调用两次只是常数级重复计算，不构成真实缺陷；缺少时间字段属于快照内容设计选择，未违反文档声明的不变量。
- **[logic/critical]** [logic] app/domain/order/order_line.py:27-28 OrderLine.subtotal 使用 quantity-1 计算，少算一件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:27-28`
  - 依据：subtotal 应为 unit_price * quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0，quantity=2 时只算 1 件，导致订单金额系统性少算一件商品。该值会经 Order.total_amount() 写入 OrderRow.total_amount_minor，直接影响下单金额与支付金额。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:112-114 运费按 CNY 计算后折算，但 base_freight 使用 round 可能引入分币误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:112-114`
  - 依据：freight_minor_cny = round(base * (1 + 0.4*(q-1)))，base 为整数分，0.4 倍可能产生小数分，round 到整数分是合理的最小货币单位处理，误差不超过 1 分，属于可接受的舍入。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:118-124 关税按 CNY 小计计算但免税额度与费率口径混用，且免税判定忽略运费（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:118-124`
  - 依据：文档明确说明关税 = 商品小计超出免税额度部分 × 费率，代码实现与文档一致：taxable = max(0, subtotal_cny - de_minimis)，de_minimis_applied = taxable == 0。虽然真实海关口径可能含运费，但这是文档声明的简化规则，不构成实现缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:66-76 InMemoryOrderIdempotencyStore 的 find/record 非原子，存在检查-写入竞态（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:66-76`
  - 依据：find 和 record 各自加锁，但调用方典型模式是 `existing = await store.find(key); if existing: return existing; ... await store.record(key, order_id)`。两个协程可以同时 find 到 None，然后都调用 record；record 内部虽然用锁保证只有一个返回 True，但另一个返回 False 后调用方若未处理 False（例如直接继续创建订单），就会产生重复下单。锁只保护单次操作，不保护“检查后写入”这一复合操作。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:31-32 InMemoryProductRepository.find_by_ids 静默丢弃不存在的 id，调用方无法区分缺失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:31-32`
  - 依据：find_by_ids 用列表推导过滤掉不存在的 pid，返回顺序与输入一致但长度可能小于输入。这是仓储接口常见的“批量查询返回存在的实体”语义，调用方若需要检测缺失应自行比对。没有证据表明接口契约要求返回等长列表或抛错，因此不认定为缺陷。
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:40-47 InMemoryStockRepository.release 对未登记 SKU 补登记，可能凭空创造库存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:40-47`
  - 依据：release 在 SKU 未登记时直接把库存设为 quantity，注释称“补登记而不是静默丢弃”。但 release 的语义是回补已扣减的库存；若对从未 reserve 过的 SKU 调用 release（例如重复取消、错误 SKU、或 reserve 失败后仍执行 release），会凭空创造库存。正确做法应是拒绝或记录告警，而非无条件补登记。
- **[boundary/low]** [boundary] app/infrastructure/persistence/json_file_stores.py:27-30 _safe_name 清洗后不同 ID 可能映射到同一文件名，造成数据串号（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:27-30`
  - 依据：_safe_name 丢弃所有非字母数字/-_ 字符，因此 "a/b"、"a.b"、"a b" 都映射为 "ab"，"user@x" 与 "userx" 也相同。不同 buyer_id/session_id 会共享同一文件，偏好与对话互相污染。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/json_file_stores.py:55-61 append 的读-改-写非原子，并发追加会丢失偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:55-61`
  - 依据：append 先 await list_by_buyer 读取，再在内存中追加并整体覆盖写回。两个协程并发 append 同一 buyer 时，后写者基于旧快照覆盖，先写者的条目丢失；去重判断也基于旧快照，可能写入重复条目。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:186-195 list_turns 中 record["role"] 对缺失字段抛 KeyError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:186-195`
  - 依据：其余字段都用 record.get 带默认值，唯独 role 用下标访问。若某行 turn 记录缺少 role（旧版本写入、手工编辑或部分写入），list_turns 直接抛 KeyError，整个会话历史读取失败，而不是跳过该行。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:213-221 find_session 对损坏行未捕获 TypeError，且返回的 dict 混入 kind 字段（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:213-221`
  - 依据：list_turns 中同样解析 JSONL 时只捕获 ValueError，但 json.loads 对合法 JSON 的非 dict 值（如数字、字符串、null）会返回非 dict，随后 record.get(...) 抛 AttributeError；find_session 中 record.get("kind") 同理。此外 find_session 返回 {"session_id": session_id, **record}，把内部字段 kind 也暴露给调用方，与端口返回结构不一致。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:88-94 偏好写入非原子，进程崩溃可能留下截断的 JSON 文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:88-94`
  - 依据：_write 直接对目标文件 write_text，非原子。写入过程中进程崩溃/断电会留下半截 JSON，下次 list_by_buyer 解析失败后按空处理，用户全部偏好被静默清空（且随后 append 会以空列表覆盖写回，数据永久丢失）。应写临时文件再 os.replace。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:196-197 list_turns 用 turns[:limit] 截断，返回最早的 N 条而非最近的 N 条（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:196-197`
  - 依据：JSONL 按追加顺序写入，文件头部是最早的对话。list_turns 顺序读取全部行后执行 turns[:limit]，得到的是最早的 limit 条，而不是最近的 limit 条。当会话轮数超过 limit（默认 50）时，返回给调用方的上下文会停留在会话开头，最新的对话被丢弃，多轮对话上下文错乱。正确做法应是 turns[-limit:]（或先反转）。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:203-210 touch_session 以文件存在性判断会话是否已登记，首条 turn 先写入会导致 session 元信息永久缺失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:203-210`
  - 依据：touch_session 仅当 path 不存在时才写 session 记录。但 append_turn/append_events 也会创建同一文件。若调用顺序是先 append_turn 再 touch_session（或并发下 append 先落盘），文件已存在，session 元信息永远不会写入，find_session 只能返回仅含 session_id 的兜底 dict，buyer_id/locale/currency 丢失。
- **[boundary/low]** [boundary] app/infrastructure/persistence/seed_products.py:196-214 _build_extra 未校验 SKU 后缀唯一性，重复后缀会生成重复 sku_id（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:196-214`
  - 依据：当前 _EXTRA_SPECS 中每个 SPU 的 SKU 后缀均唯一（多为 S1），且 sku_id 由 pid 前缀保证全局唯一，不存在重复。属于潜在风险但当前数据安全。
- **[boundary/low]** [boundary] app/infrastructure/persistence/seed_products.py:88-90 P1023 SilentBuds 价格币种为 USD 但数值 189 与同类 CNY 商品混排，可能造成价格排序/筛选异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:88-90`
  - 依据：种子数据中 P1004、P1010 也使用 USD，属于既有设计（跨境商品多币种）。Money 类型携带币种，价格比较应由上层换算处理，种子数据本身不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:100-102 P1026 描述含“锂电池空运限制”但 ships_to 仅 CN，与描述一致，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:100-102`
  - 依据：描述中“锂电池空运限制”与 ships_to 仅 CN 一致，属于有意的数据设计，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:128-130 P1033 亮点值“天然楱竹”疑似错别字（应为“楠竹”），影响关键词召回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:128-130`
  - 依据：亮点值写成“天然楱竹”，而描述写“竹制餐具”。若用户 query 含“楠竹”或“天然竹”，亮点字段无法命中；同时“楱”是错字，会污染 searchable_text 的召回语料。这是数据内容错误，会直接影响关键词召回评测结果。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:148-150 P1041 描述含“结实抗造”，与注释声称新增语料避开“抗造”相矛盾（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:148-150`
  - 依据：注释只承诺避开与 P1001 在“旅行三件套 抗造”这条 query 上正面相撞，P1041 是露营凳，不含“旅行三件套”，因此不违反承诺。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:36-38 P1011 竞品描述含“轻便”但注释声称避开与 P1001 的 query 相撞，实际 P1011 与 P1001 在“旅行三件套”上仍高度重叠（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:36-38`
  - 依据：注释说明新增语料刻意避开与 P1001 在“旅行三件套 抗造”query 上正面相撞，P1011 确实不含“抗造”，因此不会推翻 top-1 断言。虽然 P1011 与 P1001 在“旅行三件套”上重叠，但这是有意为之的区分度设计，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:52-54 P1016 描述含“塑料箱体”，与“不要塑料”类 query 的负向意图冲突，但属于有意设计的易混淆项（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:52-54`
  - 依据：注释明确说明要造出“含易混淆项”，P1016 含“塑料”正是负向样本，用于测试召回区分度，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:78-80 P1050 与 P1015 同为铝镁合金箱，价格 2999 vs 1199，可能影响“结实抗摔”query 排序（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:78-80`
  - 依据：P1050 是 26 寸全铝、P1015 是 24 寸铝框，属于有意的价位梯度设计，用于制造排序区分度，不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/migrations/env.py:108-111 env.py 在模块导入时执行迁移，且 asyncio.run 在已有事件循环中会失败（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/env.py:108-111`
  - 依据：这是 Alembic env.py 的标准写法：模块顶层根据 offline/online 分派执行，由 alembic CLI 以脚本方式运行，不存在已有事件循环。asyncio.run 在此上下文中安全。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/migrations/env.py:47-57 _database_url 捕获所有异常后静默回退到本地 SQLite，可能对错误库执行迁移（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/env.py:47-57`
  - 依据：except Exception 吞掉了 load_settings 的所有错误（不仅是缺 LLM_API_KEY，还包括配置语法错误、DATABASE_URL 格式错误等）。此时会静默回退到本地 SQLite 并对其执行迁移，运维以为迁移了生产库，实际改的是本地文件，造成静默错配——这正是文件头注释想避免的问题。
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:30-31 基线迁移 downgrade 使用 drop_all，会删除所有表包括 alembic_version 之外的表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:30-31`
  - 依据：downgrade 调用 Base.metadata.drop_all(bind=op.get_bind())，会按 metadata 中登记的所有表执行 DROP。若数据库中存在不属于 Base.metadata 的表（例如 alembic_version 本身、或同库其他应用的表），drop_all 只删 metadata 内的表，通常不会误删外部表；但问题在于 drop_all 不处理外键依赖顺序之外的视图/序列，且与 upgrade 的 create_all 对称。更关键的是：基线迁移的 downgrade 语义应是“回到空库”，drop_all 确实做到了，但若后续迁移已添加列/表，回滚到 0001 时 alembic 会先执行后续迁移的 downgrade，再执行本 downgrade，此时 metadata 是当前代码的 metadata（可能已包含后续迁移新增的表），drop_all 会把这些表也删掉——这本身是期望行为。真正的问题是 create_all/drop_all 依赖运行时 models 而非迁移时快照，导致历史迁移不可重现：在代码演进后重放 0001 会建出未来版本的表结构。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:300-305 next_order_id 依赖 inserted_primary_key，部分驱动可能返回 None（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:300-305`
  - 依据：result.inserted_primary_key[0] 在 SQLAlchemy 中对某些后端（如未启用 RETURNING 的驱动、或 executemany 场景）可能为 None，此时 f"GBX-{None:06d}" 会抛 TypeError。虽然 sqlite+aiosqlite 通常可用，但模块 docstring 声称可换 MySQL/PostgreSQL 而仓储代码不需改，此处对 inserted_primary_key 的假设在换驱动时可能失效。
- …另有 4 条未列出

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:44-46 ExchangeRateTable 使用 float 汇率做金额换算，存在精度/舍入偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:44-46`
  - 依据：金额以最小单位整数表示，但换算经过 float 乘除再 round，二进制浮点误差在边界（如 .5 分）可能产生 1 分偏差；且 round 使用银行家舍入，与业务常见的四舍五入不一致。对金额计算属于可复现的精度缺陷。
  - 争议对手：12cf0f8c0af4
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-33 Money.from_major_units 用 int(major*100) 截断，浮点误差导致金额少 1 分（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：`int(major * 100)` 对浮点乘法结果直接截断而非四舍五入。经典例子：from_major_units(1.15, 'USD') 中 1.15*100 = 114.99999999999999，int 截断得 114，即 1.14 而非 1.15，少 1 分。金额类值对象出现系统性向下偏差，且该函数被用于把外部输入（如价格上限、SKU 价格）转成 Money。
  - 争议对手：624e06f60ba7

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：32｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/infrastructure/persistence, app/domain/catalog, app/domain/order, app/domain/shipping, app/application/usecases

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `001a0c61fa51` | 1 | 3 | `partition_gap` | — |
| `00e2b01edb94` | 1 | 1 | `partition_gap` | — |
| `1bd894600f10` | 1 | 1 | `partition_gap` | — |
| `36316f1e43cb` | 1 | 0 | `partition_gap` | — |
| `3f29e8d0f73c` | 1 | 2 | `partition_gap` | — |
| `4662743c2106` | 1 | 1 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `48cc2d0a9307` | 1 | 1 | `partition_gap` | — |
| `4ad98b411bb7` | 1 | 0 | `partition_gap` | — |
| `52e48d38e8e3` | 1 | 2 | `partition_gap` | — |
| …另有 22 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app/application/usecases` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| `app/domain/shipping` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 1 |

矩阵填充率 45%（单元格值 = 独立 Agent 数）
