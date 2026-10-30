# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 76 | 支持不足、相关性超限或尚待验证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：114
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：155 个节点 / 372 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 81 | 100% | 20% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **76** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:27-35 _cosine 对零向量与维度不一致返回 0.0 属安全降级（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:27-35`
  - 依据：维度不一致或零向量时返回 0.0 是合理的降级，不会抛异常；排序仍稳定（index 次序键）。不构成缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-99 top_k<=0 时仍返回全部 dislike，可能超出调用方预期（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-99`
  - 依据：文档明确声明 dislike 全量保留、不参与 top_k 截断，top_k<=0 时返回 dislikes 是刻意的安全底线设计，与模块 docstring 一致，不构成缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:108-116 embed_batch 返回条数与 likes 不一致时降级，但未校验单条向量维度（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:108-116`
  - 依据：已校验 len(vectors) != len(likes) 与 query_vector 为空的情况并降级；单条向量维度不一致由 _cosine 返回 0.0 兜底，不会崩溃。不构成缺陷。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:118-119 重复 statement 的 like 偏好会突破 top_k 截断（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-119`
  - 依据：picked 是从 scored[:top_k] 取出的偏好对象列表，随后用 `[p for p in likes if p in picked]` 回到原始顺序。`in` 使用 dataclass 的相等性（BuyerPreference 若为 dataclass 则按字段比较），因此任何与 picked 中某条偏好字段完全相同的其它 like 也会被判定为“在 picked 中”而被保留。当存在重复 statement/相同字段的偏好时，返回条数会超过 top_k，违背 top_k 语义，注入块被重复偏好挤占。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:121-124 _latest_first 用 `p in newest` 过滤导致重复偏好突破 top_k（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:121-124`
  - 依据：newest 是 sorted(...)[:top_k] 的结果，再用 `[p for p in likes if p in newest]` 复原顺序。`in` 基于相等性比较，重复字段的偏好会被一并保留，返回条数超过 top_k。这是默认（relevance 关闭）路径，影响面更大。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:84-85 select 中 kind 非 dislike 的条目全部当作 like，未知 kind 被静默纳入正向偏好（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:84-85`
  - 依据：BuyerPreference.__post_init__ 已强制 kind ∈ VALID_KINDS，因此 `p.kind != "dislike"` 等价于 `p.kind == "like"`，不会出现未知 kind。此处不是缺陷。
- **[error_handling/low]** [error_handling] app/application/prompts/loader.py:16-19 load_prompts 对空文件或非映射 YAML 返回 None/非 dict，调用方按 dict 使用会出错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:16-19`
  - 依据：yaml.safe_load 对空文件返回 None，但 globex.yml 是仓库内受控文件，缺失或为空属于部署错误，会在首次调用时立即暴露。未发现调用方证据表明需要容错。
- **[logic/low]** [logic] app/application/prompts/loader.py:16-19 load_prompts 使用 lru_cache 缓存，globex.yml 修改后进程内不会重新加载（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:16-19`
  - 依据：提示词在进程生命周期内固定是常见设计，注释也说明全项目从这里取。修改需重启，属于预期行为而非缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:232-240 _rerank 中 rerank_scores 与 scored 长度不一致时索引越界或错配（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:232-240`
  - 依据：代码用 enumerate(scored) 的索引 i 去取 rerank_scores[i]，但未校验 rerank_scores 长度是否等于 scored 长度。若 Reranker 实现返回的分数数量少于候选数（例如内部截断、过滤或实现 bug），会抛 IndexError；该异常被外层 except Exception 捕获后降级为按向量分排序，看似安全。但若返回数量多于候选数则多余分数被静默丢弃，且若 Reranker 返回顺序与输入不对应（例如按分数排序后返回），则分数与商品错配，导致精排结果完全错误且无任何告警。这是对 Reranker 端口契约的隐式假设，缺少长度校验。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:196-210 _to_rejected 与 _within_price_cap 对 primary_sku 价格折算未处理汇率缺失（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-210`
  - 依据：_within_price_cap 在过滤循环中对每个候选调用 rates.convert，_to_rejected 同样调用。这两处都没有 try/except，若某商品价格币种在汇率表中缺失，convert 抛异常会中断整个 execute，导致检索完全失败，而不是跳过该商品或降级。过滤阶段本应健壮，单个商品汇率缺失不应拖垮整个请求。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-137 向量召回成功但结果为空时，recall_strategy 仍标为 embedding_only 且不触发关键词兜底（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-137`
  - 依据：当 embedder 与 vector_index 均配置且 _vector_recall 正常返回空列表（例如索引为空、或所有命中 product_id 在仓库中都不存在被过滤掉）时，recall_strategy 被置为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支执行关键词召回——这一步本身是对的。但问题在于：如果向量召回返回非空、而 rerank 阶段抛异常，recall_strategy 保持 'embedding_only'，这是预期。真正的问题在另一条路径：当 _vector_recall 抛异常时 scored=[] 且 recall_strategy 仍为初始 'keyword_2gram'，随后 `elif not scored` 触发关键词召回，正确。综合看，空结果路径实际会走关键词兜底，因此该处不构成缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:128-137 关键词召回在向量召回成功但为空时被触发，但 recall_strategy 标注与实际召回来源可能不一致（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:128-137`
  - 依据：当向量召回返回空时进入 elif not scored 分支执行关键词召回并设置 recall_strategy='keyword_2gram'，标注与实际来源一致。此路径安全。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:258-266 关键词召回中 category 槽位加权使用子串匹配，可能误命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:258-266`
  - 依据：spec.category in product.category 是子串包含判断，若 spec.category 为短词（如"配件"）会命中"数码配件"等，属于有意的宽松匹配以提升召回。虽然可能误命中，但这是关键词兜底路径的加权策略，且最终仍受 ship_to/价格硬约束过滤，不构成明确缺陷。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:296-310 _overlay_authoritative_stock 中 sku_ids 可能包含重复项，get_many 结果按 id 映射无影响（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-310`
  - 依据：sku_ids 列表可能含重复（不同商品共享 sku_id 不太可能，但同商品多 sku 不会重复）。即使重复，get_many 返回 dict 后按 id 查找，功能正确，仅轻微冗余查询参数，不构成缺陷。
- **[boundary/low]** [boundary] app/application/usecases/order_usecases.py:76-82 PlaceOrder 中 quantity 校验在商品/SKU 查询之后，且未校验重复 SKU 行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:76-82`
  - 依据：quantity<=0 会在扣减前被拒绝，重复 SKU 行会各自 reserve，条件 UPDATE 保证不会超卖，只是多一次往返。不构成正确性缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:175-180 取消订单回补库存与保存订单非原子，保存失败会导致库存已回补但订单仍为已确认（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:175-180`
  - 依据：先 release 库存再 save 订单。若 save 抛异常（DB 故障），库存已回补但订单状态未变，重试取消会再次 release，造成库存虚增。
- **[error_handling/medium]** [error_handling] app/composition.py:138-147 startup 中 bootstrap_product_index / bootstrap_category_knowledge 未捕获异常，与文档“任一失败只告警”不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:138-147`
  - 依据：startup 的 docstring 明确声明“建表 / 建向量库 / 建知识库。任一失败只告警，对应能力降级但服务可用”。但只有 bootstrap_schema 与 ensure_group 包了 try/except；_seed_stock 内部自带 try；而 bootstrap_product_index 与 bootstrap_category_knowledge 直接 await，未捕获异常。若向量库（Qdrant）不可达或知识库构建抛错，异常会从 startup 冒泡，导致整个服务启动失败，与声明的降级语义相反。
- **[error_handling/low]** [error_handling] app/composition.py:78-86 _prompt_fingerprint 只捕获 OSError，路径存在但为目录时 read_bytes 抛 IsADirectoryError 属 OSError 子类，实际安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:78-86`
  - 依据：IsADirectoryError、PermissionError 均为 OSError 子类，会被 except OSError 捕获并返回 'noprompt'，符合“读不到文件时返回固定值，不因此阻断启动”的设计。故不构成缺陷。
- **[logic/low]** [logic] app/composition.py:1-300 composition.py 被截断，无法完整审查装配逻辑（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-300`
  - 依据：提供的文件内容在 build_container 中途被截断（原文件 300 行，仅显示开头部分），无法对后半段装配逻辑（偏好选取、Agent 工厂、限流器构造等）做出有代码依据的判断。截断本身不是代码缺陷，只是审查输入不完整，故记为 not_a_defect 而非臆测缺陷。
- **[logic/low]** [logic] app/composition.py:196-197 use_database 判定仅比较字符串 "file"，DATABASE_URL 为 sqlite:///... 时仍走数据库分支，与文档“未配 → SQLite”一致但需确认 load_settings 默认值（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:196-197`
  - 依据：use_database = settings.database_url != "file"，只要 load_settings 的默认 database_url 不是 "file"（文档称未配 → SQLite），逻辑即正确：未配走 SQLite，显式 "file" 走 JSON。该判定本身无缺陷，取决于 Settings 默认值，而 Settings 不在本次可审查文件内，无法据此断言缺陷。
- **[resource_leak/low]** [resource_leak] app/composition.py:148-152 shutdown 未关闭 task_queue/backplane 且未处理 cache 关闭异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:148-152`
  - 依据：shutdown 只关闭 vector_index、cache、db_engine。task_queue 与 backplane 复用 cache.client，随 cache.close() 一并释放，因此不构成独立泄漏；RedisStreamTaskQueue/RedisEventBackplane 未定义 close 也说明它们不持有独立连接。故不判定为缺陷。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:24-31 BuyerPreference 未校验 buyer_id 非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-31`
  - 依据：buyer_id 为空字符串时值对象仍可构造，但下游存储以 buyer_id 为键，空 id 会落到同一命名空间。不过这是调用方职责，且无明确证据表明会导致错误行为，不列为缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:30-31 created_at 默认值使用 datetime.now 而非注入时钟，且为字符串排序依赖 ISO 格式（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：created_at 用 timezone-aware ISO 字符串，_latest_first 按字符串倒序排序。只要所有 created_at 都是同一时区（UTC）的 ISO 格式，字典序与时间序一致。若外部传入非 UTC 或非 ISO 格式字符串，排序会错，但这是调用方违约，不是本文件缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:44-52 PreferenceStore.delete 文档声明与实现可能不一致（实现不在本文件）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-52`
  - 依据：本文件仅为端口抽象，delete 的具体实现位于 json_file_stores.py（已由其他审查者报告）。端口文档本身自洽，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:100-102 quantity 为浮点数时运费计算 round 后可能产生非整数分，但 Money.of 要求整数（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-102`
  - 依据：quantity 只校验了 <= 0，未校验是否为整数。若传入 1.5，round 后仍是整数分，Money.of 接受整数，不会出错；若传入极大值可能溢出但 Python 无整数溢出。实际调用方 _to_card 固定传 quantity=1，不构成现实缺陷。
- **[error_handling/medium]** [error_handling] app/domain/shipping/tariff_schedule.py:96-110 免税额度判断基于折算后 CNY 小计，汇率缺失时 convert 抛异常未被捕获（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-110`
  - 依据：quote 中多次调用 self.rates.convert(subtotal, ...)。若 subtotal 的币种在汇率表中缺失，convert 抛出的异常会直接冒泡出 quote。调用方 _to_card 只捕获 ValueError，若 convert 抛的是 KeyError 或其他异常类型则不会被捕获，导致整个检索失败。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:33-47 免税额度与运费表用硬编码汇率折算，与 ExchangeRateTable 实际汇率不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:33-47`
  - 依据：注释已明确标注为"简化口径"，免税额度用固定汇率折算成 CNY 分是设计选择，属于业务规则常量而非缺陷。虽然与实时汇率不一致，但这是规则内核的既定口径，不构成代码缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/embedding/openai_embedding_client.py:47-48 embed() 在 embed_batch 返回空列表时索引越界（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:47-48`
  - 依据：embed(text) 直接取 embed_batch([text])[0]。embed_batch 对非空输入理论上返回一条向量，但 _embed_chunk 在网关返回 data 为空数组时（body 有 'data' 键但为空）会返回 []，此时 embed_batch 返回 []，embed 抛 IndexError 而非有意义的错误。触发条件是网关返回 {"data": []} 或 data 被过滤为空。
- **[logic/medium]** [logic] app/infrastructure/embedding/openai_embedding_client.py:76-78 _embed_chunk 未校验返回向量条数与 chunk 长度一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:76-78`
  - 依据：embed_batch 依赖每个 chunk 返回与 chunk 等长的向量列表来保证最终 vectors 与 texts 一一对应。若网关返回的 data 条数少于 chunk（部分失败/截断），_embed_chunk 不校验，vectors 会变短，调用方（如 PreferenceSelector._rank_by_relevance 有长度校验会降级，但其他调用方如建库可能静默错位）。这里缺少长度断言，属于边界校验缺失。
- **[performance/low]** [performance] app/infrastructure/embedding/openai_embedding_client.py:55-62 embed_batch 串行分片请求，大批量时延迟线性放大（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:55-62`
  - 依据：注释明确说明分片串行是刻意设计（网关侧约束），且建库为离线操作，串行可接受。不构成缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:50-51 InMemoryOrderRepository.next_order_id 非原子但单进程 asyncio 下安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:50-51`
  - 依据：itertools.count 的 next() 在 CPython 下是原子的，且 next_order_id 是 async 函数但内部无 await，不会在取号与返回之间被切换。单进程内不会撞号。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:62-80 InMemoryOrderIdempotencyStore 跨进程失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:62-80`
  - 依据：类文档已明确声明仅够单进程开发态使用，跨进程必须用 SqlOrderIdempotencyStore。composition.py 在 DATABASE_URL=file 时才用它，此时队列也通常未启用。属于已声明的取舍，不是缺陷。
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:36-42 release 对未登记 SKU 直接补登记 quantity，可能凭空创造库存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:36-42`
  - 依据：release 的语义是归还之前 reserve 扣减的库存。若 SKU 从未登记（current is None），说明该 SKU 不存在或从未被扣减，此时把库存设为 quantity 等于凭空创造库存。注释声称'避免库存凭空消失'，但实际是'凭空出现'。若上层在 reserve 失败后仍调用 release（例如订单取消流程对未成功预占的订单执行释放），会污染库存。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:59-63 seed 使用 setdefault 导致重复 seed 无法更新库存，且对已扣减为 0 的 SKU 不重置（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:59-63`
  - 依据：注释明确说明'只登记缺失项：已有值代表真实扣减结果，不能被 seed 重置'，这是有意的设计取舍，与文档字符串中'重启即回到 seed 初值'一致（重启后 _stock 为空，setdefault 会写入初值）。不是缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/json_file_stores.py:188-195 JsonFileConversationStore.touch_session 先 exists 后写，并发首轮可能重复写 session 记录（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:188-195`
  - 依据：touch_session 检查 path.exists() 后调用 _append_line，但 _append_line 用 "w" 模式会覆盖文件。并发首轮时两个调用都可能看到文件不存在，后写者覆盖前者；且与 append_turn 交错时可能覆盖已写入的 turn。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/json_file_stores.py:42-48 JsonFilePreferenceStore.append 先读后写非原子，并发追加可能丢更新（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:42-48`
  - 依据：append 先 await list_by_buyer 读取，再 _write 覆盖整个文件。两个并发 append 可能都读到旧列表，后写者覆盖前者，导致偏好丢失。文件形态虽声明不做并发控制，但 append 是 async 且中间有 await，单进程内也可能交错。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:108-109 JsonFileSessionStore.save 非原子写，崩溃可能留下半截 JSON（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:108-109`
  - 依据：直接 write_text 覆盖目标文件，进程在写入中途崩溃会留下截断的 JSON，下次 load 返回损坏内容且无异常处理，会话恢复失败。应写临时文件再 rename。
- **[error_handling/high]** [error_handling] app/infrastructure/persistence/json_file_stores.py:168-186 list_turns 未过滤 kind，event/session 记录被当作 turn 解析并可能 KeyError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:168-186`
  - 依据：循环里只跳过 kind 为 None 的行，但 event 记录 kind="event"、session 记录 kind="session" 都会进入构造 ConversationTurn 的分支，而它们没有 role 字段，record["role"] 会抛 KeyError；即便有 role，也会把事件/会话元信息当成对话轮次返回。异常未被捕获，直接冒泡给调用方。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:197-207 find_session 对损坏行静默跳过，可能返回不含元信息的 dict（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:197-207`
  - 依据：损坏行被跳过是设计意图（单行损坏不影响其余记录），最后返回 {"session_id": session_id} 作为兜底，调用方拿到的是最小可用信息而非异常。属于容错设计。
- **[logic/critical]** [logic] app/infrastructure/persistence/json_file_stores.py:137-139 JSONL 追加写使用 "w" 模式，每次写入都会覆盖整个文件（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:137-139`
  - 依据：_append_line 的注释与类文档都声称是“追加写不覆盖”，但实际用 open("w") 打开文件，会截断已有内容。因此 append_turn 每写一条 turn 就把之前所有 turn/event/session 记录清空，list_turns 永远只能看到最后一条记录；append_events 循环里每条 event 也会互相覆盖，最终只剩最后一条。touch_session 写入的 session 元信息同样会被后续 turn 覆盖，find_session 退化为只返回 session_id。
- …另有 36 条未列出

## 争议（需裁决）

- **[logic/high]** [logic] app/application/usecases/order_usecases.py:104-116 幂等键登记在订单保存之后，登记失败回滚库存但订单已落库，导致订单存在而库存未扣（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:104-116`
  - 依据：order 在 line 104 已通过 _order_repo.save(order) 持久化，随后 record 返回 False 时只回滚库存，没有删除/取消已保存的订单。结果：赢家订单（另一路）与本次订单都存在，但本次订单的库存被释放，造成超卖；且本次订单仍可通过 order_id 查询到。
  - 争议对手：b0b523e050ef
- **[logic/medium]** [logic] app/infrastructure/persistence/seed_products.py:44-46 P1011 与 P1001 同品类同 ships_to，扩充语料可能改变既有单测依赖的排序（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:44-46`
  - 依据：docstring 声明“前 10 个 SPU 逐字段展开写，保持不变——多个单测依赖它们的 id 与排序”，但新增的 P1011 与 P1001 同为“旅行装备”、ships_to 均含 CN/US/SG、标题均含“旅行三件套”、描述均含“轻便/长途飞行”，且价格 139 低于 P1001 的 189。若排序含价格或关键词密度因子，P1011 可能排在 P1001 之前，破坏“依赖排序”的单测。注释的“保持不变”只保证了 P1001 字段不变，未保证其相对排序不变。
  - 争议对手：291b6b753a06
- **[logic/low]** [logic] app/infrastructure/persistence/sql/tables.py:137-139 BuyerPreferenceRow 唯一约束名与列不匹配（kind 未纳入约束）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:137-139`
  - 依据：约束名为 uq_pref_buyer_kind_statement，暗示 (buyer_id, kind, statement) 三元组唯一，但实际 UniqueConstraint 只包含 (buyer_id, statement)。这意味着同一 buyer 对同一 statement 不能同时存在 like 和 dislike 两条记录，与 kind 字段（like/dislike）的语义冲突；若业务允许同一 statement 既被 like 又被 dislike（或需要记录变更历史），插入会触发唯一约束。约束名与内容不一致也会误导后续维护者。
  - 争议对手：49e9b56862a2
- **[performance/low]** [performance] app/infrastructure/persistence/sql/tables.py:76-76 ConversationMessageRow 的 ix_msg_session_turn 索引只含 session_id，未含 turn_index（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:76-76`
  - 依据：索引名为 ix_msg_session_turn，暗示按 (session_id, turn_index) 联合索引以支持按会话取轮次/排序，但实际只索引了 session_id。repositories 中 append_turn 的 max(turn_index) 查询和 list_turns 的按 turn_index 排序都无法利用该索引做覆盖/有序扫描，会退化为回表排序。索引名与内容不一致也会误导后续优化。
  - 争议对手：7b874d2593bf
- **[error_handling/low]** [error_handling] app/infrastructure/rag/category_knowledge.py:84-92 bootstrap_category_knowledge 捕获所有异常返回 0，无法区分部分入库与完全失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/rag/category_knowledge.py:84-92`
  - 依据：整个循环包在一个 try 中，若第 3 个文件插入失败，前 2 个已入库但函数返回 0，调用方会认为一篇都没入库；同时已入库文档的 document_id 已进入 existing，下次重跑会跳过它们，导致失败文件之外的状态不可观测。返回值语义（新增文档数）与实际副作用不一致。
  - 争议对手：09d1e14a9961

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：17｜无法判定：0
- 单 Reader 检出率：64.5%（重捕对 3，已观测 81，估计总体 125.6667
- 待补检分组：app, app/application/memory, app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/infrastructure/queue, app/infrastructure/rerank, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 12.6% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 12.6% |
| `36316f1e43cb` | 2 | 0 | `reader_miss` | 12.6% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 12.6% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 12.6% |
| `4fcaf3c8939f` | 2 | 0 | `reader_miss` | 12.6% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 12.6% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 12.6% |
| `84f86f29ed0c` | 2 | 0 | `reader_miss` | 12.6% |
| `9bf6060729dc` | 2 | 0 | `reader_miss` | 12.6% |
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 2 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 2 | 0 | 2 | 2 | 0 | 0 | 1 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 2 | 0 | 2 | 0 | 0 | 0 | 2 | 0 |
| `app/infrastructure/persistence` | 2 | 2 | 2 | 2 | 0 | 2 | 2 | 1 |
| `app/infrastructure/queue` | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 |
| `app/infrastructure/rag` | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |

矩阵填充率 35%（单元格值 = 独立 Agent 数）
