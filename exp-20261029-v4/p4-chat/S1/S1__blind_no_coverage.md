# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 30 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：32
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：70 个节点 / 100 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 31 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-128 CatalogSearch 在向量召回成功但结果为空时错误降级为关键词召回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-128`
  - 依据：向量召回成功但返回空列表（库里确实没有匹配商品）时，`elif not scored` 分支会执行关键词召回，并把 recall_strategy 标为 keyword_2gram。这混淆了"向量服务正常但无结果"与"向量服务异常降级"两种情况，导致 recall_strategy 标注失真，且关键词召回可能返回与语义查询无关的结果。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:196-200 _to_rejected 与 _within_price_cap 使用 primary_sku 价格，但商品卡展示的 price_major 未换算币种（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-200`
  - 依据：商品卡 price_major 使用 primary.price.to_major_units() 并带 currency 字段，是原币种展示；过滤用目标币种换算，两者语义不同但都正确。landed_price 单独给出目标币种到手价。不构成缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:176-181 CancelOrder 先回补库存再 save，save 失败会导致库存已回补但订单仍为 CONFIRMED（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:176-181`
  - 依据：order.cancel(reason) 修改的是内存对象，随后先 release 库存、再 save。若 save 抛异常（DB 故障/乐观锁冲突），内存中的取消不会持久化，订单在库中仍是 CONFIRMED，但库存已经回补。之后买家再次取消会再次 release，造成库存超卖式虚增。缺少事务边界或补偿逻辑。
- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:116-126 幂等冲突回滚时未删除已保存的订单，留下孤儿订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:116-126`
  - 依据：流程是先 `await self._order_repo.save(order)`，再 record 幂等键。当 record 返回 False（并发下另一路先登记）时，代码只回滚库存，没有删除/作废刚 save 的订单。结果：库存已释放，但订单仍以 CONFIRMED 状态存在于仓储中，买家可通过 QueryOrder 看到一张实际未占库存的订单，且该订单可被取消并再次 release 库存（重复回补）。
- **[logic/low]** [logic] app/application/usecases/order_usecases.py:78-100 PlaceOrder 未校验收货地址国家与商品 ships_to 的一致性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:78-100`
  - 依据：检索链路用 ship_to 过滤，但下单链路没有校验 shipping_address.country 是否在 product.ships_to 中。不过从代码看，Order 聚合与 PlaceOrder 的职责说明中并未声明该不变量，且 Address.country 注释写明"MVP 仅存储与展示"，因此不构成已声明的缺陷，仅记录为潜在业务缺口。
- **[boundary/low]** [boundary] app/domain/catalog/exchange_rate.py:41-46 ExchangeRateTable.convert 用 round() 做银行家舍入，且对 JPY 口径不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:41-46`
  - 依据：round() 在 Python 3 中采用银行家舍入（round-half-to-even），例如 round(0.5)=0、round(2.5)=2，与业务上通常期望的四舍五入不一致，会在恰好 .5 分时少算 1 分。此外 convert 假定所有币种最小单位都是 1/100，与 Money.from_major_units 对 JPY 的 100 倍口径叠加后，JPY 换算结果会再放大 100 倍。
- **[error_handling/low]** [error_handling] app/domain/catalog/exchange_rate.py:41-46 ExchangeRateTable.convert 未校验源币种是否在 SUPPORTED_CURRENCIES（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:41-46`
  - 依据：convert 只校验目标币种，源币种由 self.rate() 内部校验（不在 rates_to_cny 中即抛 ValueError）。由于 Money 构造时已保证 currency 在 SUPPORTED_CURRENCIES 内，且 _RATES_TO_CNY 覆盖全部支持币种，源币种校验实际由 rate() 兜底，不会漏检。
- **[logic/low]** [logic] app/domain/catalog/exchange_rate.py:27-28 ExchangeRateTable 为 frozen dataclass 但持有可变 dict，可被外部篡改（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:27-28`
  - 依据：frozen=True 只阻止字段重新赋值，不阻止对 rates_to_cny 这个 dict 的原地修改。default_factory 每次创建新 dict 避免了共享默认值问题，但实例创建后仍可通过 table.rates_to_cny['USD'] = 0 篡改汇率，破坏值对象不可变语义，且该实例可被多处共享导致隐性串改。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:31-33 from_major_units 用 int() 截断浮点，产生分位误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-33`
  - 依据：int(major * 100) 对浮点乘法结果直接截断而非四舍五入。例如 19.99 * 100 = 1998.9999999999998，int() 得 1998，少 1 分；0.29*100=28.999999999999996 同样少 1 分。这是可复现的金额精度缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:41-43 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 等长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:41-43`
  - 依据：这是抽象端口定义，仅声明契约，具体校验责任在 Infrastructure 实现。端口层不实现逻辑，因此不构成缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 未包含 skus 规格信息，召回文本可能缺失关键属性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：docstring 明确声明可检索文本为“标题 + 品牌 + 品类 + 描述 + 亮点”，实现与声明一致，未包含 sku 规格是设计选择而非实现错误，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-27 Address 校验未覆盖 state/postal_code/phone，one_line 可能输出 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-27`
  - 依据：只校验了 recipient_name/country/city/address_line，state、postal_code、phone 允许为空。one_line() 会把空值格式化成空串或 None 拼进地址串。但注释说明 MVP 仅存储与展示，且这些字段在跨境场景中确实可能缺失，不构成明确缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/order/order.py:88-108 Order.snapshot 未输出 confirmed_at/cancelled_at，取消后无法区分时间（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-108`
  - 依据：snapshot 只输出 created_at 与 cancel_reason，未输出 confirmed_at/cancelled_at。这是信息缺失而非错误行为，且注释说明金额只出现在这里，未承诺输出全部时间戳。不构成缺陷。
- **[boundary/high]** [boundary] app/domain/order/order.py:44-50 Order.__post_init__ 只检查 lines 为 None，空列表可通过，导致 total_amount 索引越界（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:44-50`
  - 依据：不变量注释声称"至少一条订单行"，但校验只写了 `if self.lines is None`，空列表 [] 能通过构造。随后 total_amount() 直接访问 self.lines[0]，snapshot() 也会调用 total_amount()，于是空行订单在快照/查询时抛 IndexError。PlaceOrderUseCase 虽然挡住了空 items，但 Order 聚合本身可被其他路径（反序列化、测试、未来用例）以空 lines 构造，聚合根的不变量应当自洽。
- **[boundary/low]** [boundary] app/domain/order/order_line.py:22-24 OrderLine 未校验 unit_price 非负/类型，负价可构造（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:22-24`
  - 依据：__post_init__ 只校验 quantity，未校验 unit_price。但价格快照来自 Sku，负价是否可能取决于上游 Money/Sku 的约束；在本文件范围内无法确认存在可触发的负价路径，且 Money 类型本身可能已保证非负。因此不认定为缺陷，仅记录。
- **[logic/high]** [logic] app/domain/order/order_line.py:27-28 OrderLine.subtotal 使用 quantity - 1 计算，少算一件商品金额（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:27-28`
  - 依据：subtotal 应为 unit_price * quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0，quantity=3 时只算 2 件，导致订单总额系统性少算一件商品的价格。__post_init__ 已保证 quantity>0，因此该错误在任何合法输入下都会触发。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:110-113 免税额度判断使用单件小计而非含运费/数量的应税额，且 de_minimis_applied 语义与 landed 计算脱节（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:110-113`
  - 依据：de_minimis_applied 定义为 taxable_minor_cny == 0，即小计未超额度时关税为 0，这与文档口径“关税=小计超出免税额度部分×费率（不足免税额度则为 0）”一致；边界上恰好等于额度时 taxable=0 也符合“不足/等于”免税的简化口径。此处不构成独立缺陷（真正的缺陷是未乘 quantity，已单列）。
- **[logic/high]** [logic] app/domain/shipping/tariff_schedule.py:108-113 关税免税额度按单件小计判断，未乘以数量，导致多件订单被错误免税（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:108-113`
  - 依据：quote() 接收 quantity 参数，运费按 quantity 递增计算，但关税的免税额度判断只用了 subtotal（单件小计）折算成 CNY 后的金额，没有乘以 quantity。当买家购买多件、单件小计低于免税额度但总价远超额度时，taxable_minor_cny 会被算成 0，de_minimis_applied=True，关税被错误地免掉。例如 CN 目的国、单件 4000 元、quantity=3，总货值 12000 元已超 5000 元免税额度，但代码仍判定免税。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:30-36 免税额度与运费表用硬编码汇率折算，与传入的 ExchangeRateTable 不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:30-36`
  - 依据：_DE_MINIMIS_CNY_MINOR 用写死的汇率（如 US: 800*710、EU: 150*780）把外币额度折成 CNY 分，而实际金额换算走 self.rates（ExchangeRateTable）。当 rates 中的汇率与这些硬编码值不同（汇率会波动，或测试注入固定汇率表）时，免税判断与实际折算口径不一致，导致同一订单在不同汇率表下免税结论错误。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:52-54 get_many 对未登记 SKU 返回 0 而非 None，与 get 语义不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:52-54`
  - 依据：get 返回 int|None 区分“未登记”，get_many 返回 Mapping[str,int] 且用 get(sku_id, 0) 把未登记映射为 0。类型签名本身声明了 int 值域，调用方无法区分未登记与零库存，但这是接口设计选择而非可证实的错误行为；reserve 对未登记 SKU 也返回 False，与 0 库存表现一致，不产生错误结果。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:62-66 InMemoryStockRepository.seed 覆盖已有库存，运行期重复 seed 会回滚已扣减库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:62-66`
  - 依据：seed 的注释明确说明“以 seed 为准对齐库存，保证每次启动的库存与配置一致”，这是有意的启动初始化语义。只要 seed 仅在启动时调用一次，覆盖行为符合设计；若运行期重复调用才会回滚，但当前文件内无此调用路径，无法据此判定缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/json_file_stores.py:168-175 JsonFileConversationStore.touch_session 的 exists 检查与追加非原子，可能重复写 session 行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:168-175`
  - 依据：touch_session 先 path.exists() 判断，再 _append_line 追加。两个并发首轮请求都看到文件不存在，都会追加 kind=session 行，产生重复元信息。find_session 只返回第一条，功能上影响有限，但数据出现重复记录。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/json_file_stores.py:47-53 JsonFilePreferenceStore.append 的读-改-写无锁，并发追加会丢失偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:47-53`
  - 依据：append 先 await list_by_buyer 读取全量，再在内存里 append，最后 _write 覆盖整个文件。两个协程并发 append 不同 statement 时，都会读到同一份旧列表，后写者覆盖前写者，导致一条偏好静默丢失。await 点（list_by_buyer 内部虽为同步 IO，但方法声明为 async，调用处 await 会切换事件循环）使交错成为可能。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:148-160 list_turns 对缺失 role 的损坏行直接 KeyError，未纳入容错（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:148-160`
  - 依据：代码对 json.loads 失败做了 continue 容错，但随后 record["role"] 用下标访问。若某行是合法 JSON 但缺 role 字段（例如手工编辑或旧版本写入），会抛 KeyError 使整个 list_turns 失败，与“单行损坏不影响其余记录”的设计意图矛盾。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:155-166 list_turns 取前 limit 条而非最近 limit 条，长会话会丢失最新上下文（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:155-166`
  - 依据：JSONL 按时间顺序追加，list_turns 顺序读取后返回 turns[:limit]，即返回最早的 limit 条。会话超过 limit 轮后，最新对话被截断，Agent 恢复上下文时拿到的是最旧的历史，与“最近 N 轮”的常规语义相反。
- **[boundary/low]** [boundary] app/infrastructure/persistence/seed_products.py:1-1 _build_extra 中 skus 为空列表时不会报错但会生成无 SKU 商品（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:1-1`
  - 依据：当前 _EXTRA_SPECS 中每条记录都至少有一个 SKU，列表推导对空列表也安全返回 []，不会抛异常；没有证据表明存在空 SKU 记录，故不是缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:1-1 P1011 与 P1001 标题高度相似但刻意不写“抗造”，依赖单测 top-1 断言脆弱（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:1-1`
  - 依据：文件注释明确说明这是为评测区分度而刻意设计，且 P1011 描述确实不含“抗造”，与 P1001 的 top-1 断言不冲突；这是有意的数据设计而非缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/migrations/env.py:40-58 env.py 中 _database_url 的 sqlalchemy.url 回退可能拿到 ini 里的占位值（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/env.py:40-58`
  - 依据：config.get_main_option("sqlalchemy.url", None) 若 alembic.ini 中该键为空字符串会返回 ''，被 if configured 判为假而继续回退，行为正确；若 ini 里写了占位 URL 则会优先使用，但这是配置责任，代码逻辑本身无缺陷。异常兜底用 except Exception 后回退本地 SQLite，属于有意的降级设计。
- **[logic/low]** [logic] app/infrastructure/persistence/sql/repositories.py:1-1 release() 在补登记 SKU 时先 commit 再写 movement，且 movement 使用独立 session 导致日志丢失/顺序错乱（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：被截断无法定位精确行号，且 _log_movement 复用同一 db session，commit 后 add 仍会在后续 commit 落库；不构成确认缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/sql/tables.py:118-127 tables.py 中 OrderLineRow 外键未声明级联，删除订单会留下孤儿明细（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:118-127`
  - 依据：ForeignKey("orders.order_id") 未加 ondelete，但订单通常只做状态变更（cancelled_at/cancel_reason）而非物理删除，且 SQLite 默认不启用外键约束。仅凭表定义无法证明存在删除订单的代码路径，故不判定为缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/domain/catalog/money.py:31-33 from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-33`
  - 依据：JPY 的 ISO-4217 小数位为 0，最小单位就是 1 日元；但 from_major_units 对所有币种统一乘 100，导致 Money.from_major_units(1000, 'JPY') 得到 100000 个最小单位（即 1000 日元被当成 100000 日元）。to_major_units 同样除以 100，往返虽自洽，但与真实 JPY 口径不符，且与 ExchangeRateTable 中 JPY 汇率 0.048（按 1 日元计）配合时会把金额放大 100 倍。注释承认是简化，但这是真实的行为错误而非风格问题。
  - 争议对手：e43fdf0c37f2

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：32｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/infrastructure/persistence, app/domain/catalog, app/domain/order, app/domain/shipping, app/application/usecases

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `001a0c61fa51` | 1 | 1 | `partition_gap` | — |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `1bd894600f10` | 1 | 2 | `partition_gap` | — |
| `36316f1e43cb` | 1 | 0 | `partition_gap` | — |
| `3f29e8d0f73c` | 1 | 3 | `partition_gap` | — |
| `4662743c2106` | 1 | 0 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `48cc2d0a9307` | 1 | 0 | `partition_gap` | — |
| `4ad98b411bb7` | 1 | 0 | `partition_gap` | — |
| `52e48d38e8e3` | 1 | 0 | `partition_gap` | — |
| …另有 22 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app/application/usecases` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/shipping` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 38%（单元格值 = 独立 Agent 数）
