# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 37 | 支持不足、相关性超限或尚待验证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：62
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：96 个节点 / 232 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 40 | 100% | 14% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/high]** [boundary] app/application/memory/preference_selector.py:88-100 top_k 预算未扣除 dislike 数量，like 挤占 dislike 名额（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-100`
  - 依据：top_k 是总注入预算，但代码用完整的 top_k 去选取 like（`_rank_by_relevance(likes, query, top_k)` / `_latest_first(likes, top_k)`），再与 dislikes 拼接后截断。当 dislikes 非空时，like 会占用本应留给 dislike 的名额，导致 dislike 被挤出。例如 dislikes=2、likes=5、top_k=3：like 选 3 条，拼接后 5 条截断为 3 条，只剩 2 条 dislike + 1 条 like，看似 OK；但若 dislikes=2、top_k=2，like 选 2 条，拼接后截断为 2 条，dislike 全保留但 like 全丢——更严重的是 dislikes=3、top_k=2 时 dislike 被裁。正确做法应是先保留全部 dislike，再用 top_k - len(dislikes) 作为 like 预算。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-36 _cosine 对长度不一致返回 0.0 而非降级，可能把有效偏好排到末尾（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-36`
  - 依据：长度不一致时返回 0.0 是保守的降级策略，不会抛异常；虽然可能把该偏好排到末尾，但这是 embedding 维度不一致的异常场景，返回 0 比崩溃更安全，且上层有向量数量校验。不构成明确缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:118-124 _rank_by_relevance 注释声称回到原始相对顺序，实际按相似度排序输出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：注释写「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度排序后的顺序输出，并未按原始 index 重排。这导致注入块行序随 query 变化而抖动，与注释意图相反，可能影响 prompt cache 命中或造成重复注入。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:128-132 _latest_first 用 `p in newest` 依赖 dataclass 相等性，重复偏好会被错误保留/丢弃（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-132`
  - 依据：`[p for p in likes if p in newest]` 使用 == 比较（dataclass 默认按字段值相等）。若两条偏好字段完全相同（同一 statement、同一 created_at、同一 kind），它们相等，`in` 对两条都返回 True，于是两条都被保留，返回条数可能超过 top_k；反之若 newest 只含其中一条，另一条也会被误判为在 newest 中。这破坏了「取 top_k 条」的契约。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-100 select() 的最终截断会把 dislike 一起裁掉，违反「dislike 全量保留」的安全底线（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-100`
  - 依据：模块 docstring 明确声明 dislike 全量保留、不参与 top_k 截断，但实现最后一行 `return (dislikes + selected_likes)[:top_k]` 对整个拼接结果做切片。当 len(dislikes) > top_k 时，dislike 会被截断；当 len(dislikes) + len(selected_likes) > top_k 时，selected_likes 已按 top_k 选取，但 dislikes 仍可能被切掉尾部。触发条件：买家有 3 条 dislike、top_k=2，则只返回前 2 条 dislike，第 3 条黑名单丢失，可能推荐用户明确拒绝的商品。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:44-55 PreferenceStore.delete 文档与实现契约一致，无缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-55`
  - 依据：delete 是抽象方法，文档明确精确匹配、不区分 kind，契约清晰，不构成缺陷。
- **[boundary/medium]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：__post_init__ 校验了 kind 和 statement，但没有校验 buyer_id。空字符串或 None 的 buyer_id 可以构造出 BuyerPreference 并被 PreferenceStore.append 持久化，导致偏好挂到无效买家下，后续 list_by_buyer 无法按真实买家检索，且可能污染存储。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:35-43 Money.multiply 未校验 self 金额，且 add 未校验 other 类型（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：add 通过 _assert_same_currency 访问 other.currency，若 other 非 Money 会抛 AttributeError，属于可接受的类型错误；multiply 校验了 quantity。这些不构成独立缺陷，与上一条重复。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:45-49 Money.to_major_units 用浮点除法，JPY 与精度场景下表示不精确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-49`
  - 依据：to_major_units 返回 float 仅用于展示（__str__ 用 :.2f 格式化），内部存储仍是整数最小单位，不参与计算，因此浮点误差不会污染金额不变量。虽然 JPY 的 /100 展示语义错误，但根因是 from_major_units 的换算假设，已单独报告；此处本身不构成独立缺陷。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：from_major_units 对所有币种统一 round(major*100)，但 JPY 的最小单位就是 1 日元（无小数位），SUPPORTED_CURRENCIES 明确包含 JPY。调用 Money.from_major_units(1000, 'JPY') 会得到 100000 最小单位，即 1000 日元被当成 100000 日元，价格放大 100 倍。注释自认是 demo 简化，但这是真实的价格不变量破坏：Money 的文档声称以最小货币单位存储避免误差，而该工厂方法直接产出错误金额，且 to_major_units/__str__ 也按 /100 反算，导致 JPY 全链路金额错误。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:40-42 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:40-42`
  - 依据：这是抽象端口，契约由实现方保证；端口层不做长度校验是合理的，缺陷应在实现中检查。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-38 Product 为可变 dataclass 但 __post_init__ 校验 skus 非空，后续可被清空绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：`__post_init__` 校验 `if not self.skus: raise`，但 Product 非 frozen，`skus` 是可变 list，构造后可通过 `product.skus.clear()` 清空，使 `primary_sku()` 抛 IndexError。然而这是 Python 可变对象的普遍特性，且代码库未提供清空 skus 的公开方法；`primary_sku` 的 IndexError 在 skus 为空时是明确的失败而非静默错误。属于设计权衡，不构成可复现缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-36 Product 为可变 dataclass 且 __post_init__ 校验可被绕过（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-36`
  - 依据：Product 非 frozen，skus 可在构造后被清空，但这是设计选择，仓库内没有证据表明存在绕过校验导致错误的路径。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 对 ProductHighlight.detail 为空时产生多余空格（非缺陷）（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：当 detail 为空字符串时，f"{h.label} {h.detail}" 会产生尾部空格，但最终 join 后只是多一个空格，对召回文本无实质影响，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-34 Sku.stock 仅校验非负，未校验类型，bool/float 可通过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：stock 声明为 int，Python 不做运行时类型强制，但传入 bool 或 float 属于调用方违约；`self.stock < 0` 对 bool/float 仍能工作，不会产生错误行为（True<0 为 False，1.5<0 为 False）。缺少类型校验是风格/健壮性问题，未直接导致错误行为，不报告为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn 文档称 turn_index 可留空由存储层自增，但字段根本不存在（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：类 docstring 明确写『turn_index 由存储层按会话自增，写入时可留空』，list_turns 的契约也写『按 turn_index 升序返回』，但 ConversationTurn 数据类里没有 turn_index 字段。存储层实现无法在 turn 对象上携带/回填序号，list_turns 返回的 list[ConversationTurn] 也无法体现排序依据，端口契约与值对象定义自相矛盾，实现者只能自行扩展字段或另建结构，破坏端口一致性。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:24-40 ConversationTurn.role 未校验，VALID_ROLES 定义后从未使用（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-40`
  - 依据：模块定义了 VALID_ROLES = ('buyer','agent') 并在字段注释里声明 role 取值，但 __post_init__ 只校验 session_id，任意 role 字符串都能构造并落库，下游按 role 分支的逻辑会拿到非法值。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/session_store.py:17-27 SessionStore 端口仅 save/load，无删除/列举能力（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-27`
  - 依据：端口只声明 save/load 是刻意的窄接口，文档说明只为恢复上下文；缺少 delete/list 属于能力范围问题，不是错误行为，且无法从给定代码证明调用方需要这些能力。不认定为缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型的向量互相串用（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块文档明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例上先后用不同 embedding 模型（或换模型后未清缓存），同文本会命中旧模型向量，维度/语义空间不一致，导致检索与语义缓存相似度计算错误。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:108-120 set_if_absent 在 Redis 故障时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-120`
  - 依据：注释明确说明这是有意的降级策略：宁可退化成没有幂等保护，也不能因缓存故障拒绝服务。这是设计取舍而非缺陷，且文档已声明。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:130-148 zadd_and_count 在 Redis 异常时返回 0，等于不限流（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:130-148`
  - 依据：注释说明这是刻意的降级：Redis 滑窗计数失败按不限流处理，避免缓存故障导致全站拒绝服务。属于有意的可用性权衡，不是缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:68-73 get_json 脏值分支实际未删除键（与注释不符）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：注释声称「脏值当未命中，顺手删掉」，但 except ValueError 分支里确实调用了 await self.delete(key)。等等——代码里是有 delete 的。重新核对：quote 中第 71 行是 await self.delete(key)。因此该分支行为与注释一致，不构成缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:168-172 remember 截断 entries[:_BUCKET_LIMIT] 保留最旧条目、丢弃最新写入（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-172`
  - 依据：entries.append 把新条目追加到末尾，随后 entries[:_BUCKET_LIMIT] 取前 30 条，桶满后新写入的条目永远被丢弃，缓存内容冻结在最早的 30 条，与注释「保留最近条数」相反。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:143-145 lookup 中 entry.get('vector', []) 对脏数据无防护，_cosine 可能抛 TypeError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-145`
  - 依据：_load_entries 只保证返回 list，不保证元素是 dict 或含合法 vector。若 Redis 中该 key 被其他版本/其他写入方污染（例如 vector 为字符串、entry 为字符串），entry.get 会抛 AttributeError，或 _cosine 中 `sum(a*a for a in left)` 对字符串元素抛 TypeError。该异常发生在 lookup 的 try 块之外（try 只包住 embedder.embed），会直接冒泡到主链路，与「缓存异常一律当未命中」的纵深防御设计相悖。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 _bucket_key 忽略 scope 参数，偏好指纹未进入桶 key（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：文档与注释反复强调 scope（偏好指纹）必须进入桶 key，否则撤回偏好后仍命中旧回复。但实现里 f-string 只拼了 namespace 和 buyer_id，scope 完全未使用，导致偏好变更后旧回复继续被复用，向用户断言已删除的偏好。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:130-133 lookup 忽略 has_history 参数，多轮上下文会话仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:130-133`
  - 依据：模块 docstring 安全边界第 3 条明确要求「会话内已有多轮上下文时不命中」。remember 里检查了 has_history，但 lookup 的守卫只有 `not self._enabled or not is_cacheable_query(query)`，has_history 参数接收后从未使用。因此当会话已有多轮上下文时，只要问句本身不含 _UNSAFE_PATTERNS 中的词（例如「推荐个杯子」），仍会命中跨会话缓存，返回脱离当前上下文的回复——正是 docstring 警告的「跨会话复用会答错」。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:84-86 is_cacheable_query 用 re.search 匹配子串，可能误伤含「这个/那个」等词的正常问句（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:84-86`
  - 依据：这是有意的保守策略：宁可少缓存也不缓存上下文依赖问句，docstring 明确「命中任一则整条不进缓存」。误伤只降低命中率，不产生错误回复，属于设计取舍而非缺陷。
- **[api_misuse/critical]** [api_misuse] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 内联 (?i) 不在表达式开头，re.compile 会抛错（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：Python re 模块要求全局内联标志 (?i) 必须位于整个正则表达式的最开头。这里每个模式都以 (?i) 开头，看似合法；但需注意 re.compile 对每个 pattern 单独编译，(?i) 确实位于各自字符串开头，因此不会抛错。然而真正的问题在于：模块级 _compiled = [re.compile(pattern) for pattern in DANGEROUS_PATTERNS] 在导入时执行，若任一模式非法则整个模块导入失败。逐一检查：r"(?i)ignore\s+(all\s+)?previous\s+instructions?" 开头即 (?i)，合法；其余同理。因此该结论不成立——(?i) 在每个 pattern 字符串开头，re.compile 不会报 global flags not at the start。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-45 sanitize_tool_output 对空字符串返回原值，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-45`
  - 依据：text 为空时直接返回 (False, text)，避免对空串做正则替换，行为正确，不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 content_filter 正则未覆盖大小写混合的中文注入变体（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：正则覆盖了常见中英文注入模式，虽非穷尽，但文档明确说明只做正则、语义级判断交给 L4。不构成可复现缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/output_guard.py:52-58 audit_output 返回 safe=False 时调用方需发告警，但函数本身不区分「命中但已脱敏」与「命中且无法脱敏」，语义上 safe 命名易误导（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:52-58`
  - 依据：docstring 明确写「安全 = 未命中任何敏感模式；命中时文本已就地脱敏，可直接下发」，调用方按此语义使用即可。命名虽可商榷，但契约清晰，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:60-62 audit_output 对空字符串返回 (True, text)，但 text 为 None 时返回 (True, None)，调用方若按 str 处理会出错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-62`
  - 依据：函数签名声明 text: str，`if not text: return True, text` 对空串返回 (True, "")，对 None 返回 (True, None)。虽然 None 不是声明类型，但返回原值保持了幂等性，调用方拿到 None 时通常也会走 falsy 分支。这属于类型契约外的输入，不构成实际缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:47-50 audit_output 对空字符串返回 (True, text)，但 text 为 None 时返回 (True, None) 与类型标注不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:47-50`
  - 依据：`if not text: return True, text` 对 None 也成立，返回 (True, None)。类型标注为 `tuple[bool, str]`，但调用方若传入 None 会得到 None 而非 str。不过该函数签名声明 text: str，传入 None 属于调用方违约；且 `not text` 对空串和 None 都短路，行为一致（不脱敏、原样返回）。在契约内（text 为 str）无缺陷。
- **[logic/medium]** [logic] app/infrastructure/security/output_guard.py:36-37 shopping_session_id 正则只匹配 `:` 或 `=` 分隔，JSON 中带引号的 `"shopping_session_id": "abc"` 无法命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-37`
  - 依据：模式 `shopping_session_id\s*[:=]\s*[\w-]+` 在 JSON 序列化形式 `"shopping_session_id": "sess-123"` 中，`:` 后紧跟空格和引号 `"`，而 `[\w-]+` 不匹配引号，导致匹配失败——泄露的会话 ID 不会被脱敏。Agent 输出内部状态时常见 JSON 形式，这是 L4 闸门的实际漏检。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:43-44 内部工具名正则用 \b 边界，但工具名后紧跟下划线或字母时仍会命中，属预期；然而 `task_dispatch` 未带 _tool 后缀，可能误伤正常英文短语（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-44`
  - 依据：`task_dispatch` 作为独立词出现在买家可见回复中的概率极低，且脱敏方向保守。文档已说明按真实工具集逐个列出以避免宽泛模式误伤，这是刻意的取舍，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:64-72 audit_output 逐模式 subn 时 safe 标志与 cleaned 一致，但多模式命中时 REDACTED 占位符可能被后续模式再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:64-72`
  - 依据：REDACTED = "[已脱敏]" 不含任何敏感模式能匹配的子串（不含工具名、不含 URL、不含 shopping_session_id=），因此后续模式不会再次命中占位符。循环顺序替换是安全的。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:33-40 output_guard 的 SENSITIVE_PATTERNS 中内部工具名正则未转义，且 `\b` 对下划线边界行为需确认（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:33-40`
  - 依据：工具名均为 `[a-z_]+` 形式，`\b` 在 `_` 与字母之间不构成词边界（`_` 是 word 字符），因此 `\bproduct_search_tool\b` 实际匹配的是 `product_search_tool` 前后为非 word 字符的位置。由于工具名以字母开头、以字母结尾，`\b` 在首尾有效，能正确匹配独立出现的工具名。若工具名嵌在更长标识符中（如 `my_product_search_tool`），`\b` 在 `_` 前不成立，不会误匹配——这正是期望行为。未发现缺陷。

## 争议（需裁决）

- **[boundary/medium]** [boundary] app/domain/catalog/money.py:35-43 Money.add/multiply 绕过 of() 校验，可构造负数金额（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 强制 amount 非负，但 add/multiply 直接调用 Money(...) 构造器，dataclass 的 __post_init__ 没有任何校验。虽然 add 的两个操作数若都来自 of() 则和必非负，但 Money 是公开 dataclass，可直接 Money(-5, 'USD') 构造出非法实例，再经 add 传播；更关键的是 multiply 的 quantity 校验了非负，add 却没有任何溢出/符号保护，且整个类没有 __post_init__ 兜底，不变量只在 of() 路径成立，与文档声称的『不变量：amount 必须为非负整数』不符。
  - 争议对手：624e06f60ba7
- **[boundary/medium]** [boundary] app/infrastructure/cache/cached_embedding_client.py:76-76 embed_batch 用 `vector or []` 把合法零向量静默替换为空列表（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-76`
  - 依据：若 inner 返回全零向量（合法但退化），`vector or []` 会把它替换成空列表，破坏返回长度与输入一一对应的契约，下游按索引取向量会拿到空列表，_cosine 直接返回 0.0 或维度不匹配。
  - 争议对手：acbdca1f8d4b
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:68-73 get_json 在 JSON 解码失败时未删除脏键，导致缓存永久污染（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：get_json 在 json.loads 抛 ValueError 时只返回 None，没有删除该键。注释写的是「脏值当未命中，顺手删掉」，但代码里并没有 delete 调用。只要某个键被写入非 JSON 值（例如其他模块用 set 写入裸字符串，或数据被外部污染），每次 get_json 都会重复解析失败并返回 None，缓存条目在 TTL 到期前一直无效，且每次都要多一次 Redis 读 + 解析开销。
  - 争议对手：c53fc98a7633

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：13｜覆盖正常：13｜无法判定：0
- 单 Reader 检出率：80.0%（重捕对 3，已观测 40，估计总体 50.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 4.0% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 4.0% |
| `269088b25c46` | 2 | 0 | `reader_miss` | 4.0% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 4.0% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 4.0% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 4.0% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 4.0% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 4.0% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 4.0% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 4.0% |
| …另有 3 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 2 |

矩阵填充率 22%（单元格值 = 独立 Agent 数）
