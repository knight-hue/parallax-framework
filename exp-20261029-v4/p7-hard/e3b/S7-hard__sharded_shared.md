# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 40 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：63
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：96 个节点 / 227 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 42 | 100% | 20% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:33-34 _cosine 对长度不一致返回 0.0 而非报错，可能把不相关偏好排到前面（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：长度不一致返回 0.0 是防御性降级，且 _rank_by_relevance 已校验 vectors 与 likes 等长、query_vector 非空；单条向量维度异常时给 0 分属于可接受的降级，不会抛异常中断对话。不构成缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:88-91 top_k<=0 时仍返回全部 dislikes，可能超出调用方预期（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：这是文档明确声明的安全底线：dislike 全量保留、不参与截断。top_k<=0 时返回 dislikes 是刻意设计，不是缺陷。
- **[error_handling/medium]** [error_handling] app/application/memory/preference_selector.py:113-116 embed_batch 返回 None 时 len(vectors) 抛 TypeError，降级逻辑失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:113-116`
  - 依据：try 块只包住 embed 调用；`len(vectors)` 在 try 之外。若 embedder 返回 None（接口实现异常或空结果），len(None) 抛 TypeError 直接冒泡，违背「任何异常都降级为按时间倒序，不能因为选偏好把对话搞挂」的承诺。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:118-124 相关性排序取的是相似度最低的 top_k（排序方向反了）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：scored 按 (相似度, index) 升序排序后取 scored[:top_k]，得到的是相似度最低的 k 条，与「按相关性挑选」的意图完全相反。开启 relevance_enabled 且有 embedder 时，最相关的 like 偏好会被丢弃，注入的是最不相关的偏好。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:125-126 用 `p in picked` 做成员判断依赖 dataclass 值相等，可能误删/误留重复偏好（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:125-126`
  - 依据：`return [p for p in likes if p in picked]` 用 `in` 判断，而 BuyerPreference 是 dataclass（值相等语义）。若两条偏好字段完全相同（同一 statement/kind/created_at，例如重复写入或同一秒创建的同文本偏好），它们相等，则只要 picked 中含其中一条，两条都会被保留，导致返回数量超过 top_k；反之若 picked 只含一条而列表中有多条相等项，也无法区分。_latest_first 中 `p in newest` 同理。触发条件：存在字段完全相同的重复偏好且 len(likes) > top_k。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:30-32 _cosine 对维度不一致返回 0.0，可能让不相关偏好排到前面（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-32`
  - 依据：维度不一致返回 0.0 是合理的降级；配合排序方向问题才会放大影响。单独看该函数行为可接受，不构成独立缺陷。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-34 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-34`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好可被构造并写入存储，list_by_buyer('') 会把所有无主偏好混在一起返回，跨买家串数据。
- **[logic/medium]** [logic] app/domain/buyer/preference.py:47-56 PreferenceStore.delete 不区分 kind，同 statement 的 like 与 dislike 会被一并删除（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-56`
  - 依据：文档字符串明确说明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是刻意的设计决策而非缺陷。调用方按 statement 精确匹配删除，语义上同 statement 的正负偏好本就互斥，一并清除符合预期。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:40-47 Money.add/multiply 直接构造实例绕过 of() 校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:40-47`
  - 依据：在正常使用路径下，add 的 self 和 other 都来自 of()，multiply 的 quantity 已校验非负，因此结果必然满足不变量；直接构造非法 Money 属于调用方违反 API 契约，而非本方法缺陷。与上一条 finding 重复，这里记录为不构成独立缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:49-50 to_major_units 对 JPY 同样按 /100 反算，与 from_major_units 一起造成往返不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:49-50`
  - 依据：to_major_units 硬编码 /100，对 JPY 应 /1。与 from_major_units 的 100 倍问题同源，导致 JPY 金额展示错误（100000 分显示为 1000.00 JPY，而实际应为 100000 JPY）。
- **[logic/medium]** [logic] app/domain/catalog/money.py:15-18 Money 是 frozen dataclass 但未在 __post_init__ 校验，直接构造可绕过不变量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:15-18`
  - 依据：模块 docstring 声明不变量'amount 必须非负整数、currency 必须受支持'，但 dataclass 自动生成的 __init__ 不做任何校验，只有 of() 校验。任何 Money(-1, 'XXX') 或 Money(1.5, 'USD') 都能构造成功，不变量形同虚设。add/multiply 正是利用这一点绕过校验。
- **[logic/medium]** [logic] app/domain/catalog/money.py:40-47 Money.add/multiply 绕过 of() 校验，可构造非法 Money（负数/不支持币种）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:40-47`
  - 依据：Money.of() 是唯一做不变量校验的入口（非负整数、受支持币种），但 add() 和 multiply() 直接调用 Money(...) 构造器，绕过了 of()。虽然 add/multiply 的输入来自已校验的 Money 实例，但 multiply 的 quantity 校验只保证非负，amount*quantity 不会为负；真正的问题在于 add() 的 other 参数没有类型/币种之外的校验——如果 other 是通过直接构造 Money(-100, 'USD') 得到的（dataclass 构造器不校验），add 会静默产生负数金额，破坏“amount 必须非负”的核心不变量。同样，直接构造 Money(100, 'XXX') 后 add 会产出不受支持币种的 Money。由于 dataclass 是 frozen 但构造器公开，不变量并非不可绕过。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:20-27 EmbeddingClient 端口未约束 embed_batch 返回长度，调用方易踩空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:20-27`
  - 依据：端口只声明返回 list[list[float]]，未在文档中要求与 texts 等长。这是接口契约的模糊点，但端口本身不实现逻辑，无法在此文件内证明存在运行时缺陷；实际风险由实现方与调用方承担。记为 not_a_defect 以提示契约需明确。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:39-40 primary_sku 在 skus 为空时 IndexError，但 __post_init__ 已保证非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:39-40`
  - 依据：__post_init__ 强制 skus 非空，因此正常构造路径下 primary_sku 不会越界。只有通过 dataclasses.replace 或直接修改 skus 列表（Product 非 frozen，skus 是可变 list）清空后才可能触发。由于 Product 是可变 dataclass，外部可执行 product.skus.clear() 后再调用 primary_sku() 导致 IndexError，这是一个真实但低概率的可变性缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/product.py:33-37 Product 的 __post_init__ 在 skus 为 None 时抛出 TypeError 而非预期的 ValueError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-37`
  - 依据：skus 字段声明为 list[Sku] 且 default_factory=list，但 dataclass 不做运行时类型校验。若调用方显式传入 skus=None（例如从 JSON/DB 反序列化时缺失字段被映射为 None），`if not self.skus` 对 None 求值为 True，随后 f-string 中 `{self.product_id}` 正常，但真正的问题在于：`not None` 为 True 会进入 raise 分支——这本身行为正确。然而若传入的是空字符串或 0 等非列表值，`not self.skus` 同样为 True 并抛 ValueError，掩盖了类型错误。更关键的是 primary_sku() 与 find_sku() 直接索引/迭代 self.skus，若绕过 __post_init__（如 dataclasses.replace 或 object.__new__）则无保护。综合看，__post_init__ 的校验对 None 输入实际是安全的（会抛 ValueError），因此该点不构成缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 searchable_text 对 highlights 中 detail 为 None 时产生 'None' 字面量（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：ProductHighlight.detail 默认值为空字符串 ""，类型标注为 str，正常构造不会为 None。f-string 对 None 会输出 'None'，但这需要调用方违反类型约定显式传 detail=None，属于调用方违约而非本函数缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 强制为正，无法表示缺货/零库存 SKU（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：__post_init__ 中 `if self.stock <= 0: raise ValueError`，意味着 stock=0 的 SKU 无法构造。但 stock 被文档定义为「初始库存」，用于首次播种库存表；一个初始库存为 0（已售罄或尚未入库）的可售卖 SKU 是合法业务状态，构造时直接抛异常会导致商品目录加载/播种失败。若上游数据源包含 0 库存 SKU，整个 Product 构造链会中断。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:33-40 ConversationTurn 未校验 content 非空，空内容轮次可入库（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:33-40`
  - 依据：__post_init__ 校验了 role 和 session_id，但 content 允许为空字符串。对话流水用于事后追溯与 bad case 回放，空 content 的轮次会污染回放数据且无法区分“模型返回空”与“写入 bug”。同文件 BuyerPreference 对 statement 做了非空校验，此处不一致。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:62-63 embed 单条接口在 embed_batch 返回空列表时索引 [0] 抛 IndexError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:62-63`
  - 依据：embed 传入 [text] 单元素列表，embed_batch 对非空输入要么返回等长结果要么抛 RuntimeError，不会返回空列表，因此 [0] 安全。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 中 zip 截断导致结果缺失时抛 RuntimeError，但更严重的是 pending 与 fresh 长度不一致时静默错位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：当 inner.embed_batch 返回的向量数量少于 pending 数量时，zip 会静默截断，results 中剩余位置保持 None，随后 missing 检查会抛 RuntimeError。这本身是有意为之（注释说明不静默补零）。但真正的问题是：如果 inner 返回数量多于 pending，多余向量被丢弃；如果返回顺序与输入不一致，则向量会被错误地关联到错误的文本上并写入缓存，造成持久化的错误缓存（TTL 7 天）。代码没有校验 len(fresh) == len(pending)，也没有校验顺序。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:68-74 embed_batch 中缓存命中判断 `isinstance(cached, list) and cached` 会把空向量列表当未命中，但非空但维度错误的向量会被直接使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:68-74`
  - 依据：缓存中存储的向量若因模型变更或脏数据导致维度与当前模型不一致，代码只检查 `isinstance(cached, list) and cached`（非空列表），不校验元素类型或维度，直接 append 到 results 并计入 hits。后续调用方拿到维度错误的向量会在余弦相似度或向量检索中产生错误结果。key 中包含 model 名，正常情况下模型变更会换 key，但同一 model 下若缓存被污染（例如手工写入、或旧版本写入格式不同），仍会命中错误向量。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:138-148 zadd_and_count 清理边界多减 1 秒，窗口实际略长于 window_seconds（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:138-148`
  - 依据：zremrangebyscore(key, 0, now - window_seconds - 1) 把上界设为 now - window_seconds - 1，比精确窗口边界 now - window_seconds 多保留了 1 秒的旧成员，导致滑动窗口实际长度为 window_seconds + 1 秒，限流比配置略宽松。若 window_seconds 很小（如 1 秒），误差达 100%。这是边界计算偏差，非致命但确实与“窗口内当前数量”的语义不符。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-130 set_if_absent 在 Redis 故障时返回 True，幂等键与分布式锁退化为无保护（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：这是文档明确声明的设计取舍：Redis 不可用时返回 True 表示“抢到”，宁可退化为无幂等保护也不拒绝服务。对幂等键语义（首次请求放行）是合理的；对分布式锁语义则意味着锁失效、并发进入临界区。但该方法被同时用于两种语义，调用方需自行承担。就本文件而言行为与注释一致，不构成实现缺陷，故记为 not_a_defect，但提示锁场景下需额外考虑。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:78-86 get_json 对脏值删除键，但 delete 失败被静默吞掉，脏值会持续存在（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:78-86`
  - 依据：delete 内部已吞异常，get_json 中删除失败不会影响返回值（仍返回 None 视为未命中）。脏值残留只会导致后续继续未命中，不影响正确性，属于可接受的降级。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:148-156 lookup 中 similarity > threshold 使用严格大于，等于阈值视为未命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-156`
  - 依据：文档说明“低于阈值视为未命中”，严格大于意味着恰好等于阈值时不命中，属于保守策略，与文档“宁可多花一次调用”一致，不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:160-168 lookup 用严格大于阈值，相似度恰等于 threshold 时判为未命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:160-168`
  - 依据：similarity > self._threshold 使用严格大于，恰好等于 0.95 时不命中。文档说“低于阈值视为未命中”，字面上等于阈值应命中，但浮点相似度恰好等于阈值的概率极低，且偏保守（多一次调用）符合“宁可多花一次调用也不能答非所问”的设计意图。不构成实际缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:178-186 语义缓存桶读-改-写非原子，并发 remember 会丢失条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-186`
  - 依据：remember() 先 _load_entries 读出整个桶列表，append 后再 set_json 整体覆盖写回。两个并发请求（同一 buyer、同一 scope）会各自读到同一份旧列表，各自 append 自己的条目，后写者覆盖先写者，导致先写入的缓存条目丢失。RedisCache 没有提供 CAS/事务性列表操作，set_json 是普通 SET。触发条件是同一买家在短时间内并发发起两个可缓存问句（多 worker 部署下很常见）。后果是缓存命中率下降，属于性能/正确性退化而非数据损坏，故 medium。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:172-176 remember 未校验 reply 类型，非字符串 reply 调用 startswith 抛 AttributeError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:172-176`
  - 依据：remember 中 `reply.startswith("[error]")` 假定 reply 是 str。若上游传入 None 或其他类型，会抛 AttributeError，且该异常不在 try 块内（try 只包住 embed），会向上传播打断主链路。虽然类型标注为 str，但运行时无强制。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-56 is_cacheable_query 用子串正则拦截，'这个'/'那个' 等会误伤正常商品问句（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-56`
  - 依据：_UNSAFE_PATTERNS 包含 r"这个"、r"那个"、r"它" 等极短子串，任何包含这些字符的正常问句（如“这个商品多少钱”“那个牌子的鞋有货吗”）都会被判定为不可缓存，导致语义缓存命中率大幅下降。这是安全边界过宽导致的性能/功能退化，属于逻辑缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:66-72 lookup 中 _cosine 对维度不一致的向量静默截断，可能产生错误相似度（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:66-72`
  - 依据：_cosine 用 zip(left, right) 逐元素相乘，zip 在较短序列耗尽时停止，不校验两向量长度是否相等。若 embedding 模型更换或维度变化（namespace 未同步更新、或历史缓存条目残留旧维度向量），会拿前 min(len) 个分量算余弦，得到一个无意义的相似度，可能超过 0.95 阈值而错误命中，返回与当前问句无关的旧回复。namespace 设计上应包含模型名，但代码未强制校验，且 _load_entries 不校验 entry 向量维度。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:96-104 SemanticCache 构造时 enabled 依赖 cache.enabled，Redis 后续恢复也不会重新启用（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:96-104`
  - 依据：self._enabled = enabled and cache.enabled 在构造时求值一次。RedisCache 的 enabled 取决于构造时是否成功创建客户端，运行期不会变化（客户端要么有要么没有），因此不存在“运行期恢复后仍禁用”的问题。属于一次性判定，不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-45 sanitize_tool_output 对空字符串返回原值，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-45`
  - 依据：`if not text: return False, text` 对空字符串与 None 都直接返回，避免对空值做正则替换。空字符串本就不含注入内容，返回 (False, '') 是正确行为，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/content_filter.py:47-55 sanitize_tool_output 对非字符串输入调用 re.subn 抛 TypeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-55`
  - 依据：函数签名声明 text: str，但工具返回内容来自第三方，可能是 dict/list/None 等结构化结果。`if not text` 只拦截空值，非空非字符串（如 dict）会进入 pattern.subn，re 模块对非 str/bytes 输入抛 TypeError，导致工具调用链路中断而非降级过滤。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:25-25 content_filter 的 `system\s*prompt` 模式会误伤正常商品描述（如 'system prompt' 出现在技术文档/商品文案中）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:25-25`
  - 依据：这是有意的保守策略：命中即替换为占位符而非丢弃整条，保留其余内容。误伤代价是局部文本被替换，属于设计权衡而非缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-53 content_filter 正则使用 (?i) 内联标志但模式中已含中文，re.compile 正常；真正问题是 subn 替换后可能产生新的可匹配片段（替换文本本身不含危险词，安全）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-53`
  - 依据：占位符文本 '[内容已过滤：疑似注入]' 不匹配任何危险模式，替换不会级联触发，逐模式 subn 是安全的。
- **[security/medium]** [security] app/infrastructure/security/content_filter.py:24-24 content_filter 的 `忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)` 中 `.` 不匹配换行，跨行注入可绕过（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-24`
  - 依据：Python re 默认 `.` 不匹配换行符。攻击者把注入写成多行（如 '忽略\n之前的\n指令'）即可绕过该模式。同样 `ignore\s+(all\s+)?previous\s+instructions?` 中 \s 可匹配换行所以英文模式相对安全，但中文模式用 `.` 会被换行阻断。这是安全过滤的绕过缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:55-68 audit_output 对非字符串输入调用 re.subn 会抛 TypeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:55-68`
  - 依据：函数签名标注 text: str，但仅用 `if not text` 做空值判断。若调用方传入 None 会走 `return True, text` 返回 (True, None)，下游若直接下发 None 可能出错；若传入非字符串（如 dict/list），`if not text` 对非空容器为 False，随后 pattern.subn 对非字符串抛 TypeError。作为最后一道闸，缺少类型校验会让异常冒泡到主 loop。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:60-62 audit_output 对空字符串返回安全，但非字符串输入未防御（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-62`
  - 依据：`if not text: return True, text` 对 None 也返回 (True, None)，调用方若直接下发 None 可能出错，但函数签名声明 text: str，且空值语义上确实无敏感内容。属于契约内行为，不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:60-68 audit_output 对同一文本重复脱敏时，后续模式可能匹配到已脱敏占位符内部，导致 safe 判定与文本不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-68`
  - 依据：审查者怀疑 REDACTED 占位符 '[已脱敏]' 会被后续模式再次匹配。逐一核对：会话 ID 模式要求 'shopping_session_id' 前缀；sk- 模式要求 'sk-' 加 20 位以上字母数字；URL 模式要求 http(s):// 加内部主机名；工具名模式要求完整工具名。'[已脱敏]' 不含上述任何子串，因此不会二次匹配。safe 标志一旦置 False 不会被重置，逻辑正确。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:36-37 内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-37`
  - 依据：`"|".join(_INTERNAL_TOOLS)` 直接拼进正则，若工具名含正则元字符会破坏模式。当前 _INTERNAL_TOOLS 全是字母和下划线，无元字符，实际安全。属于潜在维护风险而非当前缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/catalog/money.py:33-36 from_major_units 用 round() 处理浮点，银行家舍入导致金额偏差（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：round() 使用银行家舍入（round-half-to-even），且输入是 float，0.1+0.2 之类的二进制浮点误差会让 round(2.675*100) 得到 267 而非 268。价格换算属于核心不变量，用 float 做金额换算并用 round 舍入会产生 1 分钱级别的偏差，在累加/对账时暴露。
  - 争议对手：69217fef01ae
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-44 内部工具名正则未加 re.IGNORECASE，大小写变体可绕过脱敏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-44`
  - 依据：工具名模式用 \b(?:...)\b 精确匹配小写工具名，未加 re.IGNORECASE。若模型输出 'Product_Search_Tool' 或 'PRODUCT_SEARCH_TOOL'，正则不命中，内部工具名会原样下发给买家，L4 脱敏被绕过。虽然模型通常输出小写，但输出审核作为最后一道闸不应依赖此假设。
  - 争议对手：57c54947c6ea

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：12｜无法判定：0
- 单 Reader 检出率：66.2%（重捕对 3，已观测 42，估计总体 63.4444
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 11.4% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 11.4% |
| `269088b25c46` | 2 | 0 | `reader_miss` | 11.4% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 11.4% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 11.4% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 11.4% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 11.4% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 11.4% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 11.4% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 11.4% |
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 2 |
| `app/domain/session` | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 2 | 0 | 1 | 2 | 0 | 2 | 0 | 0 |

矩阵填充率 22%（单元格值 = 独立 Agent 数）
