# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 2 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 18 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：32
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：82 个节点 / 222 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 22 | 100% | 7% |

## 高置信结论

- **[logic/high]** [logic] app/domain/order/order_line.py:25-26 OrderLine.subtotal 少乘一件：用 quantity-1 计算小计（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:25-26`
  - 依据：subtotal 应等于 unit_price × quantity，但代码写成 multiply(self.quantity - 1)。quantity=1 时小计为 0；quantity=3 时小计只有 2 件的钱。该方法通常被 Order.total_amount() 聚合（repositories.py 的 save 里 total = order.total_amount()），因此错误会直接落到订单金额/落库金额上，属于金额少算。异常只在 quantity<=1 的最常见路径被 __post_init__ 允许（quantity=1 合法），所以下单即触发。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:24-34 InMemoryProductRepository 直接返回内部可变 Product 聚合的共享引用（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:24-34`
  - 依据：Product 是可变 dataclass（product.py 第 21 行为 @dataclass，非 frozen），而仓储把同一实例同时放进 _products 字典并原样返回（find_by_id / find_by_ids / list_all 都返回同一对象引用）。任何调用方对返回对象做原地修改（改 title、append/remove skus、清空 skus 等）都会永久污染进程内的商品目录，影响后续所有请求；尤其 `product.skus.clear()` 之类操作会让 Product.__post_init__ 建立的非空 skus 不变式失效，从而让 primary_sku() 的 self.skus[0] 抛 IndexError。这不是风格问题：它使只读语义的仓储在跨请求间产生可观察的错误行为。

## 待验证（孤证）

- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:22-26 ProductSearchSpec 未校验 price_max_major 为负，但不会造成错误结果（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:22-26`
  - 依据：__post_init__ 只校验 normalized_query 非空与 top_k 为正。price_max_major 为负值（例如 -1）时会构造成功，随后结构化过滤必然召回空集。但这属于“调用方给了无意义的过滤上界”的正常语义结果：不会抛错、不会产生错误价格、不会绕过任何安全约束，且值对象本身无法判断负价是笔误还是刻意；把它强行拒绝反而可能让上一层的兜底路径失效。normalized_query 与 top_k 的校验覆盖了真正会破坏不变量的字段，因此这里不认定为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/sku.py:24-32 Sku 未设为 frozen，docstring 承诺的“库存不可在内存对象上修改”未被类型系统强制（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:24-32`
  - 依据：docstring 明确要求不要提供 deduct_stock/restore_stock 并称 stock 只读，但 @dataclass 未加 frozen=True，外部写 sku.stock -= 1 依然可行且绕过 __post_init__ 校验。不过就本次可见代码而言，没有任何位置对 Sku.stock 赋值，超卖保护实际由 SqlStockRepository.reserve 的条件 UPDATE 承担；这属于后续可加固点而非当前已触发的缺陷，故记为 not_a_defect。同样，__post_init__ 只校验 stock 非负而不校验 price，也无代码依据说明会造成错误行为。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:80-82 quote() 对 _TARIFF_RATES 之外的键只做一次存在性检查，未覆盖另两张表（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:80-82`
  - 依据：quote() 只用 `ship_to not in _TARIFF_RATES` 做白名单校验，随后却分别取 _DE_MINIMIS_CNY_MINOR[ship_to] 与 _BASE_FREIGHT_CNY_MINOR[ship_to]。目前三张表的键集合完全一致（CN/US/EU/JP/SG），所以不存在 KeyError；只有将来新增目的国时漏改其中一张表才会在运行期抛 KeyError。这是维护一致性风险而非当前代码的真实缺陷，故不按缺陷上报，但值得在新增国家时同步三张表。
- **[error_handling/low]** [error_handling] app/domain/shipping/tariff_schedule.py:88-99 tariff_schedule 的三张按国家索引的字典查表是安全的（国家键集合一致，不会 KeyError）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:88-99`
  - 依据：初看 `_BASE_FREIGHT_CNY_MINOR[ship_to]`、`_DE_MINIMIS_CNY_MINOR[ship_to]`、`_TARIFF_RATES[ship_to]` 是三处裸下标，容易怀疑漏配国家会 KeyError。逐键核对：_TARIFF_RATES、_DE_MINIMIS_CNY_MINOR、_BASE_FREIGHT_CNY_MINOR 的键集合完全相同（CN/US/EU/JP/SG），且 quote 入口第一行已用 `if ship_to not in _TARIFF_RATES: raise ValueError(...)` 做了前置校验，因此三处下标都在同一个合法集合内，不存在某国只配了费率却缺运费/免税额而抛 KeyError 的路径。品类查表 `rate_table.get(category, rate_table["*"] )` 也安全：五个国家字典都显式含有 "*" 兜底键，category 未命中或为 None 时都能取到默认费率。_DE_MINIMIS_CNY_MINOR 的常量算式（800*710、150*780、400*530 等）换算结果与其注释口径一致，未发现量纲错误。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:93-100 de_minimis_applied 对零关税品类（US/数码配件）返回 False，与字段注释“关税为 0”不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:93-100`
  - 依据：de_minimis_applied 的取值来自 taxable_minor_cny == 0，即“小计未超过目的国免税额度”；而字段行尾注释写的是“是否命中免税额度（关税为 0）”。复核后确认：对美国数码配件（费率 0.0）这类零关税品类，即使小计远超免税额，tariff 也是 0 而 de_minimis_applied 为 False。这是字段名（是否命中免税额度）与行尾括号注释（关税为 0）的措辞差异，字段本身的语义是正确的；调用方若要展示“免税”应按 tariff.amount_in_minor_units == 0 判断，而不是依赖该布尔。因此不构成计算错误，最多是注释不精确。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/in_memory_repositories.py:30-31 find_by_ids 静默丢弃不存在的 id，且不保持与请求列表一一对应（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:30-31`
  - 依据：实现只返回命中的商品，顺序与 product_ids 一致（列表推导保持入参顺序），行为是确定的、不会抛异常；丢弃缺失 id 是常见的仓储语义。只有当调用方按位置 zip(product_ids, results) 做对齐时才出问题，那属于调用方误用，无法在本文件内确认为缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:27-34 find_by_id/list_all 返回仓储内部共享的可变 Product 引用，但当前文件内无任何变更操作（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:27-34`
  - 依据：Product 是非 frozen 的 dataclass，仓储直接返回内部对象引用，理论上若下游修改了返回的 Product（或其 skus/highlights 列表），会污染整个进程内目录、影响其他并发请求。但在这五个文件范围内没有任何代码对返回对象做写入，且读取语义下共享引用是内存仓储的常见且可接受做法，故不构成本次可证实的缺陷，仅作为潜在风险记录。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:48-49 next_order_id 未加锁，但 itertools.count 在 asyncio 单线程下自增是原子的，不会产生重复单号（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:48-49`
  - 依据：next(self._counter) 与 save 之间没有 await 点，且 asyncio 单线程执行、itertools.count 的 next 在 CPython 下是原子操作，即使多个协程并发调用 next_order_id 也不会拿到相同序号。该类文件头已声明是『开发态内存仓储』且幂等存储注释明确仅单进程可用，因此缺少显式锁不构成缺陷。仅在多线程/多进程共享同一实例时才可能出问题，而那不是该实现的预期形态。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:67-72 record() 自身是原子 CAS，单看该仓储实现不会产生重复下单竞态（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:67-72`
  - 依据：容易误判为缺陷的是“find 之后再 record”两步不是原子的，并发请求可能都看到 find 返回 None。但 record 在锁内做了 if key in self._keys: return False 的检查并返回布尔值，本身就是原子的 compare-and-set；只要调用方以 record 的返回值作为“是否抢到幂等键”的裁决（而不是先 find 再无条件下单），并发重投就会被拦下。缺陷若存在，责任在调用方使用方式，而非这份实现。
- **[api_misuse/high]** [api_misuse] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30 基线迁移用 metadata.create_all/drop_all 导致后续新增表的迁移必然冲突，且 downgrade 会删掉超出基线的表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30`
  - 依据：Alembic 迁移必须是“历史快照”：0001 号 revision 只能创建它那个时间点的表结构。这里 upgrade() 直接调用 Base.metadata.create_all()，而 Base.metadata 是运行时从 models 导入的、永远等于“当前最新”结构。一旦后续提交给 models 新增一张表并用 autogenerate 生成 0002（内含 op.create_table('新表')），在空库上执行 alembic upgrade head 时：0001 先跑 create_all，把最新 metadata 里的新表一并建出来；紧接着 0002 再执行 op.create_table 就会抛 OperationalError: table ... already exists，升级链在全新环境（CI、新部署机）上直接失败。同理 downgrade() 里的 drop_all() 删除的是当前 metadata 的全部表，执行 alembic downgrade base 时会连带删除 0001 之后版本才引入的表（即使那些版本的 downgrade 已删过一次，checkfirst 掩盖了报错，但语义已经错位）。此外 create_all 依赖实际连接，alembic upgrade --sql 的离线 SQL 生成模式会直接不可用。这些都不是风格问题，而是确定会让迁移链在某次迭代后崩掉的真实缺陷。
- **[logic/high]** [logic] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30 基线迁移用 create_all 建表，导致迁移历史不可复现，并会让后续新增表的迁移在全新库上冲突失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30`
  - 依据：0001 的 upgrade 直接执行 Base.metadata.create_all(bind=op.get_bind())，而 Base.metadata 是“当前代码”的表集合，不是“0001 时刻”的表集合。因此：
(1) 不可复现——在任意 checkout 上重放迁移得到的是该 checkout 的 schema，历史版本漂移；例如把仓库回退到早期 commit 再 `alembic upgrade head`，基线只会建出早期 commit 里存在的表，之后那份老的 0002/0003 迁移再 alter 一张从未被建出的表就会失败（或反之，在最新 commit 上基线把 0002+ 才新增的表也建出来）。
(2) 全新库必然冲突——一旦有人按文档说的 `alembic revision --autogenerate` 新增一张表（假设 0002 的 upgrade 是 op.create_table('t_new', ...)），在空库上执行 `alembic upgrade head` 时，0001 的 create_all 已经用最新 metadata 把 t_new 建出来了（create_all 默认 checkfirst=True，缺表就建），紧接着 0002 的 op.create_table 不是 checkfirst，会抛 `OperationalError: table t_new already exists`，即从头安装直接失败。
(3) 同一根因也污染 downgrade：下方 drop_all 同样是 metadata 驱动，drop 的目标集合随代码变化，而不是 0001 时刻的 schema。
根因是基线应当固化一份快照（显式 op.create_table），而不是在迁移里反向引用活代码里的 metadata。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:366-378 get_many/seed 的 Iterable、Mapping 注解未导入，但当前不会在运行期报错（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:366-378`
  - 依据：文件顶部只 from typing import Optional，却没有导入 Iterable 和 Mapping，二者被用在 get_many 的入参与返回值、seed 的入参注解上。因为模块启用了 from __future__ import annotations，所有注解都是字符串形式、不会被求值，所以导入模块、调用这两个方法都不会触发 NameError；只有在显式调用 typing.get_type_hints() 或依赖注解求值的工具（如某些 schema 生成、反射框架）时才会失败。当前代码路径下不构成运行时缺陷，因此记为 not_a_defect。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/repositories.py:353-358 release 在补登记分支里 commit 之后才写库存流水，流水永远不会落库（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:353-358`
  - 依据：未登记 SKU 的分支先 db.add(SkuStockRow(...)) 并 await db.commit()，之后才调用 _log_movement 把 StockMovementRow 加进 session，然后直接 return。async with 退出时 session 被关闭，未提交的 pending 对象被丢弃（没有第二次 commit，也没有 flush）。结果是库存表补登记成功，但 stock_movements 审计流水缺少这条记录，与其它分支（先 log 后 commit）行为不一致，库存流水与库存变化无法对账。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/repositories.py:384-392 seed() 声称 INSERT OR IGNORE，实际是先查后插，多进程同时启动会撞唯一约束抛出 IntegrityError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:384-392`
  - 依据：文档字符串写“INSERT OR IGNORE 语义”，但实现是 `select(...) -> if 存在 continue -> db.add(...)` 的读-判断-写，并非原子。模块头注释明确说明 worker 是独立进程、与 API 进程并发写同一个 db 文件，而 seed 是启动时播种，两个进程同时启动时可能都查到“不存在”，随后 INSERT 时后提交的一方触发主键/唯一约束 IntegrityError。该异常在 seed 内未被捕获，会冒出整个启动流程（且前面已 add 的行未提交，随 session 关闭回滚，播种变成部分完成）。这与模块注释里“偏好去重靠唯一约束，重复插入吞掉 IntegrityError（比先查后插更可靠）”的自述自相矛盾。
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/repositories.py:353-358 release() 为未登记 SKU 补登记后，库存流水在提交之后才 add 且未 commit，流水丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:353-358`
  - 依据：未登记 SKU 分支的写法是：db.add(SkuStockRow(...)) → await db.commit() → await self._log_movement(...) → return。_log_movement 只是 db.add(StockMovementRow(...))，之后没有 commit；紧接着 async with 块退出，session.close() 会丢弃未提交的 pending 对象，StockMovementRow 永远不会落库。对比同函数正常分支（第 359-360 行）是 _log_movement 后紧跟 commit，可确认这里少了提交。结果是库存被回补了但审计流水缺失，库存账面与流水无法对账。
- **[error_handling/low]** [error_handling] app/infrastructure/settings.py:118-119 EMBEDDING_BASE_URL/EMBEDDING_API_KEY 为空字符串时不回退到 LLM 网关，配置空值反而变成坏配置（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:118-119`
  - 依据：os.getenv 的 default 只在键不存在时生效。.env.example 这类模板通常把可选键留成 `EMBEDDING_BASE_URL=`，此时 getenv 返回空串，settings.embedding_base_url 就是 ""，不会回退到 llm_base_url，而 embedding_api_key 也变成 ""。启动阶段没有任何校验，直到第一次做 embedding 时才以一个指向空 URL 的请求失败，错误信息远离根因。而其余可选能力（qdrant_url / reranker_base_url / tavily_api_key）确实把空串当“关闭/降级”，说明本文件的设计约定是“空值即关闭”，这里的行为与约定不一致。中文注释“embedding 默认复用 LLM 网关”也表明作者期望空值/缺省时复用的是 llm_base_url。
- **[error_handling/medium]** [error_handling] app/infrastructure/settings.py:162-164 布尔型环境变量解析只认 '0'/'false'/'False'，空值和大写 FALSE 被当作开启（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:162-164`
  - 依据：所有布尔开关都用 `os.getenv(NAME, default) not in ("0", "false", "False")` 判定。这带来两个偏离设计的行为：1) 大小写/常见写法未归一，`DRIFT_DETECT_ENABLED=FALSE`、`=False` 之外的 `=no`、`=off`、`=FALSE` 全都被判定为 True；2) 更严重的是空字符串：当 .env 里写下 `DRIFT_DETECT_ENABLED=`（键存在、值为空）时，getenv 返回 ""，而 "" 不在禁用元组里，结果为 True —— 于是默认应为 False 的 drift_detect_enabled 被静默打开，每个请求多一次轻量 LLM 调用。这与文件顶部“可选能力全部按空值即关闭/降级设计”以及字段注释“需额外轻量 LLM 调用，默认关”直接矛盾，属于会实际改变线上行为（额外计费/延迟）的配置解析缺陷。同理 breaker_shared、preference_relevance_enabled 等默认关的开关也受影响。
- **[logic/low]** [logic] app/infrastructure/settings.py:221-224 布尔型环境变量解析只接受 "0"/"false"/"False"，写成 FALSE/off/no 会被静默当作开启（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:221-224`
  - 依据：各处布尔开关统一用 `os.getenv(NAME, default) not in ("0", "false", "False")` 判定。该表达式把除这三个字面量以外的任何取值都当成 True。因此把 `HARNESS_ENABLED=FALSE`、`OUTPUT_GUARD_ENABLED=off`、`SEMANTIC_CACHE_ENABLED=no`（或在 .env 里带尾随空格写成 `false `）写进环境时，配置项不会关闭，仍会开启对应能力；这与运维/文档语义相反，尤其对 harness_enabled/output_guard_enabled 这类“以为已关掉、实际仍拦截/改写输出”的护栏开关会产生难以察觉的行为差异。同一文件里既有默认开启(`"1"`)也有默认关闭(`"0"`)的开关，两种极性都受影响。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-40 primary_sku() 的不变式可被外部修改 skus 打破，导致 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-40`
  - 依据：Product 是非 frozen 的 dataclass，skus 是公开可变的 list；__post_init__ 只在构造时校验非空，之后任何持有该 Product 的代码（包括 InMemoryProductRepository 直接交出的同一实例）都可以 clear()/pop()/remove() 掉 skus，随后 primary_sku() 直接 self.skus[0] 会抛 IndexError，而不是抛出可预期的域异常或返回 None。与之相邻的 find_sku() 用 next(..., None) 做了空集合安全处理，说明 primary_sku() 的越界假设与本类其余 API 不一致。
  - 争议对手：56979a9cc0ef
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:162-173 touch_session 先查后插，同会话并发首触会抛出未捕获的 IntegrityError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:162-173`
  - 依据：会话行不存在时走 db.get -> db.add -> commit 的“读-判断-写”路径，session_id 是主键。两个并发请求（同一 session_id 的两次首轮消息，或 API 进程与 worker 同时 touch）都可能 get 到 None，随后第二个 commit 触发主键冲突；此处没有像模块文档里描述的偏好去重那样捕获 IntegrityError（模块头部注释明确写了“重复插入吞掉 IntegrityError（比先查后插更可靠）”），异常会冒泡到业务调用方并中断该轮对话。相比之下 SqlSessionStore.save 用 merge 覆盖写，不受影响。
  - 争议对手：08914bacf91a, 13d060078bf5

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：34｜覆盖正常：9｜无法判定：0
- 单 Reader 检出率：89.8%（重捕对 3，已观测 22，估计总体 24.5
- 待补检分组：app, app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/domain, app/domain/order, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.1% |
| `36316f1e43cb` | 3 | 0 | `reader_miss` | 0.1% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.1% |
| `4ad98b411bb7` | 3 | 0 | `reader_miss` | 0.1% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.1% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.1% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.1% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.1% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.1% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.1% |
| …另有 24 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 3 | 3 | 0 | 2 | 0 | 0 | 0 | 3 |

矩阵填充率 14%（单元格值 = 独立 Agent 数）
