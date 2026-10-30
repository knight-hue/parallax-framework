# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 54 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：58
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：94 个节点 / 155 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 56 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **54** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[api_misuse/medium]** [api_misuse] app/application/memory/preference_selector.py:108-111 _rank_by_relevance 中 `not query_vector` 对 numpy 数组会抛 ValueError（truth value ambiguous）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:108-111`
  - 依据：`if len(vectors) != len(likes) or not query_vector:` 中 `not query_vector` 依赖 query_vector 的 __bool__。若 EmbeddingClient.embed 返回 numpy.ndarray（常见实现），`not ndarray` 会触发 `ValueError: The truth value of an array with more than one element is ambiguous`。该异常发生在 try 块之外，不会被降级捕获，会直接向上抛出，违背「选偏好失败不阻断对话」的承诺。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:30-38 _cosine 对 numpy 数组使用 sum(a*b for ...) 可工作但 zip 长度不一致时静默截断——已有长度校验，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-38`
  - 依据：_cosine 首先检查 len(left)!=len(right) 返回 0.0，避免 zip 静默截断。逻辑正确。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:55-64 render_preference_hint 在 preferences 为空时仍输出空块，可能注入无意义的 <buyer-preferences> 标签（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:55-64`
  - 依据：render_preference_hint 是纯渲染函数，是否在空列表时调用由调用方决定；select 在空列表时返回 []，调用方通常会跳过渲染。没有代码证据表明此处会注入空块造成错误行为。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:88-91 select 中 top_k<=0 时直接返回 dislikes，但未校验 top_k 为负数与 0 的语义差异——行为符合注释，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：注释明确说明 top_k<=0 时只保留安全底线，返回 dislikes 是预期行为。不构成缺陷。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:118-120 _rank_by_relevance 用 `p in picked` 复原顺序，依赖 BuyerPreference 的 __eq__；若 dataclass 未定义 eq 或存在重复 statement 的偏好，会错误匹配/丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-120`
  - 依据：`return [p for p in likes if p in picked]` 通过相等性判断复原顺序。若 BuyerPreference 是 dataclass（默认 eq=True 按字段比较），两条字段完全相同的偏好会被视为相等，导致 picked 中只保留一条时两条都被输出（数量超过 top_k）；若 BuyerPreference 定义了自定义 __eq__ 或未定义（默认身份比较），则行为依赖实现。更关键的是：当 likes 中存在两条内容相同但 created_at 不同的偏好时，`p in picked` 会把两条都保留，破坏 top_k 截断。_latest_first 中同样使用 `p in newest`，存在相同问题。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:122-125 _latest_first 同样用 `p in newest` 复原顺序，重复偏好会突破 top_k（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:122-125`
  - 依据：与 _rank_by_relevance 相同：`[p for p in likes if p in newest]` 在存在相等偏好时会把所有相等项都保留，导致返回数量超过 top_k。这是关闭相关性排序时的默认路径，影响面更大。
- **[logic/low]** [logic] app/application/prompts/loader.py:16-19 load_prompts 使用 lru_cache 缓存，配置文件更新后不会重新加载（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:16-19`
  - 依据：lru_cache(maxsize=1) 使 load_prompts 在进程生命周期内只读一次文件。对于提示词这种启动时加载、运行期不变的配置，这是预期行为而非缺陷。若需要热更新则需额外机制，但当前 docstring 未声明支持热更新。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:218-228 _rerank 中 rerank_scores 长度与 scored 不一致时索引越界或静默错配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:218-228`
  - 依据：_rerank 直接用 `rerank_scores[i]` 按 scored 的下标取值，未校验 rerank_scores 长度是否等于 len(scored)。若 Reranker 实现返回的分数条数少于文档数（例如 HTTP reranker 丢弃了部分结果，或返回空列表），会抛 IndexError；若多于文档数则多余分数被忽略。IndexError 会被外层 except 捕获并降级为按向量分排序，但此时 recall_strategy 仍为 embedding_only，行为上虽可接受，但属于对下游契约的隐式假设，且当 reranker 返回乱序/缺失时无法察觉。
- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:196-210 _to_rejected 与 _within_price_cap 对 primary_sku 价格做币种转换，但未处理转换异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-210`
  - 依据：ExchangeRateTable.convert 在目标币种缺失时可能抛异常，但 _to_card 中对 tariff.quote 的 ValueError 做了捕获，而 _within_price_cap/_to_rejected 未捕获。不过 spec.target_currency 通常来自受控配置，且若 convert 抛异常会向上冒泡到 execute 调用方，属于显式失败而非静默错误。未确认存在具体缺陷路径，故记为 not_a_defect。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:130-145 向量召回成功但返回空结果时，仍会走关键词召回并覆盖 recall_strategy，但 embedding 分支的 scored 为空时 elif 逻辑正确；然而 rerank 分支条件 `recall_strategy == "embedding_only" and scored` 在向量召回返回空列表时不会进入 rerank，随后 `elif not scored` 触发关键词召回——这是预期降级，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:130-145`
  - 依据：当向量召回成功但返回空列表时，recall_strategy 被设为 embedding_only，scored 为空。第一个 if 条件 `recall_strategy == "embedding_only" and scored` 为 False，进入 elif `not scored` 为 True，执行关键词召回并重置 recall_strategy 为 keyword_2gram。这是文档声明的降级链行为，逻辑自洽。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:240-250 关键词召回分数并列时排序不稳定，与向量分支的 product_id 兜底排序不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:240-250`
  - 依据：_keyword_recall 中 `candidates.sort(key=lambda pair: pair[0], reverse=True)` 只按分数排序，分数并列时依赖 list_all() 的返回顺序。虽然 execute 后续对 filtered 做了 `(-score, product_id)` 的稳定排序，但 filtered 只包含通过硬约束的候选，且 filtered_out 的收集顺序依赖 scored 顺序——当并列分数候选超过 _FILTERED_OUT_LIMIT 时，哪些被记入 filtered_out 会随 list_all 顺序变化，导致 filtered_out 摘要不可复现。这与代码注释中强调的「同一 query 不同次运行结果不同」的可复现性目标相悖。
- **[boundary/low]** [boundary] app/application/usecases/order_usecases.py:78-100 PlaceOrderUseCase 未校验重复 SKU，同一 SKU 多行会分别 reserve 但回滚逻辑正确性依赖顺序（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:78-100`
  - 依据：items 中若出现相同 sku_id 的多行，resolved 会保留多行，reserve 会分别扣减，OrderLine 也会生成多行。这在业务上可能不理想，但库存扣减与回滚都按实际 reserve 成功的条目记录，不会造成超卖或漏回滚。属于业务口径问题而非代码缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:113-118 幂等键在订单保存前登记失败时，_replay 找不到订单会抛错而非重试（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:113-118`
  - 依据：_replay 的 docstring 声称「找不到（登记后写单前崩溃）返回 None，让调用方继续新建」，但在 record 冲突分支里，若 _replay 返回 None，代码直接 raise ValueError。这意味着当赢家进程在 record 之后、save 之前崩溃时，输家既回滚了库存又抛错，整个下单失败，而幂等键已被占用，后续重投会一直命中 _replay 返回 None 然后继续新建——但键已存在，record 又会失败，形成死循环式失败。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:108-118 PlaceOrderUseCase 幂等键冲突回滚后未删除已保存的订单，导致库存与订单不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-118`
  - 依据：execute 在 save(order) 之后才调用 idempotency.record。若并发下另一路先登记了同一键，claimed 为 False，代码只回滚库存（_rollback(reserved)），却没有删除或作废刚刚 save 的订单。结果是：库存被释放，但订单仍留在 order_repo 中，形成「订单存在但库存未扣」的超卖/账实不符。此外该订单的 order_id 与幂等键无关联，后续查询会看到一张幽灵订单。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:175-182 CancelOrderUseCase 先回补库存再 save，save 失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:175-182`
  - 依据：execute 中先 order.cancel(reason) 修改内存状态，然后循环 release 回补库存，最后才 save(order)。若 save 抛异常（DB 故障、乐观锁冲突等），库存已经回补但订单状态未持久化为 cancelled。调用方重试时，order 从仓库重新加载仍是未取消状态，cancel 再次通过，库存被第二次回补，造成库存虚增。注释「重复取消会被状态机挡在上一步」只在 save 成功的前提下成立。
- **[error_handling/low]** [error_handling] app/composition.py:78-88 _prompt_fingerprint 路径拼接依赖 __file__ 位置，打包/安装后可能读不到提示词（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:78-88`
  - 依据：函数已用 try/except OSError 兜底返回 "noprompt"，注释也说明读不到不阻断启动。最坏情况是语义缓存 namespace 不含 prompt 指纹，导致改 prompt 后旧缓存不失效——这是降级而非崩溃，且属于已知取舍。
- **[logic/medium]** [logic] app/composition.py:232-250 composition.py 中 use_database 判断与 create_engine 对空 database_url 的处理可能不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:232-250`
  - 依据：use_database = settings.database_url != "file"，即空字符串或 None 也会走数据库分支并调用 create_engine。文档字符串声称「DATABASE_URL 未配 → SQLite」，说明 create_engine 对空值应回退到 SQLite。无法从给定文件确认 create_engine 的实现，因此不能断定缺陷。
- **[resource_leak/low]** [resource_leak] app/composition.py:155-160 shutdown 未关闭 task_queue/backplane 的 Redis 连接，且 cache.close 与 backplane 共享 client 可能重复关闭（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:155-160`
  - 依据：backplane 与 task_queue 都复用 cache.client（同一 Redis 连接），cache.close() 关闭该 client 即覆盖两者；没有独立连接需要释放。未发现泄漏。
- **[logic/low]** [logic] app/domain/buyer/preference.py:22-32 BuyerPreference 的 created_at 默认值在 __post_init__ 中设置，但 dataclass frozen 下 object.__setattr__ 可行；kind 校验正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-32`
  - 依据：frozen dataclass 中 __post_init__ 使用 object.__setattr__ 设置 created_at 是标准做法，kind 与 statement 校验逻辑正确。未发现缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:109-109 quote 中 freight 计算使用 round 后可能因浮点误差产生 1 分偏差，但属可接受舍入（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:109-109`
  - 依据：round 对整数乘浮点系数做四舍五入，结果确定；1 分偏差属于业务可接受的舍入，不构成缺陷。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:116-117 tariff_rate 使用 rate_table.get(category, rate_table["*"]), 但 EU/JP/SG 只有 "*" 键，category 命中时仍走兜底——行为正确但 category 参数被静默忽略（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:116-117`
  - 依据：对于只有 "*" 的国家，get(category, rate_table["*"]) 会返回 "*" 的费率，这是设计上的兜底行为，符合注释「未列品类走 "*" 兜底」。不构成缺陷。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:33-39 免税额度按目的国硬编码但 US/EU/JP/SG 的汇率折算常量与 ExchangeRateTable 实际汇率可能不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:33-39`
  - 依据：_DE_MINIMIS_CNY_MINOR 用硬编码汇率（US 800*710、EU 150*780、JP 10000*5、SG 400*530）把外币免税额度折成 CNY 分，而 quote 中 subtotal 通过 self.rates.convert 使用 ExchangeRateTable 的动态汇率折算。当实际汇率偏离硬编码常量时，免税判定会与真实外币额度不符：例如 US 实际汇率若为 7.0 而非 7.10，800 USD 的真实 CNY 额度应为 5600 元，但代码用 5680 元，导致本应缴税的订单被判为免税（或反之）。这是硬编码汇率与动态汇率表之间的口径不一致，属于真实缺陷。
- **[boundary/low]** [boundary] app/infrastructure/embedding/openai_embedding_client.py:44-45 embed() 在 embed_batch 返回空列表时索引越界（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:44-45`
  - 依据：embed 调用 embed_batch([text])，texts 非空，embed_batch 不会走 `if not texts: return []` 分支。除非 _embed_chunk 返回空列表（网关返回 data 为空数组），此时 [0] 会 IndexError。但 data 为空数组属于网关异常响应，抛 IndexError 虽不友好但仍是显式失败，且会被上层降级捕获。未构成静默错误，记为 not_a_defect。
- **[boundary/medium]** [boundary] app/infrastructure/embedding/openai_embedding_client.py:70-76 _embed_chunk 按 index 排序后未校验返回条数与请求条数一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:70-76`
  - 依据：_embed_chunk 只检查 body 中是否有 "data" 键，然后按 index 排序返回 embedding 列表，未校验 len(ordered) == len(chunk)。若网关返回的 data 条数少于请求条数（部分失败、截断），embed_batch 的 vectors 长度会小于 texts 长度，调用方按位置对应文本与向量时会错配——例如 embed() 取 [0] 可能拿到错误文本的向量，建库时向量与商品错位。这是静默的数据损坏，比抛异常更危险。
- **[error_handling/medium]** [error_handling] app/infrastructure/embedding/openai_embedding_client.py:47-56 embed_batch 分片串行请求，任一分片失败会丢弃已获取的向量且无重试（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:47-56`
  - 依据：embed_batch 在循环中逐片调用 _embed_chunk，若第 N 片失败（网络抖动、网关 5xx、空 body），异常直接向上抛出，已成功获取的前 N-1 片向量全部丢弃，且没有重试。对于建库场景（60 个商品分 6 片），一次瞬时失败会导致整批失败，而调用方 bootstrap_product_index 会吞掉异常降级到关键词召回，表现为「向量检索静默失效」。这与文件头注释描述的故障模式一致，但代码未提供任何重试或部分成功保留机制。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:62-73 InMemoryOrderIdempotencyStore 的 find 与 record 分离，存在检查-写入竞态（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:62-73`
  - 依据：find 与 record 各自加锁，调用方若先 find 再 record 确实存在 TOCTOU 窗口，但 record 本身是原子的「不存在才写入并返回 True」，调用方应以 record 的返回值作为是否首次处理的判据。类 docstring 也明确说明仅用于单进程开发态。因此 record 的原子性足以保证幂等键不被重复登记，不构成缺陷。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/in_memory_stock_repository.py:17-58 InMemoryStockRepository 未实现 StockRepository 协议（缺少接口方法）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:17-58`
  - 依据：该类在 composition.py 中被赋给 stock_repo: StockRepository 并传给 CatalogSearchUseCase/PlaceOrderUseCase/CancelOrderUseCase。它实现了 reserve/release/get/get_many/seed，与 SqlStockRepository 的方法集一致；Python 是结构化鸭子类型，只要调用方用到的方法都存在即可。无法从给定文件确认 StockRepository 协议还要求别的方法，因此不判定为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:56-60 seed 使用 setdefault 不覆盖已有值，但负库存或非法 stock 值未校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:56-60`
  - 依据：seed 接受任意 int（含负数），但商品目录中的 stock 由领域数据保证非负；reserve 对 quantity<=0 抛错，负库存会导致 reserve 永远返回 False 而非超卖。没有证据表明 seed 会收到负值，且这是数据契约问题而非本方法缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:38-46 release 对未登记 SKU 直接补登记为 quantity，可能凭空造出库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:38-46`
  - 依据：注释明确说明这是有意设计：未登记 SKU 不该出现，补登记而非静默丢弃。若 release 被调用说明此前 reserve 成功过（或 seed 过），补登记 quantity 与「回滚一次扣减」语义一致。只有在 release 被错误调用（无对应 reserve）时才会虚增库存，但那是调用方缺陷，不是本方法缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:52-54 get_many 对重复 sku_id 的迭代器只读取一次，行为正确但依赖 dict 推导（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:52-54`
  - 依据：get_many 在锁内构造字典推导，对 sku_ids 迭代一次；若传入生成器也能正确消费。返回的是新 dict，调用方修改不会影响内部状态。未发现缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:108-109 JsonFileSessionStore.save 直接覆盖写，非原子写可能留下半截 JSON（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:108-109`
  - 依据：write_text 不是原子操作，进程在写入中途崩溃会留下损坏文件，load 时 pydantic 解析失败。但该实现明确标注为「零外部依赖的默认形态」「仅用于本地开发与排查」，且 load 返回原始字符串由上层解析，损坏属于开发态可接受风险，不构成需要报告的缺陷。
- **[logic/critical]** [logic] app/infrastructure/persistence/json_file_stores.py:148-150 JsonFileConversationStore._append_line 用 "w" 模式打开文件，每次追加都会覆盖整个 JSONL 文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:148-150`
  - 依据：方法名为 _append_line，docstring 也声明「一行一条记录，追加写不覆盖」，但实际用 open("w") 打开，会截断文件。因此每次 append_turn / append_events / touch_session 都会把该 session 之前的所有记录清空，只剩最后写入的那一条。list_turns 只能读到最后一轮，多轮对话历史与事件轨迹全部丢失；touch_session 的「已存在则跳过」判断也会因为文件始终存在而失效（首轮之后不再写 session 元信息，但文件内容已被后续 turn 覆盖，find_session 找不到 kind=session 记录）。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:78-86 JsonFilePreferenceStore.delete 只删除 kind=="dislike" 的条目，与 docstring 声明的「同 statement 一并清除」不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:78-86`
  - 依据：docstring 明确说「按 statement 而不分 kind……同 statement 的条目一并清除」，但过滤条件额外要求 p.kind == "dislike"。当同一 statement 同时以 like 与 dislike 存在时，like 条目不会被删除；若只有 like 条目，delete 返回 False 且不写文件，买家「忘掉这条说法」的意图无法实现。
- **[boundary/low]** [boundary] app/infrastructure/persistence/seed_products.py:175-190 _build_extra 中 ships_to 直接 list(ships_to) 复制，但 skus 列表推导使用 f-string 拼接 pid，若 pid 含特殊字符会破坏 SKU id 格式（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:175-190`
  - 依据：复核后认为：_EXTRA_SPECS 中所有 pid 均为「P」+数字的固定格式，不含特殊字符，f"{pid}-{suffix}" 生成的 SKU id 与 P1001~P1010 的手写格式（如 P1001-S1）一致。当前数据下不存在边界问题，属于安全实现。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:118-120 P1033 亮点值「天然楱竹」为错别字，应为「楠竹」，影响关键词召回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:118-120`
  - 依据：P1033 的 highlights 值为「天然楱竹，无塑料」，「楱」是错别字（应为「楠」）。该字段会进入商品索引参与关键词召回，若用户 query 含「楠竹」将无法命中该商品的亮点字段，造成召回漏检。虽然描述字段含「竹制餐具」可部分兜底，但亮点字段的错字是可直接引用的数据错误。
- **[logic/low]** [logic] app/infrastructure/persistence/seed_products.py:88-90 P1023 SilentBuds 价格币种为 USD 但数值 189 与同类 CNY 商品不可比，且 ships_to 含 CN 却以美元计价（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:88-90`
  - 依据：P1023 的 SKU 价格为 189.0 USD，而同品类竞品 P1022 为 299.0 CNY、P1004 为 219.0 USD。种子数据中混用币种本身是设计（P1004/P1010 也用 USD），但 P1023 的 ships_to 包含 "CN"，即向中国配送却以美元标价，而 P1004 同样 ships_to 含 CN 也用 USD——这说明混币种是既有模式而非本文件引入的新问题。真正的问题在于：P1023 作为「降噪竞品」被放入以 CNY 为主的数码配件梯度中，若下游价格排序/过滤未做币种换算，189 USD 会被当作 189 元排到 P1022（299 元）之前，造成价格梯度失真。这属于种子数据层面的逻辑不一致。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:280-292 next_order_id 使用 inserted_primary_key 在非自增主键或某些驱动下可能为 None（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:280-292`
  - 依据：insert(OrderSequenceRow).values() 后取 result.inserted_primary_key[0]。若 OrderSequenceRow 的主键不是自增整型（例如 UUID 或复合主键），inserted_primary_key 可能为 None 或抛 InvalidRequestError；且对 PostgreSQL 需 RETURNING 才可靠。代码未做防御，直接格式化 f"GBX-{...:06d}"，None 会抛 TypeError。
- **[api_misuse/low]** [api_misuse] app/infrastructure/persistence/sql/repositories.py:400-410 delete 依赖 result.rowcount，某些驱动/场景下 rowcount 为 -1（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:400-410`
  - 依据：bool(result.rowcount) 在 rowcount 为 -1（部分驱动对 DELETE 不返回行数）时为 True，会误报删除成功；rowcount 为 0 时为 False 正确。SQLite/aiosqlite 通常返回正确行数，但换驱动后语义不稳。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:175-190 append_turn 的 turn_index 取 max+1 存在并发撞号，且无唯一约束兜底（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:175-190`
  - 依据：append_turn 先 select max(turn_index) 再插入 max+1，两个并发请求会读到同一个 max 并写入相同 turn_index。模块注释自承此风险，但声称'只影响展示顺序'。实际上 list_turns 按 turn_index 排序，撞号会导致顺序不确定；若表上存在 (session_id, turn_index) 唯一约束则会直接抛 IntegrityError 使写入失败。代码未捕获该异常，属于未处理的错误路径。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/sql/repositories.py:330-345 seed 逐条先查后插，并发或重复调用可能触发唯一约束异常（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/repositories.py:330-345`
  - 依据：seed 对每个 sku 先 select 判断存在再 add，注释声称是 INSERT OR IGNORE 语义，但实现是读-判断-写。两个进程同时 seed 同一 sku 时都会读到不存在并各自 add，commit 时后提交者触发 IntegrityError，而代码未捕获，整个 seed 事务失败。这与注释宣称的语义不符。
- …另有 14 条未列出

## 争议（需裁决）

- **[error_handling/medium]** [error_handling] app/composition.py:140-152 startup 中 bootstrap_product_index / bootstrap_category_knowledge 失败未捕获，与文档「任一失败只告警」不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:140-152`
  - 依据：startup 的 docstring 明确写「建表 / 建向量库 / 建知识库。任一失败只告警，对应能力降级但服务可用」，但只有 bootstrap_schema 和 ensure_group 包了 try/except；bootstrap_product_index 与 bootstrap_category_knowledge 直接 await，一旦抛异常（如 Qdrant 不可达、知识库文件缺失）整个 startup 抛出，服务无法启动，与声明的降级语义矛盾。
  - 争议对手：233a2ff9c8e1
- **[logic/medium]** [logic] app/infrastructure/persistence/seed_products.py:33-35 P1011 竞品描述含「轻便」但注释声称避开与 P1001 的 query 相撞，实际 P1011 与 P1001 在「旅行三件套」上正面冲突（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:33-35`
  - 依据：模块 docstring 明确声明新增语料「刻意避开与 P1001 在『旅行三件套 抗造』这条 query 上正面相撞（竞品 P1011 不写『抗造』）」，以免推翻已有单测的 top-1 断言。但 P1011 的标题是「Voyager 旅行三件套 记忆棉款」，描述含「轻便 长途飞行 出差 旅行必备」，与 P1001 的「旅行三件套」+「轻便」高度重合。虽然 P1011 确实不含「抗造」二字，但 P1001 的 description 同时含「抗造 轻便」，若召回/排序按词项覆盖度或 BM25 计算，P1011 在「旅行三件套 轻便」类 query 上会与 P1001 竞争；更关键的是 docstring 的保证只针对「抗造」一个词，而 P1011 与 P1001 在「旅行三件套」这个核心词上完全相撞，一旦排序权重变化（如标题匹配权重高于描述），P1011 可能挤掉 P1001 的 top-1，使依赖 top-1 断言的单测变得脆弱。这是种子数据设计意图与实际数据不一致导致的逻辑缺陷。
  - 争议对手：de64ff1b0708

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：31｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/infrastructure/persistence, app, app/application/memory, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/queue, app/infrastructure/rerank, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `001a0c61fa51` | 1 | 10 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `254c9186a2ba` | 1 | 4 | `partition_gap` | — |
| `36316f1e43cb` | 1 | 0 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `48f4b9cac1c9` | 1 | 4 | `partition_gap` | — |
| `4ad98b411bb7` | 1 | 0 | `partition_gap` | — |
| `4fcaf3c8939f` | 1 | 0 | `partition_gap` | — |
| `52e48d38e8e3` | 1 | 1 | `partition_gap` | — |
| …另有 21 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/application/prompts` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/persistence` | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| `app/infrastructure/queue` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rag` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
