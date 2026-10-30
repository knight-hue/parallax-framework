# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 24 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：28
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：61 个节点 / 90 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 26 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:55-61 render_preference_hint 在 preferences 为空时仍生成带空正文的注入块（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:55-61`
  - 依据：render_preference_hint 对空列表会生成 `<buyer-preferences>\n...\n\n</buyer-preferences>`，正文为空。但 select() 在 preferences 为空时返回 []，调用方通常不会对空结果调用渲染；且即便调用，也只是注入一个空块，不构成错误行为。属于边界情况但无实际危害，故判定非缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-130 _rank_by_relevance 注释声称“回到原始相对顺序输出”，但实际按相似度排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-130`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度降序输出，并未恢复原始顺序。这与 _latest_first 的行为（恢复原始相对顺序）不一致，且与注释承诺不符，导致注入块行序随 query 变化而抖动，可能影响 prompt 缓存命中。虽然不影响正确性，但属于实现与设计意图不符的逻辑缺陷。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-88 select() 用 [:top_k] 截断会丢弃 dislike，违反“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-88`
  - 依据：模块文档明确声明 dislike 全量保留、不参与 top_k 截断，但实现把 dislikes + selected_likes 拼接后又整体切片 [:top_k]。当 dislike 数量 >= top_k 时，selected_likes 被全部切掉（正向偏好丢失，尚可接受）；更关键的是当 dislikes 数量本身超过 top_k 时，部分 dislike 会被截断丢弃，直接违反安全底线。此外当 len(likes) <= top_k 时 selected_likes 是全部 likes，拼接后仍被 [:top_k] 截断，导致 likes 也未被完整保留，与“dislike 全量保留”的语义不一致。触发条件：dislikes 数量 > top_k（例如 5 条忌口、top_k=3），此时至少 2 条黑名单被丢弃，可能推荐用户明确拒绝的商品。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-33 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：__post_init__ 校验了 kind 和 statement，却漏掉 buyer_id。buyer_id 是 PreferenceStore 的主键维度（list_by_buyer/delete 都按它索引），空 buyer_id 会把偏好写入一个无法归属的桶，后续按买家查询永远取不到，且 append 的幂等去重（同 buyer 同 statement）会把所有空 buyer_id 的偏好错误地合并去重。
- **[logic/low]** [logic] app/domain/buyer/preference.py:22-33 created_at 默认值在 dataclass 定义期求值而非实例化期（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-33`
  - 依据：created_at: str = "" 是空串默认值，真正的赋值发生在 __post_init__ 里调用 datetime.now()，因此每个实例拿到的是各自实例化时刻的时间，不存在共享默认值问题。这里确认安全。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:36-44 add/multiply 直接构造 Money 绕过 of() 校验（不变量入口不唯一）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-44`
  - 依据：add() 与 multiply() 直接调用 Money(...) 而非 Money.of(...)，看似绕过校验。但两者输入均来自已通过 of() 校验的 Money 实例，且 multiply 已显式校验 quantity 为非负整数（并排除 bool），add 的结果是两个非负整数之和，币种由 _assert_same_currency 保证一致，因此结果必然满足不变量。当前实现是安全的，不构成缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:31-34 from_major_units 用 round() 做浮点换算，存在银行家舍入与精度误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：round(major * 100) 使用 Python 的银行家舍入（round-half-to-even），且 major 是 float，0.1*100 等二进制浮点表示会产生 10.000000000000002 或 9.999999999999998 之类的值。例如 round(2.675 * 100) 得到 267 而非 268（2.675 实际存储为 2.67499999...），round(0.5*100)=50 但 round(1.5*100)=150、round(2.5*100)=250 看似正常，而 round(0.125*100)=12（应为 13 若按四舍五入）。金额换算出现 1 分误差在跨境结算中是真实缺陷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:36-44 Money.add/multiply 绕过不变量校验，直接构造 dataclass（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-44`
  - 依据：of() 是唯一执行不变量校验（非负整数、受支持币种）的入口，但 add() 和 multiply() 直接调用 Money(...) 构造器，绕过了 of()。虽然当前 add/multiply 的输入来自已校验的 Money 实例，结果仍非负且币种合法，但 multiply 的 quantity 校验与 of 的 amount 校验不一致：multiply 显式拒绝 bool（isinstance(quantity, bool)），而 of() 的 `isinstance(amount, int)` 对 bool 返回 True，因此 Money.of(True, 'USD') 会成功构造 amount_in_minor_units=True 的实例（bool 是 int 子类），随后 add/multiply 会传播该 bool 值，to_major_units 返回 0.01 而非预期的整数语义。这是 of() 校验的真实漏洞。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:38-39 Product.primary_sku 直接取 skus[0]，依赖 __post_init__ 保证非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:38-39`
  - 依据：__post_init__ 已强制 skus 非空，否则抛 ValueError，因此 primary_sku 的 skus[0] 不会 IndexError。构造后 skus 是可变 list，理论上可被外部清空，但这是 dataclass 可变字段的通用风险，非本函数特有缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:47-52 Product.searchable_text 对空 highlights 产生多余空格，但不影响检索语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：当 highlights 为空时 highlight_text 为空串，join 结果末尾会多一个空格。这只是文本格式上的冗余空白，对 embedding/关键词召回无实质影响，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-38 ConversationTurn 未校验 buyer_id 与 content，与 session_id 校验不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-38`
  - 依据：__post_init__ 只对 session_id 做非空校验，而 buyer_id 和 content 是对话流水的核心字段。空 buyer_id 会导致按买家维度的追溯/客服排查查不到记录；空 content 会写入无意义的空轮次。虽然严重度低于 role，但同属值对象不变量缺失，且与 session_id 的校验标准不一致。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:41-48 ConversationEventRecord 未校验 session_id 与 type（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:41-48`
  - 依据：ConversationEventRecord 是过程事件的持久化形态，但没有任何 __post_init__ 校验：session_id 为空、type 为空、payload 非 dict 都能构造成功。append_events 是批量写入，一条脏事件会污染整批。与 ConversationTurn 对 session_id 的校验标准不一致，属于遗漏。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:22-38 ConversationTurn 未校验 role 取值，VALID_ROLES 定义后从未使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:22-38`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，完全没有校验 role。任何非法 role（如 'system'、'tool'、空串）都能构造成功并落库。由于该值对象是业务可读对话流水的持久化形态，下游按 role 过滤/渲染（如只取 buyer 轮次）时会静默漏数据或渲染异常。VALID_ROLES 的存在表明作者本意是要校验的，属于遗漏而非有意设计。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 用 zip 对齐 pending 与 fresh，回源结果数量不足时静默丢向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：zip 在较短序列处截断。若 inner.embed_batch 返回的向量数少于 pending 数（部分失败、过滤空文本等），未对齐的 results[index] 保持 None，最终被 `vector or []` 转成空列表返回，调用方拿到长度正确但内容为空的向量，且没有任何告警。这会把上游的异常静默转成空 embedding，后续检索/相似度计算会得到错误结果。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 embedding 缓存 key 未包含 model，换模型后复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 实际只哈希 text，self._model 从未参与。同一 Redis 实例上切换 embedding 模型（或不同模型实例共享缓存）时，会命中另一模型生成的向量，维度/语义空间不一致，导致余弦相似度计算错误或维度不匹配返回 0。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:139-145 close 使用 aclose，旧版 redis-py 可能没有该方法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:139-145`
  - 依据：redis.asyncio 的 Redis 客户端在较新版本提供 aclose()；旧版本提供 close()。若版本不匹配，aclose 不存在会抛 AttributeError，但被 except Exception 吞掉，仅导致连接未优雅关闭。考虑到 from_url 本身在导入失败时已降级，且异常被吞，影响有限。属于版本兼容性风险而非确定缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:66-72 get_json 在 json.loads 失败时调用 delete，但 delete 自身吞异常，脏值可能残留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-72`
  - 依据：json.loads 抛 ValueError 时调用 await self.delete(key)，delete 内部吞掉异常。即使删除失败，下次读取仍会走同样的“脏值当未命中”路径，不会返回错误数据，只是多一次 Redis 往返。行为正确，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:128-136 zadd_and_count 的 expire 在 pipeline 中位于 zcard 之后，结果索引正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-136`
  - 依据：pipeline 命令顺序为 zremrangebyscore、zadd、zcard、expire，results[2] 对应 zcard，索引正确。transaction=True 保证原子性。无缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:74-86 get_raw 与 get_json 对同一 key 的语义差异可能导致幂等键被误删（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:74-86`
  - 依据：get_raw 文档明确说明幂等键存裸 task_id，不能走 get_json，因为 get_json 在 json.loads 失败时会删除键。get_raw 不做 json 解析，不会误删。两个方法职责分离清晰，无缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 语义缓存桶 key 忽略 scope，偏好变更后旧回复仍会命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：_bucket_key 接收 scope 参数，但计算 digest 时只用了 namespace 和 buyer_id，scope 完全没有参与哈希，也没有拼进返回的 key。文档明确要求桶 key 必须带偏好指纹，否则买家撤回/新增偏好后，旧回复（可能断言已删除的偏好）仍会被命中并返回给用户。lookup/remember 都通过 _bucket_key(buyer_id, scope) 取 key，因此 scope 实际完全失效。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-141 lookup 忽略 has_history，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-141`
  - 依据：remember 在 has_history 为真时拒绝写入，但 lookup 完全没有检查 has_history 参数，直接进入缓存查询。文档安全边界第 3 条要求“会话内已有多轮上下文时不命中”，否则“刚才那款多少钱”这类依赖上下文的问题会跨会话复用错误回复。lookup 的 has_history 形参从未被使用。
- **[performance/low]** [performance] app/infrastructure/cache/semantic_cache.py:155-163 lookup 中 best.reply 为空时返回 None 但已消耗 embedding 调用（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:155-163`
  - 依据：仅当命中相似度但 reply 为空时返回 None，属于正确性兜底；embedding 调用是必要的相似度计算成本，不算缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-53 sanitize_tool_output 逐模式替换可能产生嵌套/重复占位符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-53`
  - 依据：多个模式顺序替换，后一模式可能匹配到前一模式插入的占位符文本，但占位符 `[内容已过滤：疑似注入]` 不含任何危险模式关键词，不会被再次匹配。替换是幂等安全的，不构成缺陷。
- **[error_handling/critical]** [error_handling] app/infrastructure/security/output_guard.py:44-52 output_guard 正则 (?i) 拼接同样导致编译失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-52`
  - 依据：SENSITIVE_PATTERNS 中工具名模式用 `"|".join(_INTERNAL_TOOLS)` 拼接，本身无内联标志，单独看合法；但整个列表被逐个 re.compile，其中 `r"\b(?:" + ... + r")\b"` 合法。真正风险在于若任一 pattern 含非开头 (?i) 会失败——此处模式均无 (?i)，因此该文件本身可编译。经核对，output_guard 的 SENSITIVE_PATTERNS 不含内联标志，编译不会失败，故此项判为 not_a_defect。

## 争议（需裁决）

- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，导致限流失效（fail-open）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：zadd_and_count 的文档说明它用于跨进程限流。当 _client 为 None（REDIS_URL 未配置）或 pipeline 抛异常时，函数返回 0，调用方通常会把 0 解释为“窗口内没有请求”，从而完全放行。这与 set_if_absent 的 fail-open 语义一致，但限流场景下 fail-open 意味着 Redis 故障期间限流被完全绕过，可能压垮下游。这是设计上的取舍，但返回值 0 与“不限流”语义耦合，调用方无法区分“真的 0 次”和“Redis 挂了”。
  - 争议对手：25db3af0c24a
- **[error_handling/critical]** [error_handling] app/infrastructure/security/content_filter.py:24-32 content_filter 正则 (?i) 内联标志位置导致编译失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：Python 3.11+ 要求全局内联标志 (?i) 必须位于模式开头，否则抛出 re.error: global flags not at the start of the expression。DANGEROUS_PATTERNS 中多个模式以 `(?i)` 开头没问题，但 `r"(?i)忽略..."` 等均以 (?i) 开头，实际都合法；真正的问题在于这些模式被 `"|".join` 拼接后，只有第一个分支的 (?i) 在开头，后续分支的 (?i) 出现在字符串中间，re.compile 会抛错。模块导入即失败，L3 过滤层完全不可用。
  - 争议对手：a8c8502c30f7

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
| `1ea202d2ad5b` | 1 | 3 | `partition_gap` | — |
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
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 0 | 1 | 0 | 0 | 1 | 1 |
| `app/infrastructure/security` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 19%（单元格值 = 独立 Agent 数）
