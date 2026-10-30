# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 6 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 27 | 支持不足、相关性超限或尚待验证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：55
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：94 个节点 / 264 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 36 | 100% | 7% |

## 高置信结论

- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:60-74 InMemoryOrderIdempotencyStore 的 find/record 分离导致检查-写入非原子，并发重复下单可被放行（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:60-74`
  - 依据：find() 与 record() 各自加锁，但调用方通常先 find 再 record，两步之间锁已释放。两个并发请求携带同一幂等键时都可能 find 返回 None，随后 record 中只有一个返回 True，另一个返回 False——若调用方在 record 返回 False 时正确回读 find 并复用已有 order_id，则不会重复下单；但该 store 的接口设计本身无法保证原子性，且 record 返回 False 时并不返回已存在的 order_id，调用方必须再 find 一次，存在竞态窗口。更关键的是：record 返回 False 时调用方若未处理（例如直接忽略返回值），就会重复创建订单。这是接口契约层面的缺陷，属于真实风险点。
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:33-40 release 对未登记 SKU 直接补登记 quantity，可能凭空创造库存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:33-40`
  - 依据：release 在 SKU 未登记时把库存设为 quantity，而不是报错或忽略。若调用方对从未 reserve 成功的 SKU 调用 release（例如下单流程中 reserve 失败后仍走补偿路径，或重复补偿），库存会被凭空创建。注释声称“避免库存凭空消失”，但实际效果是凭空增加。与 SQL 实现（未登记分支只记 movement 不增加库存）行为不一致，导致两种持久化形态下库存语义漂移。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:245-258 next_order_id 依赖 inserted_primary_key，SQLite 下 insert().values() 空值可能不返回主键（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:245-258`
  - 依据：insert(OrderSequenceRow).values() 不带任何列值，依赖自增列。SQLAlchemy 对 SQLite 的 lastrowid 通常能拿到 inserted_primary_key，但 result.inserted_primary_key 在部分驱动/方言下可能为 None 或抛 InvalidRequestError（当无法确定主键时）。更稳妥的是显式 returning 或使用 result.lastrowid。此外 result 在 commit 之后才访问 inserted_primary_key，某些驱动在 commit 后结果对象失效。
- **[boundary/medium]** [boundary] app/infrastructure/persistence/sql/repositories.py:200-215 list_turns 的 limit 未按时间倒序取最近 N 条，而是取最早 N 条（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:200-215`
  - 依据：list_turns 用 order_by(turn_index).limit(limit)，当会话消息超过 limit 时返回的是最早的 limit 条，而不是最近的 limit 条。对于「取最近对话上下文」的典型用途，这会丢掉最新消息，导致模型看不到用户刚说的话。正确做法是先按 turn_index desc 取 limit 再反转，或子查询。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/sql/repositories.py:330-345 seed 在循环内逐条查询并 add，未处理并发插入的 IntegrityError（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:330-345`
  - 依据：seed 的注释声称是 INSERT OR IGNORE 语义，但实现是「先 select 判断存在，再 add」。两个进程（API 与 worker）同时启动并 seed 同一 SKU 时，双方 select 都返回 None，随后都 add 并 commit，第二个 commit 会抛 IntegrityError（sku_id 主键冲突），导致整个 seed 事务失败、启动报错。注释里明确说 worker 是独立进程，与 API 并发写同一 db，这正是触发条件。
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/repositories.py:300-312 release 在未登记 SKU 分支中先 commit 再写 movement，且 movement 使用新 session 之外的状态（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:300-312`
  - 依据：release 的 row is None 分支里，先 db.add(SkuStockRow(...)) 并 await db.commit()，然后调用 self._log_movement(db, ...) 再 await db.commit()。第一次 commit 后 SQLAlchemy 默认 expire_on_commit=False（session_factory 设置了），所以 db 仍可用；但更关键的是：如果第二次 commit 失败，库存已补登记而 movement 丢失，审计不一致。此外该分支的 stock_after 传的是 quantity，与补登记后的库存一致，这点没问题。真正的问题是两次 commit 之间没有事务原子性，movement 记录可能丢失。

## 待验证（孤证）

- **[error_handling/low]** [error_handling] app/composition.py:196-198 use_database 判断仅比较字符串 'file'，其他非法 DATABASE_URL 会走 SQL 分支并在 create_engine 处失败（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:196-198`
  - 依据：create_engine 在 build_container 中同步调用，若 URL 非法会直接抛异常导致启动失败。这是配置错误的显式失败，符合“配置错误应尽早暴露”的预期，不属于静默降级缺陷。
- **[error_handling/low]** [error_handling] app/composition.py:78-86 _prompt_fingerprint 路径拼接依赖 __file__ 位置，打包/安装后可能读不到提示词文件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:78-86`
  - 依据：函数已用 try/except OSError 兜底返回 'noprompt'，读不到文件不会阻断启动，只是语义缓存 namespace 退化为固定值。这是设计上接受的降级，不构成缺陷。
- **[error_handling/low]** [error_handling] app/composition.py:88-96 composition.py 中 _prompt_fingerprint 路径拼接依赖 __file__ 位置，打包/移动后静默降级为 noprompt（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:88-96`
  - 依据：注释明确说明读不到文件时返回固定值且不阻断启动，这是有意的降级设计。路径基于 __file__ 的 parent 拼接 application/prompts/globex.yml，在标准源码布局下正确；打包场景下会降级但不会导致错误行为，仅使缓存 namespace 失去 prompt 指纹，属于可接受的取舍。
- **[logic/low]** [logic] app/composition.py:88-96 composition 中 _prompt_fingerprint 路径拼接依赖 __file__ 位置（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:88-96`
  - 依据：Path(__file__).resolve().parent 为 app/，拼接 application/prompts/globex.yml 得到 app/application/prompts/globex.yml，与仓库结构一致；OSError 时返回固定值 'noprompt'，不会阻断启动。路径正确，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_repositories.py:30-31 InMemoryProductRepository.find_by_ids 静默丢弃不存在的 id，调用方无法区分缺失（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:30-31`
  - 依据：find_by_ids 用 `if pid in self._products` 过滤掉不存在的 id，返回的列表长度可能小于输入。这本身是常见语义（批量查询返回存在的子集），是否缺陷取决于调用方契约。若调用方依赖返回列表与输入一一对应（例如按索引对齐价格），则会错位。但仅从本文件看，没有证据表明调用方这样使用；且 SQL 实现通常也是返回存在的行。因此不判定为缺陷，但记录该语义风险。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:27-33 InMemoryProductRepository 返回内部可变对象引用，外部修改会污染仓储状态（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:27-33`
  - 依据：find_by_id、find_by_ids、list_all 都直接返回 self._products 中存储的 Product 对象本身（list_all 只复制了列表，未复制元素）。若 Product 是可变对象（dataclass 非 frozen），调用方对返回对象的任何字段修改都会直接改写仓储内的商品数据，且跨请求可见，造成状态污染。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:44-52 InMemoryOrderRepository.next_order_id 使用 itertools.count 但 save 不校验 order_id 唯一性，重启后计数器归零会覆盖已有订单（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:44-52`
  - 依据：该仓储是进程内开发态实现，文档明确说明重启即失效，计数器归零后订单字典也一并清空，不存在覆盖已有订单的问题。save 直接以 order_id 为键写入，若调用方传入重复 order_id 会覆盖，但 next_order_id 保证单调递增，正常流程不会重复。属于设计上的已知限制而非缺陷。
- **[resource_leak/low]** [resource_leak] app/infrastructure/persistence/in_memory_repositories.py:56-74 InMemoryOrderIdempotencyStore 无过期/清理机制，进程内字典无限增长（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:56-74`
  - 依据：幂等键只增不删，没有 TTL 或容量上限。开发态长时间运行或压测时，_keys 会随请求数线性增长，最终内存膨胀。虽然注释说明仅用于开发态，但作为可运行的实现，缺少清理是真实缺陷（SQL 实现通常有 TTL 列或定期清理）。
- **[resource_leak/low]** [resource_leak] app/infrastructure/persistence/in_memory_repositories.py:62-73 InMemoryOrderIdempotencyStore 无容量上限，长期运行内存持续增长（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:62-73`
  - 依据：_keys 字典只增不减，没有任何过期或清理机制。开发态长时间运行或压测时，每个幂等键都会永久驻留内存，最终导致内存持续增长。虽然文档说明仅用于开发态，但作为可运行的实现仍构成资源泄漏。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/in_memory_stock_repository.py:15-17 InMemoryStockRepository 未实现 StockRepository 端口，缺少 get_many 之外的接口契约保证（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:15-17`
  - 依据：类没有显式继承 StockRepository 协议，但 Python 结构化子类型（Protocol）下只要方法签名一致即可被当作 StockRepository 使用；composition.py 中 stock_repo: StockRepository = InMemoryStockRepository() 在运行时不会报错。方法集合（reserve/release/get/get_many/seed）与 SQL 实现一致，因此不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:22-30 reserve 对 quantity<=0 抛 ValueError，但未校验 sku_id 为空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:22-30`
  - 依据：空 sku_id 在 _stock 中查不到，reserve 返回 False，属于合理的“库存不足/不存在”语义，不会造成错误扣减。调用方需自行处理 False。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:45-47 get_many 在锁内对可迭代对象惰性求值，若传入生成器且被外部复用可能不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:45-47`
  - 依据：get_many 在锁内一次性消费 sku_ids 构造字典，生成器在锁内被完整迭代，不存在锁外惰性求值问题。返回的是新字典，调用方修改不影响内部状态。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_stock_repository.py:51-55 seed 使用 setdefault 只补缺失项，但并发 reserve 与 seed 交错时可能覆盖已扣减库存（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:51-55`
  - 依据：seed 与 reserve 共用同一把 asyncio.Lock，且 setdefault 只在键不存在时写入。若 reserve 先执行把库存扣到 0，seed 不会覆盖；若 seed 先执行，reserve 在锁内看到已登记值再扣减。两种交错都不会丢失扣减结果，因此并发安全。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/in_memory_stock_repository.py:22-30 reserve 对未登记 SKU 返回 False 而非报错，可能掩盖播种失败（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:22-30`
  - 依据：current is None 时返回 False 是“库存不足”的合理语义，调用方据此拒绝下单；播种失败在 composition._seed_stock 中已记录告警。行为可预期，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:40-50 InMemoryStockRepository 未实现 StockRepository 协议（缺少 get_many 之外的接口一致性无法验证，但 release 对未登记 SKU 静默补登记会掩盖超卖/回滚错误）（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:40-50`
  - 依据：release 对未登记 SKU 补登记为 quantity 而非报错，注释说明是有意为之（避免库存凭空消失）。在正常流程中 release 只会在 reserve 成功后调用，未登记分支属于异常路径；补登记虽可能掩盖 bug，但不构成可复现的错误行为，且与 SQL 实现语义一致。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:268-280 next_order_id 使用 inserted_primary_key，在非自增主键或某些驱动下可能为 None（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:268-280`
  - 依据：result.inserted_primary_key[0] 依赖驱动返回自增主键。SQLite/aiosqlite 通常可用，但若 OrderSequenceRow 主键不是自增整型（例如 UUID 或复合主键），inserted_primary_key 会抛 InvalidRequestError 或返回 None，导致 f"GBX-{None:06d}" 抛 TypeError。代码未做防御。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:400-410 delete 依赖 result.rowcount，部分异步驱动返回 -1 导致误判（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:400-410`
  - 依据：bool(result.rowcount) 在 rowcount 为 -1（某些驱动/方言不报告行数）时为 True，即使没有删除任何行也会返回 True，破坏『返回是否真的删到了行』的契约。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:75-95 create_engine 对 sqlite 未设置 pool_pre_ping，但注释说服务型必需——sqlite 分支正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:75-95`
  - 依据：sqlite 分支不传 pool_size 等参数是正确的，因为 SQLite 默认池不接受这些参数。WAL 与 busy_timeout 通过 connect 事件设置，逻辑正确。
- **[boundary/low]** [boundary] app/infrastructure/persistence/sql/repositories.py:400-410 delete 使用 result.rowcount 判断，某些驱动 rowcount 为 -1 时 bool(-1) 为 True（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:400-410`
  - 依据：SQLAlchemy 的 CursorResult.rowcount 在部分驱动/场景下返回 -1（表示未知）。bool(-1) 为 True，会把『未删除任何行』误报为删除成功。虽然 sqlite 通常返回真实行数，但代码注释声称返回是否真的删到了行，跨驱动不可靠。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:130-140 SqlSessionStore.save 用 merge 覆盖写，并发下后写覆盖前写（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:130-140`
  - 依据：merge 是覆盖写，若同一 session 并发保存状态，后写覆盖前写会丢失更新。但会话状态通常由单请求串行处理，且注释未承诺并发安全。属于设计取舍而非明确缺陷，除非有证据表明同一 session 会被并发写。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/sql/repositories.py:150-165 touch_session 并发首次插入同一 session 会抛 IntegrityError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:150-165`
  - 依据：touch_session 先 get 判断不存在再 add，两个并发请求对同一新 session_id 都会 get 到 None，随后都 add 并 commit，第二个 commit 抛 IntegrityError（主键冲突），导致请求失败。这是典型的 check-then-act 竞态。
- **[error_handling/medium]** [error_handling] app/infrastructure/persistence/sql/repositories.py:100-125 bootstrap_schema 在 Alembic 失败时静默降级为 create_all，可能掩盖迁移错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:100-125`
  - 依据：_upgrade_with_alembic 捕获所有异常仅 warning 后返回 False，bootstrap_schema 随即用 create_all 建表。若迁移脚本本身有 bug（例如部分迁移已应用后失败），create_all 不会修复已存在表结构，系统会以错配的 schema 继续运行，产生难以诊断的运行时错误。注释虽称『明确报出并降级』，但仅 warning 级别，生产环境易被忽略。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:280-295 reserve 中 rollback 后 return False 但未提交 movement 之外的清理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:280-295`
  - 依据：row 为 None 时 rollback 并返回 False，此时没有需要提交的变更，rollback 是安全的清理。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:395-410 append 吞掉 IntegrityError 但未区分唯一约束与其他完整性错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:395-410`
  - 依据：append 捕获 IntegrityError 后一律 rollback 并静默返回，注释称「唯一约束命中 = 该偏好已存在」。但 IntegrityError 也可能来自 NOT NULL 违反、外键失败、CHECK 约束等，这些是真实数据错误，静默吞掉会让调用方误以为偏好已保存。应检查异常的具体约束名或错误码。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:70-85 create_engine 对 sqlite 未设置 pool_pre_ping 等，但更关键的是 WAL PRAGMA 在连接事件中执行可能失败被吞（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:70-85`
  - 依据：connect 事件中执行 PRAGMA 若失败会抛异常导致连接建立失败，不会被静默吞掉；busy_timeout 与 WAL 是合理的。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/sql/repositories.py:232-258 save 中 merge 订单后 delete 订单行再 add_all，未 flush 前 merge 可能未插入导致外键顺序问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:232-258`
  - 依据：SQLAlchemy 的 unit of work 会在 commit 时按依赖顺序 flush：先插入/更新 OrderRow，再执行 delete，再插入 OrderLineRow。delete 通过 db.execute 立即发出，但此时 OrderRow 的 merge 尚未 flush；若订单是新建的，delete 语句在订单行不存在时无影响，随后 add_all 的订单行在 flush 时会先插入 OrderRow 再插入行。因此顺序由 SQLAlchemy 保证，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/sql/repositories.py:240-250 SqlOrderRepository.save 中 merge 与 delete 之间未 flush，若订单行有外键约束且订单为新建，delete 先于 OrderRow 插入执行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:240-250`
  - 依据：delete 针对 OrderLineRow，订单新建时无行可删，不会触发外键问题；OrderRow 的插入在 commit flush 时先于 OrderLineRow 插入。SQLAlchemy 的依赖排序保证正确顺序。

## 争议（需裁决）

- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:44-52 InMemoryOrderRepository.next_order_id 与 save 非原子，并发下单可能撞单号（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:44-52`
  - 依据：next_order_id 通过 itertools.count 取号，save 单独写入 dict，两者之间没有锁也没有原子性。虽然 itertools.count 的 next() 在 CPython 下是原子的（不会取到重复号），但取号与 save 之间若发生异常或调用方在取号后未保存，号会被浪费；更关键的是 next_order_id 与 save 之间没有事务边界，若调用方在取号后、save 前有 await 点且失败，订单号空洞。此外，若未来把 next_order_id 改成基于 len(self._orders)+1 之类的实现，并发下会直接撞号。当前实现本身取号不重复，但缺少与 save 的原子性保证，属于设计缺陷。
  - 争议对手：868f79149b21
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:175-195 append_turn 的 turn_index 取 max+1 在并发下撞号，且无唯一约束兜底（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:175-195`
  - 依据：注释自承「同会话并发写有极小概率撞号，撞号只影响展示顺序不影响数据完整性」。但 list_turns 用 order_by(turn_index) 排序，撞号后两条消息顺序不确定，且若表上 (session_id, turn_index) 有唯一约束则会直接抛 IntegrityError 导致消息丢失。注释说「不影响数据完整性」并不成立——撞号本身不丢数据，但若存在唯一约束则丢；即使无约束，展示顺序错乱也是可观察缺陷。
  - 争议对手：13d060078bf5
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/repositories.py:205-220 list_turns 的 limit 未与 order_by 配合分页语义，取的是最早 N 条而非最近 N 条（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:205-220`
  - 依据：list_turns 按 turn_index 升序取 limit 条，返回的是会话最早的 N 条消息。对于长会话，注入上下文时应取最近 N 条，否则模型看到的是陈旧对话开头而丢失最新上下文。方法名与默认 limit=50 暗示取最近记录，但实现取最早记录。
  - 争议对手：3e7e071201da, 95767705c138

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：27｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 36，估计总体 36.7778
- 待补检分组：app, app/application/memory, app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/queue, app/infrastructure/rerank, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `36316f1e43cb` | 3 | 0 | `reader_miss` | 0.0% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.0% |
| `4ad98b411bb7` | 3 | 0 | `reader_miss` | 0.0% |
| `4fcaf3c8939f` | 3 | 0 | `reader_miss` | 0.0% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.0% |
| `654d43b51949` | 3 | 0 | `reader_miss` | 0.0% |
| `6f1585325107` | 3 | 0 | `reader_miss` | 0.0% |
| `6f7ff70921bd` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 17 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 3 | 3 | 3 | 3 | 2 | 0 | 0 | 3 |
| `app/infrastructure/queue` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rag` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 8%（单元格值 = 独立 Agent 数）
