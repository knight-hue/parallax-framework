# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 3 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 6 | 支持不足、相关性超限或尚待验证 |
| 争议 | 7 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：39
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：83 个节点 / 257 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 16 | 100% | 22% |

## 高置信结论

- **[logic/critical]** [logic] app/domain/order/order_line.py:27-28 OrderLine.subtotal 使用 quantity - 1 计算，少算一件（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:27-28`
  - 依据：subtotal 应为 unit_price * quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0，quantity=3 时只算 2 件。由于 Order.total_amount 通常汇总各 line.subtotal()，订单总额会系统性偏低，且 quantity=1 的订单总额为 0，属于直接的资金计算错误。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:66-77 InMemoryOrderIdempotencyStore 的 find+record 非原子，并发重投可能双写订单（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:66-77`
  - 依据：find 与 record 各自加锁，但二者之间锁已释放。两个并发请求携带同一幂等键时，都可能先 find 得到 None，然后各自创建订单，再调用 record：第一个返回 True，第二个返回 False。若调用方在 record 返回 False 时没有回滚/丢弃已创建的订单，就会产生重复订单。幂等存储的契约本应保证“检查并占位”原子完成，这里把原子性责任推给了调用方且未在文档中说明。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:300-305 next_order_id 在 commit 之后读取 inserted_primary_key，可能拿到 None 或失效值（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:300-305`
  - 依据：SQLAlchemy 的 CursorResult.inserted_primary_key 应在 execute 之后、commit 之前读取；commit 后 session 关闭/结果对象可能已失效，且对某些驱动（如 asyncpg 的 RETURNING 行为）在 commit 后取值不可靠。更稳妥的写法是 execute 后立即取 inserted_primary_key 再 commit。当前写法在部分驱动下会抛 InvalidRequestError 或返回 None，导致 f"GBX-{None:06d}" 抛 TypeError。

## 待验证（孤证）

- **[logic/low]** [logic] app/domain/catalog/product.py:47-53 Product.searchable_text 未包含 skus 信息，且 origin_country 与文档描述不一致（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-53`
  - 依据：docstring 明确写的是“标题 + 品牌 + 品类 + 描述 + 亮点”，实现与 docstring 一致，origin_country 额外加入属于增强而非缺陷；skus 不在召回文本范围内是设计选择（SKU 粒度在结算阶段处理）。没有可引用的错误行为。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:28-33 ProductSearchSpec 未校验 price_max_major 为负值（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:28-33`
  - 依据：__post_init__ 只校验 normalized_query 与 top_k，未校验 price_max_major。但 price_max_major 为负值时检索链路会自然过滤掉所有商品（价格 <= 负数无命中），属于合法的“无结果”语义，不会引发异常或错误数据。缺少校验是设计取舍而非缺陷。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-27 Sku.stock 注释称只读但 dataclass 非 frozen，仍可被就地修改（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-27`
  - 依据：文档明确说明 stock 是初始库存参考数据，真正的扣减走 StockRepository；dataclass 未 frozen 只是允许修改，但没有任何代码路径依赖就地修改来扣库存，且 __post_init__ 校验了非负。不构成实际缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:108-113 关税按 CNY 小计计算后再折算，与目标币种口径不一致导致四舍五入误差累积（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:108-113`
  - 依据：文档明确说明关税以 CNY 口径计算（免税额度也是 CNY 分），先 convert 到 CNY 再算税再折回目标币种是符合设计意图的。虽然两次汇率折算会引入分位舍入误差，但这是既定口径而非缺陷。
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_repositories.py:41-47 InMemoryOrderRepository 返回共享可变 Order 实例，save 后调用方修改会绕过持久化语义（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:41-47`
  - 依据：save 直接存引用、find_by_id 直接返回引用，Order 是可变对象。调用方在 save 之后继续修改 order（例如改状态、加行）会“自动”反映到仓储里而无需再次 save；反之若期望未 save 的修改不生效，也会被破坏。与 SQL 仓储（每次查询重建对象）语义不一致。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:78-88 create_engine 对 sqlite 未设置 pool_pre_ping，且 WAL 的 PRAGMA 在连接建立时执行但未处理异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:78-88`
  - 依据：sqlite 本地文件连接不存在服务端回收问题，pool_pre_ping 无必要；PRAGMA 执行失败会直接抛异常使连接创建失败，属于快速失败而非静默错误，符合预期。

## 争议（需裁决）

- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:110-112 运费按 quantity 线性递增但未按件数乘首件价，语义与注释“首件全价+续件40%”不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:110-112`
  - 依据：注释写“首件全价 + 续件 40%”，公式 (1 + 0.4*(quantity-1)) 确实表达该语义（首件 1 份 + 每续件 0.4 份），因此公式与注释一致，不构成缺陷。
  - 争议对手：372e6320fdbe, d058bfd2851c
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:47-48 InMemoryOrderRepository.next_order_id 非原子，并发下可能重复发号（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:47-48`
  - 依据：next_order_id 直接调用 next(self._counter) 且没有加锁。itertools.count.__next__ 在 CPython 中受 GIL 保护，单次调用本身是原子的，因此不会出现两个协程拿到同一个号；但该仓储的 save/find 也没有锁，且 next_order_id 与 save 之间不是原子操作——两个并发下单流程可能各自取到不同号（这没问题），真正的问题是：调用方若在 await 之间穿插，取号与落库不构成事务，进程崩溃会跳号（可接受）。更关键的是 InMemoryOrderIdempotencyStore 有锁而 OrderRepository 没有，说明作者意识到并发问题却漏掉了这里；不过由于 count 的原子性，实际不会产生重复单号。
  - 争议对手：481fa92b7e11, cfad3d7abbb5
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_repositories.py:24-33 InMemoryProductRepository 返回共享可变 Product 实例，调用方修改会污染仓储状态（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:24-33`
  - 依据：find_by_id / find_by_ids / list_all 直接返回内部 dict 中保存的 Product 对象引用，而 Product 是可变 dataclass（非 frozen，skus/highlights 都是 list）。任何上层用例对返回对象做原地修改（例如调整 skus 顺序、追加 highlight、改 title）都会永久改变仓储中的“数据库”状态，后续请求读到被污染的数据。真实仓储（SQL）每次查询都会返回新实例，内存实现与端口契约行为不一致，导致开发态与生产态行为分叉。
  - 争议对手：787e93b96ddc
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:27-33 基线迁移用 create_all/drop_all 而非显式 op，downgrade 会删掉所有表且无法表达增量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:27-33`
  - 依据：Alembic 迁移要求 upgrade/downgrade 是显式、可审计、可回滚的 DDL 序列。这里用 Base.metadata.create_all/drop_all：1) create_all 只建不存在的表，若库中已有部分表（例如手工建过或从旧库迁移）会静默跳过，导致 alembic_version 标记为已应用但实际表结构缺失；2) drop_all 会删除 metadata 中所有表，包括后续迁移新增的表，downgrade 到 base 时行为超出本版本职责；3) 迁移文件依赖运行时 import 的 tables.Base，模型后续变更会改变历史迁移的语义（历史迁移不再可重放）。
  - 争议对手：354b8a2c3dcc
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:30-31 基线迁移 downgrade 使用 drop_all 会删除所有表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:30-31`
  - 依据：downgrade 调用 Base.metadata.drop_all，会按当前 models 定义删除所有表，而不是仅删除基线创建的表。若后续迁移新增了表（autogenerate 生成），回滚到基线之前时 drop_all 会连带删除这些后续表，且顺序由 metadata 决定，可能因外键依赖失败或误删数据。基线迁移的 downgrade 应只 drop 基线自身创建的表集合，或至少显式列出。
  - 争议对手：c82ef15d0a9a
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/sql/repositories.py:196-210 append_turn 的 turn_index 读最大值再 +1 存在并发撞号（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:196-210`
  - 依据：先 select max(turn_index) 再插入 max+1，两个并发事务会读到同一最大值并写入相同 turn_index。若表上有 (session_id, turn_index) 唯一约束则一方 IntegrityError 导致整轮对话写入失败；若无唯一约束则出现重复序号，list_turns 的 order_by 顺序不确定。模块注释自承“极小概率撞号”，但撞号并非只影响展示——插入失败会丢消息。
  - 争议对手：d405fe61fd82
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/repositories.py:258-285 save 中 merge 订单头与 delete/insert 订单行不在同一原子边界内，且 merge 后 delete 可能删掉刚插入的行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:258-285`
  - 依据：save 先 db.merge(OrderRow) 再 db.execute(delete(OrderLineRow)...) 再 db.add_all(新行)。SQLAlchemy 的 autoflush 会在执行 delete 前把 pending 的 merge 刷入，但 add_all 的新行在 delete 之后才加入，顺序上没问题；真正的问题是 delete 是直接 SQL 执行，而如果同一 session 中此前已加载/挂起同 order_id 的 OrderLineRow 对象，delete 后这些对象仍处于 persistent 状态，commit 时可能被重新 flush 回去或触发 StaleDataError。此外 merge 与行重写之间若 commit 失败，订单头已更新而行未更新，产生不一致（虽然同一事务内会回滚，但 merge 的 autoflush 时机使问题难以推理）。
  - 争议对手：714759d82390, f58d9051dab6

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：24｜覆盖正常：8｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 16，估计总体 16.3333
- 待补检分组：app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/domain/catalog, app/domain/order

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `36316f1e43cb` | 3 | 0 | `reader_miss` | 0.0% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.0% |
| `4ad98b411bb7` | 3 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.0% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.0% |
| `7d3fc36631b9` | 3 | 0 | `reader_miss` | 0.0% |
| `87535cbc08cd` | 3 | 0 | `reader_miss` | 0.0% |
| `8bcd4993ad83` | 3 | 0 | `reader_miss` | 0.0% |
| `8bd6a46280ac` | 3 | 0 | `reader_miss` | 0.0% |
| `9b22164343f5` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 14 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 3 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 3 | 3 | 0 | 2 | 0 | 0 | 0 | 3 |

矩阵填充率 22%（单元格值 = 独立 Agent 数）
