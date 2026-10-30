# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 19 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：21
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：51 个节点 / 72 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 20 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:128-135 embed_batch 返回向量维度与 query 不一致时静默得 0 分而非降级（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-135`
  - 依据：_cosine 在维度不一致时返回 0.0，所有候选同分，随后按 index 稳定排序取前 top_k，等价于取原始顺序前 top_k。这不会崩溃也不会丢 dislike（dislike 不参与该路径），只是相关性失效退化为顺序截断，属于可接受的降级，不构成缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-139 相关性排序后未恢复原始相对顺序，与注释及 _latest_first 行为不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-139`
  - 依据：_rank_by_relevance 的注释声称“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但 picked 直接按相似度降序返回，并未按原始 index 重排。而 _latest_first 分支确实做了 `[p for p in likes if p in newest]` 的原始顺序复原。两条分支输出顺序语义不一致：相关性开启时注入块行序随 query 变化，可能造成同一批偏好每轮顺序抖动，与注释承诺相反。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:143-146 _latest_first 用 `in` 做成员判断，依赖 dataclass 相等性而非身份（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:143-146`
  - 依据：`p in newest` 使用 == 比较。若两条 BuyerPreference 字段完全相同（同 kind/statement/created_at），它们会被视为相等，导致两条都被保留或都被排除，结果条数可能偏离 top_k。但这是极端重复数据场景，且 BuyerPreference 通常带唯一 id/created_at，实际影响很小；更稳妥的写法是按 index 选取。记录为可疑但非确认缺陷。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 dislike 偏好被 top_k 截断，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单是安全问题。但 select() 最终返回 (dislikes + selected_likes)[:top_k]，当 dislike 数量超过 top_k 时，末尾的 dislike 会被切片丢弃；当 dislike 数量接近 top_k 时，like 也会被挤掉。例如 top_k=3、dislikes 有 5 条时，只注入前 3 条 dislike，另外 2 条忌口被静默丢弃，正是文档要防止的“推了用户明确拒绝的东西”。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:34-41 Money.add/multiply 直接构造绕过 of() 校验，可产生非法 Money（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:34-41`
  - 依据：of() 强制 amount 为非负 int 且 currency 受支持，但 add/multiply 用 Money(...) 直接构造，绕过校验。若通过 dataclass 直接构造出非法实例（如 amount 为 bool 或 currency 非法），add 会传播非法值而不报错，破坏“amount 必须非负整数”的不变量。
- **[logic/medium]** [logic] app/domain/catalog/money.py:30-32 Money.from_major_units 对 JPY 等零小数币种按 100 换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-32`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 最小单位就是 1 日元。from_major_units(1000, 'JPY') 返回 100000 分，to_major_units 又除 100，虽然往返一致，但与真实 JPY 语义不符；与外部系统（支付/展示）交互时金额被放大 100 倍。注释承认是“简化”，但这是跨境价格不变量，属于真实缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 在 highlights 为空时产生多余空格（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：highlight_text 为空串时，join 结果末尾会多一个空格。这只影响召回文本的空白，不影响分词/检索语义，属于无害的格式瑕疵，不构成缺陷。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:27-40 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:27-40`
  - 依据：定义了 VALID_ROLES = ('buyer','agent') 但 __post_init__ 只校验 session_id，role 可为任意字符串。存储层按 role 区分买家/客服流水，非法 role 会污染数据且无法在领域层拦截。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:78-84 embed_batch 用 `vector or []` 把合法空向量/None 静默转成空列表，且 zip 截断导致结果错位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-84`
  - 依据：若 inner.embed_batch 返回的列表长度短于 pending（部分失败或实现返回不足），zip 会静默截断，剩余 results[index] 保持 None，最终被 `vector or []` 变成空向量返回给调用方，调用方无法区分“未命中/失败”与“真实空向量”，会把空向量写入向量索引或参与余弦计算（_cosine 对空向量返回 0.0），造成静默错误而非显式异常。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 缓存 key 未包含 model，换模型后仍复用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块文档声称 key 用 sha256(model + text)，但 _key 只对 text 做哈希，self._model 从未参与。切换 embedding 模型后，同文本会命中旧模型向量，维度/语义不一致，导致向量检索错误或维度不匹配。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:135-141 close 使用 aclose，旧版 redis-py 无此方法会抛 AttributeError 被吞（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:135-141`
  - 依据：aclose 是 redis-py 4.2+ 的异步关闭方法，close 内部 try/except 吞掉异常，即使版本不兼容也不会导致崩溃，只是连接可能未优雅关闭。属于可接受的降级，不构成真实缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:126-126 zadd_and_count 的 member 若重复，zadd 更新分数而非新增，计数偏小（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:126-126`
  - 依据：zadd 对已存在 member 更新分数，这是滑动窗口计数的预期语义：同一 member 在窗口内只算一次。调用方需保证 member 唯一（如请求 ID）。docstring 未承诺对重复 member 去重计数，因此不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:66-72 get_json 在 json.loads 失败时 await self.delete(key)，但 delete 内部吞异常，脏值可能残留（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-72`
  - 依据：get_json 对脏值调用 self.delete(key)，delete 内部 try/except 吞掉异常。即使删除失败，下次读取仍会 json.loads 失败并再次尝试删除，行为是幂等且安全的（始终返回 None 视为未命中）。这不会导致错误结果，只是脏值可能短暂残留，属于可接受的降级。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:60-62 is_cacheable_query 用子串匹配“这个/那个/它”，会误伤正常商品咨询（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:60-62`
  - 依据：这是刻意的保守策略：宁可少缓存也不答错。误伤只导致缓存命中率下降，不会产生错误回复，属于设计取舍而非缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-124 语义缓存桶 key 忽略 scope，偏好指纹失效导致撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-124`
  - 依据：_bucket_key 的文档明确说 key = namespace + buyer_id + scope，且注释强调 scope（偏好指纹）必须参与 key，否则买家撤回“不要塑料”后仍会命中撤回前的旧回复。但实现里 sha256 只拼了 namespace 和 buyer_id，scope 参数完全没被使用，所有 scope 落到同一个桶。lookup/remember 传入的 scope 因此形同虚设，安全边界 2b 被破坏。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-141 lookup 忽略 has_history，会话内多轮上下文仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-141`
  - 依据：模块文档安全边界 3 要求“会话内已有多轮上下文时不命中”，remember 里检查了 has_history，但 lookup 只检查 enabled 和 is_cacheable_query，完全没用 has_history 参数。于是带上下文的问句（如“那这款呢”）仍会命中缓存，答非所问。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-55 sanitize_tool_output 对已过滤文本重复替换，且占位符本身可能被后续模式再次匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-55`
  - 依据：占位符“[内容已过滤：疑似注入]”不含任何 DANGEROUS_PATTERNS 的关键词（ignore/system prompt/you are now 等），后续模式不会再次匹配它，因此不会出现重复替换或无限膨胀。逐个 pattern 顺序 subn 是安全的。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回安全，但 None 输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：`if not text: return True, text` 对空串和 None 都返回 (True, 原值)，不会进入正则替换，因此 None 也不会抛异常。类型标注为 str，调用方传 None 属于契约外，但函数本身对 falsy 输入是安全的，不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-45 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-45`
  - 依据：`r"\b(?:" + "|".join(_INTERNAL_TOOLS) + r")\b"` 直接把工具名拼进正则。当前 _INTERNAL_TOOLS 全部是字母和下划线，不含正则元字符，拼接结果合法且能正确匹配。若未来加入含 `.` 或 `+` 的工具名会出问题，但就当前代码而言不是缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-133 zadd_and_count 在 Redis 不可用时返回 0，与 set_if_absent 的 fail-open 策略不一致，导致限流失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-133`
  - 依据：zadd_and_count 的 docstring 说用于跨进程限流。当 self._client is None（REDIS_URL 未配置）时直接 return 0，异常分支也 return 0。调用方通常以 `count > limit` 判断是否限流，返回 0 意味着永远不超限，即限流完全失效。这与同文件 set_if_absent 明确选择的 fail-open（返回 True 放行）语义方向一致，但限流场景下返回 0 是“放行”还是“拒绝”取决于调用方约定；若调用方按 `count >= limit` 或 `count > 0` 判断，行为会反转。更关键的是：Redis 故障时返回 0 会让限流静默失效，而 docstring 只写了“按不限流处理”，没有让调用方感知降级。这是真实的行为缺陷（限流在缓存故障时被绕过），而非风格问题。
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
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 4 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 2 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 1 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure/security` | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 15%（单元格值 = 独立 Agent 数）
