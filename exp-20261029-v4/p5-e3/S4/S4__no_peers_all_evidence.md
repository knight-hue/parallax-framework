# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 10 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 30 | 支持不足、相关性超限或尚待验证 |
| 争议 | 3 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：80
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：114 个节点 / 355 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 43 | 100% | 16% |

## 高置信结论

- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-141 _rank_by_relevance 注释声称回到原始相对顺序，实际按相关性分数排序输出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-141`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码 picked = [preference for _, _, preference in scored[:top_k]] 直接按 scored 排序（相关性降序）输出，并未按原始 index 复原顺序。这与 _latest_first 的实现（用 [p for p in likes if p in newest] 复原原始顺序）不一致，也与注释承诺不符。后果是注入块行序随 query 变化而抖动，可能影响 Prompt Cache 命中率（正是该模块关心的点）。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:146-150 _latest_first 用 `p in newest` 依赖 dataclass 相等性，可能误删/重复（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:146-150`
  - 依据：`[p for p in likes if p in newest]` 使用 BuyerPreference 的相等性（dataclass 默认按字段比较）而非身份。若存在两条字段完全相同的偏好（例如同一 statement、同一 created_at 的重复记录），`in` 会把两条都保留，导致输出数量超过 top_k；反之若 newest 中某条与 likes 中另一条相等但非同一对象，也会被错误保留。应使用 id() 或索引集合。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-108 dislike 偏好被 top_k 截断，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单是安全问题。但 select() 在最后返回 (dislikes + selected_likes)[:top_k]，这个切片会同时截断 dislikes。当 dislike 数量 >= top_k 时，部分 dislike 被丢弃；当 dislike 数量 > top_k 时甚至可能一条 like 都不返回。此外 likes 分支用 len(likes) <= top_k 判断，未考虑 dislikes 已占用的预算，导致 dislikes + likes 总数超过 top_k 时 like 被截断（这本身可接受），但 dislike 被截断不可接受。触发条件：买家有 3 条 dislike、top_k=2，则第 3 条 dislike 被丢弃，可能推荐用户明确拒绝的东西。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:35-43 Money.add/multiply 绕过 of() 校验，可构造负数金额（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 强制 amount 非负，但 add() 与 multiply() 直接调用 Money(...) 构造器，绕过校验。虽然当前 add 两个非负值不会为负，但 Money 的 dataclass 构造器本身不校验，任何直接 Money(-1, 'USD') 或未来引入减法都会产生非法状态；更关键的是 multiply 的 quantity 校验了 bool，而 of() 的 isinstance(amount, int) 对 bool 为 True（True 是 int 子类），Money.of(True, 'USD') 会通过校验得到 amount=1，与 multiply 的严格校验不一致。
- **[logic/high]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数位币种按 100 倍换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的最小货币单位就是 1 日元（无小数位）。from_major_units(1000, 'JPY') 会返回 100000 minor units，即 100000 日元，比真实金额大 100 倍。注释承认“demo 暂统一”，但该函数是公开 API 且 JPY 在支持列表中，任何用 JPY 走该入口的调用都会产生 100 倍价格错误，属于真实逻辑缺陷而非风格问题。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，role 字段完全未校验，VALID_ROLES 成为死代码。任意 role（如 "system"、拼写错误 "buyr"）都能构造成功并落库，破坏对话流水的角色约束，下游按 role 过滤/统计时会漏数据。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 缓存 key 未包含 model，换模型后可能复用旧向量（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。若同一 Redis 实例被不同模型（或不同维度）的客户端共用，换模型后旧向量仍会命中，导致维度不匹配（_cosine 返回 0.0 静默失效）或语义错配。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:66-74 embed_batch 串行 await 缓存读取，批量请求性能退化（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-74`
  - 依据：循环内对每个 text 逐个 await _safe_get，N 条文本产生 N 次串行 Redis 往返；批量场景下延迟线性叠加。可用 asyncio.gather 并发。属于性能问题而非正确性缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-128 scope 参数被忽略，偏好指纹未进入桶 key，撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-128`
  - 依据：_bucket_key 接收 scope 参数，但函数体只把 namespace 和 buyer_id 拼进 sha256，scope 完全没有参与计算。文档明确要求 scope 装载偏好指纹，使偏好新增/撤回后旧回复自动失效。实际实现下，买家撤回“不要塑料”偏好后，桶 key 不变，lookup 仍会命中撤回前生成的回复，向用户断言一条已删除的偏好——正是注释里说“实测踩过”的安全问题。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:129-137 lookup 忽略 has_history，带上下文的问句仍会命中缓存（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:129-137`
  - 依据：模块文档第 3 条安全边界要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 只在 enabled 和 is_cacheable_query 上做判断，has_history 参数完全未使用。结果是：多轮会话中依赖上下文的问句（如“那款多少钱”）只要没被 _UNSAFE_RE 拦住，就会跨会话复用旧回复，答非所问。

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:92-95 top_k<=0 时提前返回空列表，dislike 也被丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:92-95`
  - 依据：当 top_k<=0 时直接 return []，连 dislike 都不注入。虽然注释说“预算为 0 时不注入任何偏好”，但这与“dislike 全量保留、不参与截断”的安全底线冲突：若调用方因配置错误或预算计算得到 top_k=0，黑名单会完全失效，可能推荐用户明确拒绝的商品。至少应保留 dislike。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-37 embed_batch 返回向量维度与 query 不一致时 _cosine 静默返回 0（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：_cosine 在维度不一致或零向量时返回 0.0，属于防御性降级，不会抛异常。虽然会静默把该偏好排到末尾，但这是合理的容错行为，且上层有数量校验。不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/ports/__init__.py:1-2 PreferenceStore.delete 文档承诺同 statement 的 like/dislike 一并清除，但端口未约束实现（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/ports/__init__.py:1-2`
  - 依据：该文件只有编码声明，无实际代码。delete 的语义约束写在 preference.py 的 docstring 中，属于端口契约文档，不是可执行缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:41-42 primary_sku 直接取 skus[0]，依赖列表顺序而非显式主 SKU 标记（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:41-42`
  - 依据：__post_init__ 已保证 skus 非空，因此 skus[0] 不会 IndexError。虽然“主 SKU”语义依赖插入顺序，但这是该聚合根的设计约定，没有代码证据表明会导致错误行为，故不判为缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-34 Sku.stock 校验非负，符合只读初始库存语义（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：__post_init__ 校验 sku_id 非空与 stock 非负，逻辑正确，无缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn.role 未校验，非法角色可写入流水（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，从不校验 role。任何拼写错误（如 "Agent"、"assistant"、"system"）都能构造成功并落库，破坏「业务可读的对话流水」的数据一致性，且下游按 role 过滤/回放时会漏掉这些记录。VALID_ROLES 定义后完全未被使用，说明校验被遗漏。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:70-71 embed 对空 texts 返回 [] 正确，但 embed 单条依赖 embed_batch 索引 0（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:70-71`
  - 依据：embed 传入 [text]，embed_batch 对非空输入至少返回一个元素（未命中时 inner 返回，命中时 cached），索引 0 安全。若 inner 违约返回空列表，则 IndexError，但那是上游违约。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：results 中 None 只可能来自未命中且 inner 未返回对应向量的情况；正常路径下 zip(pending, fresh) 会填满。若 inner 返回的向量本身是空列表，`vector or []` 与之一致；若 inner 返回 None（违反端口契约），则被替换为空列表，属于对上游违约的容错。端口契约要求返回 list[list[float]]，因此这不是本文件的缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:78-78 embed_batch 用 `vector or []` 把合法空向量/None 静默替换为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-78`
  - 依据：若 inner.embed_batch 返回的 fresh 列表长度短于 pending（实现异常或部分失败），zip 会截断，results 中对应位置仍为 None，最终 `vector or []` 把它变成空列表返回给调用方，调用方无法区分“未取到向量”和“空向量”，会把空向量写入向量索引或参与检索，产生难以排查的错误而非显式失败。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:139-145 close 使用 aclose，旧版 redis-py 无此方法会抛 AttributeError 被吞，连接未关闭（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:139-145`
  - 依据：redis.asyncio 的 Redis 客户端在 redis-py 4.2+ 提供 aclose()，更早版本用 close()。项目若锁定较新版本则无问题；即便版本不匹配，异常被吞只是连接未优雅关闭，进程退出时 OS 会回收。不构成功能性缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:128-137 zadd_and_count 的 pipeline 中 expire 在 zcard 之后执行，但结果索引固定取 results[2]，若 pipeline 命令顺序变化会取错值（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-137`
  - 依据：pipeline 中命令顺序为 zremrangebyscore(0)、zadd(1)、zcard(2)、expire(3)，results[2] 确实是 zcard 的返回值。当前代码顺序与索引一致，不存在取错值的问题。虽然用魔法索引不够健壮，但当前实现正确。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:143-150 zadd_and_count 使用 pipeline 但未处理 zadd 成员重复导致计数偏大（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:143-150`
  - 依据：zadd 对同一 member 是更新分数而非新增，zcard 统计的是唯一成员数，语义正确。若调用方传入相同 member 则本就不应重复计数。不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:100-106 set_json 使用 json.dumps 序列化，遇到不可序列化对象时异常被吞，缓存静默不写入（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:100-106`
  - 依据：json.dumps 在 try 块内，不可序列化对象（如 datetime、自定义类）会抛 TypeError，被 except Exception 捕获并记录 warning，缓存跳过。这符合模块文档“缓存绝不能影响主链路”的设计意图，调用方拿到的是未命中而非错误。虽然会导致缓存命中率下降，但这是有意的降级策略，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:69-71 get_json 中 delete 调用未包裹在 try 内，但 delete 自身已吞异常（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:69-71`
  - 依据：delete 方法内部已 try/except 吞掉所有异常，因此此处 await self.delete(key) 不会抛出，get_json 的降级语义完整。不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:148-155 lookup 中 entry.get('vector', []) 对损坏条目返回空向量，_cosine 返回 0 安全（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-155`
  - 依据：若桶内条目缺少 vector 字段，_cosine 收到空列表，长度不等返回 0.0，低于阈值不会命中；若 vector 全零，norm 为 0 也返回 0.0。不会抛异常也不会误命中，属于安全降级。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:178-182 remember 的 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在超过 30 条后被丢弃。结果是缓存永远停留在最旧的一批问句，新问句无法进入缓存，与设计意图相反。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/semantic_cache.py:168-174 remember 先读后写非原子，并发写会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-174`
  - 依据：remember 通过 _load_entries 读出整个列表，append 后再 set_json 整体覆盖。同一 buyer 的并发请求（或同一请求内多次 remember）会互相覆盖，后写者丢失先写者的条目。属于 read-modify-write 竞态，缓存场景下影响有限但确实存在。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:66-68 _cosine 对维度不一致返回 0.0 而非报错，掩盖向量模型变更（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:66-68`
  - 依据：维度不一致时返回 0.0 视为未命中，是保守且安全的降级行为，不会产生错误回复，只是多一次模型调用。属于有意的容错设计，不构成缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:148-152 lookup 忽略 has_history 参数，会话内多轮上下文仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-152`
  - 依据：文档安全边界第 3 条要求“会话内已有多轮上下文时不命中”，remember 中检查了 has_history，但 lookup 完全没有使用 has_history，只要问句可缓存就直接查桶。带上下文的问句（如“那款多少钱”）会命中跨会话缓存，答非所问。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:178-182 remember 的 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries 是 append 追加，切片 [:_BUCKET_LIMIT] 取的是最前面的旧条目，新写入的条目在超过 30 条后会被直接丢弃。结果是桶内永远保留最早的 30 条，新回复无法进入缓存，与设计意图相反。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 中 (?i) 内联标志位置在部分 Python 版本下会报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：Python 3.11+ 起 (?i) 允许出现在模式开头（全局标志），这些模式均以 (?i) 开头，re.compile 正常。若在 3.6 以下会报 “global flags not at the start”，但项目使用 from __future__ import annotations 与 dataclass，实际运行版本远高于此，不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:26-34 DANGEROUS_PATTERNS 中 system\s*prompt 等模式过宽，会误伤正常商品描述（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:26-34`
  - 依据：r"(?i)system\s*prompt" 会匹配任何包含「system prompt」字样的文本，例如商品标题「System Prompt Engineering 实战书」或技术类商品描述；r"(?i)you\s+are\s+now" 会匹配「You are now able to...」这类正常营销文案。命中后整段被替换为占位符，导致正常商品信息丢失，与模块注释「保留其余正常内容（商品标题、价格）」的目标相悖。
- **[error_handling/low]** [error_handling] app/infrastructure/security/content_filter.py:36-52 sanitize_tool_output 对非 str 输入（None 以外）会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:36-52`
  - 依据：函数签名声明 text: str，且 `if not text` 已处理 None 与空串。工具返回若为 dict/list 属于调用方违反契约，不是本函数缺陷；在类型契约内行为正确。
- **[error_handling/low]** [error_handling] app/infrastructure/security/content_filter.py:41-45 sanitize_tool_output 对非 str 输入（None 以外）会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:41-45`
  - 依据：函数签名声明 text: str，只对空值做短路。工具返回若为 dict/list 等非 str，pattern.subn 会抛 TypeError。但这是类型契约内的调用方错误，且 docstring 明确输入为文本；在 Python 动态类型下属于调用方责任，不认定为该函数缺陷。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:55-63 sanitize_tool_output 对已替换的占位符再次匹配，可能重复替换/误伤（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-63`
  - 依据：占位符文本「[内容已过滤：疑似注入]」不含任何 DANGEROUS_PATTERNS 能匹配的子串（不含 ignore/system prompt/you are now 等），因此后续 pattern 不会再次命中占位符，不存在重复替换或无限膨胀。逐个 pattern 顺序 subn 是安全的。
- **[security/medium]** [security] app/infrastructure/security/content_filter.py:24-33 content_filter 正则未覆盖大小写混排的中文注入与多行，且 system prompt 模式会误伤正常商品描述（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-33`
  - 依据：r"(?i)system\s*prompt" 会匹配任何包含 'system prompt' 的正常文本（例如商品描述里讨论 LLM 的书籍），把正常内容替换为占位符，造成信息丢失；同时中文模式 r"(?i)忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)" 中 . 默认不匹配换行，攻击者用换行分隔即可绕过。这是过滤器的真实覆盖缺口与误伤，而非风格问题。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-66 audit_output 对空字符串返回 safe=True 但未处理 None 之外的非字符串（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-66`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回安全。虽然类型标注是 str，但若上游传入 None，返回 (True, None) 而非字符串，调用方若直接下发可能出错。不过函数签名声明为 str，且空值语义上确实“无内容可泄露”，返回原值合理。属于边界但非明确缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:62-64 audit_output 对空字符串返回安全，但 None 输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-64`
  - 依据：`if not text: return True, text` 对空字符串和 None 都返回 (True, text)，不会进入正则处理，因此 None 不会抛异常。类型标注为 str，调用方传 None 属于类型违约，但函数本身对 falsy 输入是安全的。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:38-44 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-44`
  - 依据：_INTERNAL_TOOLS 中的名称只含字母和下划线，拼进正则无需转义，不会产生元字符问题。`\b` 边界对下划线结尾的名称（如 product_search_tool）能正确匹配。不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-47 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-47`
  - 依据：`r"\b(?:" + "|".join(_INTERNAL_TOOLS) + r")\b"` 直接拼接工具名进正则。当前 _INTERNAL_TOOLS 全是字母和下划线，无正则元字符，拼接安全。若未来加入含元字符的工具名会出问题，但当前代码无缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空 buyer_id 的偏好会被 append 写入，list_by_buyer('') 时可能把不同来源的空 buyer 偏好混在一起，破坏“按买家隔离”的语义。
  - 争议对手：5e80e47f8b6c
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，与 set_if_absent 的 fail-open 策略不一致，导致限流失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：set_if_absent 明确注释说明 Redis 故障时应 fail-open（返回 True 放行），但 zadd_and_count 在 _client 为 None 或异常时返回 0。调用方通常用 `count > limit` 判断是否限流，返回 0 意味着永远不触发限流，即 fail-open；但若调用方用 `count >= limit` 或把 0 当作“无计数”做其他逻辑（例如判断是否首次请求、是否达到阈值做降级），语义就反了。更关键的是：当 Redis 配置了但运行时故障时，zadd_and_count 返回 0 会让所有请求都“未超限”，限流完全失效——这与模块文档声称的“跨进程限流”目标相悖，且没有任何告警升级。这是一个真实的降级语义缺陷：限流器在缓存故障时静默失效，攻击者可通过打挂 Redis 绕过限流。
  - 争议对手：8a6b0fd4d717, e3cf0fb18c3c, f90afb31b3cd
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:128-137 zadd_and_count 的 member 参数若重复（同一请求重试），zadd 会覆盖分数而非新增，导致计数偏小（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-137`
  - 依据：zadd 对已存在的 member 是更新分数而非新增成员。若调用方用固定 member（如 user_id 或 task_id）做限流，同一用户窗口内多次请求只会保留一条记录，zcard 永远返回 1，限流形同虚设。文档说“加入本次”暗示每次请求应新增成员，但 member 由调用方传入，若调用方传固定值就会失效。这是接口契约模糊导致的真实缺陷：方法名和文档暗示计数语义，但实现依赖调用方保证 member 唯一。
  - 争议对手：5280ced115e4, fdb212663f5e

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：12｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 43，估计总体 43.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

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
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 3 | 1 | 3 | 3 | 0 | 0 | 2 | 1 |
| `app/infrastructure/security` | 2 | 0 | 3 | 3 | 0 | 3 | 0 | 1 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
