# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 30 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：30
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：61 个节点 / 86 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 30 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:47-56 render_preference_hint 在 preferences 为空时仍生成带空正文的注入块（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:47-56`
  - 依据：render_preference_hint 对空列表会生成 `<buyer-preferences>\n...\n\n</buyer-preferences>`，正文为空。但 select() 在 preferences 为空时返回 []，调用方通常不会对空结果调用渲染；且即便调用，也只是注入一个空块，不构成错误行为。属于边界但非缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-37 _cosine 对长度不一致向量返回 0.0 而非报错，可能掩盖 embedding 维度不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：长度不一致时返回 0.0 是刻意的降级策略，避免因单个向量维度异常导致整个选偏好流程崩溃；且 _rank_by_relevance 已对向量数量做校验。返回 0.0 会让该偏好排到末尾，符合「异常不阻断对话」的设计。不构成缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-135 _rank_by_relevance 注释声称「回到原始相对顺序输出」，但实际按相似度排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-135`
  - 依据：注释说「回到原始相对顺序输出，避免注入块的行序每轮抖动」，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度降序输出，并未恢复原始顺序。这与 _latest_first 的实现（确实恢复了原始顺序）不一致，导致注入块行序随 query 变化而抖动，与注释意图相反。虽然不影响正确性，但注释与实现矛盾，且与另一分支行为不一致，属于可复现的行为偏差。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-99 select() 用 [:top_k] 截断会把 dislike 挤掉，违背「dislike 全量保留」的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-99`
  - 依据：模块文档明确承诺 dislike 全量保留、不参与 top_k 截断，但实现把 dislikes 与 selected_likes 拼接后又做了一次 [:top_k] 截断。当 dislike 数量 >= top_k 时，末尾的 dislike 会被切掉；当 dislike 数量 < top_k 时，likes 的选取也按 top_k 而非 top_k - len(dislikes) 计算，导致最终注入条数被截断且部分 dislike 丢失。触发条件：preferences 中 dislike 条数 >= top_k（例如 top_k=2、有 3 条 dislike），或 dislike 与 like 总数超过 top_k。这正是文档所说的「推了用户明确拒绝的东西」的安全问题。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:44-55 PreferenceStore.delete 的精确匹配语义依赖实现，端口层未约束 statement 规范化（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-55`
  - 依据：文档明确说明 delete 按 statement 精确匹配、不做模糊匹配，并说明未命中时调用方应回传现存列表让模型用原文重试。这是有意的设计取舍（避免误删相似语句），端口层不强制规范化是合理的，因为规范化（trim/大小写）会改变“精确匹配”的语义。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:32-33 created_at 只校验空值，不校验格式，非法时间字符串会被接受（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:32-33`
  - 依据：created_at 是 str 类型，__post_init__ 仅在为空时填充当前时间，对非空值不做任何格式校验。调用方传入 '2024/01/01' 或 'yesterday' 都会被接受，后续按时间排序/比较偏好的逻辑会出错或抛异常。ConversationTurn 的 created_at 同样只依赖 default_factory，但至少没有暴露可传入非法值的路径（仍可显式传入非法值）。
- **[logic/low]** [logic] app/domain/buyer/preference.py:36-39 append 的幂等去重语义未在端口层定义键，可能因实现差异导致重复（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:36-39`
  - 依据：文档写明“同 buyer 同 statement 幂等去重”，去重键（buyer_id + statement）已足够明确，kind 不参与去重是有意为之（与 delete 不区分 kind 一致）。端口层不实现逻辑是 ABC 的正常形态，具体去重由 Infrastructure 实现负责，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:31-33 from_major_units 用 round 处理浮点，存在银行家舍入与精度问题（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-33`
  - 依据：round() 使用银行家舍入（round-half-to-even），且浮点乘法本身有精度误差。例如 from_major_units(2.675, 'USD') 因 2.675*100=267.49999... 得到 267 而非 268；from_major_units(0.125, 'USD') 得 12（偶数）而非 13。金额换算应使用 Decimal 或整数运算。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:45-46 to_major_units 返回 float，可能引入精度误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-46`
  - 依据：金额除以 100 返回 float，对某些值无法精确表示（如 0.1、0.29），下游若用该 float 做比较或再运算会累积误差。虽然 __str__ 用 .2f 格式化掩盖了显示问题，但公开 API 返回 float 本身有风险。
- **[error_handling/low]** [error_handling] app/domain/catalog/money.py:36-38 add 未校验 other 类型，非 Money 对象会抛 AttributeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-38`
  - 依据：add 调用 _assert_same_currency(other) 访问 other.currency，若 other 非 Money 会抛 AttributeError 而非 ValueError。但这属于 Python 动态类型的常规行为，且类型标注已声明 other: Money，调用方违反契约时抛 AttributeError 可接受，不构成真实缺陷。
- **[logic/low]** [logic] app/domain/catalog/money.py:24-28 multiply 拒绝 bool 但 of 接受 bool（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:24-28`
  - 依据：multiply 显式排除 bool（isinstance(quantity, bool)），但 of 的校验 `isinstance(amount, int)` 对 True/False 返回 True，因此 Money.of(True, 'USD') 会创建金额为 1 的 Money。两处对 bool 的处理不一致，of 的校验存在漏洞。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-40 Product 为可变 dataclass 且 skus 列表可被外部修改，绕过 __post_init__ 校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-40`
  - 依据：Product 是可变 dataclass，skus 列表可被外部 append/clear，从而绕过 __post_init__ 的「至少一个 Sku」校验。但这是 Python dataclass 的常见模式，且代码中未见外部修改 skus 的路径；是否应改为不可变属于设计选择，无法从现有代码确认会导致实际错误。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 未包含 skus 的规格信息，可能影响召回（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 的 docstring 明确说明只包含标题+品牌+品类+描述+亮点，未承诺包含 SKU 规格。这是设计选择而非缺陷；SKU 规格是否应参与召回属于产品决策，无法从代码判定为错误。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-38 ConversationTurn 未校验 buyer_id 与 content，与 session_id 校验不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-38`
  - 依据：__post_init__ 只对 session_id 做非空校验，而 buyer_id 和 content 是必填字段（无默认值）却允许空字符串。空 buyer_id 会让按买家维度的追溯/客服排查失效，空 content 会写入无意义的对话流水。虽然 dataclass 强制传参，但传空串是合法调用，校验缺失导致脏数据落库。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:41-48 ConversationEventRecord 完全无校验，session_id/type 可为空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:41-48`
  - 依据：ConversationEventRecord 没有 __post_init__，session_id、type、payload 均可为空/None。append_events 批量写入时，空 session_id 的事件无法归属到任何会话，空 type 的事件无法被回放/过滤，与 ConversationTurn 对 session_id 的校验标准不一致。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:63-65 list_turns 的 limit 参数未约束，负数/0 行为未定义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:63-65`
  - 依据：limit 默认 50，端口层未校验负数/0，但这是抽象方法，具体行为由实现决定；调用方传负数属于调用方错误，且不同存储（SQL LIMIT -1 在部分方言中表示无限制）语义不同，端口层强行校验反而限制实现。不构成确认缺陷。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:22-38 ConversationTurn 未校验 role 取值，VALID_ROLES 定义后从未使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:22-38`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，完全没有校验 role。任何拼写错误（如 'Agent'、'assistant'、'user'）或空字符串都会被接受并持久化，导致下游按 role 过滤/渲染对话流水时漏掉或错分类记录。VALID_ROLES 的存在表明作者本意是要校验的，属于遗漏而非有意设计。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:66-73 embed_batch 对缓存值只校验非空 list，不校验维度，可能返回错误长度向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-73`
  - 依据：缓存命中条件仅为 isinstance(cached, list) and cached，未校验元素类型或维度。若模型更换（key 未含 model，见下一条）或缓存被写入脏数据，会返回维度不符的向量，下游 _cosine 直接返回 0.0 造成永久未命中，或向量库写入报错。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 用 zip 对齐 pending 与 fresh，回源结果数量不足时静默丢向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：zip 在较短序列处截断。若 inner.embed_batch 返回的向量数少于 pending 数（上游部分失败、过滤空文本等），未对齐的 results[index] 保持 None，最终被 `vector or []` 变成空列表返回给调用方，且没有任何告警。调用方拿到长度正确但内容为空的向量，会在下游余弦相似度等处静默失效。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 embedding 缓存 key 未包含 model，换模型后复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。更换 embedding 模型后，同一文本仍命中旧模型向量，导致向量空间不一致、检索与语义缓存相似度全部失真，且 TTL 长达 7 天。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:138-143 zadd_and_count 的 pipeline 中 zadd 使用 now 作为 score，但 member 相同会覆盖而非累加，导致同一 member 重复请求不计数（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:138-143`
  - 依据：zadd 以 member 为唯一标识，同一 member 重复加入只会更新 score 而不会增加 zcard。若调用方用固定 member（如用户 ID）做限流，则同一用户窗口内多次请求计数恒为 1，限流形同虚设。但方法签名接受 member 参数，调用方通常会传入带唯一性的 member（如 request_id 或时间戳），此时行为正确。是否构成缺陷取决于调用方，本文件内无法确认误用，故不判定为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:68-73 get_json 的 delete 在 json 解析失败分支中未 await 异常保护，但 delete 已吞异常，无泄漏（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：与第一条重复，确认 delete 内部已 try/except 吞异常，此处不会向外抛出，不构成缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-126 set_if_absent 在 Redis 异常时返回 True，幂等键与分布式锁退化为无保护（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-126`
  - 依据：这是文档中明确声明的降级策略：Redis 不可用时返回 True（视为抢到），避免整条链路因拿不到幂等键而卡死。虽然会失去幂等/互斥保护，但这是有意的可用性取舍，且注释已说明。属于设计决策而非实现缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:145-152 zadd_and_count 在 Redis 异常时返回 0，限流完全失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:145-152`
  - 依据：异常分支返回 0 表示“窗口内计数为 0”，调用方据此判定未超限，即按不限流处理。注释明确写了“按不限流处理”，与 set_if_absent 的降级哲学一致：缓存故障不能拒绝服务。这是有意的可用性取舍，不是实现错误。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:178-182 remember 截断 entries 时保留最旧条目而非最新（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries.append 后取 entries[:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在桶满后被立即丢弃。结果是缓存永远停留在最初 30 条，新问句无法进入，与设计意图相反。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-126 语义缓存桶 key 忽略 scope，偏好变更后旧回复仍会命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-126`
  - 依据：_bucket_key 的文档与签名都声明 key = namespace + buyer_id + scope，但实现里 sha256 只拼了 namespace 和 buyer_id，scope 参数完全没参与计算。于是 remember/lookup 传入不同 scope 时仍读写同一个桶：买家撤回或新增偏好后，旧回复（可能断言已删除的偏好）依然会被命中，正是文档里明确要求避免的场景。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:143-148 lookup 忽略 has_history，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-148`
  - 依据：模块文档第 3 条要求“会话内已有多轮上下文时不命中”，remember 也据此拒绝写入，但 lookup 的签名接收 has_history 却从未使用。当会话已有历史时，像“多少钱”这类依赖上下文的问句仍会命中跨会话缓存，返回答非所问的回复。
- **[error_handling/critical]** [error_handling] app/infrastructure/security/content_filter.py:24-32 content_filter 正则 (?i) 内联标志位置导致编译失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：Python 3.11+ 要求全局内联标志 (?i) 位于模式开头，否则抛 re.error。DANGEROUS_PATTERNS 中多条模式以 `(?i)` 开头没问题，但 `r"(?i)忽略..."` 等同样在开头，实际风险在于 `_compiled = [re.compile(pattern) ...]` 在模块导入时执行：只要任一模式非法，整个 security 包导入即失败，L3/L4 护栏全部不可用。更关键的是 `r"(?i)system\s*prompt"` 等模式在 Python 3.11 下若被拼接或前置字符会报错；当前列表本身以 (?i) 开头可编译，但 `r"\b(?:" + ... ` 在 output_guard 中无此问题。此处需确认：content_filter 的模式均以 (?i) 开头，可编译，故本条降级为 not_a_defect。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:47-60 sanitize_tool_output 逐模式替换可能产生嵌套占位符或漏检跨模式注入（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-60`
  - 依据：逐条 subn 替换后，后续模式可能匹配到已插入的占位符文本（占位符含“注入”等词），但占位符本身不含危险模式关键词，实际不会二次命中。跨模式组合注入（如“忽略之前”+“system prompt”分处两段）仍会被各自命中。未发现可复现的绕过，记为 not_a_defect。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:40-44 output_guard 内部服务地址正则未转义点号且缺少词边界，可能误伤正常 URL（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-44`
  - 依据：模式 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 中主机名后紧跟可选端口与路径，未加词边界。像 `https://redis.example.com` 会匹配到 `https://redis` 前缀并被替换为 `[已脱敏]`，留下 `.example.com` 残片，产生畸形输出。但该场景在买家可见回复中极少出现，且脱敏方向偏安全，故记为 not_a_defect 供参考。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

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
| `3af4356ea741` | 1 | 1 | `partition_gap` | — |
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
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 20%（单元格值 = 独立 Agent 数）
