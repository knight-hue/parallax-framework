# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 7 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 31 | 支持不足、相关性超限或尚待验证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：59
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：94 个节点 / 215 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 42 | 100% | 14% |

## 高置信结论

- **[logic/low]** [logic] app/application/memory/preference_selector.py:133-135 _rank_by_relevance 声称『回到原始相对顺序输出』但实际按相似度排序返回（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:133-135`
  - 依据：注释写『回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入』，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按 scored 的相似度降序取前 top_k，并未按原始 index 重新排序。结果是注入块的行序随 query 变化而抖动，与注释承诺相反；同时 select() 的 docstring 承诺『保持 dislike 在前、like 在后的稳定顺序』，like 内部顺序却每轮不同。这会导致同一批偏好在不同轮次以不同顺序注入，影响 prompt 缓存/可测性。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 dislike 偏好被 top_k 截断，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单会导致推荐用户明确拒绝的商品（安全问题）。但 select() 最后返回 (dislikes + selected_likes)[:top_k]，这个切片对 dislikes 同样生效。当 dislike 数量超过 top_k 时，超出的 dislike 会被静默丢弃；更常见的是 dislike 数量接近 top_k 时，切片会挤掉部分 like 甚至部分 dislike。例如 top_k=3、dislikes 有 5 条时只返回前 3 条 dislike，另外 2 条黑名单丢失，正是文档所说的“推了用户明确拒绝的东西”。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:20-25 Money.of 用 isinstance(amount, int) 会放行 bool（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:20-25`
  - 依据：of() 用 isinstance(amount, int) 校验，但 bool 是 int 子类，Money.of(True, 'USD') 会通过校验得到 1 最小单位。multiply 里作者已经意识到并显式排除了 bool，of() 却漏了，属于同一类校验不一致。虽然实际影响小，但会让『非负整数』不变量被 bool 绕过。
- **[logic/low]** [logic] app/domain/catalog/money.py:35-43 Money.add/multiply 绕过 of() 校验，可构造非法 Money（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add() 和 multiply() 直接调用 Money(...) 构造器，绕过校验。虽然当前输入来自已校验的实例，但 dataclass 构造器本身公开可用，且 add 未校验 other 类型（传入非 Money 会在 _assert_same_currency 抛 AttributeError 而非 ValueError）。更关键的是 multiply 允许 quantity 为 0 但 add 未做溢出保护，大额累加可超出预期。属于不变量被绕过的设计缺陷，严重度较低。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-127 语义缓存桶 key 忽略 scope 参数，偏好变更后旧回复不会失效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-127`
  - 依据：_bucket_key 接收 scope 参数，但计算 digest 时只用了 namespace 和 buyer_id，scope 完全没有参与哈希。文档明确要求 scope（偏好指纹）必须进入桶 key，否则买家撤回/新增偏好后仍会命中旧回复。lookup/remember 都传入 scope，但实际读写的是同一个桶，导致偏好变更后旧回复继续被复用，直接违背安全边界 2b。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:143-148 lookup 忽略 has_history 参数，多轮上下文会话仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-148`
  - 依据：lookup 签名接收 has_history，但函数体只检查 _enabled 和 is_cacheable_query，从未使用 has_history。文档安全边界 3 要求“会话内已有多轮上下文时不命中”，remember 侧检查了 has_history，lookup 侧却没有，导致有上下文的会话仍会命中缓存并返回脱离上下文的回复。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:178-182 remember 中 entries[:_BUCKET_LIMIT] 保留最早条目而非最近条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 保留的是最旧的 30 条，新写入的条目在超过 30 条后会被立即丢弃。这导致缓存永远停留在最早的 30 条，新回复无法进入缓存，与设计意图相反。

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:88-90 top_k<=0 时连 dislike 也一并丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-90`
  - 依据：top_k<=0 分支直接 return []，把 dislike 也丢掉了。按模块声明的安全底线，dislike 不应受预算截断影响；预算为 0 时至少应保留黑名单（或由调用方明确决定）。当前实现让“预算为 0”变成“黑名单全部失效”，与文档语义冲突。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-34 embed_batch 返回向量维度不一致时 _cosine 静默返回 0（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：_cosine 在长度不等时返回 0.0，属于防御性降级：不会抛异常，只是该条偏好得分为 0，可能被排到末尾。虽然会静默掩盖 embedding 维度错误，但不会导致崩溃或错误注入，且上层已有向量数量校验。属于可接受的降级策略，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-33 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：__post_init__ 校验了 kind 和 statement，却漏掉 buyer_id。buyer_id 是偏好归属的唯一键，list_by_buyer/delete 都按它检索。空 buyer_id 会写入一条无法归属到任何买家的偏好，且 delete('', statement) 可能误删所有空 buyer 的条目。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:40-43 Money.multiply 显式排除 bool，校验正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:40-43`
  - 依据：isinstance(True, int) 为 True，这里显式加了 isinstance(quantity, bool) 排除，避免 True 被当作 1 参与乘法。校验是完备的，不是缺陷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:45-49 Money.to_major_units 返回 float，JPY 等零小数位币种显示错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-49`
  - 依据：to_major_units 固定除以 100，__str__ 固定格式化为两位小数。对 JPY 而言最小单位就是 1 日元，1000 最小单位应显示为 '1000 JPY'，实际显示 '10.00 JPY'。与 from_major_units 的 100 倍问题同源，但这里是展示路径，会直接误导用户和客服。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:41-43 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:41-43`
  - 依据：这是抽象端口定义，契约由实现方保证；端口层不做参数校验是合理的，且注释说明由 UseCase 负责降级。不构成可引用的缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:33-38 Product 为可变 dataclass 且 __post_init__ 只校验 skus 非空，未校验 sku_id 唯一（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-38`
  - 依据：find_sku 使用 next 返回第一个匹配，若存在重复 sku_id 会静默返回第一个。但重复 sku_id 属于上游数据构造问题，聚合根未强制唯一性并不必然导致错误行为，且没有代码证据表明会传入重复 sku。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 对空 detail 的亮点产生多余空格，且未包含 skus 信息（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 用 f"{h.label} {h.detail}" 拼接，当 detail 为空字符串时会生成尾部空格，但随后用 " ".join 拼接，多余空格对召回文本影响极小，不构成错误行为。skus 未纳入检索文本是设计选择（注释明确说明是标题+品牌+品类+描述+亮点），不是缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 只校验非负，未校验类型，bool/float 可绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：`if self.stock < 0` 对 bool 和 float 都能正常比较，bool 是 int 子类，float 库存虽语义奇怪但不会导致错误行为；dataclass 无类型强制是 Python 常态，且该字段被声明为只读参考数据，不参与扣减。未发现可复现的错误行为，故不认定为缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:44-51 ConversationEventRecord 完全无校验，session_id/type 可为空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:44-51`
  - 依据：ConversationEventRecord 没有任何 __post_init__ 校验，session_id 和 type 均可为空串，payload 可为任意 dict。append_events 是批量写入，一条非法记录会污染整批事件流，且事件按 session_id 关联会话，空 session_id 的事件无法归属。与 ConversationTurn 至少校验 session_id 的做法不一致。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:27-41 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-41`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，完全没有使用 VALID_ROLES。role 字段注释写『buyer / agent』，实际可写入任意字符串（如 'system'、'tool'、空串），下游按 role 分流（如回放、bad case 采集、前端渲染）会拿到非法值。VALID_ROLES 成为死代码，说明校验被遗漏。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/session_store.py:17-26 SessionStore 端口定义完整，无缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-26`
  - 依据：save/load 均为 async 抽象方法，load 返回 Optional[str] 表示不存在返回 None，与文档一致。端口按更严格异步语义定义，符合注释说明，未发现缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换为空列表（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：results 中每个位置要么是缓存命中的非空 list，要么被 fresh 回源结果覆盖。若 inner.embed_batch 返回数量少于 pending，zip 会截断，剩余位置保持 None 并被 `or []` 转为空列表——这属于上游契约违约，但此处不会抛异常也不会错位。空向量本身在 _cosine 中返回 0.0，不会造成错误命中。属于可接受的防御性兜底，不构成缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:84-87 embed_batch 中 zip(pending, fresh) 长度不一致时静默截断（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:84-87`
  - 依据：若 inner.embed_batch 返回的向量数少于 pending 数（上游实现异常或部分失败），zip 会静默截断，未覆盖的位置保持 None，最终被 `or []` 变成空向量返回给调用方，且不会记录任何告警。调用方拿到空向量后可能写入缓存或参与相似度计算，造成难以排查的错误。缺少长度校验。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 缓存 key 未包含 model，换模型后可能复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块文档字符串声称 key 用 sha256(model + text)，但 _key 实际只对 text 做哈希，self._model 从未参与。若同一 Redis 实例被不同模型（或不同维度）的 CachedEmbeddingClient 共用，换模型后旧向量会被当作命中返回，导致向量维度/语义不匹配，进而使向量检索或语义缓存余弦计算出错。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:148-156 zadd_and_count 的 zremrangebyscore 与 zadd 使用不同时间基准，成员分数为 now 但清理上界为 now-window（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:148-156`
  - 依据：zremrangebyscore(key, 0, now - window_seconds) 清理分数 <= now-window 的成员，zadd 用 now 作为分数，zcard 统计剩余数量，逻辑自洽：窗口内成员分数落在 (now-window, now]，清理后计数正确。expire 设为 window+1 秒足够覆盖窗口。未发现边界错误。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:120-138 zadd_and_count 在 Redis 故障时返回 0，限流静默失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:120-138`
  - 依据：与 set_if_absent 同理，异常时返回 0 表示『不限流』，是文档化的降级策略（『按不限流处理』）。这是可用性优先的显式权衡，不是实现错误。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:78-82 get_json 在 JSON 解析失败时调用 delete，但 delete 内部吞异常，脏值可能残留（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:78-82`
  - 依据：get_json 在 json.loads 抛 ValueError 时调用 self.delete(key) 清理脏值。delete 内部吞掉异常，若删除失败脏值会残留，但下次读取仍会走同样的解析失败路径并再次尝试删除，行为上等价于持续未命中，不会导致错误结果。属于可接受的降级，不构成缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:108-118 set_if_absent 在 Redis 故障时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-118`
  - 依据：文档明确说明这是有意的降级策略：Redis 不可用时返回 True 视为抢到，宁可退化成没有幂等保护也不拒绝服务。这是显式的可用性优先权衡，调用方被文档告知了语义。虽然从正确性角度有风险，但属于设计决策而非实现缺陷，且注释与 docstring 一致。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:128-137 zadd_and_count 的 zremrangebyscore 与 zadd 在同一事务中，但 member 重复时 zcard 计数正确（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-137`
  - 依据：zadd 对同一 member 是更新 score 而非新增，zcard 返回的是唯一成员数。若调用方用同一 member 重复调用，计数不会增长，这是 ZSET 语义而非缺陷；调用方应保证 member 唯一（如含请求 id）。pipeline 使用 transaction=True 保证原子性，results[2] 对应 zcard 结果，索引正确。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:140-158 zadd_and_count 在 Redis 故障时返回 0，限流完全失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:140-158`
  - 依据：异常分支返回 0 表示窗口内计数为 0，即不限流。注释写明“按不限流处理”，与 set_if_absent 的可用性优先策略一致，是有意设计。虽然安全上偏宽松，但属于文档化的取舍，不是实现错误。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:96-98 is_cacheable_query 对 None 输入会抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:96-98`
  - 依据：is_cacheable_query 直接对 query 调用 _UNSAFE_RE.search，若 query 为 None 会抛 TypeError。但调用方 lookup/remember 的 query 参数类型标注为 str，且上游应保证非空字符串。属于契约内输入，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:158-165 lookup 中 entry.get('vector', []) 对非 list 值调用 _cosine 可能抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:158-165`
  - 依据：_cosine 首先比较 len(left) != len(right)，若 entry 中 vector 缺失则默认 []，长度不等直接返回 0.0；若 vector 是 None 则 len(None) 会抛 TypeError。但 entries 由本类 remember 写入，结构受控，且 _load_entries 已做 list 校验。外部污染缓存属于低概率场景，且 lookup 外层无 try 包裹——不过这是可辩护的边界，不构成明确缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:163-170 lookup 中 entry.get('vector', []) 对非列表值可能抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:163-170`
  - 依据：_cosine 对 len(left)!=len(right) 返回 0.0，且 entry 由本模块 remember 写入，vector 恒为 list[float]。即使 Redis 中数据被外部污染成非列表，len() 对字符串也可用，最坏是返回 0.0 不命中，不会崩溃主链路。属于可接受的防御范围，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:91-94 _normalize 去除尾部标点但不去除首部标点，且未做大小写归一（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:91-94`
  - 依据：文档只承诺“压空白 + 去尾部标点”，实现与文档一致。首部标点与大小写差异会降低命中率但不会产生错误回复（相似度阈值 0.95 仍会拦截），属于设计取舍而非缺陷。
- **[error_handling/high]** [error_handling] app/infrastructure/security/__init__.py:12-16 output_guard 导入 content_filter 模块，但该文件不在仓库中，导致 security 包导入失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:12-16`
  - 依据：security/__init__.py 在包初始化时无条件执行 `from app.infrastructure.security.content_filter import (...)`，但给定文件列表中不存在 content_filter.py。任何 `import app.infrastructure.security`（或导入其子模块 output_guard 时经由包 __init__）都会抛 ModuleNotFoundError，使 L3/L4 护栏整体不可用。这是可引用的具体导入语句，不是风格问题。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/content_filter.py:24-32 DANGEROUS_PATTERNS 中 (?i) 内联标志位于模式开头，Python re 允许但与其他标志组合时需注意（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：Python 3.11+ 要求全局内联标志 (?i) 必须位于模式最开头，这里每个模式都以 (?i) 开头，符合要求，re.compile 不会报错。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:55-62 sanitize_tool_output 逐个模式替换，占位符本身可能被后续模式再次匹配（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-62`
  - 依据：占位符文本为“[内容已过滤：疑似注入]”，不含任何危险模式的关键词（ignore/previous/system prompt 等），后续模式不会匹配到占位符，因此不会出现重复替换或无限增长。逐个 subn 的顺序替换是安全的。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 危险模式正则未覆盖大小写混合的中文/变体写法，且 system prompt 模式会误伤正常内容（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：正则过滤本就是尽力而为的启发式，文档明确说语义级判断交给 L4。`system\s*prompt` 会误伤商品描述中正常出现的『system prompt』字样，但这是过滤层可接受的误报（保留其余内容）。不构成实现缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空文本返回安全，符合预期（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：空字符串直接返回 (True, text)，没有敏感内容可泄露，行为正确。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:43-43 内部工具名正则使用 \b 边界，下划线属于单词字符导致前后缀变体漏检（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-43`
  - 依据：`\b(?:product_search_tool|...)\b` 中 `\b` 在 `_` 与字母之间不成立，因此 `product_search_tool_v2` 或 `my_product_search_tool` 不会被匹配。但工具名本身以 `_tool` 结尾，正常泄露形态就是裸工具名，且文档明确说明刻意不用宽泛模式以避免误伤；把变体视为需拦截属于推测性需求，不构成可确认缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/domain/buyer/preference.py:30-31 BuyerPreference 的 statement 校验用 strip 但存储原值，前后空白导致去重/删除失配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：校验时用 self.statement.strip() 判断非空，但保存的是未 strip 的原值。PreferenceStore.append 承诺『同 buyer 同 statement 幂等去重』，delete 承诺『按 statement 精确匹配删除』。若模型输出 ' 不要塑料 ' 与 '不要塑料'，两者 strip 后相同但原值不同，去重失效、delete 精确匹配也会未命中，用户会看到重复偏好且删不掉。
  - 争议对手：097d396327ec, ccb69a82021c
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:39-41 ConversationTurn 未校验 buyer_id 与 content 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:39-41`
  - 依据：__post_init__ 只校验 session_id，buyer_id 和 content 可为空串。对话流水是客服排查与 bad case 回放的数据底座，buyer_id 为空会导致按买家检索失效，content 为空会写入无意义记录。与同仓库 BuyerPreference 对 statement 做 strip 校验的做法不一致，说明是遗漏而非有意设计。
  - 争议对手：03b08871891b
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:78-84 embed_batch 用 `vector or []` 把合法空向量与缺失结果混为一谈（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-84`
  - 依据：当 inner.embed_batch 返回的列表比 pending 短（上游实现异常或截断）时，zip 会静默丢弃多余 pending 项，results 中对应位置保持 None，最终被 `vector or []` 转成空列表返回，调用方拿到长度正确但内容为空的向量，且没有任何告警。此外 `vector or []` 也会把合法的空向量（如某些模型对空串返回 []）与缺失结果合并，无法区分。
  - 争议对手：acbdca1f8d4b
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:40-40 内部服务地址正则未加词边界，会误伤正常 URL 中的主机名子串（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-40`
  - 依据：模式 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 在主机名后没有边界约束，`https://redis.example.com/docs` 会匹配到 `https://redis` 并把整段（含后续路径）替换为 [已脱敏]，把买家可见的正常链接破坏掉，同时 safe 被置为 False 触发误告警。文档明确要求避免误伤正常措辞，此处与设计意图不符。
  - 争议对手：7f5ea164963a

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.77% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：14｜无法判定：0
- 单 Reader 检出率：68.5%（重捕对 3，已观测 42，估计总体 61.3333
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 9.9% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 9.9% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 9.9% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 9.9% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 9.9% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 9.9% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 9.9% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 9.9% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 9.9% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 9.9% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 2 | 0 | 2 | 1 | 0 | 2 | 0 | 1 |

矩阵填充率 22%（单元格值 = 独立 Agent 数）
