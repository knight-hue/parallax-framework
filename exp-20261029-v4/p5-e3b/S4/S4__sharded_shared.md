# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 34 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：53
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：86 个节点 / 196 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 36 | 100% | 15% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:92-94 top_k <= 0 时提前返回空列表，dislike 也被丢弃（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:92-94`
  - 依据：top_k<=0 表示预算为 0，不注入任何偏好是显式设计意图（注释已说明）。虽然与『dislike 全量保留』的绝对表述有张力，但预算为 0 时无法注入任何内容，返回空是合理边界行为，不构成缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-34 _cosine 对长度不一致返回 0.0 而非报错，可能静默把有效偏好排到末尾（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：embed_batch 与 embed 返回的向量维度不一致时返回 0.0 相似度，属于防御性降级；上层已校验向量数量一致，维度不一致是异常输入，返回 0 不会崩溃且排序仍确定。不构成真实缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-130 _rank_by_relevance 注释声称回到原始相对顺序，实际按相似度排序输出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-130`
  - 依据：注释写『回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入』，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度降序输出，并未按原始 index 重排。这与 _latest_first 的行为不一致（后者确实复原了原始顺序），且与注释承诺不符：注入块行序会随 query 变化而抖动，可能影响 prompt cache 命中与可测性。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 select() 的最终截断会把 dislike 一起裁掉，违反『dislike 全量保留』的安全底线（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 全量保留、不参与 top_k 截断，但返回语句 `(dislikes + selected_likes)[:top_k]` 对拼接后的整体再做一次切片。当 dislikes 数量 >= top_k 时，所有 like 被裁掉尚可接受，但更严重的是当 dislikes 数量 > top_k 时，部分 dislike 会被丢弃；即使 dislikes 数量 <= top_k，只要 dislikes + likes 超过 top_k，被裁掉的也是尾部 like（这部分符合预期），但 dislike 本身在 dislikes 数量超过 top_k 时会被截断。触发条件：买家有 3 条 dislike、top_k=2，则只注入前 2 条 dislike，第 3 条黑名单丢失，可能推荐用户明确拒绝的商品。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:47-56 PreferenceStore.delete 文档声称不按 kind 区分，但接口无法表达『同 statement 的 like 与 dislike 一并清除』的原子性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-56`
  - 依据：delete 签名 (buyer_id, statement) -> bool 足以表达按 statement 精确匹配删除，文档说明不区分 kind 是契约的一部分，实现方需遵守。接口本身没有缺陷，只是文档约束。
- **[boundary/medium]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：__post_init__ 校验了 kind 和 statement，但未校验 buyer_id。空 buyer_id 的偏好会被写入存储，list_by_buyer('') 可能返回所有空 buyer 的偏好，或导致存储层 key 冲突。作为值对象，buyer_id 是核心标识，缺失校验会让非法状态进入领域模型。
- **[logic/low]** [logic] app/domain/buyer/preference.py:44-52 PreferenceStore.delete 不区分 kind 会同时删除 like 与 dislike（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-52`
  - 依据：docstring 明确声明『不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除』，这是刻意的设计决策而非缺陷。调用方按 statement 精确匹配删除，语义已文档化。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:20-25 Money.of 用 isinstance(amount, int) 会接受 bool（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:20-25`
  - 依据：multiply 特意排除了 bool（isinstance(quantity, bool)），说明作者知道 bool 是 int 子类；但 of() 只写 isinstance(amount, int)，Money.of(True, 'USD') 会通过校验得到 1 分。两处校验标准不一致，of() 的『必须是非负整数』不变量对 bool 失效。
- **[logic/low]** [logic] app/domain/catalog/money.py:35-43 Money.add/multiply 直接构造实例绕过 of() 校验，可产生非法 Money（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造，跳过校验。虽然当前输入来自已校验实例，但 multiply 的 quantity 校验允许 bool 被排除、add 的 other 未校验类型；更关键的是 dataclass 本身没有 __post_init__ 校验，任何直接 Money(-1, 'XXX') 都能构造出违反不变量的对象，of() 的校验形同虚设。
- **[logic/low]** [logic] app/domain/catalog/money.py:45-49 Money.to_major_units 返回 float，与模块『避免浮点误差』目标冲突（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-49`
  - 依据：to_major_units 仅用于展示（__str__ 用 :.2f 格式化），不参与金额运算；内部存储仍是整数分。虽然返回 float 有精度隐患，但当前用途是格式化输出，不构成实际错误行为。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:39-41 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:39-41`
  - 依据：这是抽象端口声明，契约由实现方保证；在 ABC 中加校验并不常见，且文档未承诺长度校验。缺少校验属于实现层责任，不构成本文件缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:33-38 Product 为可变 dataclass 且 __post_init__ 只校验 skus 非空，未校验 skus 元素类型（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：类型标注已声明 list[Sku]，Python 运行时不做类型检查是语言特性；__post_init__ 只做业务不变量校验（product_id 非空、至少一个 sku），符合聚合根设计。不构成缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 对空 detail 的亮点产生多余空格，且未包含 skus 信息（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：highlight_text 用 f"{h.label} {h.detail}" 拼接，当 detail 为空字符串时会留下尾随空格，但最终 join 后只是多一个空格，不影响召回语义；searchable_text 未包含 skus 是设计选择（文档字符串明确列出字段）。因此不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:26-30 Sku.stock 校验非负但未校验 price 非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:26-30`
  - 依据：Sku 的 __post_init__ 只校验 sku_id 与 stock，未校验 price 是否为 None。但 price 类型标注为 Money，构造时若传 None 会在后续使用处报错。这属于契约外输入，且 Money 本身有校验，不构成明确缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:28-41 ConversationTurn 文档声称 turn_index 可留空，但类中根本没有 turn_index 字段（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:28-41`
  - 依据：docstring 写『turn_index 由存储层按会话自增，写入时可留空』，list_turns 也承诺『按 turn_index 升序返回』，但 ConversationTurn 没有 turn_index 字段。存储层无法在值对象上携带/回填序号，list_turns 的排序契约无法通过该类型表达，实现者只能另造结构或依赖隐式顺序，接口契约自相矛盾。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:27-41 ConversationTurn 声明 role 但未校验，非法 role 可入库（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-41`
  - 依据：模块定义了 VALID_ROLES = ('buyer', 'agent')，但 ConversationTurn.__post_init__ 只校验 session_id，从未使用 VALID_ROLES。role 字段注释写 buyer/agent，实际可传入任意字符串（如 'system'、空串）并被持久化，下游按 role 分流展示/回放时会出错。VALID_ROLES 成为死代码，说明校验被遗漏。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:63-72 CachedEmbeddingClient 缓存命中判断 `isinstance(cached, list) and cached` 会拒绝合法空向量（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:63-72`
  - 依据：空向量对 embedding 无意义，把它当未命中回源是合理且安全的降级，不会产生错误结果，只是多一次调用。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 用 `vector or []` 把合法空向量/None 静默替换为空列表，且长度可能与输入不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：若 inner.embed_batch 返回的列表比 pending 短（上游异常/截断），zip 会静默丢弃尾部，results 中对应位置保持 None，最终 `vector or []` 变成空列表返回给调用方，调用方拿到长度正确但内容为空的向量，错误被吞掉而非抛出。同时 `vector or []` 也会把合法的空向量与失败混为一谈。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型的向量会互相串用（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例上部署了多个模型（或切换模型后复用旧缓存），相同文本会命中另一模型生成的向量，维度/语义都不匹配，导致检索结果错误。_cosine 在维度不同时返回 0.0，但维度相同而语义空间不同的模型会静默返回错误相似度。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:108-118 set_if_absent 在 Redis 异常时返回 True 放行，幂等保护失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-118`
  - 依据：这是文档明确声明的降级策略（宁可无幂等也不拒绝服务），属于有意的可用性权衡而非缺陷。但需注意：若该 key 同时被用作分布式锁，异常时返回 True 会让多个 worker 同时获得锁，可能引发并发写。当前代码注释已说明取舍，判定为设计决策。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:62-70 get_json 在 json.loads 失败时删除键，可能误删非 JSON 值（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:62-70`
  - 依据：get_json 只用于 JSON 值，脏值删除是设计意图；get_raw 已单独提供避免误删幂等键。但需注意：若同一 key 被 set_json 与 set_if_absent 混用（如幂等键），get_json 会删掉裸字符串。当前代码中 get_raw 的 docstring 已明确区分，属于调用方契约问题而非本方法缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:70-76 RedisCache.get_json 在 JSON 解析失败时调用 delete，但 delete 内部吞异常，且脏值删除可能误删并发写入的新值（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:70-76`
  - 依据：get_json 读到脏值时调用 self.delete(key) 删除。虽然存在并发窗口（读到脏值后、删除前其他进程写入新值会被误删），但这是缓存场景，最坏结果是未命中，不影响正确性。且 delete 本身吞异常，不会抛错。属于可接受的缓存降级行为，不构成真实缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:178-183 remember 用 entries[:_BUCKET_LIMIT] 截断保留最旧条目，新写入的回复会被丢弃（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-183`
  - 依据：entries.append 把新条目追加到末尾，随后 entries[:_BUCKET_LIMIT] 取前 30 条。桶满后新条目永远落在切片之外被丢弃，缓存内容冻结在最早的 30 条，与注释『保留最近条数』相反，热点新问句永远无法进入缓存。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:62-64 SemanticCache._cosine 维度不一致返回 0.0 而非报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:62-64`
  - 依据：维度不一致时返回 0.0 等价于未命中，是安全的降级行为，不会给出错误回复。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:158-166 lookup 对 entry 的 vector 未做类型校验，非列表值会抛异常（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:158-166`
  - 依据：_load_entries 只保证顶层是 list，未校验每个 entry 是 dict 且 vector 是 list。若缓存被污染或旧格式数据存在，entry.get 在非 dict 上会 AttributeError，_cosine 在 vector 为 None 时 len() 抛 TypeError，异常会冒泡出 lookup，破坏『缓存异常一律当未命中』的纵深防御承诺。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-126 SemanticCache._bucket_key 忽略 scope 参数，偏好指纹未进入桶 key（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-126`
  - 依据：docstring 与模块注释（安全边界 2b）明确要求桶 key 带买家偏好指纹 scope，偏好变更后旧回复必须失效。但 _bucket_key 的 f-string 只拼接了 namespace 和 buyer_id，scope 形参完全未使用。结果：买家撤回『不要塑料』偏好后，仍会命中撤回前生成的、声称符合该偏好的旧回复，直接向用户断言已删除的偏好。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:143-148 lookup 忽略 has_history 参数，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-148`
  - 依据：模块注释安全边界 3 要求『会话内已有多轮上下文时不命中』，remember 侧确实检查了 has_history，但 lookup 侧完全没有使用该参数。带上下文的会话（如『那款多少钱』虽被 _UNSAFE_RE 部分拦截，但仍有漏网问句）会命中跨会话缓存，给出脱离上下文的错误回复。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-46 sanitize_tool_output 对空字符串返回原值（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-46`
  - 依据：空字符串无内容可过滤，直接返回 (False, '') 是正确行为，不会导致错误。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:24-32 content_filter 正则未加词边界，'system prompt' 等模式会误伤正常商品描述（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：DANGEROUS_PATTERNS 中 r"(?i)system\s*prompt" 会匹配任何包含 'system prompt' 子串的文本，包括正常商品描述如『this system prompts the user to...』或技术文档。虽然过滤只替换命中片段而非整条丢弃，但会把正常内容替换为占位符，造成信息丢失。同理 'you are now' 会匹配 'you are now able to...' 这类正常英文。这是过度匹配导致的误伤。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 content_filter 正则未覆盖大小写混合的中文注入与多行绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：正则过滤本就是尽力而为的 L1 防线，文档明确说明语义级判断交给 L4。模式覆盖常见写法，未覆盖的变体属于已知局限而非代码缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:52-53 audit_output 对非 str 输入（如 None 之外的 bytes/对象）会抛异常，但空串处理正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:52-53`
  - 依据：`if not text: return True, text` 覆盖了 None 和空串，返回 (True, None/''), 调用方拿到 None 文本可能有问题，但函数签名标注 text: str，None 属于调用方违约。对合法 str 输入行为正确，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:60-62 audit_output 对空字符串返回安全，但 None 输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-62`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回 (True, text)，不会进入正则处理，因此 None 不会抛异常。类型标注为 str，调用方传 None 属于契约外，但函数本身对 None 是安全的。
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:37-37 SENSITIVE_PATTERNS 中 shopping_session_id 模式只匹配带分隔符的赋值形式，裸 ID 值不被脱敏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:37-37`
  - 依据：模式 r"shopping_session_id\s*[:=]\s*[\w-]+" 要求出现 'shopping_session_id' 这个键名。若 Agent 回复中直接写出会话 ID 的值（例如 '你的会话是 sess-abc123' 或 'session: sess-abc123'），键名不出现，则完全不会被脱敏。L4 的目标是拦截内部会话 ID 泄露，而实际泄露场景往往只带值不带键名，因此该模式覆盖不足，属于安全护栏的漏检。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-46 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-46`
  - 依据：`_INTERNAL_TOOLS` 中所有工具名只含字母和下划线，拼进正则后 `\b(?:...)\b` 能正确匹配。下划线在 Python re 中属于 \w，`\b` 边界在 `product_search_tool` 前后能正确识别（前面是空格/标点，后面是空格/标点）。不存在未转义的特殊字符导致误匹配。

## 争议（需裁决）

- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:137-152 zadd_and_count 在 Redis 不可用时返回 0，导致限流失效（放行全部请求）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-152`
  - 依据：zadd_and_count 用于跨进程限流。当 Redis 不可用或 pipeline 抛异常时返回 0，调用方通常以『窗口内计数 >= 阈值则拒绝』判断，返回 0 意味着永远不触发限流，所有请求被放行。这与 set_if_absent 的『放行』策略一致（可用性优先），但限流是安全/资源保护机制，静默失效会让下游被打爆。文档注释也承认『按不限流处理』，属于有意的降级，但降级方向对限流场景是危险的——应至少返回一个哨兵值让调用方能区分『Redis 故障』与『窗口为空』。
  - 争议对手：d1b93614ea49
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:41-41 output_guard 的 URL 正则未加词边界，会误伤正常域名（如 redis.example.com 或 vllm 前缀域名）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:41-41`
  - 依据：模式 r"https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?" 在主机名后没有要求边界（如 (?![\w.-]) 或 / 或 : 或结尾）。因此 https://redis.example.com/docs 这类买家可见的合法外部链接会被匹配：'https://redis' 命中前缀，随后 (?::\d+)? 不匹配，(?://\S*)? 也不匹配，但 re.subn 仍会把 'https://redis' 替换成 [已脱敏]，留下 'example.com/docs' 这种残缺文本，同时把 safe 置为 False 触发误告警。同理 https://vllm.io 也会被误伤。这与模块文档『避免把买家可见的正常措辞误伤』的意图相悖。
  - 争议对手：225ca509773b, 225ca509773b

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：12｜无法判定：0
- 单 Reader 检出率：66.7%（重捕对 3，已观测 36，估计总体 54.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 11.1% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 11.1% |
| `269088b25c46` | 2 | 0 | `reader_miss` | 11.1% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 11.1% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 11.1% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 11.1% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 11.1% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 11.1% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 11.1% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 11.1% |
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 1 | 0 | 2 | 2 | 0 | 2 | 0 | 0 |

矩阵填充率 21%（单元格值 = 独立 Agent 数）
