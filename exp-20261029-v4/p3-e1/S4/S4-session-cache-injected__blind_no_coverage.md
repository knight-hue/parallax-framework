# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 27 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：27
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：58 个节点 / 80 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 27 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/__init__.py:1-2 六个包初始化文件均为空（不是缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/__init__.py:1-2`
  - 依据：app/__init__.py、app/domain/buyer/__init__.py、app/domain/session/__init__.py、app/domain/session/ports/__init__.py、app/infrastructure/__init__.py 仅含编码声明，用于把目录标记为常规包并统一源码编码。文件中没有可执行语句，不存在导入副作用、循环导入或命名导出丢失等可触发的问题；ports 包未在此处 re-export SessionStore 只是风格取向，调用方仍可从 app.domain.session.ports.session_store 导入。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:119-121 _rank_by_relevance 未复原原始相对顺序，直接返回相关性排序结果（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:119-121`
  - 依据：注释明确写着「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，同文件的 `_latest_first` 也确实是「取 top_k 后再按原始顺序过滤」的实现（`[p for p in likes if p in newest]`）。但这里 `picked` 就是按 `(-score, index)` 降序排好的列表，被原样返回，注释描述的行为根本没有实现。效果是：开启相关性排序后，注入块的 like 行序随本轮 query 的分数排序变化，与注释声明的去抖动目的相反，也让「保持稳定顺序」的对外承诺不成立。只影响顺序、不影响选出集合，故定为 low。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:126-127 _latest_first 用 `p in newest` 做成员判定，依赖 BuyerPreference 的 __eq__（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:126-127`
  - 依据：这里不复用索引而用相等性过滤：若 BuyerPreference 是默认 dataclass（按字段 __eq__），两条字段完全相同（含 created_at 相同）的偏好会同时命中，使返回长度可能大于 top_k；若未定义 __eq__ 则退化为身份比较，行为正确。由于 select 最后还有 `[:top_k]` 截断，最坏情况只是多算后又被切掉，注入内容不会出错，且真实数据里 created_at 相同的重复偏好极少见，故不认定为缺陷；如果后续改为不去重直接注入，此处值得改成按下标过滤。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:85-92 dislike 被 top_k 截断：违反「黑名单全量保留」的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:85-92`
  - 依据：模块 docstring 与 select 的注释都声明 dislike 全量保留、不参与 top_k 截断，但最后一行把 `dislikes + selected_likes` 整体切 `[:top_k]`。两个后果：(1) 当 dislikes 条数 >= top_k 时，排在后面的 dislike 被直接丢弃，黑名单失效，用户明确拒绝的属性（如「不要塑料材质」）会重新进入注入块；(2) 选择 likes 时预算仍按完整的 top_k 计算（第 85-90 行），没有扣除 dislikes 已占用的名额，所以 dislikes>0 时 likes 只能注入 top_k-len(dislikes) 条，而被丢的是「原始列表位置靠后」的那几条——`_latest_first` 返回的是原始相对顺序、`len(likes) <= top_k` 分支连排序都不做，因此被丢弃的 like 既不是最不相关的，也不是最旧的，纯属位置偶然。这与「只有 like 走相关性排序，dislike 全量保留」的设计直接矛盾。
- **[error_handling/low]** [error_handling] app/domain/buyer/preference.py:20-23 BuyerPreference 不校验 buyer_id，空字符串会被当作合法主体键（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:20-23`
  - 依据：__post_init__ 强校验了 kind 与 statement，但没有校验 buyer_id 非空，同一仓的 ConversationTurn 则校验了 session_id。表面上是不一致；但 buyer_id 来源于已认证的会话上下文，本文件只给出端口定义、具体存储实现不在审查范围内，无法证明存在会把空 buyer_id 写进去的真实路径，因此按“无法引用代码证明错误行为”处理，记为非缺陷。若后续发现 store 实现直接以 buyer_id 作为文件名/主键，则空值会导致所有匿名偏好塌缩到同一条记录，那时应升级为缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:14-17 值对象未在构造期校验不变量，直接 Money(...) 可绕过 of() 生成负金额/非法币种（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:14-17`
  - 依据：文档字符串声明不变量「amount_in_minor_units 必须为非负整数；currency 必须是受支持的 ISO-4217 三位代码」，但校验只写在静态工厂 of() 里，dataclass 没有 __post_init__。该类是公开的冻结数据类，任何代码都可以 `Money(-100, "XXX")` 直接构造并成功，随后 to_major_units()/__str__/add()/multiply() 都会基于这个非法值继续运算（例如 Money(-100,"USD").add(Money(50,"USD")) 得到 -50 分），使「价格是核心不变量」的保证完全失效。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:28-30 from_major_units 依赖浮点乘法 + round()，半分边界会丢失/多加 1 分（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:28-30`
  - 依据：major 是 float，`major * 100` 会先产生二进制浮点误差，再用内置 round()（银行家舍入，round-half-to-even）取整。对 2.675、1.005、8.035 这类十进制值，乘 100 后得到的是 267.49999999999994 / 100.49999999999999 / 803.4999999999999，round 后分别变成 267 / 100 / 803，即少 1 分；而恰好落在 x.5 的值（如 0.005 → round(0.5)）会被舍成偶数 0。文件头声称「避免浮点误差」，但入口函数本身引入浮点误差，金额被静默改写。
- **[error_handling/low]** [error_handling] app/domain/catalog/money.py:30-30 from_major_units 对 NaN/inf/负数的处理 —— 经确认不会静默产生错误金额（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-30`
  - 依据：round(float('nan')) 会抛 ValueError、round(float('inf')) 会抛 OverflowError，负数经 round 后交给 Money.of() 会因 amount < 0 抛 ValueError，都不会静默写入非法金额（inf 抛的是 OverflowError 而非 ValueError，但仍是显式失败，不构成数据损坏）。因此这里不认定为缺陷；如需统一异常类型可另行处理。
- **[logic/low]** [logic] app/domain/catalog/money.py:32-39 add()/multiply() 用裸构造器而非 of() —— 经确认不是缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:32-39`
  - 依据：表面上 add()/multiply() 绕过了 of() 的校验，但两个方法都只对已通过 of() 的实例做非负整数加法和「非负整数 quantity 乘法」（line 37 已排除 bool 和负数），结果必然仍是非负整数，currency 也沿用原实例的受支持币种，不变量不会被破坏；重复调用 of() 只会带来无效开销。真正的不变量漏洞在「外部直接构造 Money」，已在另一条 finding 中单独记录。
- **[logic/medium]** [logic] app/domain/catalog/money.py:41-45 JPY 等零小数位币种被硬编码按 100 换算，金额放大 100 倍且展示带两位小数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:41-45`
  - 依据：SUPPORTED_CURRENCIES 明确包含 JPY（ISO-4217 中 JPY 小数位为 0，最小单位就是 1 日元），但 to_major_units/__str__ 对所有币种无条件除以 100 并格式化为两位小数，配合 from_major_units 的 `major * 100`，Money.from_major_units(1000, "JPY") 会得到 100000 个最小单位，与真实的 1000 日元相差 100 倍；to_major_units() 返回 1000.0、str() 输出 "1000.00 JPY"，对零小数位币种是错误展示。代码注释自认「demo 暂统一」，但对外暴露的仍然是错误金额，一旦与支付网关或账务对账就会产生 100 倍差异。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:37-39 ProductVectorIndex.upsert_products 不校验 products 与 embeddings 等长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:37-39`
  - 依据：端口方法只声明契约，不校验 `len(products) == len(embeddings)`。这是抽象端口，实现方（Qdrant 适配器）与调用方（UseCase 的 embed → upsert 流程）负责保证一一对应；同文件 `Reranker.rerank` 的 docstring 也把「等长/等长返回」写成契约而非运行时校验。端口层加校验会和具体实现的校验重复，因此判定为不是缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:26-30 Sku 是可变 dataclass，stock 的只读约束与 __post_init__ 校验可被属性赋值绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:26-30`
  - 依据：`Sku` 未使用 frozen=True，`sku.stock = -1` 可以绕过 __post_init__ 的非负校验，与注释里「stock 是只读参考数据」的说法在语言层面并不吻合。但审查范围内没有任何代码对已构造的 Sku 做属性赋值：stock 只在从目录数据构造时填充（首播库存走 StockRepository.seed），真正的扣减/回补在 StockRepository 的原子操作里。__post_init__ 需要防的是「脏目录数据构造出负库存」这个真实入口，它已覆盖。因此这属于潜在硬化点（可考虑 frozen 或 property），不是当前代码的缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:26-33 ConversationTurn 文档声称有 turn_index 字段，但数据类中并不存在该字段（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:26-33`
  - 依据：类的 docstring 写明“turn_index 由存储层按会话自增，写入时可留空”，暗示 turn_index 是可选字段；ConversationStore.list_turns 的契约也写明“按 turn_index 升序返回该会话的对话流水”。但字段列表里只有 session_id/buyer_id/role/content/model/latency_ms/created_at，没有任何 turn_index 字段。后果有二：(1) 照文档写入 turn_index（无论在有值还是“留空”的语义下）都会直接抛 TypeError: unexpected keyword argument；(2) list_turns 返回的对象上不存在 turn_index，调用方若按文档做 `turn.turn_index` 排序/翻页/去重会 AttributeError，且冻结数据类无法事后补写，排序信息只能存活在存储层内部，跨实现（JSON 文件 ↔ OpenSearch/PG）回放顺序无法被调用方校验。
- **[error_handling/medium]** [error_handling] app/domain/session/ports/conversation_store.py:36-38 ConversationTurn.role 未按已定义的 VALID_ROLES 校验，任意角色字符串都会被接受（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-38`
  - 依据：模块顶部声明了 VALID_ROLES = ("buyer", "agent")（第 17 行），显然是为 role 校验准备的；但 ConversationTurn.__post_init__ 只校验了 session_id，完全没有用到 VALID_ROLES。ConversationTurn 是写入对话流水的持久化结构，上层 append_turn 的实现在给定文件中不可见，因此只要构造时传入 role="assistant"/"system"/拼写错误（例如 "Buyer"、"agent "），就会静默通过校验并被落库，之后按 role 过滤/回放的分析与客服排查逻辑（以及文档承诺的 buyer/agent 二分）就会出现漏数据或分组错乱，且发现时脏数据已经写入。对比同仓 app/domain/buyer/preference.py 中 BuyerPreference 对 kind 用 VALID_KINDS 做了强校验，这里属于同类校验的遗漏而非设计选择。
- **[error_handling/low]** [error_handling] app/domain/session/ports/conversation_store.py:41-48 ConversationEventRecord 未校验 session_id/type，与 ConversationTurn 的校验强度不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:41-48`
  - 依据：ConversationTurn 有 __post_init__ 校验 session_id，而 ConversationEventRecord 没有任何 __post_init__，空 session_id 或空 type 的事件都能构造出来；理论上会写出无法按 session 检索的孤儿事件。但这里没有像 VALID_ROLES 那样的常量表明校验意图，事件由一轮结束后的编排代码一次性构造（session_id 来自当前会话），且具体存储实现是否校验不可见，无法证明会产生真实错误行为，故记为非缺陷而非缺陷。
- **[logic/low]** [logic] app/domain/session/ports/session_store.py:20-27 SessionStore 抽象方法仅有 docstring 作为方法体（不是缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:20-27`
  - 依据：save/load 被 @abstractmethod 装饰，方法体只有 docstring，因此隐式返回 None。这是 Python 中声明纯接口的惯用写法：SessionStore 无法被直接实例化（ABCMeta 会在实例化时抛 TypeError），任何具体子类只要未覆写这两个方法也同样无法实例化，所以不会出现“调用抽象方法拿到 None”的运行期路径。save 声明返回 None，与隐式返回一致；load 声明 Optional[str]，抽象层不实现也不构成契约违背，因为契约由覆写方承担。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:71-77 inner.embed_batch 返回数量不足时 zip 静默截断，缺失位置的向量退化为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:71-77`
  - 依据：`zip(pending, fresh)` 在 fresh 长度小于 pending 时按短的一方截断，未匹配到的 results[index] 保持 None，最后由 `vector or []` 转成空列表返回给调用方。空向量既不会被写入缓存也不会报错，会静默流到下游（余弦相似度恒 0，或写入向量库时报维度错误），丢失了“批量返回条数与请求不一致”这一异常信号。应该做长度校验并抛错，而不是用 `or []` 掩盖。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:30-32 embedding 缓存 key 未包含 model，换模型后仍复用旧模型的向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:30-32`
  - 依据：模块 docstring 声明“key 用 sha256(model + text)”，构造函数也把 model 存进了 self._model，但 _key 只对 text 做哈希，self._model 全程未被使用。换 embedding 模型（甚至只是改模型版本/维度）后，旧模型的向量会在 7 天 TTL 内被当作新模型的向量直接返回；维度不同会让下游余弦相似度恒为 0（语义缓存永久不命中），维度相同则悄悄返回语义不兼容的向量。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:121-127 zadd_and_count 用 member 作为 ZSET 成员，同一 member 重复调用只更新 score 不会累加，滑窗计数恒为 1（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:121-127`
  - 依据：ZADD 对相同 member 是「覆盖 score」而非新增，因此若调用方把限流主体（如 IP、user_id）直接当 member 传入，zcard 永远返回 1，限流器永远不会触发。但这属于调用方契约问题：该方法签名与文档约定的是「加入本次」，正确用法是每次请求传唯一 member（如 f'{now}-{uuid4}'）。在本文件范围内该实现是自洽的（MULTI/EXEC 原子、results[2] 正是 zcard、expire 时长覆盖窗口），无法确认仓库内调用方是否误用，故不判定为本文件的缺陷。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/redis_cache.py:105-111 set_if_absent 在 Redis 异常时返回 True，调用方无法区分「已抢占」与「降级放行」，配合 delete 释放会破坏分布式锁互斥（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:105-111`
  - 依据：该方法文档明确声明用于「幂等键与分布式锁」。当 _client 为 None 或 set(nx=True) 抛异常时它一律返回 True，调用方拿到 True 会认为自己持有了锁/幂等键，但 Redis 里对应的 key 可能根本不存在，甚至可能正被另一个进程真实持有（例如本次 SETNX 因网络超时抛错、而旧持有者的锁尚未过期）。由于本类没有提供「带 token 的比较删除」原语，调用方在 finally 中只能无条件调用 delete(key)；于是一个「降级放行」的进程在释放时会删掉另一个进程真实持有的锁，第三个进程即可同时进入临界区，互斥被真正打破，而不只是退化。对幂等键来说，后果是多一次重复执行（可接受）；对锁来说，后果是并发写同一资源。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:62-67 get_json 解析失败时直接删除 key，若该 key 由 get_raw/set_if_absent 写入的裸字符串触发，会销毁幂等键（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:62-67`
  - 依据：脏值删除是文档写明的设计（「脏值当未命中，顺手删掉」），并且类里专门提供了 get_raw 并注释说明幂等键不能走 get_json，职责划分是清晰的。只有当调用方把裸字符串键误传给 get_json 时才会真的破坏幂等语义，属于调用方误用，而非本方法实现错误；对写入方本身就是 JSON 的键，删除脏值是正确的自愈行为。
- **[resource_leak/low]** [resource_leak] app/infrastructure/cache/redis_cache.py:135-138 close() 调用 aclose() 并用 except Exception: pass 吞掉一切异常，旧版 redis-py 下连接池不会被断开（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:135-138`
  - 依据：redis.asyncio.Redis.aclose() 只在 redis-py >= 5.0.1 存在；在 4.2~4.6（redis.asyncio 已可用、from_url 可用，因此本类初始化不会报错）上会抛 AttributeError，而这里是裸 except Exception: pass，既没有日志也没有回退到 close()/connection_pool.disconnect()，结果是关闭流程静默无效：连接池不释放，进程退出时出现未关闭连接/挂起任务的告警，长生命周期测试或热重载场景会累积连接。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:165-167 桶裁剪取前 N 条而非最近 N 条，写满 30 条后新条目永远写不进去（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:165-167`
  - 依据：新条目是 append 到列表末尾的，而 `entries[:_BUCKET_LIMIT]` 保留的是列表前 30 个元素、丢弃末尾。注释写的是“保留的最近条数”，实际行为相反：桶一旦达到 30 条，本次 append 的新条目位于索引 30 且被切片丢弃，缓存从此只保留最旧的 30 条直到 TTL 到期（24h），语义缓存对新问句完全失效，而旧回复持续被复用，进一步放大陈旧回复问题。正确写法是 `entries[-_BUCKET_LIMIT:]`。叠加 remember 不去重（相同归一化问句会重复 append），30 条更容易被同义重复问句占满。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/semantic_cache.py:163-167 remember 的读-改-写无并发保护，并发写会丢条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:163-167`
  - 依据：remember 先 _load_entries 读出整个列表，在进程内 append 后再 set_json 覆盖写回，整个序列没有任何 CAS/WATCH/分布式锁。同一 buyer 的两个并发请求（或同一进程内两个并发协程在 await 点交错）会互相覆盖：后写的 set_json 用基于旧快照的列表覆盖前一次写入，造成条目丢失；与 _BUCKET_LIMIT 的前缀裁剪问题叠加时表现更明显。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:101-113 _bucket_key 丢弃了 scope 偏好指纹，撤回偏好后仍会命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:101-113`
  - 依据：方法签名接收 scope，docstring 明确声明“桶 key = namespace + buyer_id + scope”，并解释如果不带偏好指纹，买家撤回“不要塑料”后旧回复会继续复用、向用户断言一条已删除的偏好。但 digest 只拼了 self._namespace 和 buyer_id，scope 完全没有参与哈希；lookup/remember 都把 scope 一路传进来却在 _bucket_key 里被静默丢弃，偏好变更不会使桶失效。这是文档点名的“实测踩过”场景，属于真实功能失效，而非风格问题。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:124-128 lookup 完全忽略 has_history，多轮会话内仍会命中缓存回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:124-128`
  - 依据：模块 docstring 的安全边界第 3 条写明“会话内已有多轮上下文时不命中”，remember 里也确实用 `has_history` 做了拦截，但 lookup 的签名收了 has_history 却在函数体内从未使用，只判断 enabled 与 is_cacheable_query。于是同一句在无上下文的会话里被记住后，在有上下文的会话里仍可命中，给出与当前上下文无关的答复；remember 与 lookup 的判定不对称，说明这是漏写而不是设计。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/content_filter.py:22-32 content_filter 的正则内联 (?i) 位于模式起始，repeat 编译不会抛 bad inline flags（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-32`
  - 依据：曾怀疑 `re.compile(pattern)` 会因内联标志 `(?i)` 不在表达式开头而抛 `re.error: global flags not at the start`。实际每条模式都以 `(?i)` 作为整个 pattern 的第一个 token，符合 Python 对全局内联标志必须位于模式起始的要求，`_compiled` 构建与后续 `subn` 均正常；这不是缺陷（真正会报错的是把 `(?i)` 放在 `(` 之后或中间）。

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
| `00e2b01edb94` | 1 | 1 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 1 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 3 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 0 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 0 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |

矩阵填充率 21%（单元格值 = 独立 Agent 数）
