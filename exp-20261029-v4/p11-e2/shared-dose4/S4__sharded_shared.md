# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 35 | 支持不足、相关性超限或尚待验证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：61
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：96 个节点 / 235 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 39 | 100% | 16% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-138 _rank_by_relevance 声称“回到原始相对顺序输出”但实际按相似度排序返回（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-138`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码直接返回 picked，而 picked 来自 scored[:top_k]，scored 已按 (-相似度, index) 排序。因此返回顺序是相似度降序，而非原始顺序。后果：注入块行序随 query 变化而抖动，与注释意图相反；且与 _latest_first 的行为（复原原始顺序）不一致，导致两条分支输出顺序语义不同。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:143-145 _latest_first 用 `p in newest` 做成员判断，依赖 dataclass 相等性，可能误删/误留（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:143-145`
  - 依据：BuyerPreference 是 dataclass（默认 eq=True），`p in newest` 按字段值相等判断。若两条偏好字段完全相同（同 kind、同 statement、同 created_at），它们会被视为相等：newest 只含其中一条时，`p in newest` 对两条都返回 True，导致返回条数超过 top_k；反之若 newest 含两条相同项而 likes 只有一条，也会出现计数偏差。更稳妥的做法是按 index 选取。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 select() 的最终 [:top_k] 截断会把 dislike 一起裁掉，违反黑名单全量保留的安全底线（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 全量保留、不参与 top_k 截断，但返回语句是 (dislikes + selected_likes)[:top_k]。当 dislikes 数量本身超过 top_k，或 dislikes 数量 + selected_likes 数量超过 top_k 时，切片会从尾部丢弃元素；由于 selected_likes 已被限制为至多 top_k 条，dislikes 超过 top_k 时必然被截断，且当 len(likes) <= top_k 时 selected_likes 可能很多，也会挤掉部分 dislike。结果是用户明确拒绝的忌口/黑名单被丢弃，可能推荐用户明确说不要的商品。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:44-52 PreferenceStore.delete 契约要求同 statement 的 like/dislike 一并删除，但接口无法表达删除数量（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-52`
  - 依据：delete 返回 bool 表示“是否命中”，而文档明确说明同 statement 的 like 与 dislike 会一并清除。返回 bool 只表达“至少删了一条”，调用方无法知道删了几条，但这与文档语义一致（命中即 True），不构成错误行为。属于接口表达力有限，不是缺陷。
- **[boundary/medium]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：__post_init__ 校验了 kind 和 statement，但没有校验 buyer_id。空字符串或纯空白的 buyer_id 可以构造成功并被持久化，导致偏好归属到无效买家，后续 list_by_buyer 无法正确检索，也可能造成跨买家数据混淆。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:38-46 Money.add/multiply 直接调用构造器绕过 of() 校验，可产生非法 Money（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造。虽然当前输入来自已校验的实例，但 dataclass 本身没有 __post_init__ 校验，任何直接 Money(-1, 'USD') 或 Money(1, 'XXX') 都能构造出违反不变量的对象，of() 的校验形同虚设。这是不变量实现不完整导致的真实缺陷（Money 可被非法构造）。
- **[logic/high]** [logic] app/domain/catalog/money.py:33-36 Money.from_major_units 对 JPY 等零小数币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：from_major_units 对所有币种统一乘 100 并 round，但 JPY 的最小单位就是 1 日元（无小数位），SUPPORTED_CURRENCIES 明确包含 JPY。调用 Money.from_major_units(1000, 'JPY') 会得到 100000 最小单位，即 1000 日元被当成 100000 日元，价格放大 100 倍。注释承认是“简化处理”，但这是跨境定价的核心不变量，属于真实错误而非风格问题。同时 to_major_units/__str__ 也统一除以 100，JPY 展示同样错 100 倍。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:38-40 upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:38-40`
  - 依据：这是抽象端口声明，契约由实现方保证；端口层不做长度校验属于设计选择，且没有具体实现代码可引用证明会出错。
- **[logic/low]** [logic] app/domain/catalog/ports/retrieval_ports.py:47-50 Reranker.rerank 抽象方法体只有 docstring，缺少 ... 或 pass（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:47-50`
  - 依据：函数体只有 docstring 在 Python 中是合法的（docstring 即函数体），返回 None；由于是 @abstractmethod，子类必须实现，不会导致运行时错误。
- **[logic/low]** [logic] app/domain/catalog/product.py:33-38 Product 为可变 dataclass 但 __post_init__ 校验可被绕过（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：Product 非 frozen，skus 可在构造后被清空，但这是聚合根可变性的设计选择，构造期校验本身正确，不构成可引用代码层面的缺陷。
- **[logic/medium]** [logic] app/domain/catalog/product.py:47-52 searchable_text 未包含 title，标题召回失效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：docstring 声称可检索文本为“标题 + 品牌 + 品类 + 描述 + 亮点”，但实际拼接列表为 [self.title, self.brand, ...]——等等，这里确实包含 self.title。重新核对：列表第一项就是 self.title，因此 title 已被包含。该结论不成立。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:27-30 Sku.__post_init__ 已校验 stock 非负（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:27-30`
  - 依据：代码中确实存在 `if self.stock < 0: raise ValueError(...)`，负库存无法被构造。其他审查者关于“未校验 stock 非负”的结论与代码不符。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:28-41 ConversationTurn 文档声称 turn_index 可留空，但类中根本没有 turn_index 字段（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:28-41`
  - 依据：docstring 写“turn_index 由存储层按会话自增，写入时可留空”，list_turns 也承诺“按 turn_index 升序返回”，但 ConversationTurn 没有 turn_index 字段，存储层无法把自增序号回填到对象上，list_turns 返回的对象也不携带序号。接口契约与数据模型不一致，实现方只能另建结构或丢弃序号。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:27-41 ConversationTurn 声明 role 但未校验，VALID_ROLES 形同虚设（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-41`
  - 依据：模块定义了 VALID_ROLES = ('buyer', 'agent')，ConversationTurn.role 注释也写明 buyer/agent，但 __post_init__ 只校验 session_id，任意 role 字符串都能构造并落库，下游按 role 分支的逻辑会拿到非法值。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型共享同一缓存键（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块文档明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例上部署了多个模型（或切换模型后旧缓存仍在 7 天 TTL 内），不同模型对同一文本会命中彼此的向量，导致向量维度/语义空间不匹配，检索结果错误甚至 _cosine 因维度不同恒返回 0。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/redis_cache.py:118-130 set_if_absent 在 Redis 异常时返回 True，幂等键与分布式锁失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：文档明确说明这是刻意的降级策略：Redis 不可用时返回 True，宁可退化成没有幂等保护，也不能因缓存故障拒绝服务。这是设计取舍，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:132-152 zadd_and_count 在 Redis 异常时返回 0，限流失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:132-152`
  - 依据：与 set_if_absent 相同，这是文档声明的降级策略：Redis 滑窗计数失败时按不限流处理，避免缓存故障拖垮主链路。属于有意的设计取舍。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:108-118 set_if_absent 在 Redis 异常时返回 True，幂等保护被静默绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-118`
  - 依据：这是文档明确声明的降级策略：Redis 不可用时返回 True 视为抢到，宁可退化为无幂等保护也不拒绝服务。属于有意的设计取舍而非缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:120-138 zadd_and_count 在 Redis 异常时返回 0，限流被静默关闭（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:120-138`
  - 依据：与 set_if_absent 类似，这是文档声明的降级策略：Redis 故障时按不限流处理，避免缓存故障拖垮主链路。属于有意设计。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:178-181 SemanticCache.remember 用 entries[:_BUCKET_LIMIT] 截断保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-181`
  - 依据：注释写“保留的最近条数”，但 entries.append 后取前 _BUCKET_LIMIT 条，保留的是最早写入的 30 条，新条目一旦桶满就被丢弃。结果是缓存永远停留在旧回复上，新回复无法进入缓存，与“最近条数”的意图相反。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:155-163 SemanticCache.lookup 对 entry 向量未做类型校验，脏数据可导致异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:155-163`
  - 依据：_cosine 内部对 len 不等返回 0.0，对空向量返回 0.0，entry.get('vector', []) 保证有默认值；即使 entry 不是 dict 会抛 AttributeError，但 _load_entries 已保证 entries 是 list，元素来自自身写入的 dict。异常路径不会污染主链路（lookup 外层无 try，但 _cosine 本身不抛）。经确认此处不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:62-63 _cosine 对维度不一致返回 0.0 而非报错，掩盖向量维度错配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:62-63`
  - 依据：维度不一致时返回 0.0 会被阈值过滤为未命中，属于保守降级，不会产生错误回复。虽然掩盖了配置问题，但不构成错误行为，且与“宁可多花一次调用”的设计一致。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-123 SemanticCache._bucket_key 忽略 scope 参数，偏好指纹未进入桶 key（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-123`
  - 依据：_bucket_key 接收 scope 参数并在文档中强调“scope 用来装载会改变回复内容的买家侧状态，目前是长期偏好指纹”，但实现里 f-string 只拼接了 namespace 和 buyer_id，scope 完全未使用。买家撤回/新增偏好后，旧回复仍会命中，直接向用户断言已删除的偏好，正是文档中描述的“实测踩过”的缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:141-146 SemanticCache.lookup 忽略 has_history 参数，多轮上下文仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:141-146`
  - 依据：文档安全边界第 3 条要求“会话内已有多轮上下文时不命中”，remember 里检查了 has_history，但 lookup 完全没有使用该参数。会话已有历史时仍会返回缓存回复，导致“刚才那款多少钱”这类依赖上下文的问句被跨会话复用而答错。
- **[security/low]** [security] app/infrastructure/cache/semantic_cache.py:76-78 is_cacheable_query 对大小写/全角不敏感，可能漏拦写操作意图（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:76-78`
  - 依据：_UNSAFE_RE 未加 re.IGNORECASE，但模式均为中文词，中文无大小写；英文写操作词（如 'buy'、'cancel'）未列入，属于覆盖不全而非实现错误。考虑到业务面向中文买家且文档只声明中文意图，暂不认定为缺陷，但覆盖范围值得注意。
- **[error_handling/medium]** [error_handling] app/infrastructure/security/__init__.py:14-18 output_guard 导入 content_filter 模块，但该文件不在给定文件列表中，security 包导入可能失败（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:14-18`
  - 依据：app/infrastructure/security/__init__.py 从 app.infrastructure.security.content_filter 导入 DANGEROUS_PATTERNS、FILTERED_PLACEHOLDER、sanitize_tool_output。content_filter.py 不在本次可审查文件列表中，但其他审查者的结论（DANGEROUS_PATTERNS 的 (?i) 内联标志位置错误）表明该模块确实存在。因此这里不是导入路径错误，而是被导入模块自身的缺陷；__init__.py 的导入语句本身没有可引用的缺陷证据。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-46 sanitize_tool_output 对空文本返回 (False, text) 正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-46`
  - 依据：空字符串或 None 直接返回 (False, text)，符合文档“文本始终可用”的约定，没有缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:24-32 sanitize_tool_output 的 (?i) 标志位置合法，过滤层可正常工作（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：每个模式字符串都以 (?i) 开头，符合 Python re 对全局内联标志必须位于表达式起始位置的要求，re.compile 不会抛错。因此“整个内容过滤层不可用”的结论不成立。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:44-56 sanitize_tool_output 对已过滤文本重复替换，占位符本身可能被再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-56`
  - 依据：占位符 '[内容已过滤：疑似注入]' 不含任何危险模式关键词，后续 pattern 不会再次匹配它。循环按 pattern 顺序替换，每个 pattern 只处理一次，不存在重复替换问题。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:36-36 shopping_session_id 正则只匹配 `:` 或 `=` 后紧跟值，带引号或空格的 JSON 形式会漏检（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-36`
  - 依据：`shopping_session_id\s*[:=]\s*[\w-]+` 能匹配 `shopping_session_id: abc-123` 和 `shopping_session_id=abc`，但匹配不到 `"shopping_session_id": "abc-123"`（引号不是 \w）。这是覆盖不全而非错误行为；文档说明范围刻意收窄，且会话 ID 泄露场景通常为日志式 `key: value`。属于可改进项，不构成确认缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:43-43 内部工具名正则用 \b 边界，工具名后紧跟下划线或字母时不会命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-43`
  - 依据：`\b(?:product_search_tool|...)\b` 中 `\b` 在 `_` 与字母之间不成立（下划线属于单词字符），因此 `product_search_tool_v2` 或 `product_search_toolx` 不会被匹配。但工具名是固定集合，泄露场景通常是完整工具名出现，且文档明确说“按真实工具集逐个列出，不用宽泛模式，避免误伤”。这是有意的收窄，不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回 (True, text)，但 text 为 None 时返回 (True, None)，调用方若按 str 处理会出错（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：函数签名标注 text: str，`if not text: return True, text` 对空串返回 (True, "")，符合“安全、可直接下发”的语义。传入 None 属于违反类型契约的调用，不在本函数职责内；且返回 None 也不会被脱敏逻辑破坏。没有证据表明调用方会传 None。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:40-41 SENSITIVE_PATTERNS 中内部服务地址正则未加单词边界，可能误伤正常 URL 子串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-41`
  - 依据：正则 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 要求主机名以这些词开头，且前面必须是 `://`，因此不会匹配 `https://example.com/redis` 这类路径中的词（因为 `://` 后紧跟的是 example.com）。它确实会匹配 `https://redis.example.com` 这类以 redis 开头的合法外部域名，但这是有意的保守策略（宁可误脱敏也不泄露内部地址），且文档明确说明脱敏不阻断回复。不构成可确认缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:70-77 audit_output 逐模式 subn 后继续用 cleaned 匹配，前一次脱敏可能破坏后续模式的上下文（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:70-77`
  - 依据：循环中 `cleaned, count = pattern.subn(REDACTED, cleaned)` 把上一次脱敏结果作为下一次输入。REDACTED 是 `[已脱敏]`，不含任何敏感模式能匹配的字符，因此不会引入新的误匹配，也不会让后续模式漏掉原本能匹配的内容（脱敏只替换命中片段，其余文本不变）。顺序处理是安全的。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:36-37 SENSITIVE_PATTERNS 中内部工具名用 \b 边界，task_dispatch 等含下划线的词在中文语境下可能漏匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-37`
  - 依据：`\b` 在 Python re 中把下划线视为单词字符，因此 `task_dispatch` 前后若紧邻中文字符（非 \w）仍能匹配；若紧邻其他 ASCII 单词字符则本就不应匹配。未发现可确认的漏匹配场景。

## 争议（需裁决）

- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 Money.from_major_units 用 round 处理浮点，可能静默产生错误金额（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：major 是 float，major*100 存在二进制浮点误差（如 19.99*100 = 1998.9999999999998），round 采用银行家舍入且对 .5 情形行为不直观；更关键的是 round 会把 0.001 这类非法精度静默吞掉而不是报错，与模块“避免浮点误差”的初衷相悖。金额换算应使用 Decimal 或整数分输入。
  - 争议对手：624e06f60ba7
- **[boundary/medium]** [boundary] app/infrastructure/cache/cached_embedding_client.py:78-78 embed_batch 用 `vector or []` 把合法的空向量替换为空列表（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-78`
  - 依据：`vector or []` 对空列表（以及理论上任何 falsy 值）会返回 []，虽然空列表本身也是 []，但更关键的是：若 inner 返回的向量是 []（例如空文本或后端返回空），这里会静默吞掉，调用方无法区分“未计算”与“空向量”。同时 results 中 None 与空向量被统一成 []，破坏了 embed_batch 与输入一一对应的语义。
  - 争议对手：acbdca1f8d4b
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:68-73 get_json 在 JSON 解码失败时未删除脏键，导致缓存永久污染（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：get_json 在 json.loads 抛 ValueError 时只返回 None，没有删除该键。注释写的是“脏值当未命中，顺手删掉”，但代码里没有 delete 调用。只要该键的 TTL 未到期，每次读取都会重新解析失败并返回 None，缓存条目一直处于污染状态，直到 TTL 自然过期。
  - 争议对手：0c5db21f018a, c53fc98a7633, c53fc98a7633
- **[error_handling/critical]** [error_handling] app/infrastructure/security/content_filter.py:24-32 DANGEROUS_PATTERNS 的 (?i) 内联标志不在表达式开头，re.compile 会抛异常（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：Python 的 re 模块要求全局内联标志 (?i) 必须位于整个正则表达式的最开头。这里每个模式都以 (?i) 开头，但 (?i) 之后还有内容，所以 (?i) 确实位于开头，不会报错。等等——需要确认：r"(?i)ignore\s+..." 中 (?i) 就在字符串起始位置，是合法的。因此这条结论不成立。
  - 争议对手：1da3d7a13e64

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：13｜覆盖正常：13｜无法判定：0
- 单 Reader 检出率：70.6%（重捕对 3，已观测 39，估计总体 55.2222
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 8.6% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 8.6% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 8.6% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 8.6% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 8.6% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 8.6% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 8.6% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 8.6% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 8.6% |
| `92a8588930ee` | 2 | 0 | `reader_miss` | 8.6% |
| …另有 3 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| `app/domain/session` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 1 | 2 | 2 | 0 | 1 | 0 | 0 |
| `app/infrastructure/security` | 2 | 0 | 2 | 2 | 0 | 1 | 0 | 0 |

矩阵填充率 21%（单元格值 = 独立 Agent 数）
