# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 29 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：31
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：61 个节点 / 92 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 30 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-143 _rank_by_relevance 注释声称回到原始相对顺序，实际按相关性排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-143`
  - 依据：注释写“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但 picked 直接由 scored[:top_k] 按 (-score, index) 排序得到，并未按原始 index 重新排序。因此输出顺序是相关性降序而非原始顺序，注释与实现不符。虽然不影响选取集合，但会导致注入块行序随 query 变化，与注释声称的稳定性目标相反，属于实现与设计意图不一致的逻辑缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:146-150 _latest_first 用 `p in newest` 依赖 dataclass 相等性，可能误保留重复偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:146-150`
  - 依据：`[p for p in likes if p in newest]` 使用值相等（dataclass 默认 __eq__）而非身份判断。若存在两条字段完全相同的 BuyerPreference（例如同一 statement、同一 kind、同一 created_at 的重复记录），newest 只包含其中一条，但过滤时两条都会命中 `in newest`，导致返回数量超过 top_k，破坏 top_k 预算。此外若 BuyerPreference 未定义 __eq__ 或含不可哈希字段，行为依赖具体实现。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-105 dislike 偏好被 top_k 截断，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-105`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，否则会推荐用户明确拒绝的东西（安全问题）。但 select() 在 dislikes 数量超过 top_k 时，最终 return (dislikes + selected_likes)[:top_k] 会把 dislikes 尾部截掉；更严重的是当 len(dislikes) >= top_k 时，selected_likes 全部被切掉，且部分 dislike 也被丢弃。例如 top_k=2、dislikes 有 3 条时，只注入前 2 条 dislike，第 3 条黑名单丢失，可能推出用户明确拒绝的商品。这与文档承诺的安全语义直接矛盾。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-33 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好会被写入存储，list_by_buyer("") 时可能把不同来源的空买家偏好混在一起，破坏“按买家隔离”的语义。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-33 BuyerPreference 的 created_at 默认空串在 __post_init__ 中填充，但 frozen dataclass 的相等性/哈希会因时间不同而不同（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：created_at 参与 dataclass 相等性，导致同一 buyer/kind/statement 的两条偏好因时间戳不同而不相等。但 PreferenceStore.append 的幂等去重由存储层按 buyer+statement 实现，不依赖值对象相等性；且 created_at 是业务字段，参与相等性合理。不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:38-46 Money.add/multiply 直接构造实例绕过 of() 校验，且未校验 other 类型（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：add 与 multiply 用 Money(...) 直接构造而非 Money.of(...)，绕过了 of 中的非负整数与币种校验。虽然当前输入来自已校验的 self，但 _assert_same_currency 只访问 other.currency，若传入非 Money 对象（如带 currency 属性的鸭子类型或 None）会抛 AttributeError 而非 ValueError；同时 add 未校验 other.amount_in_minor_units 类型，若 other 是手工构造的非法 Money（dataclass 不校验），结果会携带非法值。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 Money.from_major_units 用 round() 对浮点金额四舍五入，存在银行家舍入与浮点误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：Python 的 round 使用银行家舍入（round-half-to-even），且 float 本身有二进制表示误差。例如 round(2.675 * 100) 得到 267 而非 268；round(0.5) 得 0、round(1.5) 得 2。金额换算出现 1 分偏差在电商场景是真实缺陷。模块 docstring 声称“避免浮点误差”，但该入口恰恰引入了浮点误差。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:42-46 Money.multiply 未校验 self.amount 与 quantity 的乘积溢出/类型，但已校验 quantity（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:42-46`
  - 依据：multiply 已校验 quantity 为非负整数且排除 bool，Python 整数无溢出，乘积仍为非负整数，直接构造 Money 合法。不构成缺陷。
- **[logic/high]** [logic] app/domain/catalog/money.py:33-36 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：from_major_units 对所有币种统一乘 100，但 JPY 的最小货币单位就是日元本身（无小数位），1000 JPY 会被存成 100000 minor units，to_major_units/__str__ 再除 100 得到 1000.00，看似自洽，但一旦与外部系统（支付网关、汇率换算、按 minor units 直接比较的代码）交互，JPY 金额会放大 100 倍。注释自己承认“JPY 实际为 1，demo 暂统一”，说明这是已知的简化，但 SUPPORTED_CURRENCIES 明确包含 JPY，属于真实可触发的金额错误。
- **[logic/low]** [logic] app/domain/catalog/product.py:41-42 primary_sku 依赖 skus 顺序，未定义主 SKU 语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:41-42`
  - 依据：__post_init__ 已保证 skus 非空，因此 skus[0] 不会越界。返回第一个 SKU 是明确的约定（列表顺序即优先级），没有证据表明存在错误行为，属于设计选择而非缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-40 ConversationTurn 未校验 content 与 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-40`
  - 依据：__post_init__ 只校验 session_id，buyer_id 与 content 均可为空字符串。对话流水是“谁在什么时候说了什么”的业务记录，buyer_id 为空会导致按买家追溯失效，content 为空会写入无意义记录。与 BuyerPreference 对 statement 做非空校验的同类值对象相比，此处校验缺失。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:24-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 内，VALID_ROLES 定义后从未使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-40`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，从不校验 role。任何拼写错误（如 "Agent"、"assistant"、"user"）都会被静默接受并落库，导致对话流水按 role 过滤/回放时漏数据。VALID_ROLES 成为死代码，说明校验被遗漏。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:62-63 embed 对空输入返回 [] 后取 [0] 会 IndexError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:62-63`
  - 依据：embed 固定传入 [text]，embed_batch 对非空列表返回等长结果，因此 [0] 不会越界；text 为空字符串时仍返回一个元素。不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：返回时 `[vector or [] for vector in results]` 会把 None 和空列表都转成 []，但也会把合法的空向量（某些实现可能返回 []）与未填充项混同。更关键的是：若 inner.embed_batch 返回的列表比 pending 短，zip 会静默截断，剩余 results 保持 None 并被转成 []，调用方拿到长度正确但内容为空的向量而不报错，后续向量检索会得到无意义结果。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型共享缓存向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 完全未参与。若同一 Redis 实例上先后/并行使用不同 embedding 模型（例如切换模型、A/B 两个模型、或不同维度模型），相同文本会命中另一模型写入的向量，导致维度不匹配或语义空间错位，检索结果错误。这是文档与实现不一致导致的真实逻辑缺陷。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:66-76 embed_batch 逐条串行 await 缓存读取，批量场景性能退化（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-76`
  - 依据：循环内对每个 text 串行 await self._safe_get，N 条文本产生 N 次串行 Redis 往返；批量 embedding 的初衷是减少往返，这里反而把一次批量调用拆成 N 次串行 IO，在高延迟 Redis 下显著拖慢。可用 asyncio.gather 并发。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:137-143 close 使用 aclose，旧版 redis-py 无此方法会抛 AttributeError 被吞，连接未真正关闭（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-143`
  - 依据：redis-py 在 5.0.1 之前使用 close() 而非 aclose()。若运行环境安装的是旧版 redis-py，aclose 不存在会抛 AttributeError，被 except 吞掉，连接池不会被关闭，进程退出时可能产生未关闭连接的告警或资源泄漏。虽然影响有限，但属于 API 版本兼容性缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:78-88 get_raw 与 get_json 对同一键的语义不同，get_json 会删除非 JSON 值而 get_raw 不会，混用可能破坏幂等键（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:78-88`
  - 依据：文档字符串已明确警告幂等键必须走 get_raw，不能走 get_json。这是有意的 API 分离，且已在注释中说明风险。不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:126-131 zadd_and_count 的 pipeline 中 expire 使用 int(window_seconds)+1，window_seconds 为小数时截断可能使 TTL 短于窗口（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:126-131`
  - 依据：int(window_seconds)+1 对正数 window_seconds 总是 >= window_seconds（因为 +1 补偿了截断），TTL 不会短于窗口。例如 window_seconds=0.5 时 int(0.5)+1=1 > 0.5。安全。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:96-101 set_json 的 ttl_seconds 未校验，传 0 或负数时 redis 会抛错被吞，缓存静默不写入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:96-101`
  - 依据：redis 的 SET ex=0 会抛 ResponseError（invalid expire time），被 except 吞掉后仅打 warning，调用方以为写入成功。若上游计算 ttl 时因边界（如剩余时间已过期）得到 0 或负数，缓存会静默失效，且没有任何返回值告知调用方。这属于边界值未处理导致的行为静默改变。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:70-76 get_json 在 json.loads 失败时调用 delete，但 delete 自身吞异常，脏值可能永久残留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:70-76`
  - 依据：delete 吞异常是设计意图（缓存故障不能影响主链路），脏值删除失败最多导致下次再读一次脏值再删一次，不会造成错误行为，只是多一次无效读。属于可接受的降级，不构成缺陷。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:178-182 remember 的 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在超过 30 条后被丢弃。结果是缓存永远停留在最旧的一批问句上，新问句无法进入缓存，与设计意图相反。应使用 entries[-_BUCKET_LIMIT:]。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:62-64 _cosine 对维度不一致返回 0.0 而非报错，掩盖向量维度错配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:62-64`
  - 依据：维度不一致时返回 0.0 视为未命中，是保守且安全的降级策略，不会产生错误命中，只是多一次模型调用。属于有意的防御性设计，不构成缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 SemanticCache._bucket_key 忽略 scope 参数，偏好指纹不生效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：_bucket_key 接收 scope 参数并在 docstring 中强调桶 key 必须包含偏好指纹，但实现只对 namespace 和 buyer_id 做哈希，scope 完全没有参与。因此偏好新增/撤回后旧回复不会失效，会命中撤回偏好前的回复，向用户断言已删除的偏好——正是注释里说“实测踩过”的安全问题。lookup/remember 都传入 scope，但被静默丢弃。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:130-137 lookup 忽略 has_history 参数，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:130-137`
  - 依据：安全边界第 3 条要求“会话内已有多轮上下文时不命中”，remember 中检查了 has_history，但 lookup 完全没有使用该参数。因此当会话已有多轮上下文时，只要问句不含 _UNSAFE_PATTERNS 中的词（例如“这款有货吗”不含“这个/那个/它”），仍会命中跨会话缓存，返回脱离上下文的回复。remember 与 lookup 的不对称使该安全边界只在一侧生效。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 中 (?i) 内联标志位于模式开头，Python 3.11+ 对非开头位置会报错但此处合法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：所有模式均以 (?i) 开头，属于全局内联标志，re.compile 合法。Python 3.11 起要求全局标志位于模式开头，这里满足。因此不会在导入时抛 re.error。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:55-63 sanitize_tool_output 逐条 subn 替换，占位符本身可能被后续模式再次匹配或破坏上下文（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-63`
  - 依据：占位符为中文“[内容已过滤：疑似注入]”，不含任何 DANGEROUS_PATTERNS 能匹配的子串（如 system prompt、you are now 等），因此后续模式不会再次命中占位符，不存在重复替换或无限增长。逐条 subn 只是多次扫描，功能正确。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回 safe=True 属正常短路，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：空文本没有任何内容可泄露，返回 (True, text) 是合理的短路，不会造成安全问题。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-45 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-45`
  - 依据：_INTERNAL_TOOLS 中所有名称仅含字母和下划线，拼入正则后无特殊元字符，不会导致正则注入或误匹配。

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-135 zadd_and_count 在 Redis 不可用时返回 0，与 set_if_absent 的 fail-open 策略不一致，导致限流失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-135`
  - 依据：set_if_absent 明确注释说明 Redis 故障时应 fail-open（返回 True 放行），但 zadd_and_count 在异常时返回 0，调用方通常把 0 解释为“窗口内计数为 0”，即未触发限流，这本身是 fail-open 的。但问题在于：当 _client is None（未配置 Redis）时也返回 0，而 enabled 为 False 时调用方可能期望有进程内兜底限流。更关键的是，zadd_and_count 的返回值语义是“窗口内当前数量”，返回 0 在异常时与“窗口为空”无法区分，调用方若用 `count > limit` 判断则放行，若用 `count == 0` 做特殊处理则可能误判。这属于返回值语义在故障路径下被静默改变，调用方无法区分“真的没有请求”和“Redis 挂了”。
  - 争议对手：f90afb31b3cd

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain/catalog, app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 3 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 2 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 1 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 1 |
| `app/infrastructure/security` | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 1 |

矩阵填充率 21%（单元格值 = 独立 Agent 数）
