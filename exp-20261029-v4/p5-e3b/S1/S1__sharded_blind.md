# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 13 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 49 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：87
- 独立性画像：有效通道 2.45 / 3，归一化 81.7%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：125 个节点 / 291 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 63 | 100% | 40% |

## 高置信结论

- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:196-205 rerank 分数与候选数量不匹配时索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-205`
  - 依据：_rerank 用 rerank_scores[i] 按 scored 的下标取值，未校验 rerank_scores 长度是否等于 scored 长度。若 Reranker 实现返回的分数条数少于候选数（例如服务端截断、部分失败），会抛 IndexError；该异常被外层 except 捕获后降级为按向量分排序，行为上尚可接受。但若返回条数多于候选数，多余分数被静默丢弃，不会报错——这属于静默数据丢失而非崩溃。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:108-122 向量召回成功但结果为空时不会走关键词兜底，直接返回空结果（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:108-122`
  - 依据：当 embedder 与 vector_index 均可用且 _vector_recall 正常返回空列表时，recall_strategy 被置为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支——该分支确实会调用 _keyword_recall。但注意：若 _vector_recall 抛异常，scored=[] 且 recall_strategy 仍为 'keyword_2gram'，此时 `elif not scored` 也会走关键词召回，逻辑正确。真正的问题在于：向量召回返回空（例如索引为空/过滤后无候选）时，代码会静默降级到关键词召回，但 recall_strategy 被覆盖为 'keyword_2gram'，丢失了'向量召回曾成功但无结果'的信息；更关键的是，若 _vector_recall 返回空是因为索引尚未建好，关键词兜底可能返回大量低质结果，而调用方无法区分。这属于可观测性/降级语义问题，但不会导致错误结果。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:196-202 取消订单时先回补库存再保存订单，保存失败会导致重复回补（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-202`
  - 依据：order.cancel(reason) 只修改内存中的聚合状态，随后立即 release 库存，最后才 save。若 save 抛异常（DB 故障等），订单在持久层仍是未取消状态，但库存已经回补；调用方重试取消时状态机不会拦截（因为持久层订单仍未取消），会再次 release，造成库存虚增。注释“重复取消会被状态机挡在上一步”只在 save 成功的前提下成立。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:133-145 幂等键冲突回滚时未撤销已保存的订单，留下无库存支撑的孤儿订单（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:133-145`
  - 依据：order 在 record 之前已经 await self._order_repo.save(order) 落库。当 record 返回 False（并发下另一路先登记同一键）时，代码只回滚库存，没有删除/作废刚保存的订单。该订单仍存在于 OrderRepository 中，但对应库存已被 release，形成“订单存在但库存未扣”的不一致状态；若后续按订单发货则超卖。
- **[logic/low]** [logic] app/domain/catalog/money.py:38-46 Money.add/multiply 绕过 of() 校验，可构造非法 Money（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 是唯一做不变量校验的入口，但 add/multiply 直接调用 Money(...) 构造器，绕过校验。虽然当前输入来自已校验的 Money 且 quantity 已校验非负，结果仍合法；但 dataclass 构造器本身公开，任何直接 Money(-1, 'USD') 都能绕过不变量。这削弱了「不变量」保证，属于封装缺陷。
- **[boundary/high]** [boundary] app/domain/order/order.py:47-53 Order.__post_init__ 只检查 lines is None，空列表可通过，导致 total_amount 索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：文档声明不变量为“至少一条订单行”，但实现只判断 self.lines is None，空列表 [] 能通过校验。随后 total_amount() 直接访问 self.lines[0]，snapshot() 也调用 total_amount()，因此空行订单在快照/金额计算时抛 IndexError，而不是在构造时给出明确 ValueError。
- **[logic/critical]** [logic] app/domain/order/order_line.py:27-28 OrderLine.subtotal 使用 quantity - 1 计算，少算一件（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:27-28`
  - 依据：subtotal 应为 unit_price * quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0，quantity=2 时只算 1 件，导致订单金额系统性少算一件，直接影响下单金额、到手价与关税计算。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:47-48 InMemoryOrderRepository.next_order_id 非原子，并发下单可能产生重复单号（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:47-48`
  - 依据：next_order_id 直接调用 next(self._counter) 并格式化返回，没有加锁，也没有与 save 原子绑定。itertools.count 的 __next__ 在 CPython 下受 GIL 保护，单次调用本身不会返回重复值；但调用方通常是“先取号、再 save”，两个协程在 await 点交错时，取号与落库不是原子的。更关键的是：如果调用方在取号后失败重试，或进程重启（_counter 重置为 1），已存在的 GBX-000001 会被再次生成，save 会静默覆盖旧订单（self._orders[order.order_id] = order），造成订单丢失。这与同文件 InMemoryOrderIdempotencyStore 显式加锁的做法不一致，说明作者意识到并发问题但漏掉了单号生成。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/json_file_stores.py:47-53 JsonFilePreferenceStore 的读-改-写非原子，并发 append 会丢偏好（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:47-53`
  - 依据：append 先 await list_by_buyer 读取全量，再在内存里追加，最后 _write 覆盖整个文件。两个协程并发 append 时，二者都读到同一份旧列表，后写者覆盖先写者，导致一条偏好静默丢失。await 点（list_by_buyer 内部有文件读）使交错成为可能。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/json_file_stores.py:66-72 delete 的读-改-写同样非原子，并发下会复活已删条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:66-72`
  - 依据：delete 与 append 共享同一份文件的全量覆盖写。若 delete 与 append 并发，append 基于旧快照写回，会把 delete 刚删掉的条目重新写回文件。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:168-190 JsonFileConversationStore.list_turns 取前 limit 条而非最近 limit 条（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:168-190`
  - 依据：JSONL 按追加顺序写入，list_turns 顺序遍历后返回 turns[:limit]，即返回最早的 limit 条对话，而不是最近的 limit 条。对于多轮对话恢复/上下文构建，通常需要最近 N 轮；返回最旧 N 轮会导致上下文错乱（模型看到的是会话开头而非最新进展）。这与数据库实现（通常 ORDER BY created_at DESC LIMIT n 再反转）语义不一致。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/migrations/env.py:44-55 _database_url 的异常兜底会吞掉配置错误并静默指向本地 SQLite（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/env.py:44-55`
  - 依据：try 块捕获 Exception 后无条件退化为本地 SQLite。如果 load_settings() 因 DATABASE_URL 配置错误（如拼写错误、连接串格式非法）而抛异常，迁移会静默地对本地 data/globex.db 执行，而不是报错。运维以为迁移了生产库，实际改的是本地文件，造成'迁移成功但线上库未变'的静默错配——这正是该文件 docstring 声称要解决的问题。捕获范围过宽（Exception）掩盖了真实配置错误。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:27-33 Alembic 基线迁移使用 create_all/drop_all，无法反映后续结构变更且 downgrade 会删全部表（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:27-33`
  - 依据：upgrade 用 Base.metadata.create_all 只建缺失表，不会修改已存在表；downgrade 用 drop_all 会删除所有表（包括非本迁移创建的表）。虽然文件注释解释了这是基线设计，但 downgrade 的 drop_all 在共享库上会误删其他 schema 的表，且 create_all 在已有部分表时不会补列，与 Alembic 版本管理语义冲突。

## 待验证（孤证）

> ⚠️ 本节共 **49** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:296-302 库存覆盖只更新已存在 SKU，缺失 SKU 静默保留初始库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-302`
  - 依据：_overlay_authoritative_stock 中 `if sku["sku_id"] in current` 才覆盖，缺失的 SKU 保留 Sku.stock 初始值。文档已说明这是'退化为初始库存展示'的降级行为，且 get_many 异常时整体 return 也保留初始值。属于有意的降级设计，不是缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:246-258 到手价计算使用 primary_sku 价格但未考虑 quantity 与多 SKU 订单（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:246-258`
  - 依据：_to_card 中 quote 固定 quantity=1 且只用 primary_sku 价格，这是检索场景下展示'单件到手价'的合理设计，文档也说明是'小计+运费+关税'的单件估算。不是缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:268-280 库存覆盖只对 get_many 返回的 sku 生效，未返回的 sku 保留初始库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:268-280`
  - 依据：get_many 的契约是“未登记的 SKU 返回 None”，但返回类型是 Mapping[str, int]，未登记的 sku 不会出现在映射中。代码用 `if sku["sku_id"] in current` 判断，未登记的 sku 保留 Sku.stock 初始值。这与 StockRepository 文档中“Sku.stock 保留为初始库存，仅用于库存服务不可用时的展示兜底”的约定一致，属于有意的降级行为，不是缺陷。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:213-222 关键词召回未按 top_k 截断前先全量排序，且未利用 spec 中的品类/价格做预过滤（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-222`
  - 依据：_keyword_recall 对 list_all() 全量商品逐个 tokenize 并计算交集，复杂度 O(N * 文档长度)。在商品量级不大时（当前实现为内存/JSON 存储）可接受；且 execute 后续会做硬约束过滤与 top_k 截断。这不是缺陷，只是性能特征。
- **[api_misuse/low]** [api_misuse] app/application/usecases/order_usecases.py:30-36 OrderAccessDenied 继承 ValueError，调用方按 ValueError 捕获会误判为参数错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:30-36`
  - 依据：OrderAccessDenied 继承 ValueError 是有意设计：文档说明对外一律映射为 404，避免 403 泄露订单存在性。调用方若用 except ValueError 统一捕获，会把访问拒绝与参数错误混为一谈，但这是调用方选择，不是本文件的缺陷。
- **[concurrency/high]** [concurrency] app/application/usecases/order_usecases.py:118-130 幂等键登记与订单保存非原子，record 失败时订单已落库但库存被回滚（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：execute 先 await self._order_repo.save(order) 落库，再调用 self._idempotency.record 抢占幂等键。若 record 返回 False（并发下另一路先登记了同一个键），代码执行 _rollback(reserved) 释放库存，但已经 save 的订单并没有被删除/取消。结果是：赢家订单正常，输家订单也存在于订单库中，且其库存已被释放——订单库出现两张同键订单，且输家订单的库存未扣减（超卖）。此外若 record 抛异常，同样会走 except 分支回滚库存，但订单已保存，留下无库存支撑的订单。
- **[concurrency/low]** [concurrency] app/application/usecases/order_usecases.py:88-110 PlaceOrder 先校验全部商品再扣减，但校验与扣减之间无锁，SKU 价格可能已变（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:88-110`
  - 依据：resolved 中保存的是校验时刻的 sku.price 快照，后续 Order.place 使用该快照计算金额。商品目录是只读参考数据（seed 重建），价格在进程生命周期内不变，因此不存在校验与扣减之间价格漂移的问题。库存扣减本身走 reserve 原子操作，不依赖此处的读。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:36-49 ExchangeRateTable.rate 未校验 from/to 是否在 SUPPORTED_CURRENCIES，convert 只校验目标币种（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:36-49`
  - 依据：rate() 会检查两个币种都在 rates_to_cny 中，不在则抛 ValueError；convert() 额外检查 to_currency 在 SUPPORTED_CURRENCIES 中。若 money.currency 不在 rates_to_cny 中，rate() 会抛 ValueError，行为是安全的（显式失败而非静默错误）。虽然错误信息措辞不同，但不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:45-46 ExchangeRateTable.convert 使用 round 对浮点汇率取整，存在银行家舍入与浮点误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:45-46`
  - 依据：round 对 .5 采用银行家舍入，且浮点乘法可能产生 0.4999999 之类的误差，理论上会让个别金额少 1 分。但这是 MVP 静态汇率表的既定口径，注释已说明“换算后再取整”，且没有明确的业务舍入规则要求。属于精度取舍而非可确认缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/exchange_rate.py:40-46 ExchangeRateTable.convert 未校验源币种是否在 SUPPORTED_CURRENCIES，且 rate 对未知币种报错信息不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:40-46`
  - 依据：convert 只校验目标币种，源币种由 rate() 校验：若 money.currency 不在 rates_to_cny 中会抛 ValueError。Money 构造时已保证 currency 在 SUPPORTED_CURRENCIES 内，而 _RATES_TO_CNY 覆盖了全部支持币种，因此实际不会出现未校验路径。属于防御性差异，不构成缺陷。
- **[logic/medium]** [logic] app/domain/catalog/exchange_rate.py:47-49 ExchangeRateTable.convert 用 round() 做银行家舍入，金额换算结果与常规四舍五入不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:47-49`
  - 依据：Python 内置 round() 对 .5 采用 banker's rounding（向偶数舍入），而金额换算通常期望四舍五入（half-up）。例如 0.5 分会被舍成 0，1.5 分舍成 2，2.5 分舍成 2。当 money.amount_in_minor_units * rate 恰好落在 .5 上时，换算结果会与业务预期差 1 分，且方向不一致（有时舍去、有时进位），造成对账偏差。此外 round() 返回 int（当无 ndigits 时），这里恰好符合 Money.of 的整数要求，但舍入语义仍是缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 Money.from_major_units 用浮点乘法后 int() 截断，产生精度误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：int(major * 100) 对浮点结果直接截断而非四舍五入。例如 19.99 * 100 = 1998.9999999999998，int() 得 1998 而非 1999，金额少 1 分。这是典型的浮点边界缺陷，且 Money 的设计初衷正是「避免浮点误差」。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:41-43 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:41-43`
  - 依据：这是抽象端口定义，仅声明契约，不包含实现逻辑。长度一致性应由具体 Infrastructure 实现或 UseCase 保证；在端口层加校验并非必需，且不会在此文件产生运行时错误。
- **[logic/low]** [logic] app/domain/catalog/product.py:20-36 Product 为可变 dataclass 且 skus 列表可被外部修改，破坏聚合不变量（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:20-36`
  - 依据：__post_init__ 保证构造时至少一个 Sku，但 skus 是可变 list，外部可 clear() 后使 primary_sku() 抛 IndexError。不过这是 Python 领域模型的常见取舍，且当前仓库内没有代码在构造后修改 skus；没有具体调用点能证明该不变量被破坏，因此不判定为确认缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:52-57 Product.searchable_text 对空 highlights 产生多余空格，但不影响检索正确性（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:52-57`
  - 依据：当 highlights 为空时 highlight_text 为空串，join 结果末尾会多一个空格；当某个 highlight 的 detail 为空时也会出现连续空格。这只是文本规范化问题，对分词/embedding 召回没有实质影响，不构成可复现的功能缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:30-34 ProductSearchSpec 未校验 price_max_major 非负（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:30-34`
  - 依据：price_max_major 为可选过滤条件，负值会导致检索无结果但不会产生错误行为或数据损坏，属于调用方输入问题，不构成必须报告的缺陷。
- **[logic/low]** [logic] app/domain/catalog/sku.py:24-33 Sku.stock 为初始库存只读，但 dataclass 非 frozen 可被外部改写（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:24-33`
  - 依据：文档明确 stock 是只读参考数据，但 dataclass 未 frozen，调用方仍可赋值 sku.stock = x。然而这只是约定而非强制，且真正扣减走 StockRepository，内存改写不会影响持久化库存，不构成数据完整性缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-25 Address.__post_init__ 未校验 state/postal_code/phone，one_line 可能输出空字段（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-25`
  - 依据：文档说明 country 用于关税/运费口径，MVP 仅存储与展示；state/postal_code/phone 未列为必填，one_line 输出空字段只是展示瑕疵，不违反声明的不变量。不构成缺陷。
- **[performance/low]** [performance] app/domain/order/order.py:88-92 Order.snapshot 重复调用 total_amount 两次，且未包含 confirmed_at（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-92`
  - 依据：total_amount 被调用两次是轻微冗余，但订单行数量小，不构成性能缺陷；缺少 confirmed_at 是快照字段选择问题，非错误行为。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:108-110 关税计算使用 round() 对浮点费率取整可能产生银行家舍入偏差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:108-110`
  - 依据：round(taxable_minor_cny * tariff_rate) 对分为单位取整，Python round 采用银行家舍入，在 .5 边界会向偶数舍入，可能少/多 1 分。但这是金额取整的常见可接受做法，且费率多为两位小数，触发 .5 的概率极低，不构成明确缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:92-94 运费按 CNY 计算后再折算，但 base_freight 用 round 可能引入分单位舍入误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:92-94`
  - 依据：round 到整数分单位是合理的货币舍入，误差不超过 1 分，不构成真实缺陷。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:100-108 免税额度判断基于折算后 CNY 小计，但 subtotal 可能已是目标币种导致重复折算（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-108`
  - 依据：quote 中 subtotal 参数按其自身 currency 折算到 CNY，ExchangeRateTable.convert 应处理同币种恒等；若 convert 对同币种直接返回则无问题。无法确认 convert 实现，故不报告。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:96-103 关税按 CNY 小计计算但免税额度与费率混用硬编码汇率，且未按目标币种口径校验（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-103`
  - 依据：免税额度以 CNY 分为单位，代码先把 subtotal 折算成 CNY 再比较，口径一致；_DE_MINIMIS_CNY_MINOR 中的硬编码汇率只是常量近似，不构成逻辑错误。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:33-34 InMemoryProductRepository.find_by_ids 静默丢弃不存在的 id，破坏调用方对“按序返回”的假设（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:33-34`
  - 依据：实现用列表推导过滤掉缺失 id，返回顺序与入参一致但长度可能小于入参。这是仓储层常见的“尽力而为”语义，本身不构成缺陷；只有当上层依赖 len(result)==len(ids) 做对齐（例如与打分列表 zip）时才会出错。当前文件内没有这样的调用，无法从给定代码证明存在错误行为，因此记为非缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:51-72 InMemoryOrderIdempotencyStore 跨进程无法拦截重复下单（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:51-72`
  - 依据：类注释已明确说明仅用于单进程开发态，跨进程需用 SqlOrderIdempotencyStore。这是有意的设计约束而非缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/in_memory_stock_repository.py:15-15 InMemoryStockRepository 未继承 StockRepository 端口（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:15-15`
  - 依据：StockRepository 是 ABC，实现类应继承它以在实例化时强制校验所有抽象方法已实现。此处 class InMemoryStockRepository: 未继承端口，签名漂移（如 seed 覆盖语义）不会被 ABC 捕获，也无法通过 isinstance 做依赖注入校验。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:59-63 seed 直接覆盖库存，不校验负值也不与已有预留协调（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:59-63`
  - 依据：seed 语义即“以 seed 为准对齐库存”，覆盖是预期行为；负值 seed 属于配置错误，且 reserve 对 current < quantity 会拒绝。不构成代码缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/in_memory_stock_repository.py:24-30 reserve 对未登记 SKU 返回 False 而非报错，可能掩盖播种缺失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:24-30`
  - 依据：端口约定 reserve 库存不足返回 False 且不改变状态。未登记 SKU 视为库存不足返回 False 是合理且安全的（不会超卖），调用方据此回滚。release 对未登记 SKU 补登记也符合注释意图。因此不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/persistence/json_file_stores.py:27-30 _safe_name 清洗后不同 ID 可能映射到同一文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:27-30`
  - 依据：清洗只保留字母数字与 -_，其余字符被丢弃。'a/b' 与 'ab'、'a.b' 与 'ab' 都会映射到同一文件名，导致不同 buyer/session 的数据互相覆盖或串读。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/json_file_stores.py:172-178 touch_session 的 exists 检查与追加非原子，可能写入重复 session 行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:172-178`
  - 依据：先检查 path.exists() 再追加，两个并发首轮请求都会看到文件不存在，各自追加一条 session 记录。find_session 只返回第一条，重复行虽不致命但会污染流水。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:108-109 JsonFileSessionStore.save 非原子写，进程崩溃可能留下截断的会话快照（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:108-109`
  - 依据：save 直接用 write_text 覆盖目标文件，非原子（未写临时文件再 rename）。若写入过程中进程崩溃或磁盘满，会留下部分写入的 JSON，下次 load 返回损坏字符串，AgentState 反序列化失败，会话无法恢复。对于'重启恢复多轮对话'的核心用途，这是可观测的失败模式。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:186-194 find_session 对损坏行未捕获 TypeError，且空文件返回伪造会话（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:186-194`
  - 依据：json.loads 对合法 JSON 标量（如 '123'、'null'）返回非 dict，随后 record.get 抛 AttributeError，未被 except ValueError 捕获，整个 find_session 崩溃。另外文件存在但无 session 行时返回 {'session_id': ...} 而非 None，与“未找到返回 None”的语义不符，调用方无法区分。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:205-216 JsonFileConversationStore.find_session 对损坏行未捕获异常，且返回结构包含 kind 字段（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:205-216`
  - 依据：find_session 对每行 json.loads 用 try/except ValueError 跳过损坏行，与 list_turns 一致，不会因单行损坏崩溃。返回 {'session_id': session_id, **record} 会把 kind 字段也带出，但这是文件形态的内部表示，调用方按需取字段，不构成明确缺陷。
- **[boundary/low]** [boundary] app/infrastructure/persistence/seed_products.py:175-196 _build_extra 未校验 product_id 唯一性，表中存在 P1049/P1050 与 P1051~P1060 编号跳跃但无重复（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:175-196`
  - 依据：检查 _EXTRA_SPECS 中所有 product_id：P1011~P1021、P1051~P1053、P1058~P1060、P1049、P1050、P1022~P1030、P1054、P1031~P1037、P1055~P1057、P1038~P1048。逐一核对无重复，且与 P1001~P1010 不冲突。编号跳跃不影响功能。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:105-107 P1026 描述含"锂电池空运限制"但 ships_to 仅 CN，与 P1004 等含锂电池商品可跨境配送不一致（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:105-107`
  - 依据：P1026 明确标注"含锂电池，仅国内配送"，ships_to 仅 CN，是自洽的数据设计，用于制造 ships_to 分布区分度。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:124-126 P1031 亮点值"灶变色"疑似错别字（应为"窑变"），影响展示与召回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:124-126`
  - 依据：P1031 的 SKU 规格写作"灶变色"，而描述中写的是"窑烧"，"灶变"应为"窑变"（陶瓷工艺术语）。这是可引用的具体数据错误，会展示给用户并影响基于规格的关键词召回。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:175-190 _build_extra 中 skus 列表推导变量名 suffix 与元组解包顺序一致，无缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:175-190`
  - 依据：元组解包 (suffix, spec, major, currency, stock) 与 _sku 参数顺序 (sku_id, spec, major, currency, stock) 一致，f"{pid}-{suffix}" 生成 SKU id 正确。无缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:44-46 P1011 起新增语料中 P1011 与 P1001 同为"旅行三件套"，但 P1011 价格 139 低于 P1001 189，可能影响价格排序评测（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:44-46`
  - 依据：价格差异是刻意设计的区分度来源，注释明确说明"价格与 ships_to 分布拉开"。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:96-98 P1023 SilentBuds 价格币种为 USD 但数值 189 与同类 CNY 商品混排，可能影响价格排序评测（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:96-98`
  - 依据：P1023 使用 USD 189，与 P1004（USD 219/229）、P1010（USD 149）一致地使用 USD，属于刻意设计的跨币种数据。Money 携带币种，排序逻辑若正确应按币种换算，种子数据本身不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/migrations/env.py:108-111 Alembic env.py 在模块导入时即执行迁移，且 asyncio.run 在已有事件循环中会失败（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/env.py:108-111`
  - 依据：env.py 末尾在模块级调用 run_migrations_online()，这是 Alembic 的标准约定（env.py 由 alembic 命令作为脚本执行，不是被 import）。asyncio.run 在 alembic CLI 的同步上下文中调用是安全的。若有人以编程方式在已有事件循环中 import 该模块才会出问题，但这不是预期用法。
- …另有 9 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:50-52 get_many 对未登记 SKU 返回 0 而非缺失，与 get 语义不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:50-52`
  - 依据：端口约定 get 对未登记 SKU 返回 None，get_many 返回 Mapping[str, int] 用于批量查询。实现用 self._stock.get(sku_id, 0)，把「未登记」和「库存为 0」混为一谈。调用方无法区分「该 SKU 不存在/未播种」与「确实售罄」，可能导致对未登记 SKU 展示为售罄，或在回滚逻辑中误判。
  - 争议对手：d0d1741d9d88

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.70% ≥ 0.00%
- 有效通道：2.45｜归一化 81.7%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：20｜无法判定：0
- 单 Reader 检出率：66.3%（重捕对 3，已观测 63，估计总体 95.0
- 待补检分组：app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/domain/catalog, app/domain/order

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `36316f1e43cb` | 2 | 0 | `reader_miss` | 11.3% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 11.3% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 11.3% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 11.3% |
| `7d3fc36631b9` | 2 | 0 | `reader_miss` | 11.3% |
| `87535cbc08cd` | 2 | 0 | `reader_miss` | 11.3% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 11.3% |
| `a760b2d04e87` | 2 | 0 | `reader_miss` | 11.3% |
| `a97afbf9a0c4` | 2 | 0 | `reader_miss` | 11.3% |
| `bbc63879339e` | 2 | 0 | `reader_miss` | 11.3% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app/application/usecases` | 2 | 2 | 2 | 2 | 0 | 0 | 1 | 1 |
| `app/domain/catalog` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 2 | 0 | 2 | 0 | 0 | 0 | 2 | 0 |
| `app/domain/shipping` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 2 |

矩阵填充率 48%（单元格值 = 独立 Agent 数）
