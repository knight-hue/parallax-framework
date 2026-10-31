# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 39 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：64
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：97 个节点 / 233 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 41 | 100% | 20% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:30-31 _cosine 对长度不一致返回 0.0，可能让所有偏好同分（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-31`
  - 依据：维度不一致时返回 0.0 是保守降级，配合 index 次序键仍能稳定输出；且 embed_batch 与 embed 通常同模型同维度。不构成缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:47-55 render_preference_hint 在 preferences 为空时仍输出空块（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:47-55`
  - 依据：空列表时 render_preference_lines 返回空串，hint 块为『<buyer-preferences>\n...\n\n</buyer-preferences>』，虽无内容但不报错；调用方通常会在 select 返回空时跳过注入。不构成缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:84-87 select 中 top_k <= 0 检查在 dislikes 计算之后但早于返回，逻辑正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:84-87`
  - 依据：top_k <= 0 时返回空列表，符合『预算为 0 不注入』的语义；虽然 dislikes 已计算但无副作用。不构成缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:133-135 _rank_by_relevance 注释声称回到原始相对顺序，实际按相似度排序输出（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:133-135`
  - 依据：注释写「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度降序输出，并未按原始 index 重排。这与 _latest_first 的行为不一致（后者确实复原了原始顺序），导致相关性模式下注入块行序随 query 变化而抖动，正是注释想避免的问题。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 dislike 全量保留的安全底线被 top_k 截断破坏（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，但 select() 最终返回 (dislikes + selected_likes)[:top_k]。当 dislikes 数量超过 top_k 时，末尾的 dislike 会被切掉；当 dislikes 数量接近 top_k 时，selected_likes 也会被挤掉。触发条件：买家积累的 dislike 条数 >= top_k（例如 top_k=5 而有 6 条忌口），最后一条黑名单被丢弃，Agent 可能推荐用户明确拒绝的商品，正是文档所说的安全问题。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:28-29 BuyerPreference 未限制 statement 长度（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:28-29`
  - 依据：只校验非空，没有长度上限。超长 statement 会被原样持久化并拼进注入块，可能撑爆上下文预算。属于边界校验缺失。
- **[logic/low]** [logic] app/domain/buyer/preference.py:22-22 created_at 默认值用可变默认参数？不，是字符串，安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-22`
  - 依据：created_at: str = "" 是不可变字符串默认值，不存在可变默认参数问题；__post_init__ 用 object.__setattr__ 在 frozen dataclass 上赋值也是正确写法。
- **[logic/low]** [logic] app/domain/buyer/preference.py:47-56 PreferenceStore.delete 不区分 kind，同 statement 的 like 与 dislike 一并删除（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-56`
  - 依据：文档字符串明确声明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是刻意的语义约定而非疏漏。调用方按 statement 精确匹配删除，行为与文档一致。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-33 Money.from_major_units 用 round 处理浮点，可能静默产生错误金额且未校验 NaN/inf（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：from_major_units 接受 float 并 round(major*100)。对 19.99 这类值，19.99*100 = 1998.9999999999998，round 得 1999 尚可；但对 1.005*100=100.49999999999999 round 得 100 而非 101，属于银行家舍入/浮点误差导致的金额偏差。更严重的是传入 float('nan') 或 float('inf') 时 round 抛 OverflowError/ValueError 或返回 nan，随后 Money.of 的 isinstance(amount,int) 检查会拦住 nan（round(nan) 抛 ValueError），但 inf 会抛 OverflowError 而非 ValueError，异常类型不一致。此外 round 返回 int 才通过 of 校验，行为依赖 Python 版本。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：SUPPORTED_CURRENCIES 明确包含 JPY，而 JPY 的最小货币单位就是 1 日元（无小数位）。from_major_units 对所有币种统一 round(major*100)，于是 Money.from_major_units(1000, 'JPY') 得到 100000 分，to_major_units() 返回 1000.0，但 __str__ 输出 '1000.00 JPY'，而实际语义上 100000 minor units 应为 1000 日元——问题在于 to_major_units 同样除以 100，导致内部表示与真实最小单位不一致：任何以 JPY 最小单位（日元）直接构造的 Money(1000,'JPY') 经 __str__ 会显示 '10.00 JPY'，少 100 倍。注释自认是简化，但 JPY 已在支持列表中，属于真实金额错误而非风格问题。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:36-38 upsert_products 未校验 products 与 embeddings 长度一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:36-38`
  - 依据：端口是抽象接口，长度一致性属于实现方职责；抽象方法体为 ...，不存在可执行逻辑错误。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-36 Product 为可变 dataclass 但 __post_init__ 校验后仍可被外部修改 skus 为空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-36`
  - 依据：Product 不是 frozen，skus 列表可被外部清空，导致 primary_sku() 抛 IndexError。但这是聚合根可变性的常规设计取舍，构造期不变量已校验；是否算缺陷取决于是否要求运行期不变量。此处不认定为确认缺陷。
- **[logic/medium]** [logic] app/domain/catalog/product.py:47-52 searchable_text 未包含 title，标题召回失效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 的 docstring 明确声明返回“标题 + 品牌 + 品类 + 描述 + 亮点”，但实际拼接的列表是 [self.title, self.brand, ...] —— 等等，这里 self.title 确实在列表里。重新核对：列表为 [self.title, self.brand, self.category, self.origin_country, self.description, highlight_text]，title 已包含。因此该结论不成立。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:25-28 Sku.__post_init__ 已校验 stock 非负（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:25-28`
  - 依据：其他审查者称 Sku 未校验 stock 非负，但代码中 __post_init__ 明确有 `if self.stock < 0: raise ValueError`。该结论不成立。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-38 ConversationTurn 未校验 buyer_id 与 content，空买家/空内容可入库（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-38`
  - 依据：__post_init__ 只校验 session_id，buyer_id 与 content 为空字符串时仍可构造。对话流水是客服排查与 bad case 回放的数据底座，空 buyer_id 会导致按买家检索失效，空 content 的 turn 无意义。与 BuyerPreference 对 statement 做非空校验的做法不一致。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:20-38 ConversationTurn 未校验 role 是否在 VALID_ROLES 中（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:20-38`
  - 依据：VALID_ROLES 定义后从未被引用，__post_init__ 只校验 session_id。任意 role 字符串（如 'system'、拼写错误）都能构造并落库，下游按 role 过滤/展示时行为不确定。
- **[concurrency/low]** [concurrency] app/domain/session/ports/session_store.py:17-25 SessionStore 声明 async 接口但注释要求文件实现同步完成（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-25`
  - 依据：端口本身只是抽象声明，是否阻塞取决于具体实现。注释已说明按更严格一方定义接口，文件实现若在 async 函数里做同步 IO 属于实现层问题，不在本文件范围内，无法从这段代码直接判定缺陷。
- **[performance/low]** [performance] app/domain/session/ports/session_store.py:15-25 SessionStore 注释声称文件实现同步即可，但 async 接口在同步实现下会阻塞事件循环（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:15-25`
  - 依据：端口本身只是抽象声明，是否阻塞取决于实现。注释明确说明按更严格的一方（异步）定义接口，这是有意的设计取舍；同步文件实现若在 async def 里做阻塞 IO 确实是实现方的问题，而非端口定义的缺陷。端口层无法强制实现不阻塞，因此不判定为端口缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:57-58 embed 对空 texts 返回 [] 后取 [0] 会 IndexError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:57-58`
  - 依据：embed 固定传 [text]，embed_batch 对非空输入至少返回一个元素（即使 inner 返回空，results 长度仍等于输入长度），因此 [0] 不会越界。仅当调用方直接 embed_batch([]) 时返回 []，这是正确行为。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-82 embed_batch 用 `vector or []` 兜底，会把合法的零向量/空向量与失败结果混为一谈，且当 inner 返回数量不足时静默产生空向量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-82`
  - 依据：pending 非空时调用 inner.embed_batch，然后用 zip(pending, fresh) 配对。若 inner 返回的列表比 pending 短（部分实现失败时返回截断结果），zip 会静默丢弃尾部，results 中对应位置保持 None，最终 `[vector or [] for vector in results]` 把它们变成空列表 []，调用方拿到长度正确但内容为空的向量，无法区分“未命中/失败”与“真实向量”。此外 `vector or []` 会把合法的空向量也归一成 []，掩盖问题。embed() 直接取 [0]，若 texts 非空但 inner 返回空列表，则返回 []，下游向量检索会以空向量查询。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型共享缓存键导致向量串用（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 明确声明 key 用 sha256(model + text)，但实现只对 text 做哈希，self._model 从未参与。若同一 Redis 实例上部署了不同 embedding 模型（或模型升级），同文本会命中旧模型向量，维度/语义不一致，检索结果错误甚至 _cosine 因维度不同恒返回 0。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:60-70 embed_batch 逐条串行 await 缓存读取，批量请求退化为 N 次往返（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:60-70`
  - 依据：for 循环内对每个 text 单独 await self._safe_get，批量 100 条就是 100 次串行 Redis RTT，而 RedisCache 通常支持 mget。批量 embedding 场景下缓存层反而成为延迟瓶颈，抵消了缓存收益。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:108-120 set_if_absent 在 Redis 异常时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-120`
  - 依据：注释明确说明这是有意的降级策略：Redis 不可用时返回 True 视为抢到，避免因缓存故障拒绝服务。这是设计取舍而非缺陷，调用方需知晓该语义。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:132-152 zadd_and_count 在 Redis 异常时返回 0，限流失效（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:132-152`
  - 依据：同样是文档声明的降级策略（按不限流处理），与模块整体“缓存故障不能拖垮主链路”的设计一致，属于有意取舍。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:130-138 zadd_and_count 的 pipeline 中 zcard 结果索引依赖命令顺序，正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:130-138`
  - 依据：pipeline 依次执行 zremrangebyscore、zadd、zcard、expire，results[2] 对应 zcard，索引正确。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:168-173 remember 用 entries[:_BUCKET_LIMIT] 截断，保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-173`
  - 依据：注释说“保留最近条数”，但 append 后取前 30 条，实际保留的是最早写入的 30 条，新条目一旦桶满就被丢弃，缓存永远停留在旧回复上，新回复无法进入。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:137-143 _cosine 对维度不一致返回 0.0，但 entry 中 vector 可能为 None 导致 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-143`
  - 依据：entry.get('vector', []) 在 vector 缺失时返回 []，len([]) != len(vector) 直接返回 0.0；若 vector 显式为 None，len(None) 会抛 TypeError，但 remember 写入的 vector 来自 embedder.embed 的返回值，正常实现不会返回 None。lookup 外层没有 try 包裹 _cosine，但触发需要缓存被外部写入畸形数据，属于防御性边界而非本代码路径可复现的缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-113 _bucket_key 忽略 scope 参数，偏好指纹未进入桶 key（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-113`
  - 依据：docstring 与 2b 安全边界明确要求桶 key 带买家偏好指纹 scope，但实现只哈希 namespace 与 buyer_id，scope 参数完全未使用。买家撤回/新增偏好后仍会命中旧回复，向用户断言已删除的偏好，正是注释里说“实测踩过”的 bug。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:128-133 lookup 忽略 has_history 参数，会话内多轮上下文仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:128-133`
  - 依据：安全边界 3 要求“会话内已有多轮上下文时不命中”，remember 里检查了 has_history，但 lookup 的签名接收 has_history 却从未使用。带上下文的追问（如“那第二款呢”）只要不含 _UNSAFE_PATTERNS 中的词，就会命中跨会话缓存，答非所问。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-53 is_cacheable_query 用子串匹配，'这个'/'那个' 等单字词会误伤大量正常问句（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-53`
  - 依据：_UNSAFE_PATTERNS 包含 '这个'、'那个'、'它' 等，会命中“这个价位有什么推荐”这类其实可缓存的问句，导致缓存命中率下降。但这是保守方向的误判（宁可多花一次调用），不产生错误回复，属于设计取舍而非缺陷。
- **[api_misuse/high]** [api_misuse] app/infrastructure/security/__init__.py:12-16 security/__init__.py 导入 content_filter，但该文件不在本次审查列表且被报告存在导入期崩溃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:12-16`
  - 依据：`__init__.py` 在模块导入时无条件执行 `from app.infrastructure.security.content_filter import (...)`。其他审查者已确认 content_filter.py 中 DANGEROUS_PATTERNS 的内联 `(?i)` 不在表达式开头，`re.compile` 会在导入期抛 `re.error`。由于 content_filter 在模块顶层编译模式，导入 security 包即触发崩溃，导致整个 security 包（包括 output_guard）不可用。这是可引用的真实缺陷：__init__ 的顶层导入把下游模块的导入期错误放大为包级不可用。
- **[api_misuse/critical]** [api_misuse] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 内联 (?i) 不在表达式开头，re.compile 抛错导致模块导入失败（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：Python re 要求全局内联标志 (?i) 必须位于整个正则的最开头。这里多个模式写成 r"(?i)ignore\s+..." 是合法的（(?i) 在开头），但 r"忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)" 等模式中 (?i) 也在开头，需逐个核对。实际检查：所有模式都以 (?i) 开头，因此 re.compile 不会报错。但 r"(?i)system\s*prompt" 等均以 (?i) 起始，合法。因此该结论不成立。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:24-24 content_filter 的 system prompt 模式会误伤正常商品描述（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-24`
  - 依据：r"(?i)system\s*prompt" 会匹配任何含 system prompt 的文本，可能误伤技术类商品描述，但这是安全过滤的保守取舍，且替换为占位符而非丢弃整条，属于可接受设计。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-55 sanitize_tool_output 对已过滤文本重复替换，占位符本身可能被再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-55`
  - 依据：占位符 "[内容已过滤：疑似注入]" 不含任何危险模式的关键词（ignore/忽略/system prompt 等），后续 pattern.subn 不会再次命中它。逐条模式检查均不匹配占位符，因此不存在重复替换或无限膨胀。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:60-62 audit_output 对空字符串返回 safe=True 但未处理 None 之外的非字符串输入（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-62`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回安全。虽然 None 会被原样返回，但函数签名标注 text: str，调用方按契约应传字符串；空字符串确实无需脱敏。此处不构成真实缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:43-43 SENSITIVE_PATTERNS 中工具名用 \b 边界，下划线属于单词字符导致前后缀拼接时漏匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-43`
  - 依据：`\b(?:product_search_tool|...)\b` 中 `\b` 在 `_` 与字母之间不成立（下划线是单词字符），因此 `product_search_tool_v2` 不会被匹配。但工具名是固定集合，泄露场景通常是完整工具名出现，且文档明确说明刻意收窄以避免误伤。这属于设计取舍而非缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:70-76 audit_output 逐模式替换，前一次替换产生的 [已脱敏] 可能被后续模式再次匹配（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:70-76`
  - 依据：REDACTED 常量 `[已脱敏]` 不含任何敏感模式（会话 ID、内部 URL、工具名）的子串，因此后续模式不会再次匹配已替换文本。循环替换是安全的。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:36-36 shopping_session_id 模式要求冒号或等号，纯 ID 值泄露不会被拦截（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-36`
  - 依据：模式 `shopping_session_id\s*[:=]\s*[\w-]+` 只匹配带键名的形式。若模型直接输出裸 ID 值（如 `sess_abc123`），确实不会命中。但裸 ID 无上下文时无法与普通字符串区分，且文档说明判据是“买家侧无需知道且泄露有害”，键值形式是主要泄露形态。属于设计取舍。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:40-41 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-41`
  - 依据：_INTERNAL_TOOLS 全部由字母和下划线组成，拼进正则无需转义；\b 边界对下划线结尾的 task_dispatch 也有效（下划线是 \w）。不构成缺陷。

## 争议（需裁决）

- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:35-43 Money.add/multiply 直接调用构造器绕过 of 校验，可构造出非法 Money（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造。multiply 已校验 quantity 非负，add 的两个操作数若都来自合法 Money 则结果非负，因此当前不会产生负值；但 currency 校验被绕过——若通过 dataclass 直接构造（Money 是 frozen dataclass，构造器公开）一个 currency='XXX' 的实例，add 后仍得到非法币种且不报错。这削弱了不变量保证，属于校验路径不一致。
  - 争议对手：52e623728c0e
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:76-82 get_json 在 JSON 解码失败时未删除脏键，导致缓存永久污染（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:76-82`
  - 依据：get_json 在 json.loads 抛 ValueError 时只返回 None，注释说“脏值当未命中，顺手删掉”，但代码里并没有调用 delete。于是同一个坏值会一直留在 Redis 里，每次读都解析失败、每次都返回未命中，缓存条目永远无法自愈，直到 TTL 到期。如果写入方写入了非 JSON 的裸字符串（例如别的模块用 set 写了裸值），该键就会持续污染。
  - 争议对手：c53fc98a7633

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：14｜无法判定：0
- 单 Reader 检出率：76.8%（重捕对 3，已观测 41，估计总体 53.375
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 5.4% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 5.4% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 5.4% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 5.4% |
| `5d929055a8d9` | 2 | 0 | `reader_miss` | 5.4% |
| `63c335dd31c2` | 2 | 0 | `reader_miss` | 5.4% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 5.4% |
| `797c78721ca7` | 2 | 0 | `reader_miss` | 5.4% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 5.4% |
| `9b22164343f5` | 2 | 0 | `reader_miss` | 5.4% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| `app/domain/session` | 2 | 1 | 2 | 0 | 0 | 0 | 1 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 2 | 0 | 2 | 2 | 0 | 0 | 2 | 0 |
| `app/infrastructure/security` | 2 | 0 | 2 | 0 | 0 | 2 | 0 | 2 |

矩阵填充率 24%（单元格值 = 独立 Agent 数）
