# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 27 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：29
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：59 个节点 / 88 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 28 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:96-99 top_k<=0 时提前返回空列表，连 dislike 也不注入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-99`
  - 依据：文档强调 dislike 是安全底线、全量保留不参与截断。但 top_k<=0 分支直接 return []，把黑名单也一并丢弃。若调用方因配置错误或预算计算得到 top_k=0，则所有忌口/黑名单偏好都不会注入，可能推荐用户明确拒绝的商品。这与“dislike 全量保留”的契约冲突。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-134 _rank_by_relevance 注释声称回到原始相对顺序，实际按相关性分数排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-134`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按 scored 的顺序（即相关性降序）输出，并未按原始 index 重新排序。因此注入块的行序会随 query 变化而抖动，与注释意图相反。虽然不影响正确性，但注释与实现不一致，且会导致每轮注入顺序不稳定（可能影响 prompt cache 或测试断言）。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-105 dislike 偏好被 top_k 截断，违反“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-105`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，但 select() 最后返回 (dislikes + selected_likes)[:top_k]。当 dislike 数量本身超过 top_k，或 dislikes 与 selected_likes 之和超过 top_k 时，dislikes 会被切片截掉尾部，导致部分黑名单偏好被丢弃。例如 top_k=2、有 3 条 dislike 时，只返回前 2 条 dislike，第 3 条被静默丢弃；top_k=3、2 条 dislike + 2 条 like 时，最后一条 like 被截断（这个可接受），但若 top_k=1、2 条 dislike，则只保留 1 条 dislike。这正是文档所说“推了用户明确拒绝的东西”的安全问题。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:22-30 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-30`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好会被写入存储，list_by_buyer('') 时可能把不同来源的匿名偏好混在一起，破坏“按买家隔离”的语义。
- **[logic/low]** [logic] app/domain/buyer/preference.py:29-30 BuyerPreference 的 created_at 默认空串在 frozen dataclass 中通过 object.__setattr__ 赋值，但未校验格式（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:29-30`
  - 依据：frozen dataclass 中 __post_init__ 用 object.__setattr__ 修改字段是标准做法，能正常工作；created_at 只作为展示/排序用途，未校验格式不构成错误行为。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:35-43 Money.add/multiply 直接构造 Money 绕过 of() 校验，且未校验 other 类型（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造，绕过校验。虽然当前输入来自已校验实例，但 add 未检查 other 是否为 Money（传入非 Money 对象会在 _assert_same_currency 抛 AttributeError 而非明确错误），且 dataclass 本身不校验，任何直接 Money(-1, 'USD') 构造都能产生非法值，of() 的“不变量”并未真正被强制。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-33 Money.from_major_units 用 round() 做银行家舍入，且未校验 major 为负数/NaN 前的类型（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：round() 在 Python 3 使用银行家舍入（round-half-to-even），round(2.675*100)=267 而非 268，round(0.125*100)=12 而非 13，价格换算会出现与业务预期（四舍五入）不一致的分位偏差；同时 float 乘法本身引入二进制误差（如 1.005*100=100.49999...）。金额换算应使用 Decimal 或整数运算。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：from_major_units 对所有币种统一乘 100，但 JPY 的最小单位就是 1 日元（无小数位），SUPPORTED_CURRENCIES 明确包含 JPY。传入 1000 JPY 会得到 100000 minor units，即 1000.00 JPY 的 100 倍；to_major_units 与 __str__ 同样固定除以 100，导致 JPY 金额展示与计算全部放大 100 倍。注释自称“简化处理”，但这是跨境价格核心不变量，属于真实错误行为而非风格问题。
- **[logic/low]** [logic] app/domain/catalog/product.py:17-20 frozen dataclass ProductHighlight 的 detail 默认值安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:17-20`
  - 依据：detail 使用不可变字符串默认值，不存在可变默认参数共享问题；frozen=True 也保证哈希/相等性稳定。无缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:41-42 primary_sku 直接取 skus[0]，依赖列表顺序而非显式主 SKU 标记（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:41-42`
  - 依据：__post_init__ 已保证 skus 非空，因此 skus[0] 不会 IndexError。虽然“主 SKU”语义依赖插入顺序，但这是该聚合根的设计约定，代码本身没有可证明的错误行为，不报告为缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-34 Sku.stock 校验只检查非负，未校验类型，bool 可通过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：`if self.stock < 0` 对 bool 值 True/False 也能比较（True=1, False=0），不会抛错。但 stock 声明为 int，传入 bool 是调用方类型违约，且 bool 是 int 子类，Python 语义上可接受。未构成实际缺陷。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：模块定义了 VALID_ROLES = ('buyer', 'agent')，但 ConversationTurn.__post_init__ 只校验 session_id，未校验 role。非法 role（如 'system'、'tool'、拼写错误）会被静默写入存储，后续按 role 回放/统计时出现脏数据。VALID_ROLES 成为死代码，说明校验被遗漏。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:60-61 embed 对空输入 embed_batch 返回空列表后取 [0] 会 IndexError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:60-61`
  - 依据：embed 固定传入 [text]，embed_batch 对非空输入必然返回长度 1 的列表（pending 或命中都会填充 results[0]），因此 [0] 不会越界。仅当 text 为空字符串时仍会走 inner 并返回一条结果，不触发 IndexError。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-76 embed_batch 用 `vector or []` 兜底，空向量/None 被静默替换为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-76`
  - 依据：若 inner.embed_batch 返回的 fresh 列表比 pending 短（实现缺陷或部分失败），zip 会截断，results 中对应位置仍为 None，最终 `vector or []` 把它变成空列表返回给调用方。调用方拿到长度与输入一致但内容为空的向量，会静默写入向量库或参与余弦计算（_cosine 对空向量返回 0.0），错误被掩盖而非抛出。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型共享同一缓存键（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例上部署了多个模型（或切换模型后未清缓存），不同模型对同一文本会命中彼此的向量，导致向量维度/语义不匹配，检索结果错误甚至维度不一致异常。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:139-145 close 使用 aclose，旧版 redis-py 无此方法导致连接未关闭（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:139-145`
  - 依据：redis.asyncio 的 Redis 客户端在 redis-py 4.2+ 提供 aclose()，更早版本用 close()。项目通过 `import redis.asyncio as aioredis` 使用异步客户端，通常要求较新版本。close 中吞异常，即使方法不存在也不会崩溃，只是连接未优雅关闭。属于版本兼容性边缘情况，不构成明确缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:96-101 set_json 的 ttl_seconds 未校验，传 0 或负数时 redis 会抛异常被吞，缓存静默不写入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:96-101`
  - 依据：set_json 直接把 ttl_seconds 传给 redis 的 `ex` 参数。Redis 对 `EX 0` 或负数会返回错误（invalid expire time），该异常被 except 捕获并只记 warning，缓存静默不写入。调用方若因配置错误传入 0（例如“不过期”的误用），会得到“写成功”的假象而实际未缓存。方法签名未声明 ttl_seconds 必须为正，也没有在入口做校验或把 0 映射为无过期。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:70-76 get_json 在 json.loads 失败时调用 delete，但 delete 自身吞异常，脏值可能永久残留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:70-76`
  - 依据：get_json 在解析失败时调用 self.delete(key) 清理脏值。delete 内部吞掉异常并 pass，因此如果删除失败，脏值会残留，下次读取仍会解析失败并再次尝试删除。但这不会导致错误行为：每次读取都返回 None（按未命中处理），只是多一次无效删除尝试。属于可接受的降级，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:128-137 zadd_and_count 的 expire 在 pipeline 中位于 zcard 之后，results[2] 索引依赖命令顺序，但 expire 失败不影响计数（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-137`
  - 依据：pipeline 中命令顺序为 zremrangebyscore、zadd、zcard、expire，results[2] 对应 zcard，索引正确。expire 在最后设置键过期，即使 expire 失败，zremrangebyscore 也会在下次调用时清理过期成员，不会导致计数永久膨胀。逻辑正确。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:78-88 get_raw 与 get_json 对同一键的语义冲突：get_json 会把非 JSON 值当脏值删除，破坏 get_raw 存储的裸字符串（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:78-88`
  - 依据：get_raw 的 docstring 明确说明幂等键存的是裸 task_id，不能走 get_json，因为 get_json 在 json.loads 失败时会删除键。但两个方法共享同一个 Redis 命名空间，没有任何键前缀隔离。如果调用方误用 get_json 读取一个由 get_raw/set_if_absent 写入的裸字符串键（例如 task_id 是纯数字 '12345'，json.loads('12345') 实际会成功返回 int 12345，类型错误；若是 'abc' 则 ValueError 并删除键），会破坏幂等语义。这是 API 设计上缺少键空间隔离导致的误用风险，且 get_json 的删除行为是破坏性的。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:158-162 remember 截断 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:158-162`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 取的是列表前 30 条，即最旧的 30 条；新追加的条目在超过 30 条后会被直接丢弃，永远写不进缓存。桶满后 remember 实际失效，且旧回复长期占据桶。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:63-65 _cosine 对维度不一致返回 0.0 而非报错，掩盖向量模型不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:63-65`
  - 依据：维度不一致时返回 0.0 会被阈值判定为未命中，属于安全的降级行为，不会产生错误回复，只是多一次模型调用。结合 _key 缺 model 的缺陷，这里反而避免了崩溃，因此本身不构成缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-122 lookup 忽略 has_history 参数，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-122`
  - 依据：安全边界 3 要求会话内已有多轮上下文时不命中。remember 检查了 has_history，但 lookup 的签名接收 has_history 却从未使用，条件只有 enabled 与 is_cacheable_query。因此带上下文的问句（如未被 _UNSAFE_RE 覆盖的指代句）仍会命中跨会话缓存，答非所问。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:24-32 DANGEROUS_PATTERNS 中 system\s*prompt 等模式过宽，会误伤正常商品内容（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：r"(?i)system\s*prompt" 会匹配任何包含 'system prompt' 的正常文本（如商品描述“this book explains how to design a system prompt”），r"(?i)you\s+are\s+now" 会匹配“You are now able to...”这类正常营销文案，r"(?i)扮演.{0,10}角色" 会匹配正常商品描述。这些片段被替换为占位符，导致正常商品信息被破坏，与模块注释“保留其余正常内容”的目标相悖。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-55 sanitize_tool_output 对已过滤文本重复替换，占位符本身可能被再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-55`
  - 依据：占位符 '[内容已过滤：疑似注入]' 不含任何 DANGEROUS_PATTERNS 的关键词（ignore/忽略/system prompt/you are now 等），后续 pattern 不会再次命中它，因此不会出现占位符嵌套或无限替换。逐个 pattern 顺序 subn 是安全的。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:62-64 audit_output 对空字符串返回 safe=True，但 None 输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-64`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回 (True, text)。虽然类型标注是 str，但 None 也会被 `not text` 捕获并原样返回 None，不会抛异常。调用方若期望返回 str 可能拿到 None，但这属于类型契约问题而非本函数缺陷；且函数签名声明 str，传入 None 是调用方违约。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:38-44 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-44`
  - 依据：_INTERNAL_TOOLS 中的名称只含字母和下划线，拼进正则 `\b(?:...)\b` 不会引入元字符问题。`\b` 边界对下划线结尾的名称（如 product_search_tool）能正确匹配，因为 `_` 是单词字符，`\b` 在 `l` 后与非单词字符间成立。未发现实际缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，与 set_if_absent 的 fail-open 语义不一致，导致限流失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：该方法的 docstring 明确说明用于跨进程限流。当 self._client is None（REDIS_URL 未配置）或 pipeline 抛异常时，方法返回 0。调用方通常以 `count > limit` 判断是否限流，返回 0 意味着“窗口内无请求”，即完全放行——这与 set_if_absent 注释中声明的“宁可退化成没有保护也不能拒绝服务”的 fail-open 策略方向一致，但返回值语义是“计数为 0”而非“不限流”。问题在于：如果调用方用 `if count > limit: reject`，0 确实放行；但如果调用方用 `if count <= limit: allow` 或依赖计数做配额扣减/日志，0 会被误读为“当前无流量”。更关键的是，异常分支返回 0 与正常分支返回真实计数无法区分，调用方无法感知限流已失效。这是一个语义模糊的降级返回值，属于 logic 缺陷。
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
| `00e2b01edb94` | 1 | 1 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 3 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 2 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 2 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure/security` | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 20%（单元格值 = 独立 Agent 数）
