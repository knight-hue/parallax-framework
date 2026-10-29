# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 21 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`budget_exhausted`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：23
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：55 个节点 / 76 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 22 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:83-85 top_k <= 0 时提前返回空列表，忌口/黑名单也被一并丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:83-85`
  - 依据：代码在拆分 dislikes / likes 之前就 `return []`，因此预算为 0 或负数时所有 dislike 都不会被注入。这与模块文档宣称的「dislike 全量保留，不参与 top_k 截断」这一安全底线冲突：只要上游误传 top_k=0（例如配置缺失默认 0、或按剩余 token 估算为 0），黑名单就会静默失效，而调用方拿不到任何信号。是否要保留一个「0 预算 = 什么都不注入」的产品语义是设计选择，但当前写法与文档承诺直接矛盾，且没有日志提示。
- **[error_handling/medium]** [error_handling] app/application/memory/preference_selector.py:111-118 降级兜底只包住 embedding 调用，打分阶段的异常会直接抛出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:111-118`
  - 依据：try/except 只覆盖两个 await（embed_batch / embed），而后续的向量校验与打分在 try 之外：`not query_vector` 对 numpy 数组会抛 ValueError（多维数组真值不明确，而向量接口返回 ndarray 很常见）；`_cosine(vector, query_vector)` 在 embed_batch 返回含 None 的列表时 `len(None)` 会抛 TypeError；`zip(vectors, likes)` 元素不是序列时同样会炸。这些异常都不会触发文档承诺的「任何异常都降级为按时间倒序，不能因为选偏好把对话搞挂」，而是把整个 select（进而整轮对话）打断。仅 `len(vectors) != len(likes)` 这一种畸形返回被处理了。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:65-68 _relevance_enabled 已保证 embedder 非 None，_rank_by_relevance 不会 AttributeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:65-68`
  - 依据：构造函数里 `self._relevance_enabled = relevance_enabled and embedder is not None`，而 _rank_by_relevance 只在 `elif self._relevance_enabled:` 分支被调用，因此分支内 `self._embedder.embed_batch(...)` 的 self._embedder 必定非 None。初看像是「未判空就调用可选依赖」，实际已被开关短路保护，不构成缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:119-123 _rank_by_relevance 返回相关性顺序，未按注释复原原始相对顺序（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:119-123`
  - 依据：第 122 行注释声称「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，但实现 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按 (-score, index) 排序后的顺序返回，从未按原 likes 索引重排。结果是注入块的偏好行序完全由相似度决定：同一批偏好在新 query 下顺序会变化，正是注释想避免的抖动；同分时虽靠 index 稳定，但整体顺序并不等于原始顺序。注释与行为不一致，且实现没有兑现声明的稳定性目标。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:126-129 _latest_first 用 `p in newest` 还原顺序，依赖 BuyerPreference 的相等语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:126-129`
  - 依据：`[p for p in likes if p in newest]` 通过 __eq__ 在原始列表上过滤，从而复原相对顺序。在当前可见文件里无法证实 BuyerPreference 是值相等还是身份相等的 dataclass；若它是普通的不可变实体（带唯一 id 或 eq=False），该写法结果完全正确，且 `likes` 规模通常只有几十条，O(n*k) 的开销可忽略。因此仅凭可见代码不足以判定为缺陷，但存在一个依赖点值得记录：若 BuyerPreference 使用 dataclass 默认的按字段相等且允许完全相同的两条偏好并存，过滤会把所有「与选中项字段相同」的条目都保留，返回值可能超过 top_k，破坏预算。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:87-94 select() 对 dislikes+likes 整体切片，dislike 仍会被 top_k 截断（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:87-94`
  - 依据：模块文档与类文档明确承诺「dislike 全量保留，不参与 top_k 截断」，但 select 的最后一步是 `(dislikes + selected_likes)[:top_k]`：dislikes 与 likes 被拼在一起后再统一切片，因此只要 dislike 条数 >= top_k，尾部（通常是较早记录的那几条）忌口/黑名单会被直接丢弃；当 dislike 条数 > top_k 时更会出现「一条 like 都没注入、且 dislike 还被裁掉」的退化。这正是文档里描述的「推出一只塑料杯」安全问题：被丢掉的正是用户明确拒绝的约束。另外分支判断用 `len(likes) <= top_k` 决定是否排序，也未扣除 dislikes 占用的预算，导致 like 侧仍按 top_k 选取后又被切片，行为不一致。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:44-52 PreferenceStore.delete 用精确匹配且不区分 kind 是有意设计，不构成缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:44-52`
  - 依据：初看 delete(buyer_id, statement) 缺少 kind 参数、且要求整句精确匹配，像是"漏参数"或"边界过严"。但 docstring 明确论证了这是刻意取舍：删偏好是不可逆写操作，"不要塑料"与"不要塑料包装"相似度极高，模糊匹配会误删，所以要求调用方拿原文重试；不按 kind 区分同 statement 的一并清除也已写明。缺陷报告需要能指出与声明意图相矛盾的代码，这里没有。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:14-17 Money 为可公开构造的 dataclass，缺少 __post_init__ 校验，不变量可被绕过（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:14-17`
  - 依据：模块文档声称不变量是「amount_in_minor_units 必须为非负整数；currency 必须是受支持的 ISO-4217 三位代码」，但该不变量只写在工厂方法 Money.of 里。Money 是普通 frozen dataclass，字段构造器完全公开且没有 __post_init__，所以 Money(-100, "BTC") 可以直接创建出违反不变量的实例；add/multiply 内部同样绕过校验直接调用 Money(...)（第 34、39 行），一旦任一操作数是绕过工厂构造的非法实例，非法性会静默传播到后续结果（例如负数金额、未知币种），错误只在很晚的环节才暴露。校验点分散在少数入口、且不以类型自身为保障，是真实的可触发缺陷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:11-41 JPY 被列入支持币种却仍按 100 换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:11-41`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY（ISO-4217 中 JPY 的最小单位就是 1 日元，指数为 0），但 from_major_units 与 to_major_units 对所有币种一律除以/乘以 100。注释承认「JPY 实际为 1，demo 暂统一」，但代码未做任何拦截或告警，因此 from_major_units(1000, "JPY") 会得到 100000 的 amount_in_minor_units，一旦与支付网关/对账系统按 JPY 小单位交互就会产生 100 倍金额错误；to_major_units 同样会把 1000 日元打印成 10.00 JPY。注释只说明了这是简化，并未阻止该路径被调用，属于未闭合的正确性缺口。
- **[api_misuse/medium]** [api_misuse] app/domain/session/ports/conversation_store.py:27-30 ConversationTurn 缺失 turn_index 字段，但文档与 list_turns 契约都依赖它（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-30`
  - 依据：类 docstring 声明 "turn_index 由存储层按会话自增，写入时可留空"，ConversationStore.list_turns 的 docstring 又承诺"按 turn_index 升序返回该会话的对话流水"，但 dataclass 根本没有 turn_index 字段。存储层即使自增了序号也无处安放，调用方拿到的 list[ConversationTurn] 无法判断顺序、也无法引用某一轮。更糟的是 created_at 来自客户端时钟（默认 _now_iso 在构造时生成），同一毫秒内多条 turn 顺序不可靠，因此"按 turn_index 升序"这条契约在现有类型上无法被实现或验证。
- **[logic/medium]** [logic] app/domain/session/ports/conversation_store.py:37-39 ConversationTurn.role 未做校验，VALID_ROLES 定义后从未使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:37-39`
  - 依据：模块顶部定义了 VALID_ROLES = ("buyer", "agent")（第 18 行），字段注释也写明 role 只能是 buyer / agent，但 __post_init__ 只校验了 session_id，完全没有检查 role。任何存储实现拿到 role="system"/"" /typo 的 turn 都会静默落库。这与同文件里对 session_id 做强制校验的做法不一致，说明是遗漏而非有意放宽：后续 list_turns 按 role 分流渲染/统计时（buyer 与 agent 分开回放是 bad case 回放的核心场景）会得到无法归类的记录，且错误在写入侧无感知、要到读取侧才暴露。
- **[error_handling/low]** [error_handling] app/domain/session/ports/session_store.py:16-22 SessionStore 抽象方法仅以 docstring 作为函数体，是合法的 Python 写法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:16-22`
  - 依据：save/load 的 async def 下只有 docstring、没有 ... 或 raise NotImplementedError，容易被误读为"空实现导致静默返回 None"。实际上 docstring 本身就是合法的语句体，配合 @abstractmethod 后，未实现该方法的子类无法实例化（TypeError），不会出现"调用到空实现却返回 None"的运行期错误。因此这不是缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:30-32 CachedEmbeddingClient 的缓存 key 不含模型名，不同模型的向量互相串用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:30-32`
  - 依据：__init__ 保存了 self._model（第 26 行），但整个类再没有引用它：_key 只对 text 做 sha256，返回固定的 "emb:<digest>"。模块 docstring 第 6 行明确写着“key 用 sha256(model + text)”，实现与文档不一致。当两个不同 embedding 模型（模型升级灰度、切换 model 配置、A/B 两套模型）共用同一个 RedisCache 时，同文本落到同一个 key：模型 A 写入的向量会被模型 B 直接命中返回，既不会回源也不会报错；维度不同会是脏向量，维度相同更是语义错位的静默污染，且 7 天 TTL 内不会自愈。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:121-127 zadd_and_count 用 ZADD 计数，member 不唯一时计数不会增长（限流失效）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:121-127`
  - 依据：实现本身正确：pipeline 内 zremrangebyscore → zadd → zcard → expire 是原子的（transaction=True），results[2] 确实对应 zcard。但 ZADD 对同一 member 是更新 score 而非新增，若调用方传入固定 member（如用户 ID、接口名），窗口内计数恒为 1，限流永远不会触发。由于 member 完全由调用方提供、本文件中没有调用点，无法据此判定为缺陷；只有在调用方不做每次请求唯一化（uuid/请求 id）时才成为真实问题。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:118-130 zadd_and_count 在 Redis 故障时返回 0（视为未超限），限流被整体旁路（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：disabled（_client 为 None）与 pipeline 抛异常两种路径都返回 0，即「窗口内计数为 0 / 不限流」。这与类头部「不能因为 Redis 挂了让主链路一起挂」的既定策略一致，日志也明确写了「按不限流处理」。返回值语义在两条路径上一致，不会让调用方拿到 None 或抛异常，因此不是实现缺陷；只是在 Redis 长时间故障时跨进程限流实际不生效，属于已声明的降级取舍。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:62-67 get_json 解析失败即删除键：可破坏非 JSON 语义的键（幂等键/锁键），且读-删非原子（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:62-67`
  - 依据：get_json 在 json.loads 抛 ValueError 时直接把键删除。该类的键空间没有任何类型隔离：set_if_absent 写入的是裸字符串（如 task_id），get_raw 的 docstring 也承认「json.loads 失败会把键当脏值删掉，直接破坏幂等语义」。因此只要有任何一条代码路径对本应存裸串的键调用 get_json（例如同名前缀、重构漏改、上游把 idempotency key 与缓存 key 拼成同一命名空间），该键会被静默删除，SETNX 的幂等保护随之失效，同一任务会被重复执行。另外 GET 与 DEL 之间没有原子性：若在两次调用之间另一进程用 set_json 写入了同一 key 的合法新值，这次 delete 会把刚写入的有效缓存删掉（后果较轻，仅一次缓存穿透）。
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:163-167 remember 用 entries[:30] 截断，桶满后新条目永远写不进去且旧条目被反复续期（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:163-167`
  - 依据：新条目 append 到列表末尾，随后却取 entries[:_BUCKET_LIMIT]（前 30 条）写回，保留的是最旧的 30 条而不是注释（第 38 行“单个 buyer 桶内保留的最近条数”）声明的最近 30 条。一旦某个桶已满，每次 remember 只是把同一份旧列表原样写回并用新的 _TTL_SECONDS 续期——新产生的问答对被全部丢弃，缓存冻结在最早的 30 条，且这 30 条因 TTL 被不断刷新而永不过期。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:110-113 语义缓存桶 key 丢弃了 scope，偏好变更后旧回复仍然命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:110-113`
  - 依据：方法签名接收 scope 参数，docstring 也明确写“桶 key = namespace + buyer_id + scope”，但 digest 只用 f"{self._namespace}\n{buyer_id}" 计算，scope 从头到尾没有参与哈希，返回的 key 与 scope 无关。lookup / _load_entries / remember 全部通过 _bucket_key 取 key，因此写入和读取都被折叠到同一个不带偏好指纹的桶里：买家撤回或新增偏好后，key 不变，lookup 仍会命中旧偏好下生成的回复（正是 docstring 描述的那种向用户断言已删偏好的错误），而且这份旧回复还会被 remember 的新写入续期 TTL。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:124-131 lookup 完全不使用 has_history，多轮会话仍可命中单轮缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:124-131`
  - 依据：lookup 的签名接收 has_history，但函数体只判断 self._enabled 和 is_cacheable_query，从未读取 has_history；只有 remember 侧做了 has_history 拦截（第 153 行）。写入侧和读取侧不对称，导致 docstring 第 3 条安全边界（“会话内已有多轮上下文时不命中”）只实现了半条：一条在单轮会话中写入的条目，会被带历史的多轮会话命中。像“要黑色的”“便宜点的”“第二个”这类依赖上下文的短句并不命中 _UNSAFE_PATTERNS，一旦命中缓存就会给出与当前会话上下文无关的回复。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:22-30 注入正则覆盖不全（如 'ignore all the previous instructions' 不匹配），属已声明的启发式层局限（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：r"(?i)ignore\s+(all\s+)?previous\s+instructions?" 中间的 (all\s+)? 只允许至多一个 'all '，因此 'ignore all the previous instructions'、'ignore the previous instructions' 以及常见的大小写/同形字变体都不会命中；新增的 (?i) 内联标志均位于模式开头，re.compile 不会报错；subn 的替换串不含反斜杠转义，也不会因替换模板出错。但这些属于正则启发式的固有覆盖面问题，文件 docstring 已明确声明本层只做正则、不做语义判断、真正的语义级判断交给 L4 与漂移检测，且命中后是替换片段而非整条丢弃，行为与设计一致，故不计为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:63-71 output_guard 的多模式 subn 脱敏不会二次污染或漏脱敏（核查为安全）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:63-71`
  - 依据：逐个用 pattern.subn(REDACTED, cleaned) 串行替换、命中即置 safe=False 的写法是可重入安全的：替换串 REDACTED="[已脱敏]" 不含反斜杠或 \g<> 引用，不会被 re 当作模板解析；替换出的文本也不匹配任何 SENSITIVE_PATTERNS（不含工具名、内部地址、session_id 形态），后面的模式不会对已脱敏结果再次命中；_INTERNAL_TOOLS 被 \b(?:...)\b 包裹时，首字符 p/t 前是串首或非单词字符、末字符 l/h 后同理，正常拼写可以命中。未发现可触发的错误行为。

## 争议（需裁决）

- **[boundary/medium]** [boundary] app/domain/catalog/money.py:28-30 from_major_units 用二进制浮点乘 100 再 round，会丢失分精度（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:28-30`
  - 依据：该函数以 float 入参并依赖 round(major * 100) 完成换算，但 float 无法精确表示十进制小数：1.005 * 100 得 100.49999999999999，round 后为 100（丢失 1 分）；1.115 * 100 得 111.49999999999999，结果为 111；且 round 使用银行家舍入，2.675→267、0.125 类边界结果与业务预期的四舍五入不一致。模块自述「避免浮点误差」却在此引入浮点误差，是真实可复现的金额偏差。
  - 争议对手：3b9c43d6bc80

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain, app, app/application, app/infrastructure

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 6 | `partition_gap` | — |
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
| `app/application` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 34%（单元格值 = 独立 Agent 数）
