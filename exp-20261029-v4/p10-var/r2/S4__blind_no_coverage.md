# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 29 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：31
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：63 个节点 / 92 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 30 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:30-37 _cosine 对 NaN/Inf 输入无防护，排序结果不确定（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：若 embedding 含 NaN，dot/norm 会产生 NaN，sort key 为 (-NaN, index)，Python 中 NaN 比较恒为 False，排序结果虽不确定但不会崩溃，且属于上游 embedding 服务异常，非本函数职责。norm 为 0 已显式返回 0.0。判定为可接受。
- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:88-99 likes 的 top_k 选取未扣除 dislike 占用预算，导致 like 被过度截断或 dislike 被截断（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-99`
  - 依据：预算分配逻辑错误：likes 按完整 top_k 选取，而不是按 top_k - len(dislikes) 选取，随后整体切片。这造成两个方向的边界错误：(1) 当 len(dislikes) > 0 时，最终结果中 like 数量被压缩到 top_k - len(dislikes)，但 _rank_by_relevance/_latest_first 内部已按 top_k 排序取前 top_k，被切掉的恰好是排序靠后的 like，结果虽不致命但预算计算与语义不符；(2) 更严重的是当 len(dislikes) >= top_k 时，所有 like 都被切掉且部分 dislike 也被切掉（见上一条）。正确做法应是先保留全部 dislikes，再用剩余预算 top_k - len(dislikes) 选 likes。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:118-126 _rank_by_relevance 中 embed_batch 返回 None 时 len(vectors) 抛 TypeError 未被捕获（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-126`
  - 依据：try 块只包住两次 embed 调用；`len(vectors)` 与 `not query_vector` 在 try 之外。若 embedder 实现返回 None（例如某些客户端在失败时返回 None 而非抛异常），`len(None)` 会抛 TypeError，未被捕获，直接冒泡到 select() 调用方，违背「任何异常都降级为按时间倒序，不能因为选偏好把对话搞挂」的承诺。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-141 _latest_first 用 `p in newest` 依赖 dataclass 相等性，可能误删/重复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-141`
  - 依据：`[p for p in likes if p in newest]` 使用 `in` 判断，依赖 BuyerPreference 的 __eq__。若 BuyerPreference 是 dataclass（默认 eq=True），两条字段完全相同的偏好会被视为相等：当 newest 中只包含其中一条时，likes 中所有相等的偏好都会被保留，导致返回条数超过 top_k；反之若 BuyerPreference 定义了自定义 __eq__ 或 eq=False（按身份比较），则行为退化为身份比较，仍能工作。此外该实现是 O(n*k) 且依赖相等语义，不如直接用索引集合稳健。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-99 select() 用 [:top_k] 截断会把 dislike 挤掉，违背「dislike 全量保留」的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-99`
  - 依据：模块文档明确承诺 dislike 全量保留、不参与 top_k 截断，但实现把 dislikes 与 selected_likes 拼接后又整体切片 [:top_k]。当 dislike 数量 >= top_k 时，末尾的 dislike 会被截掉；当 dislike 数量 < top_k 时，likes 的选取也没有为 dislike 预留预算（likes 已按 top_k 选满），拼接后截断同样会丢掉部分 dislike。例如 top_k=3、dislikes=2、likes=10：likes 选出 3 条，拼接后 5 条，切片只保留前 3 条，即 2 条 dislike + 1 条 like，看似没问题；但 top_k=3、dislikes=5 时只保留前 3 条 dislike，丢掉 2 条黑名单；top_k=2、dislikes=1、likes=10 时 likes 选 2 条，拼接 3 条切片保留 1 dislike + 1 like，丢掉 1 条 like（可接受），但 top_k=1、dislikes=2 时只保留 1 条 dislike，丢掉另一条黑名单。这正是文档所说的「推了用户明确拒绝的东西」的安全问题。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:47-58 PreferenceStore.delete 契约要求同 statement 的 like/dislike 一并删除，但接口无 kind 参数且语义易被误实现（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-58`
  - 依据：delete(buyer_id, statement) 不带 kind，docstring 明确说明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是刻意设计而非缺陷。虽然删除语义较激进，但契约已显式声明，调用方按文档使用即可。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:20-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:20-31`
  - 依据：__post_init__ 校验了 kind 与 statement，却未校验 buyer_id。空字符串 buyer_id 会被接受，随后 append 到存储后无法按买家检索/隔离，list_by_buyer("") 可能把不同来源的匿名偏好混在一起，破坏“按 buyer 持久化”的核心语义。同仓库的 ConversationTurn 至少校验了 session_id，说明此处遗漏。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:20-25 of() 未拒绝 bool 作为 amount（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:20-25`
  - 依据：multiply() 显式排除了 bool（isinstance(quantity, bool)），但 of() 只检查 isinstance(amount, int)，而 bool 是 int 的子类，因此 Money.of(True, 'USD') 会通过校验得到 1 分。同一模块内校验不一致，属于边界缺陷。
- **[logic/medium]** [logic] app/domain/catalog/money.py:31-34 from_major_units 对 JPY 等零小数币种按 100 换算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的 ISO-4217 小数位为 0，最小单位即 1 日元。from_major_units 对所有币种统一乘 100，导致 1000 JPY 被存成 100000 最小单位，to_major_units 又除以 100，虽然往返一致，但与真实最小单位语义不符，且与外部系统（支付网关按最小单位）交互时金额放大 100 倍。代码注释承认这是简化，但这是真实的行为缺陷而非风格问题。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:47-52 Product.searchable_text 中 highlight_text 为空时产生多余空格（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：当 highlights 为空时 highlight_text 为 ""，join 结果末尾多一个空格，对召回文本无实质影响（embedding 与关键词匹配均不受影响）。属于格式瑕疵而非缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/product.py:33-37 Product.__post_init__ 未校验 skus 中元素类型，find_sku 可能 AttributeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-37`
  - 依据：类型标注已声明 skus: list[Sku]，Python 动态类型下传入非 Sku 元素属于调用方违约，非本类职责；且 dataclass 不做运行时类型检查是常规做法。判定为可接受。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:24-28 Sku.stock 校验非负但未校验 price 非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:24-28`
  - 依据：price 类型为 Money，若 Money 自身在构造时校验则无需重复；此处未提供 Money 实现，无法确认缺失校验会导致错误行为。判定为证据不足，不报告为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:25-36 ConversationTurn 文档声称 turn_index 可留空但字段不存在（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:25-36`
  - 依据：类 docstring 写“turn_index 由存储层按会话自增，写入时可留空”，但 dataclass 根本没有 turn_index 字段；同时 list_turns 的契约是“按 turn_index 升序返回”。存储层无法把自增的 turn_index 回填到不可变（frozen）且无该字段的对象上，也无法在 list_turns 返回的 ConversationTurn 上携带 turn_index，导致“按 turn_index 升序”的排序依据在值对象层面缺失，实现者只能依赖外部隐式顺序，接口契约自相矛盾。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:22-36 ConversationTurn 声明 role 但未校验，非法角色可写入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:22-36`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，完全没有使用 VALID_ROLES 校验 role。因此 role 可以是任意字符串（如 "system"、""），与文档声明的 buyer/agent 语义不符，下游按 role 分流（如回放、统计买家/客服发言）时会把非法角色当成 agent 或 buyer 处理，产生错误数据。VALID_ROLES 的存在表明作者本意是要校验的。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:78-78 embed_batch 用 `vector or []` 把合法的零向量/空结果静默替换（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-78`
  - 依据：若内层 embed_batch 返回的向量为空列表（例如空文本或异常降级），`vector or []` 与 None 分支无法区分，但更关键的是：当内层返回的 fresh 列表长度短于 pending 时，zip 会截断，results 中剩余位置保持 None，最终被替换成 []，调用方拿到长度与输入不一致的结果且无任何告警。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 embedding 缓存 key 未包含 model，换模型后复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。同一 Redis 实例上切换 embedding 模型后，旧模型的向量会被当作新模型结果返回，导致向量维度/语义不一致，进而使语义缓存余弦比较失真或维度不匹配返回 0。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:63-72 embed_batch 逐条串行 await 缓存读取，批量场景性能退化（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:63-72`
  - 依据：对每个 text 依次 await _safe_get，N 条文本产生 N 次串行 Redis 往返；批量 embedding 的收益被串行 IO 抵消，大批量时延迟线性增长。可用 asyncio.gather 并发。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:157-163 close 使用 aclose 而非 close（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:157-163`
  - 依据：redis.asyncio 客户端在较新版本提供 aclose()，旧版本提供 close()。若依赖版本较旧会抛 AttributeError，但被 except 吞掉，仅导致连接未关闭。属于版本兼容风险而非确定缺陷，且异常被吞不会影响主链路。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/redis_cache.py:68-72 get_json 在 json.loads 失败时调用 delete，可能删除并发写入的新值（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-72`
  - 依据：get_json 读到脏值后调用 self.delete(key) 无条件删除该键。若在 get 与 delete 之间另一个进程/协程用 set_json 写入了合法新值，这次 delete 会把刚写入的合法值删掉，造成缓存击穿与数据丢失。虽然缓存丢失通常可容忍，但这是真实的竞态窗口，且注释声称只是『顺手删掉脏值』，实际可能删掉非脏值。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-126 set_if_absent 在 Redis 异常时返回 True，幂等键与分布式锁失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-126`
  - 依据：set_if_absent 被文档声明用于幂等键与分布式锁。异常分支返回 True（视为抢到锁/首次请求），意味着 Redis 故障时所有并发请求都会认为自己是第一个，幂等保护与互斥完全失效，可能造成重复执行副作用（重复下单、重复任务）。这是有意的降级设计，但对『分布式锁』语义而言是危险的：锁的失败模式应当是拒绝而非放行。至少对锁用途是真实缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:145-155 zadd_and_count 异常时返回 0，限流完全失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:145-155`
  - 依据：该方法用于跨进程限流，异常分支返回 0（窗口内计数为 0），调用方据此认为未超限而放行全部请求。Redis 故障时限流失效，可能压垮下游。与 set_if_absent 类似，这是有意的 fail-open 设计，但对限流语义而言是真实缺陷：故障期间无任何保护。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:68-72 get_json 脏值删除未捕获 delete 自身异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:68-72`
  - 依据：delete 方法内部已 try/except 吞掉所有异常，因此此处 await self.delete(key) 不会抛出，get_json 的降级语义保持完整。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:141-148 zadd_and_count 使用固定 member，同一调用方重复调用不会累加计数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:141-148`
  - 依据：zadd 以 member 为唯一标识，若调用方传入固定 member（如用户 ID 或 IP），同一 member 在窗口内多次调用只会更新 score 而不会增加 zcard 计数，导致限流永远只计 1 次，无法限制频率。方法签名未强制 member 唯一，注释也未说明必须每次生成唯一 member，调用方极易误用。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:178-181 remember 截断保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-181`
  - 依据：注释称“保留最近条数”，但 entries.append 后取 entries[:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在桶满后被丢弃，导致缓存永远停留在旧回复上，新回复无法进入缓存。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:152-153 lookup 未校验 entry 结构，vector 非列表时 _cosine 抛异常（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:152-153`
  - 依据：entry.get("vector", []) 若返回 None 或非列表（缓存被污染/旧格式），_cosine 中 len(None) 抛 TypeError，而该循环不在 try 内，异常会冒泡到调用方，破坏“缓存异常按未命中”的纵深防御承诺。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 语义缓存桶 key 忽略 scope，偏好变更后旧回复仍会命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：_bucket_key 的文档与签名都声明 key = namespace + buyer_id + scope，但实现里 sha256 只拼了 namespace 和 buyer_id，scope 参数完全没参与计算。于是 remember/lookup 传入不同 scope 时落到同一个桶：买家撤回或新增偏好后，旧回复（含已删除偏好的断言）仍会被命中，正是模块文档 2b 明确要求防止的场景。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-141 lookup 忽略 has_history，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-141`
  - 依据：remember 在 has_history=True 时拒绝写入，但 lookup 完全没有检查 has_history。模块文档第 3 条要求“会话内已有多轮上下文时不命中”，否则“刚才那款多少钱”这类依赖上下文的问句会跨会话复用错误回复。lookup 的 has_history 参数被声明却从未使用。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:55-60 content_filter 正则替换后可能产生新的注入拼接（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:55-60`
  - 依据：逐个 pattern 顺序 subn 替换为固定占位符，占位符本身不含危险模式，不会因替换引入新的匹配；且过滤是尽力而为的 L3 层，L4 与漂移检测兜底。未发现可复现的绕过缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:40-41 output_guard 内部服务地址正则未覆盖带路径前缀的变体（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-41`
  - 依据：正则已包含可选端口与可选路径，能匹配 http://vllm:8000/v1 等常见形态；未匹配的仅是刻意构造的变体，属于收窄范围的已知取舍，不构成可确认缺陷。

## 争议（需裁决）

- **[logic/low]** [logic] app/domain/catalog/money.py:45-46 to_major_units 返回 float，与「避免浮点误差」的设计目标冲突（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-46`
  - 依据：模块文档声明统一以最小单位存储以避免浮点误差，但 to_major_units 返回 float，调用方若用其结果做进一步计算会重新引入浮点误差；__str__ 也依赖它。对金额展示尚可，但作为公开 API 返回 float 容易被误用于计算。
  - 争议对手：26c0f59a19b8

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
| `1ea202d2ad5b` | 1 | 5 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 1 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 2 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 21%（单元格值 = 独立 Agent 数）
