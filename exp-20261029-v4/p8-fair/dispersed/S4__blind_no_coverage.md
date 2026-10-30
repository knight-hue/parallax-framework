# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 19 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：21
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：53 个节点 / 72 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 20 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:130-132 _rank_by_relevance 注释声称“回到原始相对顺序输出”，实际按相似度排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:130-132`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但代码直接 `picked = [preference for _, _, preference in scored[:top_k]]`，scored 已按 (-score, index) 排序，输出顺序是相似度降序而非原始顺序。这与 _latest_first 的行为（复原原始顺序）不一致，且与注释承诺不符，会导致注入块行序随 query 变化而抖动。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 select() 用 [:top_k] 截断会把 dislike 也裁掉，违背“dislike 全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确承诺 dislike 全量保留、不参与 top_k 截断，但最终返回 `(dislikes + selected_likes)[:top_k]`。当 dislike 数量 >= top_k 时，dislikes 本身会被截断；当 dislikes 数量 < top_k 时，selected_likes 被截到 top_k - len(dislikes)，这本身没问题，但 dislike 超过预算时就会丢黑名单。例如 top_k=2、dislikes 有 3 条，只返回前 2 条 dislike，第 3 条被丢弃，正是文档所说的“推了用户明确拒绝的东西”的安全问题。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：__post_init__ 校验了 kind 与 statement，却漏掉 buyer_id。空 buyer_id 的偏好会被 append 写入，而 list_by_buyer/delete 都以 buyer_id 为键，这条记录将永远无法被正确检索或删除（成为孤儿数据），且 delete 的精确匹配语义也依赖 buyer_id 定位。同一次校验中遗漏一个必填字段，属于边界校验缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:29-30 created_at 用 object.__setattr__ 在 frozen dataclass 中赋值是正确做法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:29-30`
  - 依据：frozen=True 的 dataclass 在 __post_init__ 中直接赋值会抛 FrozenInstanceError，必须用 object.__setattr__ 绕过。这里正是标准写法，且仅在 created_at 为空时补默认值，不会覆盖调用方显式传入的时间。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-35 Money.from_major_units 对 JPY 等零小数币种按 100 换算，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-35`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 最小单位就是 1 日元（无小数）。from_major_units(1000, 'JPY') 会得到 100000 minor units，to_major_units 再除以 100 得 1000，看似自洽，但与真实 JPY 语义不符：任何按 ISO-4217 exponent 解释 amount_in_minor_units 的外部系统（支付网关、库存价格表）都会把 100000 当作 100000 日元，即放大 100 倍。注释也承认这是简化，但这是真实的价格错误风险。
- **[logic/low]** [logic] app/domain/catalog/money.py:37-44 Money.add/multiply 直接构造 Money 绕过 of() 校验，可产生非法值（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:37-44`
  - 依据：of() 是唯一做不变量校验（非负、币种受支持）的入口，但 add/multiply 用 `Money(...)` 直接构造，绕过校验。虽然当前输入经 of() 校验后 add/multiply 结果仍合法，但一旦有代码直接构造 Money（dataclass 构造器是公开的）或未来引入减法/负数，不变量就会被绕过。更直接的问题是：dataclass 本身不校验，`Money(-1, 'USD')` 可被任意构造，of() 的校验形同虚设。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 对空 detail 的 highlight 产生多余空格，但不影响召回正确性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：当 ProductHighlight.detail 为空时，f"{h.label} {h.detail}" 会产生尾随空格，join 后出现连续空格。这只是文本格式瑕疵，embedding 与关键词召回对多余空白不敏感，不构成功能缺陷。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-30 Sku.stock 为负校验存在，但 dataclass 非 frozen，stock 可在构造后被改为负数（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-30`
  - 依据：文档明确说明 stock 是只读参考数据、可变库存走 StockRepository，且刻意不提供 deduct/restore 方法。虽然 dataclass 非 frozen 允许外部直接赋值，但这是设计取舍而非本文件引入的缺陷；__post_init__ 已覆盖构造期校验。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:43-50 ConversationEventRecord 完全无校验，session_id/type 可为空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:43-50`
  - 依据：ConversationTurn 至少校验了 session_id，而同一文件中的 ConversationEventRecord 没有任何 __post_init__ 校验。空 session_id 或空 type 的事件会被 append_events 批量写入，之后无法按会话检索、也无法按事件类型回放，且因为批量写入不会逐条报错，问题被静默吞掉。两个同类值对象校验策略不一致，说明这是遗漏而非有意设计。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:78-78 embed_batch 用 `vector or []` 把合法空向量/零向量替换为空列表（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-78`
  - 依据：返回语句 `[vector or [] for vector in results]` 对 falsy 值做替换。若 inner 返回空列表（例如空文本的 embedding）或 results 中某项仍为 None（inner 返回数量少于 pending 时 zip 截断），会被静默替换成 []，调用方无法区分“未取到”与“空向量”，且长度与输入 texts 可能不一致。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:73-76 embed_batch 中 zip 截断导致结果错位/缺失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:73-76`
  - 依据：`zip(pending, fresh)` 在 fresh 长度小于 pending 时静默截断，剩余 results[index] 保持 None，最终被 `vector or []` 变成空列表返回，调用方拿到与输入不对齐的向量列表且无任何告警。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 embedding 缓存 key 未包含 model，换模型会串用旧向量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 声称 key 用 sha256(model + text)，但 _key 实际只哈希 text，self._model 从未参与。同一 Redis 实例上切换 embedding 模型后，旧模型的向量会被当作新模型结果返回，导致语义缓存相似度计算错误。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-126 set_if_absent 在 Redis 异常时返回 True 会破坏幂等语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-126`
  - 依据：这是文档明确声明的降级策略：Redis 不可用时宁可退化为无幂等保护也不拒绝服务。属于有意的可用性权衡，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:128-146 zadd_and_count 异常时返回 0 视为不限流（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-146`
  - 依据：与 set_if_absent 一致，是文档声明的 fail-open 降级策略，属于有意设计而非缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:76-82 get_json 对脏值调用 delete 可能再次抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:76-82`
  - 依据：delete 内部已 try/except 吞掉异常，因此 get_json 中 await self.delete(key) 不会向外抛出，脏值路径是安全的。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:168-172 remember 截断保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-172`
  - 依据：注释称“保留最近条数”，但 entries.append 后取 entries[:_BUCKET_LIMIT] 保留的是最早写入的 30 条，新条目在桶满后被立即丢弃，导致缓存永远停留在旧回复上，新回复无法进入缓存。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-116 语义缓存桶 key 忽略 scope，偏好变更后旧回复仍会命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-116`
  - 依据：_bucket_key 接收 scope 参数，但计算 digest 时只用了 namespace 和 buyer_id，scope 完全没有参与哈希。文档明确要求桶 key 必须带偏好指纹，否则买家撤回/新增偏好后仍会命中旧回复（例如回复里还写着已删除的偏好）。lookup/remember 都调用 _bucket_key(buyer_id, scope)，但 scope 被静默丢弃，导致 2b 安全边界失效。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:130-137 lookup 忽略 has_history，多轮上下文仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:130-137`
  - 依据：文档安全边界第 3 条要求会话内已有多轮上下文时不命中。remember 检查了 has_history，但 lookup 完全没有使用该参数，只要问句通过 is_cacheable_query 就会查缓存并返回命中。像“多少钱”这类不含 _UNSAFE_PATTERNS 的短问句在多轮上下文中会被错误复用。
- **[performance/low]** [performance] app/infrastructure/security/content_filter.py:30-38 content_filter 正则可能被超长输入拖慢（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:30-38`
  - 依据：模式均为简单字面量/有限量词，无嵌套量词导致的灾难性回溯；对工具返回文本逐条 subn 是线性开销，符合文档“微秒级”要求。

## 争议（需裁决）

- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:24-40 ConversationTurn.role 未校验，非法角色可写入流水（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-40`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验了 session_id，没有校验 role 是否属于 VALID_ROLES。VALID_ROLES 因此成为死代码，任何拼写错误（如 'Agent'、'assistant'、'user'）或空字符串都会被静默接受并落库，导致下游按 role 过滤/回放（bad case 采集）时漏数据或分类错误。这是值对象自身承诺的约束未实现，属于逻辑缺陷而非风格问题。
  - 争议对手：6ba6656d6a2f

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
| `3af4356ea741` | 1 | 0 | `partition_gap` | — |
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
| `app/application/memory` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

矩阵填充率 14%（单元格值 = 独立 Agent 数）
