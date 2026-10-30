# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 8 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 28 | 支持不足、相关性超限或尚待验证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：61
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：97 个节点 / 230 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 41 | 100% | 16% |

## 高置信结论

- **[logic/high]** [logic] app/application/memory/preference_selector.py:118-124 相关性排序取的是相似度最低的 top_k（排序方向反了）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：scored 里存的是 (cosine, index, preference)，随后 scored.sort(key=lambda item: (item[0], item[1])) 按相似度升序排序，再取 scored[:top_k]，于是被选中的是与 query 最不相关的 top_k 条 like 偏好，而真正相关的偏好被丢弃。这与函数 docstring「按 statement 与 query 的余弦相似度取 top_k」以及模块注释「按与本轮 query 的相关性挑选」完全相反。触发条件：relevance_enabled=True 且 embedder 非空，且 likes 数量 > top_k。此时注入的个性化偏好是最不相关的那几条，推荐质量下降（虽不构成 dislike 漏注入的安全问题，但功能语义错误）。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:131-134 _latest_first 同样用 `p in newest` 做成员判断（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:131-134`
  - 依据：与 _rank_by_relevance 相同的问题：`[p for p in likes if p in newest]` 基于值相等而非身份。当 likes 中存在字段完全相同的重复偏好时，newest 只含一条，但过滤会保留所有相等项，返回数量超过 top_k。这是默认（relevance 关闭）路径，影响面更广。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:31-34 from_major_units 用 round() 处理浮点，可能产生 1 分误差（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：major 是 float，major*100 存在二进制浮点误差（如 19.99*100 = 1998.9999999999998），round() 使用银行家舍入且对 .5 情形行为与业务预期可能不一致。虽然 round 通常能纠正到正确整数，但对 0.005 类边界值会舍入到偶数，与“四舍五入”直觉不符，跨境定价场景下可能产生 1 分偏差。
- **[boundary/medium]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 强制为正，无法表达售罄/零库存 SKU（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：`if self.stock <= 0: raise ValueError` 使得 stock=0 的 SKU 无法构造。但 stock 被文档描述为「初始库存」，用于首次播种库存表与展示兜底；一个真实商品完全可能初始库存为 0（缺货上架、预售、下架待补）。此时从目录/参考数据构造 Sku 会直接抛异常，导致整个商品加载失败，而不是展示为缺货。这是边界值处理错误：0 是合法库存值。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 中 zip(pending, fresh) 在回源返回数量不足时静默截断，后续才抛错（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：zip 以较短序列为准，若 inner.embed_batch 返回的向量数少于 pending 数，zip 会静默丢弃多余 pending 项，对应 results[index] 保持 None。虽然末尾 missing 检查会抛 RuntimeError，但此时已对部分文本执行了 _safe_set 写入缓存，且错误信息只给下标不给原因；更关键的是若 inner 返回数量多于 pending，多余向量被静默丢弃而不报错。数量不匹配应在调用后立即校验。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:137-148 zadd_and_count 用 zremrangebyscore 上界 now-window-1 多减 1 秒，窗口边界计数偏小（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-148`
  - 依据：清理上界写成 now - window_seconds - 1，比窗口起点早 1 秒，导致窗口起点前 1 秒内的成员被提前清除，限流计数偏小，可能放行略超阈值的请求。
- **[security/medium]** [security] app/infrastructure/security/content_filter.py:23-23 中文注入模式 忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则) 的 . 不匹配换行，跨行注入可绕过（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:23-23`
  - 依据：Python re 默认 . 不匹配换行符。攻击者把注入写成「忽略\n之前\n的指令」或「忽略以上\n所有规则」时，.{0,10} 无法跨越 \n，模式不命中，注入文本原样进入上下文。同理英文模式 ignore\s+(all\s+)?previous\s+instructions? 中 \s 可匹配换行，但中文模式用的是 . 而非 [\s\S]，存在绕过面。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:47-47 output_guard 正则未使用 re.IGNORECASE，大小写变体可绕过脱敏（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:47-47`
  - 依据：SENSITIVE_PATTERNS 中的内部工具名、主机名、shopping_session_id 等模式均区分大小写，`_compiled = [re.compile(pattern) for pattern in SENSITIVE_PATTERNS]` 未加 re.IGNORECASE。模型输出若写成 `Product_Search_Tool`、`HTTP://VLLM:8000`、`Shopping_Session_Id: abc` 等变体，则不会被脱敏，L4 护栏被绕过。触发条件：最终回复中出现大小写变体的敏感串。

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:128-132 _latest_first 同样用值相等复原顺序，重复偏好会突破 top_k（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-132`
  - 依据：`newest = sorted(...)[:top_k]` 已正确截断，但随后 `[p for p in likes if p in newest]` 按值相等过滤，若 likes 中存在与 newest 中某条相等的重复项，则这些重复项全部被保留，最终返回条数 > top_k，违反 top_k 上限契约。触发条件：likes 中有字段完全相同的重复偏好且被截断保留。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-98 top_k<=0 时仍返回全部 dislike，未做任何上限约束（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-98`
  - 依据：这是模块文档明确声明的安全底线：dislike 全量保留、不参与 top_k 截断。top_k<=0 时返回 dislikes 是刻意设计（正向偏好全部让位，黑名单仍注入），不是缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:113-124 embed_batch 返回空列表时 len 校验通过但 zip 产生空 scored（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:113-124`
  - 依据：当 likes 非空时 len(vectors) != len(likes) 会捕获空列表并降级；likes 为空时 select 已在 len(likes) <= top_k 分支直接返回，不会进入 _rank_by_relevance。因此不存在空 scored 导致 picked 为空却未降级的路径。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-34 _cosine 对维度不一致返回 0.0 而非报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：维度不一致时返回 0.0 是合理的降级：embedding 服务返回异常维度时不应让选偏好崩溃，且 0.0 相似度会被排序自然排到末尾（在排序方向修正后）。虽然会静默掩盖配置错误，但不构成功能性缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:47-56 PreferenceStore.delete 不区分 kind（not_a_defect 记录）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-56`
  - 依据：docstring 明确说明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是刻意的设计决策而非疏漏，且与“精确匹配删除”的防误删目标一致。
- **[logic/low]** [logic] app/domain/catalog/money.py:17-19 Money 直接构造绕过校验（not_a_defect 记录）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:17-19`
  - 依据：dataclass 本身不阻止直接构造，但这是 Python 值对象的常见约定：of() 是推荐入口，直接构造属于调用方违约。单独看 dataclass 定义不构成缺陷，真正的问题是 add/multiply 内部也走直接构造（已单独报告）。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:47-50 Reranker.rerank 契约要求返回与 documents 等长分数，但端口未校验，调用方若直接 zip 会静默错配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:47-50`
  - 依据：这是抽象端口，契约在 docstring 中声明，长度校验责任在实现与调用方，端口本身不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-38 Product 的 __post_init__ 在 skus 为空时抛错，但 primary_sku 无保护地取 skus[0]（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：__post_init__ 已强制 skus 非空，因此 primary_sku 的 skus[0] 在正常构造路径下不会越界。只有绕过 __init__（如 object.__new__ 或 dataclasses.replace 后手动清空）才会触发，属于非常规用法，不构成真实缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:44-49 searchable_text 对 highlight.detail 为空时产生多余空格，但不影响功能（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:44-49`
  - 依据：当 ProductHighlight.detail 为空字符串时，f"{h.label} {h.detail}" 会产生尾随空格，join 后出现连续空格。这只是文本格式瑕疵，对召回/检索无实质影响，不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:28-34 ConversationTurn 文档称 turn_index 可留空但字段不存在（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:28-34`
  - 依据：类 docstring 写“turn_index 由存储层按会话自增，写入时可留空”，但 dataclass 根本没有 turn_index 字段，list_turns 的 docstring 又承诺“按 turn_index 升序返回”。字段缺失使存储层无法在值对象上携带/回填序号，接口契约与实现不一致。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:41-47 ConversationEventRecord 未校验 session_id/type 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:41-47`
  - 依据：ConversationTurn 对 session_id 做了 required 校验，而 ConversationEventRecord 作为同一存储的写入形态却完全没有 __post_init__ 校验。空 session_id 的事件会被 append_events 写入，之后按 session_id 查询时无法归属到任何会话，形成孤儿数据；空 type 也会让事件回放无法分类。
- **[logic/low]** [logic] app/domain/session/ports/session_store.py:18-24 SessionStore 抽象方法体为空，缺少 pass 但语法合法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:18-24`
  - 依据：docstring 作为方法体是合法的 Python，抽象方法不会被直接调用。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:66-73 缓存命中判定 isinstance(cached, list) and cached 会拒绝空向量，但空向量本身非法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-73`
  - 依据：cached 为空列表时按未命中处理并回源，这是合理的防御：空向量对检索无意义。不会导致错误结果，只是多一次回源。
- **[logic/low]** [logic] app/infrastructure/cache/cached_embedding_client.py:66-72 embed_batch 缓存命中判断 isinstance(cached, list) and cached 对空向量视为未命中，但空向量是合法 embedding 的可能性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-72`
  - 依据：空列表向量在真实 embedding 中不会出现，且视为未命中只是多一次回源，不会产生错误结果。属于防御性设计，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:70-74 get_json 中 json.loads 失败后 await self.delete(key) 未捕获异常，可能抛出（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:70-74`
  - 依据：delete() 内部已 try/except 吞掉所有异常，因此这里的 await self.delete(key) 不会抛出。安全。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-130 set_if_absent 在 Redis 异常时返回 True 放行，幂等键失效可能导致重复下单（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：文档明确说明这是有意的降级策略：宁可退化为无幂等保护也不拒绝服务。属于设计取舍而非缺陷，且注释已声明。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:143-149 lookup 中相似度比较用 > 而非 >=，阈值边界行为与文档'低于阈值视为未命中'一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-149`
  - 依据：文档说低于阈值未命中，等于阈值时用 > 会判为未命中，属于保守侧，不产生错误回复。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:63-70 _cosine 对长度不等的向量用 zip 静默截断，维度不一致时给出错误相似度（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:63-70`
  - 依据：zip(left, right) 在长度不等时按较短者截断，不报错。若缓存中存的向量维度与当前 embedder 输出维度不同（换 embedding 模型但 namespace 未变、或缓存脏数据），相似度会被错误计算，可能超过 0.95 阈值导致错误命中，把答非所问的回复返回给买家。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:168-176 remember 中 entries 读取与写回非原子，并发下丢失更新（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-176`
  - 依据：remember 先 _load_entries 读桶，append 后 set_json 整体写回，读-改-写之间无锁。同一 buyer 并发两次 remember 时，后写者覆盖先写者，导致一条缓存条目丢失。虽然只影响缓存命中率不产生错误回复，但属于真实的并发缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:108-118 语义缓存桶 key 未包含 scope 之外的偏好指纹时仍可能命中旧回复——实际 _bucket_key 已含 scope，但 lookup/remember 的 scope 默认空串，调用方漏传即失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-118`
  - 依据：scope 作为默认参数为空串，若调用方不传则桶 key 不含偏好指纹，会命中撤回偏好前的旧回复。但这是调用方契约问题，本文件内 lookup/remember 都正确把 scope 传入 _bucket_key 与 _load_entries，签名一致，不构成文件内缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-52 _UNSAFE_RE 中 '这个'/'那个'/'它' 等单字模式会误伤正常咨询问句（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-52`
  - 依据：误伤只会导致该问句不进缓存（多花一次调用），不会产生错误回复，属于保守设计。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:62-68 lookup 中 _cosine 对维度不一致的向量 zip 截断，可能产生错误相似度（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:62-68`
  - 依据：_cosine 用 zip(left, right) 计算点积，若缓存中存的向量维度与当前 embedder 返回维度不同（例如换了 embedding 模型但 namespace 未变，或缓存被污染），zip 会静默截断到较短长度，点积与范数基于不同长度计算，得到无意义的相似度，可能误命中返回错误回复。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:96-100 SemanticCache 构造时 enabled and cache.enabled，若 cache 为 disabled 实例则永久禁用，符合设计（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:96-100`
  - 依据：Redis 不可用时语义缓存禁用是合理降级。
- **[error_handling/high]** [error_handling] app/infrastructure/security/__init__.py:14-18 output_guard 导入 content_filter 模块，但该文件不在仓库中，导致 security 包导入失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:14-18`
  - 依据：security/__init__.py 在包初始化时无条件执行 `from app.infrastructure.security.content_filter import (...)`，但给定文件列表中不存在 content_filter.py。任何 `import app.infrastructure.security`（或导入其子模块 output_guard 时先触发包 __init__）都会抛 ModuleNotFoundError，使 L3/L4 护栏整体不可用。这是导入期硬失败，不是运行时才暴露的问题。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 中 system\s*prompt 等模式缺少词边界，可能误伤正常商品描述（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：r"(?i)system\s*prompt" 会匹配 "system prompts"、"system prompt engineering" 等正常技术商品/文档标题；r"(?i)you\s+are\s+now" 会匹配 "you are now able to..." 这类正常英文描述。过滤是替换而非丢弃，但会把正常商品标题/描述片段替换成占位符，导致模型看到的信息被破坏，属于误报导致的可用性缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:55-63 sanitize_tool_output 对已过滤文本重复替换导致占位符被再次匹配/嵌套（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-63`
  - 依据：逐个 pattern 顺序 subn 是常见做法。占位符 FILTERED_PLACEHOLDER 文本为「[内容已过滤：疑似注入]」，不含任何 DANGEROUS_PATTERNS 能匹配的子串（如 ignore previous instructions、system prompt、you are now 等），因此后续 pattern 不会再次命中占位符，不会产生嵌套替换或无限增长。确认安全。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:55-66 audit_output 对非字符串输入直接调用 re.subn 会抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:55-66`
  - 依据：函数签名标注 `text: str`，且首行 `if not text: return True, text` 已处理 None/空串。若调用方传入非字符串（如 dict/list），`pattern.subn` 会抛 TypeError。但这是类型契约内的调用方违约，且模块定位为纯函数层、调用方在推给买家前传入的必然是字符串回复，故不认定为该文件缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:62-66 脱敏替换后可能产生新的敏感模式匹配，但循环按模式顺序单次扫描（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-66`
  - 依据：REDACTED 为 `[已脱敏]`，不含任何敏感模式可匹配的子串（无 sk-、无 http://、无工具名、无 shopping_session_id），因此替换不会引入新的命中，单次顺序扫描已足够。不构成缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-35 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-35`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空字符串 buyer_id 会被接受并写入存储，导致偏好归属到空买家，list_by_buyer("") 可能返回所有空 ID 偏好，且无法与真实买家区分。ConversationTurn 对 session_id 做了 required 校验，此处不一致。
  - 争议对手：5bc133ae47c8
- **[logic/medium]** [logic] app/domain/catalog/money.py:36-44 Money.add/multiply 绕过 of() 校验，可构造非法 Money（负数/不支持币种）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-44`
  - 依据：Money.of() 是唯一做不变量校验（非负整数、受支持币种）的入口，但 add() 和 multiply() 直接调用 dataclass 构造函数 Money(...)，绕过了 of()。虽然 add/multiply 的输入来自已校验的 Money 实例，币种与非负性通常能保持，但 multiply 的 quantity 校验与 of 的 amount 校验是两套逻辑；更关键的是，任何通过 dataclass 直接构造（Money(-5, 'USD') 或 Money(100, 'XYZ')）得到的实例都能进入 add/multiply 并被当作合法值传播，且 add 只校验币种一致性、不校验 amount 非负。这使类文档声明的“不变量：amount 必须为非负整数；currency 必须受支持”在 add/multiply 路径上无法保证。
  - 争议对手：247a99dcc820
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-41 ConversationTurn 未校验 content 非空，空内容轮次可入库（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-41`
  - 依据：__post_init__ 只校验 role 和 session_id，未校验 content。空 content 的轮次会被持久化，list_turns 回放时产生无意义记录，影响 bad case 采集与客服排查的数据质量。
  - 争议对手：03b08871891b
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:148-156 lookup 中 entry.get("vector", []) 缺失向量时 _cosine 返回 0，安全；但 entry 非 dict 会抛 AttributeError 未被捕获（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-156`
  - 依据：_load_entries 只校验 entries 是 list，不校验元素类型。若 Redis 中桶内容被写成 list[非dict]（脏数据或旧格式），entry.get 会抛 AttributeError，而该循环不在 try 内，异常会冒泡到调用方，破坏“缓存异常一律当未命中”的纵深防御承诺。
  - 争议对手：2de2685ff92e
- **[security/low]** [security] app/infrastructure/security/output_guard.py:33-33 会话 ID 正则要求冒号或等号，裸 ID 与 JSON 引号形式漏检（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:33-33`
  - 依据：`shopping_session_id\s*[:=]\s*[\w-]+` 只覆盖 `shopping_session_id: xxx` / `= xxx` 两种形态。若模型输出 JSON 片段 `"shopping_session_id": "abc-123"`，冒号后紧跟引号，`[\w-]+` 无法匹配引号，subn 计数为 0，ID 不被脱敏；同理 `shopping_session_id 是 abc` 这类自然语言表述也漏检。
  - 争议对手：9a09dbb60c5c

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.77% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：14｜无法判定：0
- 单 Reader 检出率：75.6%（重捕对 3，已观测 41，估计总体 54.2
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 5.9% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 5.9% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 5.9% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 5.9% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 5.9% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 5.9% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 5.9% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 5.9% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 5.9% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 5.9% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 1 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 2 | 0 | 2 | 1 | 0 | 2 | 0 | 0 |

矩阵填充率 24%（单元格值 = 独立 Agent 数）
