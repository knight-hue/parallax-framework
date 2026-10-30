# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 42 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：44
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：81 个节点 / 123 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 43 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **42** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:30-38 _cosine 对 NaN/Inf 向量不设防，排序结果不确定（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-38`
  - 依据：embedding 网关正常返回有限浮点，norm 为 0 已处理。NaN 输入属于上游数据损坏，且 sort 对 NaN 的比较虽不稳定但不会崩溃，影响有限。不认定为缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:127-127 created_at 为字符串，_latest_first 按字符串排序依赖 ISO 格式一致性（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:127-127`
  - 依据：created_at 是 str，_latest_first 直接按字符串倒序排序。默认生成的是 datetime.now(timezone.utc).isoformat()，格式一致时字典序等于时间序。但若持久化层（JSON 文件实现）读回时写入的是不同格式（如带 'Z' 后缀、或本地时区偏移 '+08:00'、或省略微秒），字典序与真实时间序会不一致，导致“最新优先”选错条目。领域对象未对 created_at 格式做任何约束或校验，属于隐式契约。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:88-91 select 中 top_k<=0 时丢弃全部 like，与文档语义可能不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：top_k<=0 时返回 dislikes 是刻意的安全底线设计，注释明确说明“只保留安全底线，正向偏好全部让位”。调用方传 0 表示不要正向偏好，行为一致，不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/application/prompts/loader.py:15-18 load_prompts 使用 lru_cache 缓存可变 dict，调用方修改会污染全局（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:15-18`
  - 依据：lru_cache 返回同一个 dict 对象，若调用方原地修改会污染缓存。但当前仓库内没有调用方修改该 dict 的证据，且这是常见的只读配置加载模式。缺少证据表明存在实际错误行为，因此不判定为缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:213-222 rerank 返回分数数量与候选数不一致时索引越界或静默错配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-222`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标取值，但未校验 rerank_scores 的长度是否等于 len(scored)。若 Reranker 实现返回的分数少于候选数（例如服务端截断、过滤空文档、或返回 top_k 而非全量），会抛 IndexError；该异常被上层 except 捕获后降级为按向量分排序，看似“安全”，但实际是静默吞掉了 rerank 结果，且 rerank_applied 保持 False，调用方无法区分“reranker 未配置/异常”与“reranker 返回格式不符”。若返回分数多于候选数则多余分数被忽略。这是对 Reranker 端口契约的隐式假设，缺少防御。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:78-86 tokenize 对纯 CJK 单字 chunk 不生成 2-gram，单字查询无法命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:78-86`
  - 依据：len(chunk) >= 2 才补 2-gram，单字中文查询（如“鞋”）只会把整字加入 terms，仍可与文档 terms 中的整字匹配（文档 chunk 也会加入整字）。因此单字查询并非完全无法命中，只是缺少 2-gram 扩展。属于召回质量取舍，不是缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:186-195 _to_rejected 中 convert 可能抛异常导致整个检索失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:186-195`
  - 依据：_to_rejected 与 _within_price_cap 都直接调用 self._tariff.rates.convert(...)，未捕获异常。若商品价格币种不在汇率表中（或目标币种不支持），convert 会抛异常，而该调用发生在 execute 的过滤循环内、不在任何 try 块中，会导致整个检索请求失败——仅仅因为某个被过滤候选的币种无法折算。相比之下 _to_card 对 tariff.quote 的 ValueError 做了兜底，过滤路径却没有，处理不一致。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:154-162 filtered_out 只保留前 3 条，且未按分数排序，摘要可能不代表最相关被过滤项（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:154-162`
  - 依据：filtered_out 按 scored 的原始顺序取前 _FILTERED_OUT_LIMIT 条。scored 在向量路径下已按分数降序（_rerank 排序或向量分顺序），关键词路径也排序过，因此前几条即最相关项。截断是刻意的上下文控制，不构成缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:196-200 价格上限过滤使用 primary_sku 价格而非到手价，与文档“到手价内联”口径不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-200`
  - 依据：_within_price_cap 只把 primary_sku().price 折算到目标币种后与 price_max_major 比较，未计入运费与关税。而商品卡在 ship_to 命中时会内联 landed_price（小计+运费+关税）。结果是：一个商品小计在预算内、但加上运费/关税后到手价超预算的商品会通过过滤并展示，其 landed_price 却高于用户设定的 price_max_major，造成“过滤说符合预算、卡片显示超预算”的自相矛盾。文档明确“到手价在检索链路内联计算”，价格硬约束理应按到手价口径判断。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:296-300 库存覆盖只更新已存在的 sku_id，缺失的 sku 静默保留初始库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-300`
  - 依据：get_many 返回的映射若缺少某 sku_id（例如库存表尚未初始化该 SKU），代码保留 Sku.stock 初始值。这是有意的退化策略，且 docstring 已说明“查询失败退化为初始库存展示”。缺失条目与查询失败语义相近，不构成明确缺陷。
- **[error_handling/high]** [error_handling] app/application/usecases/order_usecases.py:175-181 取消订单先回补库存再保存，save 失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:175-181`
  - 依据：execute 中先 order.cancel(reason) 修改内存状态，然后循环 release 回补库存，最后才 order_repo.save(order)。如果 save 抛异常（DB 故障、乐观锁冲突），订单在持久层仍是未取消状态，但库存已经被回补。调用方重试取消时，状态机允许再次 cancel（因为持久层未变），于是再次 release，造成库存被重复回补（超卖）。注释“重复取消会被状态机挡在上一步”只在 save 成功时成立。
- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:118-128 幂等键在订单保存前登记，崩溃窗口内重投会重复下单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-128`
  - 依据：record 在 save 之后调用，但 _replay 的注释明确承认“登记后写单前崩溃”返回 None 让调用方继续新建。若 record 成功而 save 失败/进程崩溃，键已指向一个不存在的订单；重投时 _replay 返回 None，于是重新扣库存并新建订单，而旧键仍指向不存在的 order_id，幂等语义被破坏（虽然不会产生两张订单，但键与订单映射错误，且首次扣减的库存未回滚）。更关键的是 record 与 save 之间没有事务/补偿，属于跨存储一致性缺陷。
- **[logic/low]** [logic] app/composition.py:1-1 composition 中 use_database 判定与注释/文档不一致（DATABASE_URL 未配时并非 SQLite）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-1`
  - 依据：模块 docstring 声称『DATABASE_URL 未配 → SQLite』，但代码用 settings.database_url != "file" 判定，实际行为取决于 load_settings 的默认值（未在给定文件中）。由于无法看到 Settings 默认值，不能确认这是缺陷；若默认值就是 sqlite URL 则注释与代码一致。故记为 not_a_defect，仅提示需核对默认值。
- **[logic/low]** [logic] app/domain/buyer/preference.py:30-31 BuyerPreference.created_at 默认值在 __post_init__ 中设置，frozen dataclass 用 object.__setattr__ 可行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：frozen dataclass 中通过 object.__setattr__ 修改字段是标准做法，__post_init__ 在 __init__ 末尾调用，此时对象已构造完成，行为正确。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:92-94 运费 round 使用银行家舍入，可能产生 1 分误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:92-94`
  - 依据：Python 内置 round 对 .5 采用银行家舍入，运费金额为整数分，`base * (1 + 0.6*(q-1))` 在 q 使结果为 x.5 时可能向下取整。但这是金额计算的常见可接受误差，且运费基数均为整百分，实际触发概率低，不构成明确缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/embedding/openai_embedding_client.py:47-48 embed() 在 embed_batch 返回空列表时抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:47-48`
  - 依据：embed() 直接取 embed_batch([text])[0]。embed_batch 对非空输入会走分片循环，但若 _MAX_BATCH 被环境变量配置为 0 或负数，range(0, len(texts), _MAX_BATCH) 会抛 ValueError（step 不能为 0）或产生空 range（负数 step 时 range(0,1,-1) 为空），vectors 保持为空，embed() 随即 IndexError。更直接地：若 _MAX_BATCH 为负数，range(0, 1, -1) 为空，embed_batch 返回 []，embed() 抛 IndexError 而非有意义的错误。这是配置边界导致的崩溃，且错误信息完全指不到真因（与文件注释里批评的 JSONDecodeError 同类问题）。
- **[error_handling/medium]** [error_handling] app/infrastructure/embedding/openai_embedding_client.py:74-76 _embed_chunk 未校验返回向量条数与输入条数一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:74-76`
  - 依据：网关若对某批返回少于输入条数的 data（例如部分条目被丢弃、或 index 重复导致 sorted 后仍缺项），这里只按 index 排序后原样返回，不校验 len(ordered) == len(chunk)。embed_batch 用 vectors.extend 拼接，最终返回的向量数会少于 texts 数，且与 texts 的对应关系错位。上层 PreferenceSelector._rank_by_relevance 虽有 len(vectors) != len(likes) 的降级检查，但商品建库路径（bootstrap_product_index）会把错位向量写入索引，造成静默的向量-文本错配，比直接报错更难排查。
- **[performance/low]** [performance] app/infrastructure/embedding/openai_embedding_client.py:55-60 embed_batch 串行分片，大批量时延迟线性叠加（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:55-60`
  - 依据：分片用 for 循环串行 await，每片一次网络往返。商品库 60 条、_MAX_BATCH=10 时需 6 次串行 RTT；若单次 RTT 200ms，总耗时约 1.2s，且随商品数线性增长。分片之间无依赖，可用 asyncio.gather 并发（受网关并发限制约束），串行是明显的可优化点。不过这是性能问题而非正确性缺陷，且并发可能触发网关限流，故定为 low。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:47-48 InMemoryOrderRepository.next_order_id 使用 itertools.count，非线程安全但协程内安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:47-48`
  - 依据：next(self._counter) 在单事件循环内是原子的（无 await 点），不会产生重复单号；多线程场景才可能有问题，但该仓储为开发态单进程使用。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:66-76 InMemoryOrderIdempotencyStore 的 find+record 非原子，存在检查-写入竞态（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:66-76`
  - 依据：find 与 record 各自加锁，但调用方若先 find 再 record，两步之间可被其他协程插入；不过 record 本身是原子的（锁内检查 key 是否存在并返回 False），因此重复键最终仍会被 record 拒绝，不会产生两个订单。真正的幂等保证由 record 的返回值承担，故不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/in_memory_stock_repository.py:17-17 InMemoryStockRepository 未实现 StockRepository 端口（缺少继承）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:17-17`
  - 依据：类未显式继承 StockRepository，但 Python 结构化子类型（Protocol）下只要方法签名一致即可被接受；若端口是 ABC 则会失败，但无法从给定文件确认端口定义，故不作为缺陷报告。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:40-46 InMemoryStockRepository.release 对未登记 SKU 补登记为 quantity，可能凭空造库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:40-46`
  - 依据：注释明确说明这是有意为之（避免库存凭空消失），且 release 只应在 reserve 成功后调用；若对从未 reserve 的 SKU 调用 release 会凭空增加库存，但这是调用方契约问题，仓储行为与 SQL 版一致。
- **[logic/critical]** [logic] app/infrastructure/persistence/json_file_stores.py:137-139 JSONL 追加写使用 "w" 模式，每次写入都会覆盖整个对话文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:137-139`
  - 依据：_append_line 的注释与类文档都声称是“追加写不覆盖”，但实际用 open("w") 打开文件，会截断已有内容。每次 append_turn / append_events / touch_session 都会把整个 .jsonl 文件清空后只写入当前这一条记录，导致历史对话与事件全部丢失。list_turns 因此最多只能看到最后一条记录，多轮对话恢复完全失效。
- **[logic/high]** [logic] app/infrastructure/persistence/json_file_stores.py:168-184 list_turns 未过滤 kind，把 session/event 记录当作对话轮次解析（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:168-184`
  - 依据：list_turns 只跳过 kind 为 None 的行，但 session 记录（kind="session"）和 event 记录（kind="event"）都有 kind，会被继续处理。event 记录没有 role 字段，record["role"] 直接抛 KeyError；session 记录同样没有 role，也会 KeyError。因此只要 touch_session 或 append_events 先写过一行，list_turns 就会崩溃。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:78-86 delete 只删除 kind=="dislike" 的条目，与文档声明的“同 statement 一并清除”不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:78-86`
  - 依据：docstring 明确说“同 statement 的条目一并清除”，但过滤条件额外要求 p.kind == "dislike"，导致 kind=="like" 的同 statement 条目不会被删除。买家说“以后别管塑料了”时，正向偏好仍然残留，行为与文档和业务语义相反。
- **[security/high]** [security] app/infrastructure/persistence/json_file_stores.py:30-32 _safe_name 未做任何清洗，路径穿越防护失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:30-32`
  - 依据：函数注释称“文件名清洗，避免路径穿越”，但实现只是 raw or "anonymous"，对 "../"、"/" 等完全不做处理。buyer_id/session_id 若来自外部输入（如请求参数），可构造 "../../etc/x" 使 _path 拼出目录外的路径，实现任意文件读写。
- **[logic/medium]** [logic] app/infrastructure/persistence/seed_products.py:33-35 P1011 竞品标题含“旅行三件套”，与注释声称的“避开正面相撞”不符，可能推翻已有 top-1 单测（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:33-35`
  - 依据：模块 docstring 明确声明新增语料“刻意避开与 P1001 在‘旅行三件套 抗造’这条 query 上正面相撞（竞品 P1011 不写‘抗造’）”，但 P1011 的标题是“Voyager 旅行三件套 记忆棉款”，描述里也含“三件套 轻便 长途飞行 出差 旅行必备”。虽然它不含“抗造”，但 query 分词后“旅行三件套”这一核心短语在 P1011 标题中完整命中，且 P1011 价格 139 低于 P1001 的 189，若排序含价格/热度因子，P1011 有可能挤到 top-1，从而推翻依赖 P1001 为 top-1 的既有单测。注释与实际数据不一致，属于设计意图与实现脱节。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:51-53 P1016 描述含“塑料箱体”，与“不要塑料”类 query 的负向意图冲突但未做标记（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:51-53`
  - 依据：P1016 描述含“PC聚碳酸酯硬壳 塑料箱体”，看起来会在“不要塑料”query 下被误召回。但模块 docstring 说明扩充目的是“造出区分度”，刻意放入含易混淆项（如“旅行三件套”vs“毛巾三件装”）以及材质/价位不同的同品类候选，P1016 正是作为“塑料箱体”的负例存在，用于检验召回/排序能否区分“无塑料”正向商品与“塑料”负向商品。这是有意的评测语料设计，不是缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:71-73 P1050 与 P1015 同为铝框/铝镁合金行李箱但价格差 2.5 倍，属有意梯度非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:71-73`
  - 依据：P1050 全铝镁合金 2999 CNY 与 P1015 铝框 1199 CNY 形成高/中价位梯度，docstring 明确说明要“价格与 ships_to 分布拉开”以制造区分度。两者标题、材质描述、价位均不同，属于有意的同品类多候选设计，不是数据错误。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:88-90 P1023 价格币种为 USD 但数值 189 与同类 CNY 商品量级不一致，跨币种排序/比价会失真（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:88-90`
  - 依据：P1023 的 SKU 价格为 189.0 USD，而同品类 P1022 为 299 CNY、P1024 为 89 CNY。189 USD 约合 1300+ CNY，远高于同品类其他商品，若评测或排序逻辑直接比较 Money 的 major 数值而不做币种换算，会把 P1023 误判为高价商品；若做了换算则其价格又明显偏离“降噪耳机”合理区间（同品类 P1004 为 219 USD 头戴式）。种子数据中混用币种且数值未按汇率对齐，会让价格相关评测指标失真。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:1-1 SqlConversationStore.append_turn 的 max+1 在并发下撞号（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：模块 docstring 已明确承认该风险并说明撞号只影响展示顺序；若表上 (session_id, turn_index) 有唯一约束则会抛 IntegrityError，但无法从给定文件确认约束，故不报告为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/sql/repositories.py:1-1 SqlStockRepository.release 补登记分支先 commit 后写 movement，且第二次 commit 前未 add 到同一事务（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：该分支 db.add(SkuStockRow) 后 commit，再 _log_movement 后再次 commit，movement 会被提交；只是分两个事务，非原子但不会丢数据。文件被截断无法引用精确代码。
- **[logic/low]** [logic] app/infrastructure/persistence/sql/repositories.py:1-1 SqlStockRepository.release 在补登记分支中先 commit 再写 movement，movement 可能丢失（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:1-1`
  - 依据：被截断的文件无法定位精确行号，且该分支中 db.add 后 commit 再 _log_movement 再 commit 实际仍会提交 movement（第二次 commit 生效），不构成数据丢失。
- **[boundary/low]** [boundary] app/infrastructure/persistence/sql/tables.py:213-217 OrderIdempotencyRow 的 key 长度 80 可能不足以容纳“任务+订单内容”哈希（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:213-217`
  - 依据：注释说 key 由“任务 + 订单内容”构成，若直接拼接原始内容可能超 80 字符，但通常实现会做哈希（如 sha256 十六进制 64 字符），在 80 以内。无法从本文件确认生成方式，故不判定为缺陷。
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/tables.py:148-152 BuyerPreferenceRow 唯一约束列与注释/去重语义不一致（缺 kind）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:148-152`
  - 依据：注释写“幂等去重从应用层下沉到数据库约束”，约束名为 uq_pref_buyer_kind_statement，但 UniqueConstraint 只包含 (buyer_id, statement)，漏掉 kind。而 json_file_stores.delete 的 docstring 明确说唯一约束是 buyer+kind+statement，允许同一 statement 同时存 like 与 dislike。SQL 实现下插入同 statement 的 like 与 dislike 会触发唯一冲突，与文件实现行为不一致。
- **[performance/low]** [performance] app/infrastructure/persistence/sql/tables.py:78-78 ConversationMessageRow 的索引只含 session_id，与索引名 ix_msg_session_turn 不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:78-78`
  - 依据：索引名暗示按 (session_id, turn_index) 复合索引，但实际只索引 session_id。按会话+轮次排序/过滤的查询无法利用 turn_index，数据量大时退化为排序扫描。
- **[logic/medium]** [logic] app/infrastructure/queue/redis_stream_queue.py:213-228 claim_stale 只处理正常流，大请求流中崩溃的消息永远不会被领回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/queue/redis_stream_queue.py:213-228`
  - 依据：enqueue 会把 priority>0 的任务写入 _LARGE_STREAM，consume 也从两条流读取，但 claim_stale 只对 _STREAM 调用 xautoclaim。worker 崩溃后，_LARGE_STREAM 中未 ack 的消息留在 pending 列表，没有任何代码去认领它们，长会话任务会永久卡住。这与模块文档“worker 崩溃后未 ack 的消息能被重新领取”的承诺不符。
- **[logic/low]** [logic] app/infrastructure/queue/redis_stream_queue.py:78-90 get_status 在 queued 状态下把整条队列 lag 当作 queue_position（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/queue/redis_stream_queue.py:78-90`
  - 依据：queue_position 被赋值为 depth()，即两条流未被读取的消息总数，而不是该任务在队列中的实际位置。所有 queued 任务会得到相同的、随全局队列长度变化的“位置”，前端展示的排队位置是错误的。虽然不影响业务正确性，但属于可观测性/API 语义缺陷。
- **[resource_leak/low]** [resource_leak] app/infrastructure/queue/redis_stream_queue.py:148-152 consume 中 in_flight 清理逻辑在无批次时可能遗漏已完成任务（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/queue/redis_stream_queue.py:148-152`
  - 依据：当 batches 为空时执行 in_flight = {task for task in in_flight if not task.done()}，会清理已完成任务；当 free_slots==0 时用 asyncio.wait 等待并清理。两条路径都会移除 done 的任务，不会无限增长。虽然 done 任务的异常未被 retrieve，但 _handle_one 内部已捕获所有异常，不会产生未取回的异常警告。因此不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/rag/category_knowledge.py:76-82 bootstrap 用 document_id 去重，但文件内容变更后不会重新入库（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/rag/category_knowledge.py:76-82`
  - 依据：以文件名 stem 作为 document_id 并跳过已存在文档，是文档声明的“幂等”策略；内容更新需手动清理，属于设计取舍而非实现错误。
- …另有 2 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:137-152 向量召回成功但结果为空时，错误地降级为关键词召回并覆盖 recall_strategy（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:137-152`
  - 依据：当 embedder 与 vector_index 均可用且 _vector_recall 正常返回空列表（即向量库确实没有匹配项）时，recall_strategy 已被置为 'embedding_only'，但 scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支，执行关键词召回并把 recall_strategy 改回 'keyword_2gram'。这有两个问题：(1) 向量检索本身是健康的，却因为“无命中”被当作降级，recall_strategy 标注失真，与文档中“embedding 服务异常时兜底”的语义不符；(2) 关键词召回会返回向量库中不存在的商品，绕过向量索引的过滤/一致性，导致同一 query 在向量库为空结果时给出与向量语义无关的结果。正确做法应区分“召回异常”与“召回为空”。
  - 争议对手：5ae9dff859de

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：31｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/infrastructure/persistence, app, app/application/memory, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/queue, app/infrastructure/rerank, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `001a0c61fa51` | 1 | 3 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `254c9186a2ba` | 1 | 1 | `partition_gap` | — |
| `36316f1e43cb` | 1 | 0 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `48f4b9cac1c9` | 1 | 2 | `partition_gap` | — |
| `4ad98b411bb7` | 1 | 0 | `partition_gap` | — |
| `4fcaf3c8939f` | 1 | 0 | `partition_gap` | — |
| `52e48d38e8e3` | 1 | 2 | `partition_gap` | — |
| …另有 21 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/application/usecases` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 |
| `app/infrastructure/persistence` | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| `app/infrastructure/queue` | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `app/infrastructure/rag` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 |

矩阵填充率 23%（单元格值 = 独立 Agent 数）
