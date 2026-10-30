# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 5 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 38 | 支持不足、相关性超限或尚待验证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：60
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：95 个节点 / 209 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 47 | 100% | 11% |

## 高置信结论

- **[boundary/high]** [boundary] app/application/memory/preference_selector.py:88-96 likes 数量 <= top_k 时未按 top_k 扣除 dislike 预算，导致 dislike 被截断（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-96`
  - 依据：当 len(likes) <= top_k 时 selected_likes = likes（全量），随后 (dislikes + selected_likes)[:top_k] 截断。若 len(dislikes) + len(likes) > top_k，末尾的 dislike 会被截掉（因为 dislike 在前，likes 在后，截断发生在尾部，实际被截的是 likes 尾部——但若 len(dislikes) > top_k 则截的是 dislike）。更关键的是：likes 的选取没有考虑 dislike 已占用的预算，selected_likes 可能选满 top_k 条，加上 dislike 后总长超 top_k，截断必然发生。文档要求 dislike 全量保留，此处逻辑与文档冲突。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-130 _rank_by_relevance 注释声称「回到原始相对顺序输出」，实际按相似度排序输出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-130`
  - 依据：注释说 picked 之后要「回到原始相对顺序输出，避免注入块的行序每轮抖动」，但代码直接 `return picked`，picked 是按 (-score, index) 排序后的结果，并未按原始 index 重排。后果：注入块中 like 行的顺序随 query 变化而抖动，与注释声明的稳定性目标不符；同时与 _latest_first 分支（返回原始相对顺序）行为不一致，导致同一批偏好在开关切换时行序不同。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 select() 用 [:top_k] 截断会把 dislike 黑名单裁掉，违背安全底线（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断。但 select() 在 dislikes + selected_likes 之后又做了一次 [:top_k] 截断。当 dislike 数量 >= top_k 时，返回结果只包含前 top_k 条 dislike，后面的 dislike 被丢弃；当 dislike 数量 < top_k 时，likes 的预算被压缩为 top_k - len(dislikes)，但 selected_likes 已经按 top_k 选好，截断后仍可能丢掉部分 dislike（只要 len(dislikes) > 0 且 len(dislikes)+len(selected_likes) > top_k，即 len(dislikes) > 0 且 selected_likes 非空时，末尾的 dislike 不会被丢，但 dislike 数量超过 top_k 时必然丢）。核心触发条件：dislikes 数量 > top_k。例如 top_k=2、有 3 条 dislike，返回只有前 2 条，第 3 条黑名单丢失，正是文档所说的『推了用户明确拒绝的东西』。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：from_major_units 对所有币种统一乘 100，但 JPY 的最小单位就是 1 日元（无小数位），SUPPORTED_CURRENCIES 明确包含 JPY。调用 Money.from_major_units(1000, "JPY") 会得到 100000 最小单位，即 1000 日元被当成 100000 日元，价格放大 100 倍。注释承认这是「简化处理」，但这是真实的价格错误，不是风格问题。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 语义缓存桶 key 忽略 scope 参数，偏好变更后旧回复不会失效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：_bucket_key 的签名接收 scope，文档也明确说明 scope 必须参与桶 key（偏好新增/撤回后旧回复必须自动失效），但实现里 sha256 只拼了 namespace 和 buyer_id，scope 完全没参与计算。因此 lookup/remember 传入不同 scope 时仍读写同一个桶，买家撤回“不要塑料”偏好后仍会命中撤回前的旧回复，直接向用户断言已删除的偏好——正是注释里声称“实测踩过”的场景。

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:135-137 _latest_first 用 `p in newest` 做成员判断，依赖 dataclass 值相等而非身份（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:135-137`
  - 依据：`[p for p in likes if p in newest]` 使用 == 比较（BuyerPreference 若为 dataclass 则按字段值比较）。若两条偏好字段完全相同（同 kind、同 statement、同 created_at，例如重复写入的同一偏好），则 newest 中只保留一条，但列表推导会把两条都保留，导致返回数量超过 top_k，破坏预算约束。触发条件：存在完全重复的偏好记录且 len(likes) > top_k。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-34 _cosine 对长度不一致向量返回 0.0，可能把有效偏好排到末尾（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：长度不一致时返回 0.0 是合理的降级：不会抛异常，且 0 相似度会被排到末尾。虽然可能静默掩盖 embedding 维度不一致的问题，但 _rank_by_relevance 已对向量数量做校验，且排序失败会降级。属于可接受的防御性处理，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:24-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-31`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好可被构造并 append，list_by_buyer("") 会把这些无主偏好全部返回，造成跨买家偏好串味（偏好是跨会话注入模型的安全敏感数据）。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-33 BuyerPreference 为 frozen dataclass，__post_init__ 用 object.__setattr__ 设置 created_at 合法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：frozen=True 的 dataclass 在 __post_init__ 中通过 object.__setattr__ 修改字段是标准做法，能绕过 frozen 限制。created_at 默认空串时被填充为当前 UTC 时间，逻辑正确。不是缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:47-56 PreferenceStore.delete 文档声明不区分 kind，同 statement 的 like 与 dislike 一并删除（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-56`
  - 依据：这是抽象端口方法，文档明确声明「不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除」。这是有意的设计决策，调用方知情。不是缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:35-43 Money.add/multiply 直接构造 Money 绕过 of() 校验，且未检查 other 类型（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：add 与 multiply 用 Money(...) 直接构造而非 Money.of(...)，绕过了 of() 中的非负整数与币种校验。虽然当前输入来自已校验的 self，但 _assert_same_currency 只访问 other.currency，若传入非 Money 对象（如带 currency 属性的鸭子类型）会静默通过币种检查后在 other.amount_in_minor_units 处抛 AttributeError；若传入 currency 相同但 amount 为负的伪造对象，则会产生负金额 Money，破坏「amount 非负」不变量。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:41-43 ProductVectorIndex.upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:41-43`
  - 依据：这是抽象端口声明，契约由实现方保证；端口层不校验参数长度属于设计选择，且 docstring 未承诺校验。调用方 UseCase 负责配对。因此不构成端口层缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/ports/retrieval_ports.py:51-54 Reranker.rerank 未声明返回长度校验，但 docstring 已明确契约（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:51-54`
  - 依据：docstring 明确要求返回与 documents 等长，并说明失败抛异常由调用方降级；端口层不强制校验属于契约约定，不是缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:39-40 Product.primary_sku 在 skus 为空时抛 IndexError，但 __post_init__ 已保证非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:39-40`
  - 依据：__post_init__ 已校验 skus 非空，primary_sku 不会遇到空列表。不是缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 未包含 ships_to，且对空 detail 产生多余空格（非缺陷）（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 的 docstring 明确声明只拼接标题/品牌/品类/描述/亮点，未承诺包含 ships_to 或 skus；空 detail 产生的多余空格对召回文本无实质影响。因此不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 仅校验非负，未校验类型，浮点/布尔值可绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：`if self.stock < 0` 对 bool 和 float 也能工作（True=1 通过，-0.5 被拒），Python 动态类型下这是常见做法；stock 作为初始库存只读参考，类型错误会在下游 StockRepository.seed 暴露。不构成明确缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:76-77 embed 单条接口在 embed_batch 返回空列表时 IndexError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-77`
  - 依据：embed 传入 [text] 时 embed_batch 对非空输入必然返回长度 1 的列表（即使向量为空也是 []），因此 [0] 不会越界。只有 texts 为空才返回 []，而 embed 不会传空列表。属于安全写法。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:82-86 embed_batch 中 zip 长度不匹配时静默丢弃，未校验回源结果数量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:82-86`
  - 依据：pending 与 fresh 用 zip 配对，若 inner 返回的向量数少于请求数（部分失败、过滤空文本等），zip 会静默截断，剩余 results[index] 保持 None，最终被 `vector or []` 变成空向量返回给调用方，而不是抛错。调用方拿到长度正确但内容为空的向量，检索/相似度计算会静默失效。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 缓存 key 未包含 model，换模型后可能复用旧模型向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块 docstring 明确写“key 用 sha256(model + text)”，但 _key 只对 text 做哈希，self._model 从未参与 key 计算（构造函数里保存了 _model 却没有任何使用点）。当同一 Redis 实例被不同模型（或不同维度）的客户端共享时，切换模型后旧向量会被当作命中返回，导致向量维度/语义空间不匹配，进而使向量检索或余弦相似度计算错误。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:66-74 embed_batch 串行 await 缓存读取，批量场景下延迟线性放大（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-74`
  - 依据：循环内对每个 text 逐个 await self._safe_get，N 条文本产生 N 次串行 Redis 往返；批量 embedding 的典型用途正是大批量文本，串行化会把总延迟放大为 N × RTT。可用 asyncio.gather 并发读取。这是可测量的性能缺陷而非风格问题。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/redis_cache.py:128-137 zadd_and_count 的 zcard 在 zadd 之后执行，但 pipeline 事务内 expire 可能被覆盖（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-137`
  - 依据：pipeline(transaction=True) 保证命令原子执行，zremrangebyscore/zadd/zcard/expire 顺序正确，zcard 在 zadd 后返回包含本次的计数，符合滑动窗口语义。expire 每次刷新 TTL 是预期行为。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-130 set_if_absent 在 Redis 异常时返回 True，幂等键失效导致重复执行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：文档明确说明这是刻意的降级策略：Redis 不可用时返回 True（视为抢到），宁可退化成没有幂等保护也不能因缓存故障拒绝服务。这是有意的可用性权衡，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:68-73 get_json 在 JSON 解析失败时调用 delete，但 delete 自身吞异常，脏值可能残留（非缺陷）（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：get_json 在 json.loads 抛 ValueError 时调用 self.delete(key) 清理脏值。delete 内部吞掉所有异常，因此清理失败不会向上传播，但这是刻意的降级设计（缓存故障不能影响主链路）。即使删除失败，下次读取仍会走同样的未命中路径，行为一致，不构成缺陷。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:108-118 set_if_absent 在 Redis 故障时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-118`
  - 依据：这是文档明确声明的降级策略（宁可失去幂等也不拒绝服务），属于有意的可用性权衡而非缺陷。但需注意：若调用方把 True 当作'已抢到锁'用于分布式锁，Redis 故障时所有 worker 都会认为自己拿到锁，可能造成并发重复执行。文档只提到幂等键与分布式锁两种用途，后者在故障时语义危险。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:143-150 zadd_and_count 的 pipeline 中 zcard 在 zadd 之后执行，计数包含本次请求（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:143-150`
  - 依据：pipeline 顺序为 zremrangebyscore → zadd → zcard → expire，zcard 在 zadd 之后执行，返回的计数包含本次请求。对于限流语义（当前窗口内请求数含本次）这是正确的，调用方据此判断是否超限。不是缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:186-192 remember 的读-改-写非原子，并发写入会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:186-192`
  - 依据：remember 先 _load_entries 读出整个列表，append 后再 set_json 整体写回，中间没有锁或 CAS。同一 buyer 的两次并发 remember 会各自读到相同旧列表，后写者覆盖先写者，导致其中一条回复丢失。虽然丢失只影响缓存命中率、不影响正确性，但属于真实的并发缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:158-165 lookup 中 entry.get('vector', []) 对损坏条目返回空向量，_cosine 返回 0 不报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:158-165`
  - 依据：损坏条目被 _cosine 判为 0.0 相似度从而跳过，不会误命中，也不会抛异常影响主链路。属于合理的防御性处理，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:163-164 lookup 中 entry.get('vector', []) 对非 list 值可能抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:163-164`
  - 依据：若 Redis 中条目被外部污染成 vector 为字符串等类型，_cosine 内 len() 与 zip 可能产生意外结果或异常，但该异常未被 lookup 捕获。不过条目只由本类 remember 写入，正常路径下 vector 恒为 list；且即便抛异常，调用方（UseCase）按设计会降级。属于低概率的健壮性问题，不足以确认为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:62-63 _cosine 对维度不一致返回 0.0，静默掩盖向量维度变化（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:62-63`
  - 依据：维度不一致时返回 0.0 会让该条目视为未命中（低于阈值），行为是安全的降级而非错误结果；且换模型时 namespace 本应变化使旧桶失效。属于合理的防御性处理，不构成缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-143 lookup 完全忽略 has_history 参数，多轮上下文会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-143`
  - 依据：模块文档的安全边界第 3 条要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 只在 enabled 和 is_cacheable_query 上做判断，从未使用 has_history。于是带上下文的追问（如“那款多少钱”）只要不含 _UNSAFE_PATTERNS 中的词，就会跨会话复用旧回复，答非所问。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:148-152 lookup 未检查 has_history，带上下文的多轮问句仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-152`
  - 依据：模块注释第 3 条要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 只判断 _enabled 与 is_cacheable_query(query)，完全没有使用 has_history 参数。因此当会话已有多轮上下文时，只要问句不含 _UNSAFE_PATTERNS（例如“这款水杯多少钱”不含“这个/那个/刚才”等词），仍会命中并返回脱离上下文的旧回复。参数被声明却未使用，属于明确的逻辑遗漏。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:178-182 remember 中 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries.append 后切片 [:_BUCKET_LIMIT] 取的是列表头部，即最早写入的 30 条；新条目在超过上限后被立即丢弃，桶内容永远冻结在最早的 30 条，新回复无法进入缓存，旧回复长期占据桶。
- **[security/medium]** [security] app/infrastructure/cache/semantic_cache.py:36-42 is_cacheable_query 对英文写操作/上下文词无覆盖（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:36-42`
  - 依据：_UNSAFE_PATTERNS 只包含中文关键词，若买家以英文表达写操作（如 "cancel my order"、"buy it"、"refund"）或上下文指代（"that one"），is_cacheable_query 返回 True，写操作意图会被缓存并跨会话复用，违反安全边界第 1 条。是否构成真实缺陷取决于系统是否接受英文问句；若 locale 支持英文则成立。
- **[error_handling/high]** [error_handling] app/infrastructure/security/__init__.py:14-18 output_guard 导入 content_filter 模块，但该文件不在仓库中，导致 security 包导入失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:14-18`
  - 依据：security/__init__.py 在包初始化时无条件执行 `from app.infrastructure.security.content_filter import (...)`，但给定文件列表中不存在 content_filter.py。任何 `import app.infrastructure.security`（或导入其子模块 output_guard 时经由包 __init__）都会抛 ModuleNotFoundError，使 L3/L4 护栏整体不可用。这是导入期硬失败，不是可选依赖。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:47-49 sanitize_tool_output 对空字符串返回 (False, text)，但 text 为 None 时返回 (False, None) 与类型标注不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-49`
  - 依据：函数签名标注 text: str，调用方应传字符串。`if not text` 对空串返回 (False, "")，符合预期。若传入 None 属于调用方违反契约，不在本函数职责内。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:26-34 DANGEROUS_PATTERNS 中部分正则使用 (?i) 内联标志但整体已编译，无问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:26-34`
  - 依据：每个 pattern 都以 (?i) 开头，re.compile 能正确解析内联标志。中文模式也带 (?i)，对中文无影响但对其中英文部分生效。编译与匹配均正常，不是缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:51-58 sanitize_tool_output 逐模式替换，占位符本身可能被后续模式再次匹配导致重复替换（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:51-58`
  - 依据：占位符为「[内容已过滤：疑似注入]」，不含任何危险模式的关键词（ignore/system prompt/you are now 等），后续模式不会匹配到占位符。因此不会发生重复替换或无限增长。不是缺陷。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 content_filter 正则未覆盖大小写混排的中文注入与变体写法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：这是基于正则的启发式过滤，文档明确说明语义级判断交给 L4。正则覆盖有限是已知设计边界，不构成代码缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:55-56 audit_output 对空字符串返回 safe=True 属预期短路，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:55-56`
  - 依据：`if not text: return True, text` 对 None 和空串都短路返回安全。空输出本就不含敏感信息，返回 True 合理；对 None 返回 (True, None) 虽类型上不是 str，但调用方按‘可直接下发’处理 None 也不会泄露。未发现错误行为。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回 True 但未处理 None 之外的非字符串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回安全。虽然类型标注是 str，但 None 也会被安全处理，不会抛异常。这是防御性写法，不是缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:36-37 shopping_session_id 正则要求冒号或等号，纯 ID 值泄露不被拦截（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-37`
  - 依据：模式 `shopping_session_id\s*[:=]\s*[\w-]+` 只匹配带键名的形式。若回复只输出裸 ID 值（如 `sess_abc123`）则漏检。但裸 ID 无键名时无法与普通字符串区分，宽泛匹配会大量误伤；文档判据是‘买家无需知道且泄露有害’，键值形式是主要泄露形态。属设计取舍，不构成可复现缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:43-44 SENSITIVE_PATTERNS 中工具名用 \b 边界，下划线属单词字符导致相邻标识符不被匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-44`
  - 依据：`\b(?:product_search_tool|...)\b` 中 `_` 是 \w，因此 `product_search_tool_v2` 或 `xproduct_search_tool` 不会被匹配。但真实工具名是固定集合，泄露场景是回复里出现完整工具名，边界匹配恰好避免误伤 `product_search_toolkit` 之类正常词。文档也明确要求不用宽泛模式。属有意收窄，非缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-45 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-45`
  - 依据：`r"\b(?:" + "|".join(_INTERNAL_TOOLS) + r")\b"` 中工具名只含字母和下划线，无正则元字符，拼接安全。`\b` 边界对下划线结尾的工具名（如 product_search_tool）能正确匹配。不是缺陷。

## 争议（需裁决）

- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-33 Money.from_major_units 用 round() 做浮点转整数，存在银行家舍入与浮点误差（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：round(major * 100) 使用 Python 的银行家舍入（round-half-to-even），且 major 是 float，0.1*3 之类的二进制浮点误差会传导到金额。例如 from_major_units(2.675, "USD") 得到 267 而非 268；from_major_units(1.005, "USD") 得到 100 而非 101。金额是核心不变量，这种舍入偏差会直接造成对账差异。
  - 争议对手：624e06f60ba7
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:27-42 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-42`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent") 并在注释中说明 role 只能是 buyer/agent，但 __post_init__ 只校验了 session_id，没有校验 role。任何字符串（包括空串、"system"、"tool"）都能构造出 ConversationTurn 并落库，导致对话流水出现非法角色，破坏下游按 role 过滤/回放的正确性。VALID_ROLES 成为死代码。
  - 争议对手：8cd6e0537f23
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：若 inner 返回的某个向量是空列表（例如模型对空文本返回 []），`vector or []` 会把它变成 []，长度与输入文本数一致但向量维度丢失；下游 _cosine 因长度不等返回 0.0，表现为永远不命中，且调用方无法区分“空向量”与“正常向量”。更关键的是 zip(pending, fresh) 在 fresh 长度短于 pending 时不会报错，缺失位置保持 None 后被 `or []` 静默转成空向量，掩盖了 inner 返回数量不足的错误。
  - 争议对手：a64c83cf93d9
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:120-138 zadd_and_count 在 Redis 故障时返回 0，限流完全失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:120-138`
  - 依据：返回 0 表示窗口内计数为 0，调用方据此判断'未超限'从而放行所有请求。Redis 故障时跨进程限流彻底失效，可能压垮下游。虽然注释称'按不限流处理'是有意降级，但限流是保护性措施，静默失效比拒绝服务风险更高，且与 set_if_absent 的降级方向相反（一个放行一个也放行），缺乏统一策略。
  - 争议对手：8f92dbc781c3

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.77% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：13｜覆盖正常：13｜无法判定：0
- 单 Reader 检出率：68.4%（重捕对 2，已观测 47，估计总体 68.7143
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 10.0% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 10.0% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 10.0% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 10.0% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 10.0% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 10.0% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 10.0% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 10.0% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 10.0% |
| `92a8588930ee` | 2 | 0 | `reader_miss` | 10.0% |
| …另有 3 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 1 | 2 | 2 | 0 | 1 | 1 | 0 |
| `app/infrastructure/security` | 2 | 0 | 1 | 2 | 0 | 1 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
