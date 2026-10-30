# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 27 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：29
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：59 个节点 / 88 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 28 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:96-108 likes 数量超过 top_k 时未扣除 dislike 占用预算，导致 dislike 被挤出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：当 len(likes) > top_k 时，selected_likes 取满 top_k 条，再与 dislikes 拼接后切片 [:top_k]，dislikes 会被完全挤出（因为 selected_likes 已占满 top_k 个位置）。例如 top_k=3、dislikes=2 条、likes=5 条：selected_likes 取 3 条，拼接后前 3 个是 2 条 dislike + 1 条 like，切片保留 2 条 dislike + 1 条 like，看似 OK；但若 dislikes=2、likes 排序后 selected_likes=3，拼接为 5 条，切片取前 3 条 = 2 dislike + 1 like，仍保留 dislike。真正的问题在于 selected_likes 的预算应为 top_k - len(dislikes)，否则当 dislikes 数量接近 top_k 时，like 会挤占 dislike 的位置——例如 top_k=3、dislikes=2、likes=5，selected_likes 取 3 条，拼接后切片取前 3 条 = 2 dislike + 1 like，dislike 未被挤出。但若 dislikes=3、likes=5、top_k=3，selected_likes 取 3 条，拼接后切片取前 3 条 = 3 条 dislike，like 全丢——这反而符合安全底线。真正缺陷是：当 dislikes 数量 > top_k 时（见上一条），以及当 dislikes 数量 < top_k 但 selected_likes 取满 top_k 导致总条数超限时，切片会截掉尾部 like，这本身不违反安全底线但浪费预算。综合看，核心缺陷是预算分配未扣除 dislike 占用，导致 like 选取数量与 dislike 数量耦合错误。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-134 _rank_by_relevance 返回 picked 未按原始相对顺序复原，与注释不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-134`
  - 依据：注释声称“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度排序输出，并未按原始 index 重新排序。这导致注入块的行序随 query 变化而抖动，与注释意图相反，可能造成 Prompt Cache 命中率下降（虽然偏好作为 hint 消息注入，但行序抖动仍影响缓存）。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-108 dislike 偏好被 top_k 截断，违反“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单会导致推荐用户明确拒绝的商品（安全问题）。但 select() 最终返回 (dislikes + selected_likes)[:top_k]，当 dislikes 数量本身超过 top_k 时，dislikes 会被切片截断；即使 dislikes 数量不超过 top_k，likes 的选取也按 top_k 而非 top_k - len(dislikes) 计算，导致总条数被截断时可能挤掉部分 dislike（当 dislikes 数量 > top_k 时必然发生）。触发条件：买家积累的 dislike 偏好条数 >= top_k（例如 top_k=3 而有 5 条忌口），此时只有前 3 条 dislike 被注入，其余黑名单丢失，可能推荐用户明确拒绝的商品。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:22-33 BuyerPreference 未校验 buyer_id 非空，且 created_at 用字符串而非 datetime 导致相等性/排序语义脆弱（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-33`
  - 依据：buyer_id 为空虽不理想，但端口层 list_by_buyer/delete 以 buyer_id 为键，空串会自然查不到数据，不会造成跨买家串数据；created_at 用 ISO 字符串在 UTC 下字典序与时间序一致，且 dataclass 相等性比较包含 created_at 是预期行为。未发现可复现的错误行为，记录为 not_a_defect。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 Money.from_major_units 用 round() 处理浮点，银行家舍入导致金额偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：Python 的 round 使用银行家舍入（round-half-to-even），且浮点乘法本身有误差。例如 round(2.675 * 100) 得到 267 而非 268；round(0.5*100)=50 正常，但 round(1.005*100)=100（应为 101）。金额换算出现 1 分偏差，与模块文档声称“避免浮点误差”的核心不变量相矛盾。
- **[logic/low]** [logic] app/domain/catalog/money.py:38-46 Money.add/multiply 直接构造实例绕过 of() 校验，可产生非法 Money（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 直接调用 Money(...) 构造器，dataclass 本身无 __post_init__ 校验。虽然当前输入若来自合法 Money 则结果仍合法，但 Money 是公开 dataclass，外部可直接构造非法实例（如 Money(-1, 'XXX')）再参与 add，绕过不变量；同时 multiply 的 quantity 校验与 add 的币种校验路径不一致，说明校验分散。属于不变量可被绕过的设计缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:17-20 frozen dataclass ProductHighlight 的 detail 默认值安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:17-20`
  - 依据：detail 为 str 不可变默认值，frozen=True 下无共享可变状态问题，不构成缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:43-44 primary_sku 依赖 skus 顺序，未定义主 SKU 语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:43-44`
  - 依据：primary_sku 直接返回 skus[0]，__post_init__ 已保证 skus 非空，因此不会 IndexError。虽然“主 SKU”语义依赖插入顺序，但这是设计选择而非可证实的缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/sku.py:30-34 Sku.__post_init__ 未校验 price 非空，可能引发后续 AttributeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：__post_init__ 校验 sku_id 非空和 stock 非负，但未校验 price 是否为 Money 实例或非 None。若调用方传入 None，构造成功，后续使用 price 时才会报错。不过 dataclass 类型标注 price: Money 已表达契约，且 Money 的构造校验可能在别处；此处不校验 price 属于契约信任，不构成明确缺陷。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:22-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 内，VALID_ROLES 定义后未被使用（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:22-40`
  - 依据：模块定义了 VALID_ROLES = ('buyer', 'agent')，但 ConversationTurn.__post_init__ 只校验 session_id，未校验 role。任何拼写错误（如 'Agent'、'assistant'）都会被静默接受并落库，破坏对话流水的可读性与后续按 role 过滤/回放的正确性。VALID_ROLES 成为死代码，说明校验被遗漏。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：返回语句 `[vector or [] for vector in results]` 对 falsy 值做兜底。若内层客户端对某条文本返回空列表（合法但无意义的向量），结果仍是 []，看似无害；但若 results 中某项因 zip 长度不匹配而保持 None，也会被静默转成 []，调用方无法区分“未取到向量”与“向量为空”，后续 _cosine 会因长度不等返回 0.0 而静默不命中，掩盖了内层返回条数不足的问题。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 _key 未包含 model，换模型后可能复用旧模型向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块 docstring 明确写“key 用 sha256(model + text)”，但 _key 只对 text 做哈希，self._model 未参与。若同一 Redis 实例被不同模型（或不同维度）的客户端共用，换模型后仍会命中旧模型生成的向量，导致维度不匹配（_cosine 返回 0.0）或语义空间错位。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:74-82 embed_batch 逐条串行 await 缓存读取，批量场景退化为 N 次往返（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:74-82`
  - 依据：循环内对每条文本单独 `await self._safe_get(...)`，没有并发或批量 mget。批量 embedding 的典型用途是索引构建/批量召回，文本数可达数百，串行 Redis 往返会把延迟线性放大，抵消缓存带来的收益。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:128-136 zadd_and_count 的 expire 在 pipeline 中位于 zcard 之后，results[2] 索引正确但依赖命令顺序（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-136`
  - 依据：pipeline 中命令顺序为 zremrangebyscore、zadd、zcard、expire，results 依次对应，results[2] 确实是 zcard 的结果。索引正确，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:66-72 get_json 中 json.loads 失败后 await self.delete 未捕获异常，可能向上抛出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-72`
  - 依据：get_json 的契约是“全部读写都吞异常并降级为未命中”。get 调用被 try/except 包裹，但脏值分支里的 `await self.delete(key)` 位于 try 之外。delete 内部虽然自己吞了异常，但 delete 在 _client 为 None 时直接 return，且其 try 只包住 `await self._client.delete(key)`；如果 delete 本身在进入 try 之前出错（例如 self._client 属性访问异常，概率极低）或未来 delete 实现变化，异常会从 get_json 冒出。更实际的问题是：delete 的异常被吞掉，但 get_json 的脏值分支没有自己的 try，一旦 delete 抛出（例如 CancelledError 之外的 BaseException 子类），get_json 会违反“绝不抛异常”的契约。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:96-101 set_json 的 json.dumps 在 try 内但序列化失败会记录为“Redis 写失败”，掩盖真实原因（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:96-101`
  - 依据：json.dumps 确实在 try 内，序列化失败（如 value 含不可序列化对象）会被 except 捕获并记录为“Redis 写失败，跳过缓存”。虽然日志措辞不精确，但行为符合“缓存失败不影响主链路”的设计目标：不抛异常、不写入。这不是缺陷，只是日志分类略粗糙。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:66-72 get_json 脏值删除与 get_raw 的幂等键语义分离，但 get_json 仍可能误删非 JSON 的幂等键（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-72`
  - 依据：get_raw 的文档已说明幂等键必须走 get_raw 而非 get_json，避免被当脏值删除。只要调用方遵守该约定，get_json 删除脏值的行为是合理的。这是 API 使用约定问题，不是本文件缺陷。
- **[api_misuse/medium]** [api_misuse] app/infrastructure/cache/semantic_cache.py:132-133 lookup 中 has_history 参数未使用（与 remember 不对称）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:132-133`
  - 依据：lookup 与 remember 都声明了 has_history，remember 用它阻止写入，lookup 却完全忽略。这使“有历史不命中”的安全边界只在写入侧生效，读取侧失效，属于接口契约与实现不一致。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:178-181 remember 中 entries[:_BUCKET_LIMIT] 截断保留最旧条目（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-181`
  - 依据：append 后取前 30 条，实际保留的是最旧的 30 条而非“最近条数”，与注释“保留最近条数”措辞不符，但不会产生错误回复，只影响命中率，属注释与实现措辞偏差，不构成行为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:74-75 _cosine 对维度不一致返回 0.0 而非报错（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:74-75`
  - 依据：维度不一致时返回 0.0 视为未命中，符合“宁可多花一次调用也不能答错”的设计意图，不会产生错误回复。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:88-91 _normalize 只去尾部标点，问句中间标点差异导致缓存不共享（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:88-91`
  - 依据：归一化只压空白与去尾部标点，中间标点保留。这只是降低命中率，不会产生错误回复；语义相似度阈值本身会兜住这类差异，属于设计取舍而非缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-130 scope 参数被忽略，偏好指纹未进入桶 key，撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-130`
  - 依据：_bucket_key 的签名接收 scope，docstring 明确说明 scope 用于装载偏好指纹，且注释强调“桶 key 不含偏好指纹就会命中撤回前的旧回复”。但实现里 digest 只对 f"{self._namespace}\n{buyer_id}" 做哈希，scope 完全没有参与计算，返回的 key 与 scope 无关。因此 lookup/remember 传入不同 scope 时读写的是同一个桶：买家撤回“不要塑料”偏好后，scope 变化但 key 不变，仍会命中撤回前生成的旧回复，直接违反文件头“安全边界 2b”。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:132-140 lookup 忽略 has_history，带上下文的问句仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:132-140`
  - 依据：文件头安全边界 3 要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 只在 enabled 与 is_cacheable_query 上做判断，has_history 参数完全未使用。于是多轮会话中的问句（如“那款多少钱”）只要不含 _UNSAFE_PATTERNS 中的词，就会跨会话复用旧回复，答非所问。
- **[error_handling/low]** [error_handling] app/infrastructure/security/content_filter.py:35-52 sanitize_tool_output 对非 str 输入（None 之外）无防御，工具返回 dict/list 时抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:35-52`
  - 依据：函数签名标注 text: str，且 `if not text` 已处理 None/空串。工具结果在进入该层前按约定应已序列化为字符串；若上游传入 dict，属于调用方违反契约，而非本函数缺陷。记录为 not_a_defect 以免误报。
- **[security/medium]** [security] app/infrastructure/security/content_filter.py:24-32 content_filter 正则未覆盖大小写/空白变体，且 system prompt 模式会误伤正常商品描述（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：DANGEROUS_PATTERNS 中 `system\s*prompt` 与 `you\s+are\s+now` 无边界约束，会命中正常商品文案（如“this system prompts the buyer…”或“you are now able to…”），把正常内容替换为占位符，造成信息丢失；另一方面 `ignore\s+(all\s+)?previous\s+instructions?` 只匹配单空格分隔，`ignore   previous   instructions`（多空格）或 `Ignore previous instruction` 之外的换行/制表符变体（\s 已覆盖）尚可，但 `ignore all the previous instructions` 这类插入词不匹配，存在绕过。过滤层作为安全边界，误伤与漏检同时存在。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-64 audit_output 对空字符串返回 (True, text) 但 text 为 None 时返回 (True, None)，类型不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-64`
  - 依据：`if not text: return True, text` 对空字符串返回 (True, '')，对 None 返回 (True, None)。虽然返回类型标注为 tuple[bool, str]，但调用方若传入 None 会得到 None 而非 str。不过函数签名标注 text: str，调用方不应传 None；且 `not text` 对空字符串和 None 都短路，行为一致（不脱敏、安全）。这属于类型标注与运行时宽松的边界，不构成实际缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:38-40 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-40`
  - 依据：`r"\b(?:" + "|".join(_INTERNAL_TOOLS) + r")\b"` 将工具名直接拼入正则。当前 _INTERNAL_TOOLS 中所有名称仅含字母和下划线，无正则元字符，拼接安全。若未来新增含元字符的工具名（如 `foo.bar`）会引入正则注入/误匹配，但当前代码无此问题。

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，导致限流失效（fail-open）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：zadd_and_count 的文档说明用于跨进程限流。当 _client 为 None（REDIS_URL 未配置）或 pipeline 抛异常时，函数返回 0，调用方通常会把 0 解释为“窗口内计数为 0”，即未触发限流，从而完全放行。这与 set_if_absent 显式选择 fail-open 不同：那里返回 True 是“抢到锁/放行”的语义，而这里返回 0 是“计数为零”，会让限流器认为没有流量。若调用方用 `count > limit` 判断，Redis 故障期间限流被静默关闭，可能造成下游过载。
  - 争议对手：f90afb31b3cd

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain/catalog, app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 1 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 3 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 2 | `partition_gap` | — |
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
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 1 |
| `app/infrastructure/security` | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 19%（单元格值 = 独立 Agent 数）
