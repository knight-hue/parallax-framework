# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 29 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：29
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：58 个节点 / 84 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 29 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-108 top_k 预算只约束 like，dislike 全量保留时总条数可能超出预算（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：看似 top_k 语义不一致（likes 用 top_k 截断，dislikes 不截断），但这是文档刻意设计的安全底线：dislike 必须全量保留。真正的问题在于末尾的 [:top_k] 又反过来截断了 dislike（见上一条 finding），而不是“超出预算”。若去掉末尾切片，行为即符合设计意图。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-141 _rank_by_relevance 注释声称“回到原始相对顺序输出”但实际未复原顺序（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-141`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入”，但代码直接返回按相关性分数排序后的 picked，并未按原始 index 重新排序。结果注入块的行序随 query 变化而抖动，与注释承诺相反，可能导致 prompt 前缀不稳定/重复注入。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:143-148 _latest_first 用 `p in newest` 依赖 dataclass 相等性，可能误保留重复偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:143-148`
  - 依据：`[p for p in likes if p in newest]` 使用值相等（dataclass 默认 __eq__）而非身份判断。若存在两条字段完全相同的偏好（同 kind/statement/created_at），newest 只含其中一条，但过滤时两条都会命中 `in newest`，导致返回条数超过 top_k，破坏预算约束。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-108 dislike 偏好被 top_k 截断，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单会导致推荐用户明确拒绝的商品（安全问题）。但 select() 在最后返回 (dislikes + selected_likes)[:top_k]，这个切片会同时截断 dislikes。当 dislike 数量 >= top_k 时，部分 dislike 被丢弃；当 dislike 数量 > top_k 时甚至可能一条 like 都进不来，且被丢弃的正是排在后面的 dislike。触发条件很常见：买家积累的忌口条数达到或超过注入预算 top_k。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:24-32 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-32`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好可被构造并 append，list_by_buyer('') 会把所有空 buyer 的偏好混在一起返回，跨买家串数据。作为跨会话持久化的键，buyer_id 为空是明确的边界缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:24-32 BuyerPreference 的 created_at 默认空串在 frozen dataclass 中用 object.__setattr__ 赋值，但未校验传入值格式（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-32`
  - 依据：created_at 是字符串时间戳，传入任意字符串（如 'not-a-date'）不会被校验，但该字段仅用于展示/排序，且默认值生成正确。不构成真实缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-33 Money.from_major_units 用 round() 对浮点金额取整，存在银行家舍入与浮点误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：round() 使用银行家舍入（round-half-to-even），且输入是 float，0.1+0.2 类误差会传导到分。例如 round(2.675*100) 得到 267 而非 268；round(0.5*100)=50 但 round(1.5*100)=150、round(2.5*100)=200（2.5 元被舍成 2 元）。金额换算应使用 Decimal 或整数运算，这里直接违背了模块文档“避免浮点误差”的初衷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:35-43 Money.add/multiply 直接构造实例绕过 of() 校验，可产生非法 Money（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造，跳过校验。虽然 add 校验了币种一致、multiply 校验了 quantity，但两者都未校验 self 本身是否合法（Money 是 frozen dataclass，用户可直接 Money(-5, 'USD') 构造）。更关键的是 multiply 允许 quantity 为 0 得到 0 金额，这本身合法；但 add 未校验 other 类型，传入非 Money 会在 _assert_same_currency 抛 AttributeError 而非 ValueError。整体上不变量“amount 非负整数”在 add/multiply 路径上未被强制。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:42-43 primary_sku 在 skus 为空时抛 IndexError 而非明确异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:42-43`
  - 依据：__post_init__ 已保证构造时 skus 非空，正常路径下 primary_sku 不会越界；只有外部绕过不变量修改 skus 才会触发，属于上一条同一根因，不单独算缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/product.py:47-52 searchable_text 中 highlight_text 可能为 None 导致 join 抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：highlight_text 由 " ".join(...) 生成，永远是 str，不会是 None；列表元素 title/brand/category/origin_country/description 都是 dataclass 声明的 str 字段。虽然调用方可能传入 None，但那是调用方违反类型契约，不是本函数缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:24-40 Product 为可变 dataclass 且 skus 列表可被外部修改，破坏 __post_init__ 不变量（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:24-40`
  - 依据：Product 不是 frozen，skus 是可变 list，外部可以 product.skus.clear() 使 primary_sku() 抛 IndexError。但这是聚合根设计的常见取舍，代码中没有直接触发该问题的路径；仅凭“可变”不能判定为缺陷。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:22-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 内，VALID_ROLES 定义后未被使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:22-40`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，未校验 role。任何字符串（如 'system'、'tool'、空串）都能构造成功并落库，破坏“业务可读对话流水”的角色语义，下游按 role 过滤/回放时会漏数据或误分类。VALID_ROLES 成为死代码也印证校验被遗漏。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：若 inner.embed_batch 返回的某个向量为空列表（合法但无意义的返回），`vector or []` 会把它变成 []，调用方无法区分“未取到”与“空向量”。更关键的是 zip(pending, fresh) 在 fresh 长度短于 pending 时静默截断，剩余 results 保持 None，最终被 `or []` 变成空向量而不报错，导致下游向量索引写入维度不匹配的空向量。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 缓存 key 未包含 model，换模型后可能复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例被不同模型（或不同维度模型）的 CachedEmbeddingClient 共用，会命中另一模型生成的向量，导致维度不匹配或语义错误。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:70-78 embed_batch 逐条串行 await 缓存读取，批量场景性能退化（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:70-78`
  - 依据：循环内对每个 text 串行 await self._safe_get，N 条文本产生 N 次串行 Redis 往返；批量 embedding 的初衷是减少往返，这里反而把一次批量拆成 N 次串行 IO，在批量较大时显著增加延迟。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:135-141 close 使用 aclose，旧版 redis-py 无此方法导致连接未释放（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:135-141`
  - 依据：redis.asyncio 在 redis-py 4.2+ 提供 aclose；若版本过旧会抛 AttributeError 被 except 吞掉，连接池可能未优雅关闭，但进程退出时由 GC 回收，影响有限。属于版本兼容性风险而非确定缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:88-93 set_json 的 ttl_seconds 未校验正数，传 0 或负数时 Redis 报错被吞导致缓存静默失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:88-93`
  - 依据：Redis 对 ex<=0 会报错，但异常被捕获并记录 warning，行为退化为未写入，符合本类“写失败跳过缓存”的既定语义，不会产生错误数据。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:130-133 zadd_and_count 在 Redis 故障时返回 0，限流完全失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:130-133`
  - 依据：返回 0 表示窗口内无请求，调用方据此判定未超限，即放行。这与 set_if_absent 的降级哲学一致（缓存故障不阻断主链路），属于有意设计。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:69-72 get_json 中 delete 调用未捕获异常，但 delete 内部已吞异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:69-72`
  - 依据：delete 方法内部 try/except 吞掉所有异常，因此 get_json 中 await self.delete(key) 不会抛出，不会破坏 get_json 的降级语义。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:108-121 set_if_absent 在 Redis 故障时返回 True，幂等键与分布式锁退化为无保护（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-121`
  - 依据：文档明确说明这是有意的降级策略：宁可退化成没有幂等保护，也不能因缓存故障拒绝服务。这是设计取舍而非缺陷，但调用方需知晓该语义。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:178-182 remember 中 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在超过 30 条后被丢弃。结果是缓存永远停留在最初 30 条，新问句无法进入，且旧条目长期占据桶。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:78-80 _cosine 对维度不一致返回 0.0 而非跳过，属安全降级（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:78-80`
  - 依据：维度不一致时返回 0.0，低于阈值 0.95，等价于未命中，不会误命中错误回复。这是合理的防御行为，不构成缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-127 scope 参数被忽略，桶 key 不含偏好指纹，撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-127`
  - 依据：_bucket_key 接收 scope 参数，但计算 digest 时只用了 namespace 和 buyer_id，scope 完全没有参与哈希。文档明确要求 scope 装载偏好指纹，使偏好变更后旧回复自动失效。实际实现下，买家撤回“不要塑料”偏好后，桶 key 不变，lookup 仍会命中撤回前生成的回复，向用户断言已删除的偏好。这是文档中“实测踩过”的安全边界被代码违背。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:129-137 lookup 忽略 has_history 参数，多轮上下文会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:129-137`
  - 依据：文档安全边界第 3 条要求“会话内已有多轮上下文时不命中”。remember 中检查了 has_history，但 lookup 完全没有使用该参数，只要 query 通过 is_cacheable_query 就会查桶并返回命中。像“多少钱”这类不含 _UNSAFE_PATTERNS 的短问句在有上下文时会被错误复用，答非所问。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:96-98 is_cacheable_query 用子串匹配拦截，可能过度拦截但不会漏放（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:96-98`
  - 依据：正则子串匹配会拦截含“这个”“它”等词的问句，属于保守策略（宁可多花调用），符合文档“宁可多花一次调用”的取向，不构成安全缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/content_filter.py:44-56 sanitize_tool_output 对空字符串返回原值，但非字符串输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-56`
  - 依据：函数签名标注 text: str，调用方应保证传入字符串。`if not text` 对 None 也会返回 (False, None)，但类型契约已排除。工具返回内容在注入前通常已序列化为字符串。不构成真实缺陷。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 危险模式正则未覆盖大小写混排的中文/变体注入，且 system prompt 模式过宽会误伤正常商品描述（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：这是基于正则的启发式过滤，文档已明确“真正的语义级判断交给 L4”。模式覆盖有限是设计取舍而非缺陷；`system\s*prompt` 可能误伤含该词的商品描述，但替换为占位符而非丢弃整条，影响可控。不认定为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:44-46 SENSITIVE_PATTERNS 中内部工具名用 \b 边界，下划线连接时可能漏匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-46`
  - 依据：工具名本身以字母开头、以下划线或字母结尾，\b 在字母与下划线之间不成立，但工具名整体作为独立 token 出现时（前后为空格/标点/中文）能正常匹配。若工具名紧贴其他标识符（如 `xproduct_search_tool`）会漏匹配，但这属于刻意收窄范围、避免误伤正常措辞的设计取舍，且实际泄露场景中工具名通常独立出现，不构成确认缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回 safe=True 属正常短路（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：空文本没有可泄露内容，返回 (True, text) 是合理短路，不构成缺陷。

## 争议（需裁决）

（无）

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
| `1ea202d2ad5b` | 1 | 4 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 2 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 3 | `partition_gap` | — |
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
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 1 |
| `app/infrastructure/security` | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 20%（单元格值 = 独立 Agent 数）
