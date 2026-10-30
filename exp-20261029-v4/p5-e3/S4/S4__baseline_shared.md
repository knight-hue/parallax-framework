# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 35 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：90
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：123 个节点 / 433 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 37 | 100% | 15% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/application/__init__.py:1-2 app/application/__init__.py 为空文件（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/__init__.py:1-2`
  - 依据：该文件仅含编码声明，作为包标记文件是正常的，不构成缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-140 相关性排序后未恢复原始相对顺序，与注释承诺不符（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-140`
  - 依据：注释写“回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入”，但代码直接返回 scored[:top_k] 的偏好列表，顺序是相似度降序，并未按原始索引重排。这会导致注入块行序随 query 变化而抖动，与注释承诺相反，也影响 prompt 稳定性与可测性。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:143-146 _latest_first 用 `in` 做成员判断，依赖 dataclass 相等性，可能误删重复偏好（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:143-146`
  - 依据：_latest_first 通过 `p in newest` 过滤，BuyerPreference 若为 dataclass（值相等），两条内容完全相同的偏好会被视为同一元素，导致输出条数少于 top_k 或顺序异常。此外 `in` 是 O(n) 线性查找，整体 O(n^2)。若 BuyerPreference 未定义 __eq__（普通类），则按身份比较，行为正确。需确认 BuyerPreference 是否为 dataclass。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-108 dislike 偏好被 top_k 截断，违反黑名单全量保留的安全底线（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：select() 先构造 dislikes 与 likes，最后统一执行 (dislikes + selected_likes)[:top_k]。当 dislike 数量本身超过 top_k，或 dislike 数量接近 top_k 时，切片会把排在后面的 dislike 丢掉。模块 docstring 明确承诺 dislike 全量保留、不参与 top_k 截断，因此这是与设计契约直接冲突的逻辑缺陷：用户明确拒绝的偏好（如“不要塑料材质”）可能被裁掉，导致推荐出用户拒绝的商品。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:25-33 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:25-33`
  - 依据：__post_init__ 校验了 kind 和 statement，却漏掉 buyer_id。buyer_id 是偏好归属的唯一键，空串会让偏好落到一个共享的“空买家”桶里，list_by_buyer("") 会返回所有脏数据，delete 也可能误删他人偏好。
- **[logic/low]** [logic] app/domain/buyer/preference.py:32-33 created_at 默认空串在 frozen dataclass 中通过 object.__setattr__ 赋值，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:32-33`
  - 依据：frozen dataclass 的 __post_init__ 中修改字段必须用 object.__setattr__，这里用法正确；且仅在 created_at 为空时填充，不会覆盖调用方显式传入的时间。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:33-36 from_major_units 用 round 处理浮点，边界金额可能被舍入到错误分值（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：major 是 float，major*100 会引入二进制浮点误差，round 使用银行家舍入。例如 1.005*100 = 100.49999999999999，round 得 100 而非 101；2.675*100 = 267.49999999999997，round 得 267。金额换算出现 1 分偏差。
- **[logic/medium]** [logic] app/domain/catalog/money.py:17-21 Money 直接构造绕过 of() 校验，负金额/非法币种可进入值对象（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:17-21`
  - 依据：不变量校验只写在 Money.of 里，而 add/multiply 内部直接用 Money(...) 构造。虽然 add/multiply 的输入来自已校验实例，但 dataclass 本身是公开可构造的，任何代码 Money(-100, 'USD') 或 Money(100, 'XYZ') 都能创建非法实例，随后 add/multiply 会传播非法值。文档宣称的不变量并未在类型层面成立。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-37 Product 未校验 title/brand 等必填字段非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-37`
  - 依据：__post_init__ 只校验 product_id 与 skus 非空，title/brand/category 等允许空串。但这是聚合根的设计选择，没有代码表明这些字段必须非空，也没有下游逻辑因空串而崩溃，属于主观校验强度问题，不报告为缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:24-39 Product 为可变 dataclass，skus 列表可被外部修改绕过 __post_init__ 校验（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:24-39`
  - 依据：虽然 skus 是可变 list 且 __post_init__ 只在构造时校验，但这是聚合根常见设计，代码中没有任何地方清空 skus；缺少封装属于设计取舍，未观察到实际错误行为，不足以判定为缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:41-42 primary_sku 直接取 skus[0]，依赖列表顺序而非显式主 SKU 标记（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:41-42`
  - 依据：__post_init__ 已保证 skus 非空，因此 skus[0] 不会 IndexError。虽然“主 SKU”由列表顺序隐式决定，但这是该聚合根的设计约定，没有代码证据表明会导致错误行为，故不判为缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-34 Sku.stock 校验非负但未校验 price 类型，属于契约外（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：__post_init__ 校验 sku_id 非空与 stock 非负，符合文档声明的约束。price 类型由 dataclass 标注为 Money，Python 运行时不强制，但这是全项目一致的约定，不属于本文件引入的缺陷。stock 为负会抛 ValueError，行为正确。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:33-44 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:33-44`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 __post_init__ 只校验 session_id，role 可以是任意字符串。下游按 role 分流（如统计买家/客服消息、回放）时会遇到未知角色，且脏数据一旦落库难以修正。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/session_store.py:18-27 SessionStore 端口未定义删除/清理接口，快照无法失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:18-27`
  - 依据：端口只声明 save/load，缺少 delete 属于接口能力不足而非实现错误；调用方可通过覆盖空快照或 TTL 处理，且文件内无证据表明必须删除。不构成可复现缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:60-61 embed 对空输入列表取 [0] 会 IndexError（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:60-61`
  - 依据：embed 固定传入 [text]，embed_batch 对非空输入返回等长列表，因此 [0] 恒存在。只有 embed_batch 实现违约返回空列表时才会越界，属于上游违约而非本函数缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-76 embed_batch 用 `vector or []` 兜底，空向量被静默替换（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-76`
  - 依据：results 中元素为 None 表示未填充，但 `vector or []` 会把合法的空列表向量（或下游返回的空向量）也替换成 []，同时把 None 也变成 []，调用方无法区分“未取到”与“空向量”，且长度与输入 texts 可能不一致时不会报错而是静默返回空向量，污染后续向量检索。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 缓存 key 未包含 model，换模型后仍命中旧向量（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块文档明确承诺 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 完全未参与。换 embedding 模型后，同一文本仍会命中旧模型产生的向量，导致向量维度/语义空间不一致：轻则检索质量下降，重则维度不匹配使向量索引 upsert/search 报错。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:148-153 close 使用 aclose，旧版 redis-py 无此方法（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:148-153`
  - 依据：aclose 是 redis-py 4.2+ 的异步关闭方法，close 已被 try/except 包裹，即使方法不存在也只会被吞掉，不会导致崩溃。属于兼容性风险而非确定缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:90-96 set_json 的 ttl_seconds 未校验，非正数会导致 Redis 报错被吞（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:90-96`
  - 依据：set_json 直接把 ttl_seconds 传给 redis 的 ex 参数。若 ttl_seconds <= 0，Redis 会返回错误（invalid expire time），异常被吞掉，缓存静默不写入。调用方无法感知，可能误以为缓存已生效。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/redis_cache.py:68-73 get_json 脏值删除会误删并发写入的新值（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：get_json 先 get 到脏值 raw，解析失败后调用 delete(key)。在 get 与 delete 之间，另一个进程可能已经用 set_json 写入了合法新值，此时 delete 会把新值删掉，造成缓存击穿/数据丢失。这是典型的 check-then-act 竞态。
- **[error_handling/high]** [error_handling] app/infrastructure/cache/redis_cache.py:118-126 set_if_absent 在 Redis 异常时返回 True，幂等键与分布式锁失效（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-126`
  - 依据：set_if_absent 用于幂等键与分布式锁。Redis 异常时返回 True（视为抢到），意味着所有并发请求都会认为自己是第一个，幂等保护完全失效，分布式锁形同虚设。虽然注释声称“宁可退化成没有幂等保护”，但这与“分布式锁”语义冲突：锁场景下返回 True 会让多个持有者同时进入临界区，可能导致重复扣款、重复下单等严重后果。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:128-146 zadd_and_count 异常时返回 0，限流被完全旁路（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-146`
  - 依据：该方法用于跨进程限流，异常时返回 0 表示“窗口内无请求”，调用方据此判定未超限，限流在 Redis 故障时完全失效。与 set_if_absent 类似，这是 fail-open 的限流，攻击者可通过打挂 Redis 或制造超时来绕过限流。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:68-73 get_json 解析失败时 delete 未捕获异常，可能向上抛出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-73`
  - 依据：get_json 的契约是「全部读写都吞异常并降级为未命中」，但脏值分支里 `await self.delete(key)` 位于 try 之外。虽然 delete 内部自己 try/except 吞掉了 Redis 命令异常，但 delete 在 `self._client is None` 时直接 return，且 delete 的 except 只包住 `self._client.delete(key)`。真正的问题在于：如果 delete 内部抛出的是非 Exception 子类（如 asyncio.CancelledError 在 Python 3.8+ 是 BaseException）或 delete 本身在 await 期间被取消，异常会穿透 get_json。更直接地，delete 的 except 是 `except Exception: pass`，CancelledError 不被捕获，会从 get_json 的脏值分支向上传播，违反「读失败按未命中」的契约。触发条件：Redis 返回非 JSON 脏值且 delete 期间任务被取消/连接层抛出 BaseException。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:76-88 get_raw 与 get_json 对脏值处理不一致但符合文档意图（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:76-88`
  - 依据：get_raw 直接返回裸字符串，不做 json.loads，因此不会误删幂等键。文档明确说明这是为了避免破坏幂等语义，实现与文档一致，不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:152-158 lookup 未校验 entry 向量维度，_cosine 对缺失 vector 静默返回 0（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:152-158`
  - 依据：_cosine 对长度不等或零向量返回 0.0，低于阈值 0.95，等价于未命中，不会产生错误回复；entry.get('vector', []) 缺失时同样返回 0。行为安全，只是可能浪费一次遍历。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:178-184 remember 的读-改-写非原子，并发下丢失条目（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-184`
  - 依据：remember 先 _load_entries 读取整个桶，append 后再 set_json 整体覆盖。两个并发请求读到同一旧列表，各自 append 后写回，后写者覆盖前者，导致条目丢失，缓存命中率下降。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:155-163 lookup 中 entry.get('vector', []) 对非列表向量调用 _cosine 可能抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:155-163`
  - 依据：entry 来自本类 remember 写入的结构，vector 恒为 list[float]；即便缓存被外部污染成非列表，_cosine 的 len() 与 zip 对多数可迭代对象仍可工作，且 lookup 外层没有 try 但 _load_entries 已做类型过滤。风险极低，不构成确认缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-124 _bucket_key 忽略 scope 参数，偏好指纹未进入 key（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-124`
  - 依据：文档与 docstring 反复强调桶 key 必须包含买家偏好指纹 scope，偏好变更后旧回复必须失效。但 _bucket_key 的 digest 只拼接 namespace 与 buyer_id，scope 形参完全未使用。买家撤回“不要塑料”偏好后，仍会命中撤回前生成的旧回复，向用户断言已删除的偏好。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-141 lookup 忽略 has_history 参数，多轮上下文仍命中缓存（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-141`
  - 依据：安全边界第 3 条要求会话内已有多轮上下文时不命中缓存，remember 中检查了 has_history，但 lookup 的守卫只检查 enabled 与 is_cacheable_query，has_history 形参未被使用。带上下文的追问（如“那款多少钱”）会命中跨会话缓存而答错。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-46 sanitize_tool_output 对空字符串返回原值，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-46`
  - 依据：`if not text: return False, text` 对空串和 None 都直接返回，调用方拿到 (False, '') 或 (False, None)。虽然类型标注是 str，但 None 输入不会崩溃，且不会误报命中。这是安全的短路，不是缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:55-62 sanitize_tool_output 逐条 subn 替换，占位符本身可能被后续模式再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-62`
  - 依据：占位符为中文“[内容已过滤：疑似注入]”，不含任何 DANGEROUS_PATTERNS 的关键词（ignore/system prompt/you are now 等），后续模式不会再次命中它，因此不会出现占位符被反复替换或膨胀。逐条替换是安全的。
- **[security/medium]** [security] app/infrastructure/security/content_filter.py:26-34 正则未覆盖大小写混排的中文注入与跨行注入，过滤存在绕过（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:26-34`
  - 依据：中文模式 `忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)` 中 `.` 默认不匹配换行，攻击者只要在“忽略”与“指令”之间插入换行即可绕过；同时“忽略上面的提示”“forget previous instructions”等常见变体不在模式内。作为 L3 注入防线，这些是可直接构造的绕过路径。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:40-40 内部服务地址正则未加词边界，可能误伤正常 URL 子串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-40`
  - 依据：该模式匹配 http(s)://vllm|reranker|qdrant|redis|opensearch 等主机名，这些是内部容器主机名，正常买家可见 URL 不会以这些作为主机名开头。虽然未加词边界，但 `https?://` 前缀已足够限定，误伤概率极低，属于刻意收窄范围的设计。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:60-62 audit_output 对空字符串返回安全，但 None 输入会走 not text 分支返回 (True, None)（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:60-62`
  - 依据：text 类型标注为 str，None 不在契约内；not text 对空串返回 (True, '') 是合理行为。不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:33-34 内部服务地址正则未覆盖带路径前缀的变体，但已覆盖主机名形式（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:33-34`
  - 依据：正则 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 能匹配 http/https、可选端口、可选路径，覆盖了文档声明的容器网络主机名场景。未覆盖的是带子域名前缀（如 api.vllm.internal）或 IP 形式，但文档明确收窄范围为“容器网络内主机名”，属于有意设计而非缺陷。

## 争议（需裁决）

- **[logic/high]** [logic] app/domain/catalog/money.py:33-36 Money.from_major_units 对零小数位币种（JPY）按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的最小货币单位就是 1 日元（无小数位）。from_major_units 对所有币种统一乘 100，导致 Money.from_major_units(1000, "JPY") 得到 100000 分，即 1000 日元被放大成 100000 日元。to_major_units 同样除以 100，往返换算也不自洽。注释承认是简化，但这是跨境价格核心不变量，属于真实金额错误。
  - 争议对手：247a99dcc820
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:136-141 zadd_and_count 的 member 重复会覆盖旧分数导致计数偏小（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:136-141`
  - 依据：zadd 对同一 member 是更新分数而非新增成员。如果调用方传入的 member 在同一窗口内重复（例如同一用户 ID 多次请求），zcard 只会计 1 次，导致限流计数偏小，限流阈值被绕过。滑动窗口限流通常要求每次请求用唯一 member（如 uuid），但接口签名未强制，调用方容易误用。
  - 争议对手：5280ced115e4, fdb212663f5e

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：13｜覆盖正常：13｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 37，估计总体 37.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `269088b25c46` | 3 | 0 | `reader_miss` | 0.0% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.0% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.0% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.0% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.0% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.0% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 3 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 3 |
| `app/infrastructure/security` | 1 | 0 | 3 | 0 | 0 | 3 | 0 | 0 |

矩阵填充率 20%（单元格值 = 独立 Agent 数）
