# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 27 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：29
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：61 个节点 / 88 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 28 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-99 top_k<=0 时返回 dislikes 但未做去重/顺序保证，且忽略 likes 语义边界（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-99`
  - 依据：top_k<=0 时直接返回 dislikes 是文档明确声明的安全底线行为（「只保留安全底线，正向偏好全部让位」），dislikes 本身来自原 preferences 顺序，语义正确。虽然 top_k 为负数时行为与 0 相同，但这属于合理边界处理，不构成缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-35 _cosine 对长度不一致返回 0.0 而非报错，可能掩盖向量维度错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-35`
  - 依据：长度不一致返回 0.0 是防御性降级，配合上层「向量数量不一致则降级」的日志策略，不会导致崩溃；维度不一致时相似度置 0 属于可接受的保守行为，且上层已有数量校验。不构成真实缺陷。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:118-124 相关性排序取的是相似度最低的 top_k（排序方向反了）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：scored 中每项为 (cosine, index, preference)，随后 scored.sort(key=lambda item: (item[0], item[1])) 按相似度升序排序，再取 scored[:top_k]，得到的是与 query 最不相关的 top_k 条 like 偏好，而不是最相关的。这与函数名 _rank_by_relevance 及文档「按 statement 与 query 的余弦相似度取 top_k」完全相反。触发条件：relevance_enabled=True 且 embedder 可用、likes 数量 > top_k。此时注入的正是最不相关的偏好，相关性排序功能整体失效（虽不破坏 dislike 安全底线，但正向偏好选择逻辑错误）。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:125-126 用 `p in picked` 过滤依赖 dataclass 相等性，可能误删/重复保留偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:125-126`
  - 依据：`return [p for p in likes if p in picked]` 用成员判断而非身份判断来复原顺序。若 BuyerPreference 是 dataclass（默认 eq=True），两条字段完全相同的偏好（例如同一 statement、同一 kind、同一 created_at 的重复记录）会被视为相等：当 picked 只包含其中一条时，列表推导会把两条都保留，导致返回数量超过 top_k；反之若 picked 中某条与 likes 中另一条相等，也可能保留错误实例。_latest_first 中同样使用 `p in newest`。触发条件：存在字段完全相同的重复偏好且 likes 数量 > top_k。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:27-33 BuyerPreference 未校验 buyer_id 非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：__post_init__ 校验了 kind 和 statement，但未校验 buyer_id。端口方法 list_by_buyer/delete 都以 buyer_id 为键，空 buyer_id 会写入一个无法归属的偏好。不过契约未声明 buyer_id 必填，且上游通常保证，故不作为确认缺陷。
- **[logic/medium]** [logic] app/domain/buyer/preference.py:31-33 created_at 默认空串导致每次构造都生成新时间戳，破坏值对象相等性（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:31-33`
  - 依据：BuyerPreference 是 frozen dataclass，相等性基于所有字段。created_at 默认 ""，__post_init__ 在为空时用 object.__setattr__ 填入当前时间。因此两个除 created_at 外完全相同的偏好（同 buyer/kind/statement）不相等，且每次构造时间不同。端口 append 声称“同 buyer 同 statement 幂等去重”，若实现用值对象相等或 set 去重，则永远无法去重；同时 created_at 作为默认参数在 dataclass 层面是共享的静态默认值，但这里通过 __post_init__ 每次重写，行为虽可运行但与“值对象”语义冲突。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:14-16 Money 直接构造不校验，of() 校验可被绕过（not_a_defect 记录）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:14-16`
  - 依据：dataclass 默认生成公开 __init__，理论上可绕过 of()。但这是 Python 值对象的常见约定（of 为推荐工厂），且本仓库内所有构造点均走 of()/add()/multiply()。单独把“dataclass 可被直接构造”列为缺陷过于宽泛，故不单独计为缺陷；真正的风险已在 add/multiply 绕过校验那条中体现。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:31-34 from_major_units 用 round() 处理浮点，银行家舍入与浮点误差导致金额偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：round(major * 100) 使用 Python 的银行家舍入（round-half-to-even），且 major 为 float 时存在二进制浮点误差。例如 round(2.675 * 100) 得到 267 而非 268；round(0.5*100)=50 正常，但 round(1.005*100)=100 而非 101。金额换算出现 1 分偏差，对价格不变量是真实缺陷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:36-44 Money.add/multiply 绕过 of() 校验，可构造非法 Money（负数、非整数、非法币种）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-44`
  - 依据：Money.of() 是唯一执行不变量校验（amount 为非负整数、currency 在 SUPPORTED_CURRENCIES 内）的入口，但 add() 和 multiply() 直接调用 dataclass 构造函数 Money(...)，绕过了 of()。add() 只校验币种一致，不校验 amount 类型/非负；multiply() 校验了 quantity 但结果仍直接构造。虽然当前 add 的两个操作数若都来自 of() 则结果非负，但 Money 是公开 dataclass，可直接构造任意实例（如 Money(-5, 'USD') 或 Money(1.5, 'USD')），再调用 add/multiply 就会把非法值传播到下游，破坏类文档声明的核心不变量。此外 multiply 结果可能溢出为超大整数但无上限约束（次要）。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:55-60 Product.searchable_text 中 highlight_text 为空时产生多余空格（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:55-60`
  - 依据：当 highlights 为空时 highlight_text 为空串，join 结果末尾多一个空格，仅影响文本美观，不影响召回语义（embedding 对空白不敏感）。属于可忽略的格式问题，不构成功能缺陷。
- **[boundary/medium]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 校验拒绝 0，与“初始库存”语义冲突，无法创建零库存 SKU（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：文档说明 stock 是“初始库存”，用于首次播种库存表与展示兜底。初始库存为 0 是合法业务状态（新品未到货、售罄后重建 SKU 等），但 __post_init__ 用 `self.stock <= 0` 抛错，导致无法创建 stock=0 的 SKU。若业务确实要求正库存，则 stock 为负也应被拒绝（这点正确），但 0 被一并拒绝属于边界过严，会阻断合法的零库存播种场景。
- **[logic/low]** [logic] app/domain/catalog/sku.py:30-32 Sku.stock 未校验类型，bool/float 可通过校验（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：__post_init__ 只比较 `self.stock <= 0`，未校验 stock 是 int。传入 True（bool 是 int 子类，True<=0 为 False）或 1.5 都能通过，导致 stock 字段类型不符合“库存数量”语义，后续播种库存表时可能写入非整数。Money 类对 amount 做了 isinstance 校验，Sku 未做，属不一致的校验缺口。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn 文档声称 turn_index 可留空但字段不存在（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：类 docstring 明确写“turn_index 由存储层按会话自增，写入时可留空”，但 dataclass 根本没有 turn_index 字段。list_turns 的契约又要求“按 turn_index 升序返回”。实现者无法从值对象拿到 turn_index，也无法在 append_turn 时传入；若存储层自行生成，则 list_turns 返回的 ConversationTurn 无法携带该字段，导致“按 turn_index 升序”的排序依据在返回类型上不可见。这是端口契约与值对象定义不一致，会误导实现方。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:37-40 ConversationTurn 未校验 content 与 buyer_id 必填（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:37-40`
  - 依据：__post_init__ 只校验 role 和 session_id，未校验 buyer_id/content 非空。但端口契约并未声明这两个字段必填，且空 content（如工具调用轮）可能是合法场景，因此不构成可证实的缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:43-51 ConversationEventRecord 未校验 session_id/type 必填（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:43-51`
  - 依据：ConversationEventRecord 没有任何 __post_init__ 校验，session_id/type 可为空。但端口契约未声明必填，且事件类型由上游 TradeEventBus 保证，不构成可证实缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:68-74 embed_batch 对空字符串文本的缓存判断 isinstance(cached, list) and cached 会把空向量当未命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:68-74`
  - 依据：空列表向量在正常 embedding 中不会出现（维度固定），且 cached 为空列表时回源是安全降级，不会产生错误结果。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-80 embed_batch 中 zip(pending, fresh) 在 fresh 长度不足时静默丢弃结果，导致后续 RuntimeError 而非明确错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-80`
  - 依据：zip 会截断到较短序列，若 inner 返回少于 pending 数量，部分 results 保持 None，随后 missing 检查会抛 RuntimeError，行为符合注释意图（不静默补零向量）。虽然错误信息不够精确，但不会产生错误数据。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:118-128 redis_cache.zadd_and_count 的 zremrangebyscore 上界多减 1 秒，窗口边界清理不精确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-128`
  - 依据：now - window_seconds - 1 多清理 1 秒，属于保守清理（多删旧成员），只会让计数偏小、限流更宽松，不会误限流；且 expire 设为 window+1 保证键存活。不构成错误行为。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:100-110 redis_cache.set_if_absent 在 Redis 故障时返回 True，破坏幂等保护（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:100-110`
  - 依据：注释明确说明这是有意的降级策略（宁可失去幂等保护也不拒绝服务）。属于设计取舍，不是缺陷；但需注意在幂等键场景下 Redis 故障会导致重复执行，这是已知权衡。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:155-163 semantic_cache.remember 的读-改-写非原子，并发下会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:155-163`
  - 依据：remember 先 _load_entries 读取整个桶列表，append 后再 set_json 整体覆盖。同一 buyer 的多个并发请求（多 worker / 多协程）会各自读到相同旧列表，后写者覆盖先写者，导致部分条目丢失。缓存丢失只影响命中率不产生错误回复，但确实是并发缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:128-136 semantic_cache.lookup 中 entry.get("vector", []) 若条目缺 vector 字段，_cosine 返回 0.0 安全，但 entry 非 dict 时会抛 AttributeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:128-136`
  - 依据：_load_entries 只校验 entries 是 list，未校验元素是 dict。若缓存被污染成 list 内含非 dict 元素，entry.get 会抛 AttributeError，而 lookup 未捕获该异常，会向上传播导致主链路失败。但缓存由本模块自身写入（始终是 dict），外部污染概率低；且 _load_entries 的 try 只包住 get_json 不包住遍历。这是一个潜在的健壮性缺口，但触发条件需要缓存被外部写入非 dict 元素，属于低概率。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-55 semantic_cache 的 _UNSAFE_RE 中 '这个'/'那个'/'它' 等单字模式会误伤大量正常咨询问句，导致缓存几乎不生效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-55`
  - 依据：这是有意的保守策略（宁可多花一次调用也不答错），属于设计取舍而非缺陷；误伤只降低命中率，不产生错误回复。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:63-70 semantic_cache 的 _cosine 对维度不一致的向量用 zip 截断，可能产生虚假高相似度（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:63-70`
  - 依据：_cosine 使用 zip(left, right) 会截断到较短向量。若缓存中存的旧向量维度与当前 embedder 输出维度不同（例如换了 embedding 模型但 namespace 未变，或缓存被污染），点积只累加前 min(len) 个分量，而范数仍按各自完整长度计算，得到的相似度既非真实余弦也可能异常偏高/偏低。虽然 namespace 设计上应含模型名，但代码未强制校验维度，且 entry.get("vector", []) 缺省为空列表时 zip 直接为空、dot=0，norm_right=0 返回 0.0 是安全的；真正风险在维度不一致的非空向量。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/security/content_filter.py:24-32 正则 (?i) 内联标志与 re.compile 组合正常，但模式中 (?i) 位于开头之外位置在 Python 3.11+ 会报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：所有模式均以 (?i) 开头，属于全局内联标志，Python 3.11+ 要求全局标志必须在模式开头，这里满足该约束，re.compile 不会抛错。
- **[error_handling/medium]** [error_handling] app/infrastructure/security/content_filter.py:41-44 sanitize_tool_output 对非 str 输入（如 None 以外的 dict/list）会抛异常（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:41-44`
  - 依据：函数签名声明 text: str，但工具返回内容常为 dict/list（如结构化 JSON 结果）。if not text 只拦截空值，随后 pattern.subn 对非字符串会抛 TypeError。调用方若直接把工具原始结果传入（文档称'工具结果在注入上下文之前先过一层'），结构化结果会导致过滤层崩溃，进而使整个工具调用链失败。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:46-50 多模式顺序替换可能产生二次匹配/漏匹配，且替换后文本可能被后续模式再次命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:46-50`
  - 依据：占位符文本 '[内容已过滤：疑似注入]' 不匹配任何 DANGEROUS_PATTERNS（不含 ignore/system prompt/you are now 等），因此后续模式不会再次命中占位符本身，也不会造成无限替换或误报。逐个模式替换是幂等安全的。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-46 output_guard 的 URL 模式只匹配特定主机名，其他内部地址（如 IP、其他服务名）不脱敏（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-46`
  - 依据：文档明确说明只针对容器网络内已知主机名，属于刻意收窄范围；未列入的主机名泄露是覆盖不足而非代码缺陷，且无法从代码确认存在其他内部服务。

## 争议（需裁决）

- **[security/low]** [security] app/infrastructure/security/content_filter.py:26-26 中文注入模式 '忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)' 中 . 不匹配换行，跨行注入可绕过（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:26-26`
  - 依据：默认 . 不匹配 \n，若攻击者在'忽略'与'指令'之间插入换行（如 '忽略\n之前\n指令'），.{0,10} 无法跨越换行，模式不命中，注入内容原样进入上下文。同理英文模式 ignore\s+... 用 \s 可跨行，但中文模式用 . 不可，存在不一致的绕过面。
  - 争议对手：9dda65bb8ce9

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/catalog, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 1 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| `5e837c68a39e` | 1 | 1 | `partition_gap` | — |
| `62b74df5111f` | 1 | 4 | `partition_gap` | — |
| `63c335dd31c2` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 1 |

矩阵填充率 22%（单元格值 = 独立 Agent 数）
