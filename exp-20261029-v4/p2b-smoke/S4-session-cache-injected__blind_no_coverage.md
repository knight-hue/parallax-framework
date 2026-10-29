# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 23 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：25
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：57 个节点 / 80 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 24 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-95 return (dislikes + selected_likes)[:top_k] 违反「dislike 全量保留、不参与 top_k 截断」这一安全约定（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-95`
  - 依据：模块 docstring 明确声明：dislike（忌口/黑名单）必须「全量保留，不参与 top_k 截断」，并说明漏掉黑名单是安全问题（会推出用户明确拒绝的东西）。但 select() 先把 dislikes 与选好的 selected_likes 拼起来，再统一 `[:top_k]`，于是截断同样作用在 dislikes 上：当 len(dislikes) >= top_k 时，排在前面的只保留 top_k 条 dislike，其余黑名单被直接丢弃；len(dislikes) > top_k 时更严重，最后几条忌口永远不会注入。此外这段截断还有第二个后果：dislikes 占用了预算时，_latest_first 返回的是「最新 top_k 条中按原始顺序过滤后」的结果，截断会优先切掉末尾，也就是优先切掉其中最新的偏好——例如 likes 顺序为旧→新 L1..L10、top_k=3、dislikes=1 时，newest=[L10,L9,L8]，按原序过滤得到 [L8,L9,L10]，拼接后取前 3 条为 [D,L8,L9]，最新的 L10 反而被丢掉，与「按时间倒序」的退化语义相反。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:36-51 PreferenceStore.append 的“同 buyer 同 statement 去重”与 delete 的“like/dislike 会一并清除”互相矛盾，去重键不确定（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:36-51`
  - 依据：append 的契约写的是“同 buyer 同 statement 幂等去重”，去重键不含 kind；但 delete 的契约明确写“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这条只有在 (buyer, statement, kind) 三元组共存时才有意义。两段契约隐含的去重键不同：(a) 若实现按 (buyer, statement) 去重，则同一 statement 的 like 与 dislike 永远不可能共存，delete 的说明描述的是不可达状态，且先 append(like, "不要塑料") 再 append(dislike, "不要塑料") 是被覆盖还是被忽略，契约未定义——用户明确改口（从喜欢变讨厌）时行为不确定；(b) 若实现按 (buyer, kind, statement) 去重，则 append 的“同 buyer 同 statement 去重”被违反，重复追加相同 kind 的同一句会产生两条记录。由于这是端口契约、infrastructure 会另写 JSON/OpenSearch/PG 实现，两种理解会落到不同实现上，导致同一操作在不同存储后端语义不同，属于真实的可复现歧义而非文风问题。
- **[logic/low]** [logic] app/domain/buyer/preference.py:30-31 frozen dataclass 的 __post_init__ 用 object.__setattr__ 写入默认 created_at —— 这是官方推荐写法，不是缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：在 dataclass(frozen=True) 中，实例的常规属性赋值会被生成的 __setattr__ 拦下并抛 FrozenInstanceError，因此在 __post_init__ 里设置默认值必须绕过它；object.__setattr__(self, ...) 正是官方文档给出的做法，能正确写入且不会破坏后续的不可变性（设置完成后外部再赋值仍会抛错）。这里仅当调用方没有传 created_at（默认空串 ""）时才触发，且写入的字段全部是 str，不影响 __eq__/__hash__ 的一致性。已确认安全。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:30-30 from_major_units 在浮点乘法之后取整，导致部分金额少 1 个最小单位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-30`
  - 依据：major 是 float，先执行 major * 100 再 round 会受二进制浮点表示误差影响。例如 2.675 在二进制中略小于 2.675，乘 100 得到 267.49999999999994，round 后为 267，而按 round(267.5) 的半偶舍入应为 268。该文件的目标是避免浮点误差，但这个转换入口仍会把常见三位小数金额算错 1 分。
- **[logic/medium]** [logic] app/domain/catalog/money.py:14-17 Money 的公开 dataclass 构造函数绕过非负金额和币种校验（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:14-17`
  - 依据：类文档声明 amount_in_minor_units 必须为非负整数、currency 必须是受支持币种，但 @dataclass(frozen=True) 只阻止字段重新赋值，不会校验构造参数，也没有 __post_init__。校验只存在于 Money.of 中，而生成的 __init__ 是公开的，因此 Money(-1, "XXX") 可以直接创建非法值。add/multiply 也直接调用 Money(...) 而不是 of，非法实例一旦通过直接构造进入系统就可能继续传播。
- **[logic/low]** [logic] app/domain/catalog/sku.py:19-24 Sku.stock 声明为「只读」但 dataclass 非 frozen，字段实际可被改写（reviewed，判定不构成缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:19-24`
  - 依据：注释与类 docstring 都强调 stock 是初始库存、只读参考数据，真正的扣减/回补走 StockRepository 的原子操作。代码里 @dataclass 未加 frozen=True，也没有把 stock 设为 read-only property，因此调用方确实可以 `sku.stock = 0` 之类的赋值，与「只读」表述不符。但这只是约束未强制执行：改写该字段不会影响 StockRepository 中的真实库存，也不会重新引入「读-判断-写」超卖（本类刻意没有 deduct_stock/restore_stock），所以判定为不是行为缺陷；只有当下游把 sku.stock 当作可用库存的权威来源时才构成隐患。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:26-27 ConversationTurn 文档提到的 turn_index 字段并不存在 —— 仅为契约描述冗余，当前不产生错误行为（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:26-27`
  - 依据：类文档写“turn_index 由存储层按会话自增，写入时可留空”，list_turns 也承诺“按 turn_index 升序返回”，但数据类里没有 turn_index 字段，看似契约与结构不一致。确认其不构成运行时缺陷：created_at 使用 _now_iso()（datetime.now(timezone.utc).isoformat()，含微秒），同一会话内升序可依据 created_at 稳定还原；抽象端口本身不含任何读取 turn_index 的代码，实现方只要保证返回列表有序即可，缺失的字段只是多余的说明，不会导致异常或错误数据。若后续确有调用方需要按索引去重/断点续拉，再补字段与排序键即可。
- **[error_handling/low]** [error_handling] app/domain/session/ports/conversation_store.py:31-39 ConversationTurn 未校验 role，模块级 VALID_ROLES 完全未被使用，非法角色可静默落库（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:31-39`
  - 依据：模块第 18 行定义了 VALID_ROLES = ("buyer", "agent") 并且在 role 字段注释中重申了 buyer / agent 的取值域，但 __post_init__ 只校验 session_id，没有任何地方引用 VALID_ROLES（该常量在整个文件中是死代码）。这与同仓库 app/domain/buyer/preference.py 中 BuyerPreference.__post_init__ 对 kind 使用 VALID_KINDS 做校验的写法形成明显反差，可判定为遗漏而非有意设计。后果：role="assistant"/"Buyer"/"" 等非法值不会抛错，会被当作合法一轮对话写入持久化流水；而本类的定位是“业务可读的对话流水，供事后追溯、客服排查”，下游按 role 过滤（如只取 agent 回复做质检或飞轮回放）时会漏数据或把非法角色当成第三类角色，且错误在写入时不可见、事后难以追溯。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:42-48 frozen=True 的 ConversationEventRecord 内嵌可变 dict payload：既破坏不可变语义，又使实例不可哈希（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:42-48`
  - 依据：dataclass(frozen=True) 只禁用属性重新赋值，不会深拷贝字段值；payload: dict[str, Any] 以引用方式保存在“不可变”值对象里，调用方在构造后继续修改原 dict 会同步改变已创建的记录（事件在 append_events 中被批量异步写入，写入前的窗口足够长，容易出现落库内容与构造时刻不一致）。另外 frozen=True 且 eq=True 会让 dataclass 生成 __hash__（基于全部字段），而 dict 不可哈希，因此对 ConversationEventRecord 实例求 hash 会抛 TypeError: unhashable type: 'dict'——这与 frozen 值对象“可安全共享/作为 set 与 dict key”的常规预期相反，调用方一旦把它放进 set 去重或用于 lru_cache 就会在运行时崩溃。同文件 ConversationTurn 的字段全是 str/int，无此问题，说明此处是字段类型选择导致的特例。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/session_store.py:19-27 抽象方法体仅有 docstring，隐式返回 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:19-27`
  - 依据：SessionStore 继承 ABC，两个方法都带 @abstractmethod，因此无法直接实例化，未实现子类会在实例化时抛 TypeError，调用不到仅有 docstring 的方法体。子类实现若使用 super().save(...)/super().load(...) 会静默得到 None，但这属于子类误用而非端口本身的缺陷，且当前仓库中没有任何子类或调用方引用该端口（其余 5 个文件均为空 __init__.py），无法构成可复现的错误行为。
- **[logic/low]** [logic] app/domain/session/ports/session_store.py:17-27 端口未声明删除/列举等操作，可能是接口不完整（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-27`
  - 依据：端口只有 save/load 两个方法，若上层 SessionRegistry 需要清理过期快照则接口不足。但给定文件列表中没有任何调用方代码可作为依据，docstring 也只描述“存取快照”，因此无法证明缺失方法是缺陷，属于设计取舍而非可引用代码证明的错误。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:30-32 embedding 缓存 key 未包含模型名，换模型后会读到别的模型的向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:30-32`
  - 依据：文件头注释明确写「key 用 sha256(model + text)」，__init__ 也接收并保存了 self._model，但 _key() 只对 text 做 sha256，模型名完全没参与。只要同一个 RedisCache 被两个不同的 embedding 模型（模型升级灰度、A/B、多租户）共用，模型 B 请求同一段文本时会命中模型 A 写入的向量：inner.embed_batch 不会被调用，hits 也会被错误累加，返回的是错误维度/错误语义的向量。embedding 是「同模型同文本才必然同向量」的纯函数，缺了模型维度这个前提就不成立。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:105-111 set_if_absent 在 Redis 异常时返回 True，故障期间幂等/锁保护被静默关闭（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:105-111`
  - 依据：初看像缺陷：Redis 不可用或 SETNX 抛异常时返回 True，会让调用方误以为自己抢到了幂等键/分布式锁，从而在故障窗口内重复执行任务。但这是类 docstring 与该方法 docstring 明确声明的设计取舍（'宁可退化成没有幂等保护，也不能因缓存故障拒绝服务'），且与 get_json 返回 None、zadd_and_count 返回 0 的降级策略一致；返回 False 反而会造成全站请求被拒。因此判定为有意行为而非缺陷，风险应由调用方（幂等键写入后仍需业务侧唯一约束兜底）承担。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:128-130 zadd_and_count 失败时返回 0，限流在 Redis 故障时完全失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-130`
  - 依据：异常与 disabled 分支都返回 0（窗口内计数为空），对'count > limit 则拒绝'的调用方意味着放行，即 Redis 挂掉时跨进程限流整体失效（fail-open）。这与方法 docstring '按不限流处理' 以及类级'缓存故障不能拖垮主链路'的定位一致，是显式声明过的可用性优先取舍；把它改成 fail-closed 会因 Redis 抖动导致全量请求被限流，属于设计选择而非实现缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:62-67 get_json 在 JSON 解析失败时删除键，可能误删同键上的裸字符串值（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:62-67`
  - 依据：乍看有风险：若某个键（例如 set_if_absent 写入的裸 task_id 幂等键）被误用 get_json 读取，json.loads 抛 ValueError 会走到 `await self.delete(key)`，把幂等键直接删掉，破坏幂等语义。但本文件已专门提供 get_raw 并在其 docstring 里说明『幂等键存裸 task_id，不能走 get_json』，两条读取路径职责清晰；对 set_json 写入的值来说 json.dumps 保证内容总是合法 JSON，解析失败只可能来自外部污染，删除属于自愈。因此在本文件范围内不构成缺陷，风险来自调用方误用。
- **[resource_leak/low]** [resource_leak] app/infrastructure/cache/redis_cache.py:132-138 close() 吞掉所有异常，aclose 不存在或失败时连接池不会被关闭（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:132-138`
  - 依据：close() 用 `except Exception: pass` 包住 `await self._client.aclose()`。这个类通过 `redis.asyncio.from_url` 构造客户端（代码中只要求 redis-py>=4.2 即可 import），而 `aclose()` 是 redis-py 5.0 才加入 Async Redis 的方法；在 4.x 上这里会抛 AttributeError，被静默吞掉，连接池/异步连接永远不会被关闭，进程退出或热重载时会留下未关闭的 socket（asyncio 的 'Unclosed client session' 警告与句柄泄漏）。即使在 5.x 上，aclose 因网络错误抛异常也会被吞掉，池仍然处于打开状态且没有任何日志，运维无法察觉。异常旁路的整体设计对其他缓存读写是合理的（降级为未命中），但 close 本身就是清理路径，静默失败反而破坏清理语义。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:164-167 桶内裁剪保留最旧 30 条，新写入条目被静默丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:164-167`
  - 依据：entries 是在末尾 append 的，写回时却取 `entries[:_BUCKET_LIMIT]`（前 30 条）。注释写的是「保留最近的条数」，但实际语义是保留最早的 30 条：桶满 30 条之后，每次 remember 都只是把 30 条旧条目重新 set_json（顺带把 TTL 续到 24h），新问句永远进不了缓存。表现为缓存停止学习、长期只服务最早的一批问句，而且旧条目因为 TTL 被反复续期不会自然过期。正确写法应为 `entries[-_BUCKET_LIMIT:]`。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/semantic_cache.py:164-167 remember 的读-改-写无同步，并发写入互相覆盖（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:164-167`
  - 依据：remember 先 _load_entries 读到快照，再在本地 append，最后整桶 set_json 覆盖写。同一 buyer 的两个并发请求（或多进程 worker）交错执行时，后写的一方会用自己的快照覆盖前一方刚写入的条目，造成丢失更新：缓存条目随机丢失，命中率不稳定，且没有日志可查。由于没有 compare-and-set / 追加型结构，这个竞态是结构性的。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:110-113 语义缓存桶 key 丢弃 scope，偏好指纹失效，撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:110-113`
  - 依据：_bucket_key 的函数名/文档字符串声明 key = namespace + buyer_id + scope，且 _load_entries 与 remember 都把 scope 透传进来，但实际摘要只对 f"{namespace}\n{buyer_id}" 求值，scope 参数被完全忽略。于是「偏好前」和「偏好后」（尤其是撤回偏好后）落进同一个桶：买家删掉“不要塑料”的偏好后再问一句语义相近的问题，_load_entries 读到的仍是撤回前写入的 entries，lookup 以 ≥0.95 相似度命中，返回的那条回复里还写着已被删除的偏好。这正是注释里声称「实测踩过、必须避免」的场景，安全边界 2b 实际没有生效。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:124-131 lookup 完全忽略 has_history，多轮会话仍会命中跨会话缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:124-131`
  - 依据：lookup 的签名接收 has_history，模块文档第 3 条也明确要求「会话内已有多轮上下文时不命中」，remember 里确实写了 `has_history` 的短路判断，但 lookup 的前置判断只有 `not self._enabled or not is_cacheable_query(query)`，has_history 参数在函数体内从未被读取。结果是：一个依赖上下文的问句只要没被 _UNSAFE_RE 命中（例如「哪款更便宜一些」「推荐个替代品」），在多轮会话中依然会命中上一轮的缓存回复，给出与当前上下文无关的答案；这也让 remember 的 has_history 保护形同虚设（入口不挡，出口也不挡）。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:58-66 余弦相似度对维度不一致直接返回 0.0：是有意的未命中，不是缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:58-66`
  - 依据：_cosine 在 len(left) != len(right) 时返回 0.0，看起来像吞掉了错误，但语义缓存里「不可比 = 不命中」正是期望行为（阈值 0.95），返回 0.0 会让该条目 fail-safe 地不进 best；长度不匹配还可能来自旧版本向量残留，返回 0.0 比抛异常更安全，主链路不会被缓存数据打断。分母为 0 也同样返回 0.0，避免了 ZeroDivisionError。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:60-65 subn 的替换串是字面量占位符，不存在反斜杠模板注入问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:60-65`
  - 依据：re.subn 的 repl 会被当成模板解析，若占位符里含 \\1、\\g<name> 或反斜杠就会抛错或被改写；但 FILTERED_PLACEHOLDER = "[内容已过滤：疑似注入]"（output_guard 的 REDACTED = "[已脱敏]"）是纯字面量，不含反斜杠，也不含任何会匹配后续危险模式的片段，因此多模式顺序替换不会互相污染，也不会因 repl 解析失败而抛异常。
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:43-43 内部工具名正则的 \b 边界在相邻中文字符时失效，中文回复可绕过脱敏（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-43`
  - 依据：工具名模式是 `\b(?:...)\b`。Python re 的 \w 默认按 Unicode 匹配，汉字属于 \w，因此汉字与工具名首字符之间不存在单词边界。正常的中文回复里工具名几乎总是紧贴汉字出现（如「我已调用web_search_tool查到」「走的是cancel_order_tool」），此时开头 \b 不成立，整条规则不匹配，内部工具名原样下发，L4 这道闸被绕过；只有工具名前后是空格/英文标点（非 \w）时才会脱敏。这是把「买家侧无需知道」的内部实现信息泄露出去，与模块目标直接冲突。

## 争议（需裁决）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:122-124 _rank_by_relevance 声称「回到原始相对顺序输出」，实际返回按相似度排序的顺序（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:122-124`
  - 依据：scored 已按 (-相似度, index) 排序，picked 是 scored[:top_k] 的相似度降序结果；随后注释写着「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，但 return picked 直接返回了排序后的顺序，没有像 _latest_first 那样做 `[p for p in likes if p in newest]` 的还原。后果是：同类 likes 在注入块中的行序会随每轮 query 变化而重排，注释里想要避免的「行序抖动导致重复注入 / prompt 前缀不稳定」问题实际仍然存在，且与 _latest_first 分支的输出顺序语义不一致（同一组被选中的偏好，两个分支输出顺序不同）。
  - 争议对手：2e5486b806b8

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
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 2 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 1 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 0 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 18%（单元格值 = 独立 Agent 数）
