# Parallax 运行报告 `9d3e85392fc8`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 13 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 48 | 支持不足、相关性超限或尚待验证 |
| 争议 | 14 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：3｜停止原因：`max_rounds_reached`
- 参与 Reader：9 个（每轮全新身份）
- 账本条目：176
- 独立性画像：有效通道 2.99 / 9，归一化 33.2%，证据重叠 44.2%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：237 个节点 / 1010 条边
- 去共同上游后的通道：9；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 38 | 100% | 14% |
| 1 | 3 | 22 | 100% | 22% |
| 2 | 3 | 15 | 100% | 29% |

## 高置信结论

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:88-90 top_k<=0 时连 dislike 也一并丢弃（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-90`
  - 依据：文档的安全底线是 dislike 全量保留、不参与截断。但 top_k<=0 分支直接 return []，把黑名单也清空了。若调用方因配置错误或预算计算得到 top_k=0，用户的所有忌口都会失效，属于边界条件下违反安全约束。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:130-132 _rank_by_relevance 注释声称回到原始顺序但实际未排序（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:130-132`
  - 依据：注释说“回到原始相对顺序输出，避免注入块的行序每轮抖动”，但 picked 是按相似度排序后的结果，代码并没有按原始 index 重新排序。因此输出顺序是相似度顺序而非原始顺序，与注释承诺不符。虽然这不一定是功能错误（相似度顺序也可接受），但注释与实现不一致，且如果调用方依赖稳定顺序（如缓存 key），会导致每轮顺序抖动。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-96 dislike 全量保留的安全底线被 top_k 截断破坏（确认存在缺陷）
  - 独立来源 4 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-96`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，因为漏掉黑名单是安全问题。但 select() 的返回语句是 (dislikes + selected_likes)[:top_k]，当 dislikes 数量 >= top_k 时，dislikes 自身会被截断；当 dislikes 数量 < top_k 时，dislikes 全部保留但 like 被挤占。更关键的是：当 dislikes 数量超过 top_k 时，部分 dislike 被丢弃，直接违反安全底线。例如 top_k=2、dislikes 有 3 条时，只返回前 2 条 dislike，第 3 条黑名单丢失。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:31-34 from_major_units 用 round 处理浮点，存在银行家舍入与精度误差（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：Python 的 round 使用银行家舍入（round-half-to-even），且 float 本身有二进制表示误差。例如 round(2.675 * 100) 得到 267 而非 268；round(0.5*100)=50 但 round(1.5*100)=150、round(2.5*100)=250 看似正常，而 round(0.125*100)=12（应为 13 若按四舍五入）。金额换算应使用 Decimal 或整数运算，否则会出现 1 分钱级别的系统性偏差。
- **[logic/medium]** [logic] app/domain/catalog/money.py:15-18 dataclass 构造函数本身不强制不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r1-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:15-18`
  - 依据：Money 是 frozen dataclass，但 __init__ 不做任何校验，of() 只是静态工厂。任何代码（包括本文件的 add/multiply）都可以用 Money(-1, 'XXX') 构造非法实例，文档声称的“不变量”并未在类型层面强制。这是设计缺陷，导致校验可被绕过。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:43-50 ConversationEventRecord 未校验 session_id/type，与 ConversationTurn 校验不一致（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r1-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:43-50`
  - 依据：ConversationTurn 对 session_id 做了非空校验，但同一模块的 ConversationEventRecord 完全没有 __post_init__，session_id 和 type 均可为空。append_events 批量写入时，空 session_id 的事件会落成孤儿记录，事后按 session 追溯时查不到，违背该模块“供事后追溯、客服排查”的设计目的。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:24-38 ConversationTurn.role 未校验取值，非法角色可写入存储（确认存在缺陷）
  - 独立来源 3 个：reader-r1-0, reader-r1-2, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-38`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，从未使用 VALID_ROLES。任何调用方传入 role="system"/"tool"/空串都能构造成功并落库，导致 list_turns 回放时按 role 分支的消费方（客服排查、bad case 回放）拿到未定义角色。VALID_ROLES 的存在说明作者本意是要校验的，属于遗漏而非设计。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:78-82 embed_batch 用 zip 对齐 pending 与 fresh，回源结果数量不足时静默丢向量（确认存在缺陷）
  - 独立来源 2 个：reader-r1-2, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-82`
  - 依据：zip(pending, fresh) 在 fresh 比 pending 短时会静默截断，剩余 results[index] 保持 None，最终返回空列表 []，调用方拿到与输入等长但部分为空的向量列表，且没有任何告警。EmbeddingClient 契约要求返回与输入一一对应的向量，inner 实现异常或返回数量不符时这里会掩盖错误。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:36-38 _key 未包含 model，换模型后可能复用旧模型向量（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r1-1, reader-r2-1, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:36-38`
  - 依据：模块 docstring 声称 key 用 sha256(model + text)，但 _key 实际只对 text 做 sha256，self._model 从未参与。若同一 Redis 实例被不同模型复用（或切换模型后未清缓存），会拿到旧模型生成的向量，维度/语义都可能不匹配，导致检索错误。
- **[performance/low]** [performance] app/infrastructure/cache/cached_embedding_client.py:66-74 embed_batch 串行逐条 await 缓存读取，批量场景下 N 次 Redis 往返（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-74`
  - 依据：循环内对每个 text 单独 `await self._safe_get(...)`，是串行 N 次网络往返；批量 embedding 的初衷就是减少往返，这里把省下的往返又加回来了。文本数大时（如批量索引商品）延迟线性叠加。可用 asyncio.gather 或 mget 并行化。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:108-113 SemanticCache._bucket_key 忽略 scope 参数，偏好指纹不生效（确认存在缺陷）
  - 独立来源 5 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r1-2, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-113`
  - 依据：docstring 与模块注释（2b）都强调桶 key 必须带买家偏好指纹 scope，偏好变更后旧回复自动失效。但 _bucket_key 的 f-string 只拼接了 namespace 和 buyer_id，scope 形参完全未使用。结果：买家撤回“不要塑料”偏好后，语义相近的提问仍会命中撤回前的旧回复，向用户断言已删除的偏好——正是注释里说“实测踩过”的 bug。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:137-141 lookup 忽略 has_history，带上下文的会话仍会命中缓存（确认存在缺陷）
  - 独立来源 6 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r1-2, reader-r2-1, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:137-141`
  - 依据：模块文档安全边界 3 要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 完全没有使用该参数。只要问句本身不含 _UNSAFE_RE 关键词（例如“这款多少钱”不含“这个/刚才”等），即使会话已有多轮上下文也会命中跨会话缓存，答非所问。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:178-182 remember 截断使用 entries[:_BUCKET_LIMIT] 保留最旧而非最新条目（确认存在缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r0-2, reader-r1-1, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：entries 按追加顺序排列，新条目在末尾。`entries[:_BUCKET_LIMIT]` 取前 30 条，即保留最旧的 30 条并丢弃刚追加的新条目。当桶满 30 条后，新写入的回复永远无法进入缓存（每次 append 后又被截掉），缓存内容永久冻结在最早的 30 条，与注释“保留最近条数”相反。这会导致新回复无法被复用，且旧回复长期占据桶。

## 待验证（孤证）

> ⚠️ 本节共 **48** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:33-34 _cosine 对长度不一致向量返回 0.0，可能把有效偏好误判为不相关（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：当 embedder 返回的向量维度与 query 向量不一致时返回 0.0，属于防御性降级而非崩溃；调用方 _rank_by_relevance 已校验 vectors 数量与 likes 一致，维度不一致属于 embedder 契约违约。返回 0.0 会让该偏好排到末尾，但不会抛异常，符合“选偏好失败不阻断对话”的设计。因此不认定为缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:55-62 render_preference_hint 在 preferences 为空时仍输出空块（确认并非缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:55-62`
  - 依据：空列表时 render_preference_lines 返回空串，hint 变成只有头尾标签的块。这不会导致错误行为，只是多注入一个空块；调用方通常会在 select 返回空时跳过注入。不构成缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-32 embed_batch 返回向量维度不一致时 _cosine 静默返回 0，可能误排黑名单外的相关偏好（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-32`
  - 依据：_cosine 在维度不一致时返回 0.0 是防御性降级，不会抛异常；虽然会降低排序质量，但不会导致错误结果（最差退化为同分按 index 排序）。且 _rank_by_relevance 已校验向量数量，维度不一致属于上游 embedder 违约，此处静默处理可接受。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:47-58 PreferenceStore.delete 契约未定义 buyer_id 校验，且不区分 kind 可能误删（确认并非缺陷）
  - 独立来源 3 个：reader-r0-2, reader-r1-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-58`
  - 依据：文档已明确说明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是有意的设计决策而非缺陷；精确匹配策略也已在文档中解释。不构成缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-33 BuyerPreference 为 frozen dataclass，__post_init__ 用 object.__setattr__ 设置 created_at 合法（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：frozen dataclass 中通过 object.__setattr__ 修改字段是标准做法，可正常工作。kind 与 statement 校验也正确。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/money.py:35-43 Money.add/multiply 直接调用构造器绕过 of() 校验，可构造非法 Money（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:35-43`
  - 依据：of() 是唯一做非负整数与币种校验的入口，但 add/multiply 用 Money(...) 直接构造，绕过校验。虽然当前输入来自已校验的 self，结果仍非负，但 multiply 的 quantity 校验与 add 的币种校验是重复实现而非复用 of()，一旦后续有人给 Money 增加新不变量（如上限、币种扩展），add/multiply 会静默产出违反不变量的实例。这是可复现的封装不一致：Money(1, 'USD').add(Money(2, 'USD')) 不经过 of()。
- **[error_handling/low]** [error_handling] app/domain/catalog/money.py:36-38 add 未校验 other 类型，非 Money 对象触发 AttributeError（确认存在缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-38`
  - 依据：_assert_same_currency 直接访问 other.currency，若传入非 Money（如 None 或 int），会抛出 AttributeError 而非清晰的 ValueError/TypeError，错误信息不友好且难以定位。
- **[logic/low]** [logic] app/domain/catalog/money.py:40-43 multiply 直接构造实例，绕过 of() 校验（确认存在缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:40-43`
  - 依据：multiply 校验了 quantity，但返回时用 Money(...) 而非 Money.of(...)，若 self 本身是非法构造的实例（如负金额），结果仍为非法且不报错。与 add 同类问题：不变量只在 of() 中强制，构造函数本身无保护。
- **[api_misuse/medium]** [api_misuse] app/domain/catalog/ports/retrieval_ports.py:55-58 Reranker.rerank 契约要求等长返回但无任何校验，调用方按索引对齐会错位（确认存在缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:55-58`
  - 依据：docstring 明确承诺"返回与 documents 等长的精排分数"，但端口是 ABC，没有任何机制保证实现遵守。UseCase 侧典型写法是 zip(documents, scores) 或按索引取分，一旦 HTTP reranker 返回条数少于 documents（截断、去重、超时部分返回），zip 会静默丢弃尾部文档，导致召回结果被无声截断；返回条数多于 documents 则索引越界。文档只写了"失败抛异常"，未覆盖"成功但长度不符"这一真实故障模式，属于契约缺口。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:28-31 VectorHit 未校验 score 与 product_id，空 product_id 可进入召回结果（确认并非缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:28-31`
  - 依据：VectorHit 是纯数据载体，product_id 由向量库返回，向量库的 point id 本身即商品 id，空值意味着索引写入阶段已出错。在端口层加校验属于防御性冗余，且会掩盖上游 bug。此处不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/ports/retrieval_ports.py:41-43 ProductVectorIndex.upsert_products 未约束 products 与 embeddings 等长（确认存在缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:41-43`
  - 依据：upsert_products 接收两个平行列表 products 和 embeddings，端口未声明二者必须等长，也未声明不等长时的行为。实现若用 zip 合并，短的一侧会静默截断，导致部分商品未入索引（召回缺失且无告警）；若用索引访问则越界。embed_batch 返回条数少于输入（部分失败）是 embedding 服务的常见行为，正好会触发该场景。
- **[error_handling/low]** [error_handling] app/domain/catalog/ports/retrieval_ports.py:47-50 Reranker.rerank 返回长度未校验，调用方按等长假设使用（非缺陷）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/ports/retrieval_ports.py:47-50`
  - 依据：端口 docstring 已明确约定返回与 documents 等长的分数，长度校验责任在实现方与调用方（UseCase 负责降级）。端口本身是抽象契约，不承担运行时校验职责，因此不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:38-39 Product.primary_sku 在 skus 为空时抛 IndexError 而非受控异常（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:38-39`
  - 依据：__post_init__ 已强制 skus 非空，构造成功的 Product 不会出现空 skus；除非调用方在构造后直接修改 skus 列表（dataclass 非 frozen）。这是可变性带来的理论风险，但当前代码路径下 primary_sku 安全。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:41-42 Product.primary_sku 在 skus 为空时 IndexError，但 __post_init__ 已保证非空（确认并非缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:41-42`
  - 依据：__post_init__ 在构造时校验 skus 非空，因此 primary_sku 的 skus[0] 不会越界。除非有人绕过构造直接修改 skus 列表（dataclass 非 frozen），但这是调用方违约。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-38 Product 为可变 dataclass 且 __post_init__ 校验可被绕过（非缺陷）（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-38`
  - 依据：Product 未使用 frozen=True，skus 列表在构造后仍可被清空，从而绕过 __post_init__ 的“至少一个 Sku”不变量。但这是领域模型的常规可变聚合写法，当前仓库内没有代码在构造后修改 skus；仅凭潜在可变性不足以判定为真实缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 在 highlights 为空时产生多余空格（非缺陷）（确认并非缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：当 highlights 为空时 highlight_text 为空字符串，join 结果末尾会多一个空格。这只是检索文本的空白差异，不影响召回语义，也不构成错误行为。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-32 Sku.stock 仅校验非负，未校验类型，浮点/布尔值可绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-32`
  - 依据：`if self.stock < 0` 对 bool 和 float 也能工作（True<0 为 False，-0.5<0 为 True），不会崩溃；stock 作为初始库存只读参考，类型宽松不直接导致错误行为。缺少类型校验属于风格/健壮性问题，未构成可复现缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/sku.py:15-15 Sku 依赖的 Money 模块未在给定文件中，无法验证 price 校验（确认并非缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:15-15`
  - 依据：Sku 只校验 sku_id 与 stock，未校验 price 是否为正/非空。但 Money 类型本身可能已保证非负，且给定文件不含 money.py，无法确认缺失校验会导致错误行为。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-27 Sku.stock 注释声明只读但 dataclass 未冻结，可被就地修改（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-27`
  - 依据：文档明确说明 stock 是初始库存、可变库存走 StockRepository，并刻意不提供 deduct_stock。dataclass 未 frozen 意味着仍可 `sku.stock -= 1`，但这是约定层面的约束，代码中没有任何路径执行该操作，无法证实为运行时缺陷。
- **[api_misuse/medium]** [api_misuse] app/domain/session/ports/conversation_store.py:24-40 ConversationTurn 文档声称 turn_index 可留空，但类中根本没有 turn_index 字段（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-40`
  - 依据：类 docstring 写“turn_index 由存储层按会话自增，写入时可留空”，list_turns 的契约也写“按 turn_index 升序返回”，但 ConversationTurn 数据类没有任何 turn_index 字段。存储层无法把自增序号回填到该对象，list_turns 返回的 ConversationTurn 也无法携带 turn_index，导致“按 turn_index 升序”的契约无法在返回类型上表达，调用方拿不到排序依据。这是接口契约与数据模型不一致的真实缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/session_store.py:17-27 SessionStore 端口缺少 delete/clear 能力，会话快照无法清理（确认并非缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-27`
  - 依据：端口只定义 save/load，没有删除接口。但这是有意的端口最小化设计，注释说明“端口按更严格的一方定义”。缺少 delete 属于能力缺失而非实现错误，且无法从给定代码证明存在调用方需要删除。不判定为缺陷。
- **[resource_leak/low]** [resource_leak] app/domain/session/ports/session_store.py:17-26 SessionStore 端口无删除/过期接口，会话快照无法清理（确认并非缺陷）
  - 独立来源 1 个：reader-r1-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/session_store.py:17-26`
  - 依据：端口只定义 save/load，确实没有 delete。但这是端口最小化的合理设计：清理可由实现层（文件 TTL、Redis expire、DB 定时任务）自行完成，不必暴露给 Domain。ConversationStore 同样没有 delete 接口，说明这是有意的架构取舍而非遗漏。不报告为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:88-88 embed_batch 用 `vector or []` 兜底，零向量/空向量被静默替换（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:88-88`
  - 依据：results 中每个位置要么是缓存命中的非空 list，要么被 fresh 回源结果覆盖。若 inner.embed_batch 返回的向量本身是空 list，`vector or []` 仍返回 []，行为与直接返回一致；若返回 None（类型违约），则被替换为 []，属于对上游违约的容错而非引入错误。正常路径下不会把有效向量误判为空。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:83-86 embed_batch 中 zip(pending, fresh) 长度不匹配时静默丢结果（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:83-86`
  - 依据：若 inner.embed_batch 返回的向量数量少于 pending 数量（上游实现缺陷或部分失败），zip 会静默截断，未被填充的 results 位置保持 None，最终被 `vector or []` 变成空向量返回给调用方。调用方拿到长度正确但内容为空的向量，会在下游余弦相似度计算中恒为 0（_cosine 对零向量返回 0.0），导致检索/缓存静默失效且无任何日志。缺少长度校验使上游错误被掩盖。
- **[logic/medium]** [logic] app/infrastructure/cache/cached_embedding_client.py:76-82 embed_batch 用 `vector or []` 把合法的空向量/零向量静默替换为空列表，且 zip 长度不匹配时结果被静默丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-82`
  - 依据：1) 返回语句 `[vector or [] for vector in results]` 会把任何 falsy 的向量（空列表，或理论上长度为 0 的向量）替换成 []，调用方无法区分“未命中且回源失败”与“合法空向量”。2) 更关键的是 `zip(pending, fresh)`：如果 inner.embed_batch 返回的列表比 pending 短（部分实现/降级实现可能返回不完整结果），zip 会静默截断，剩余 results[index] 保持 None，最终变成 []，且没有任何日志或异常。调用方拿到长度正确但内容为空的向量，会把它写进向量索引或做余弦相似度，导致静默的错误召回。3) 缓存命中判断 `isinstance(cached, list) and cached` 也把空向量当作未命中，与回源结果不一致。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:135-140 close 使用 aclose，但旧版 redis-py 可能只有 close 方法（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:135-140`
  - 依据：redis.asyncio 的 Redis 类在 redis-py 4.2+ 提供 aclose（4.2 之前是 close）。若版本过旧，aclose 不存在会抛 AttributeError，被 except 捕获并 pass，连接不会被关闭但不会导致崩溃。属于资源泄漏的轻微风险，但被吞异常掩盖。考虑到项目使用 redis.asyncio（4.2+ 才有该模块），aclose 应存在。不构成确认缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:118-130 zadd_and_count 在 pipeline 中 zadd 使用 now 作为 score，但 zremrangebyscore 用 now-window 清理，若 now 为 0 或负数则清理范围异常（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：now 由调用方传入，通常是 time.time() 或 monotonic 时间戳，远大于 window_seconds。zremrangebyscore(key, 0, now - window_seconds) 在 now < window_seconds 时会得到负上界，Redis 会清理 score <= 负数的成员，而 zadd 用 now 作为 score，不会误删本次成员。只有在 now 为负数这种非现实输入下才有问题，不构成实际缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:130-137 zadd_and_count 的 zcard 在事务中读取的是 zadd 之后的值，但 expire 与 zcard 顺序导致 TTL 可能被覆盖为更短值（确认并非缺陷）
  - 独立来源 1 个：reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:130-137`
  - 依据：expire 使用 int(window_seconds)+1，每次调用都会重置 TTL 为固定窗口长度，对滑动窗口语义而言是合理的（窗口内持续有请求则键持续存在，窗口结束后自然过期）。zcard 在 zadd 之后执行，返回包含本次的计数，符合“加入本次后返回窗口内当前数量”的文档。不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:92-97 set_json 的 ttl_seconds 若为 0 或负数，Redis SET ex 会报错，被吞掉导致缓存未写入（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:92-97`
  - 依据：ttl_seconds 为 0 或负数时 Redis 会返回错误，被 except 捕获并记录 warning，缓存未写入但主链路不受影响。这是降级策略的预期行为。调用方应保证 ttl_seconds > 0，但即使传入非法值也不会导致错误行为（只是缓存不生效）。不构成缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/redis_cache.py:73-76 get_json 在 json.loads 失败后 await delete，但 delete 内部再次检查 _client，若期间被置 None 则跳过（确认并非缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:73-76`
  - 依据：_client 只在 __init__ 中赋值，运行期不会被置 None（close 不置 None）。不存在并发置 None 的路径。不构成缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-128 set_if_absent 在 Redis 故障时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-128`
  - 依据：文档字符串明确说明这是有意的降级策略：Redis 不可用时返回 True 视为抢到，宁可退化成没有幂等保护也不拒绝服务。这是显式的设计取舍而非缺陷。但需注意：若该返回值同时被用作分布式锁，故障期间所有请求都会“抢到锁”，并发保护完全失效——这是设计已知代价，调用方需自行承担。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:122-129 zadd_and_count 的 pipeline 中 expire 在 zcard 之后执行，但 results[2] 取的是 zcard 结果，索引正确（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:122-129`
  - 依据：pipeline 命令顺序为 zremrangebyscore(0)、zadd(1)、zcard(2)、expire(3)，results[2] 确实是 zcard 结果。索引正确。
- **[security/medium]** [security] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，导致限流失效（fail-open）（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：zadd_and_count 用于跨进程限流，返回窗口内计数。当 _client 为 None（REDIS_URL 未配置）或 pipeline 抛异常时，函数返回 0，调用方会认为窗口内没有任何请求，从而完全放行。这与 set_if_absent 的 fail-open 设计一致，但限流场景下 fail-open 意味着 Redis 故障时所有限流保护消失，可能被恶意流量打穿。注意：这是设计取舍，但文档字符串声称“用于跨进程限流”，而实现上 Redis 不可用时返回 0 会让限流器认为“无请求”，与“不限流”等价。如果调用方依赖此方法做安全限流，则 Redis 故障即等于无保护。
- **[security/medium]** [security] app/infrastructure/cache/redis_cache.py:128-143 zadd_and_count 在 Redis 故障时返回 0，导致限流失效（fail-open）（确认存在缺陷）
  - 独立来源 1 个：reader-r1-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-143`
  - 依据：zadd_and_count 被文档描述为跨进程限流的核心（模块三多 worker 时替代进程内信号量）。当 Redis 不可用或 pipeline 抛异常时，函数返回 0，调用方通常以 `count > limit` 判断是否限流，0 永远不大于 limit，于是所有请求被放行。这与 set_if_absent 的 fail-open 设计一致，但对限流而言意味着 Redis 一挂就等于完全没有限流保护，属于安全降级缺陷。注意：这是有意为之的 fail-open 策略，但文档未提示调用方需要额外兜底，且返回 0 与“窗口内真实计数为 0”无法区分，调用方无法感知降级。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:44-50 _UNSAFE_RE 中“这个/那个/它”等单字词导致大量正常问句被误判为不可缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:44-50`
  - 依据：模式包含裸字符“它”“这个”“那个”，会匹配到“其它”“这个价位有什么推荐”等本可缓存的问句，使语义缓存命中率大幅下降（性能退化而非正确性错误）。属于过度保守的边界问题，与注释“只缓存检索/咨询类问句”的意图不完全一致。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:168-175 remember 读-改-写桶无并发保护，并发写入会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r1-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:168-175`
  - 依据：remember 先 _load_entries 读出整个桶，append 后再 set_json 整体覆盖。两个并发请求（同一 buyer 不同问句）会各自读到旧桶，后写者覆盖先写者，导致先写入的条目丢失。RedisCache 的 set_json 是整体覆盖而非原子追加，没有 CAS/锁。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:152-158 lookup 中 entry.get('vector', []) 对非列表向量调用 _cosine 可能抛异常（确认并非缺陷）
  - 独立来源 4 个：reader-r0-1, reader-r0-2, reader-r1-2, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:152-158`
  - 依据：entry 来自本模块 remember 写入的结构，vector 一定是 list[float]。若缓存被外部污染成非列表，_cosine 的 len() 可能抛 TypeError，但 lookup 没有 try 包裹该循环。不过这是缓存数据被破坏的极端情况，且 _load_entries 已做 list 校验，正常路径不会触发，不认定为缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-56 is_cacheable_query 用子串正则匹配，'它' 等单字会误伤正常问句（确认并非缺陷）
  - 独立来源 1 个：reader-r1-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-56`
  - 依据：_UNSAFE_RE 包含 '它'、'这个' 等，会把含这些字的问句判为不可缓存。这是保守策略（宁可少缓存也不答错），属于设计取舍而非缺陷；误判只降低命中率，不产生错误回复。
- **[security/high]** [security] app/infrastructure/cache/semantic_cache.py:108-114 SemanticCache._bucket_key 忽略 scope 参数，偏好指纹未进入 key，撤回偏好后仍命中旧回复（确认存在缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:108-114`
  - 依据：docstring 与注释反复强调 scope（买家偏好指纹）必须进入桶 key，否则撤回偏好后会命中旧回复并断言已删除的偏好。但实现里 `digest = sha256(f"{self._namespace}\n{buyer_id}")`，scope 参数完全没被使用，`_bucket_key(buyer_id, scope)` 的 scope 是死参数。lookup/remember 都传了 scope，但 key 相同，等于偏好变更不失效缓存。这正是注释里“实测踩过”的场景，属于安全/隐私缺陷（向用户断言已撤回的偏好，且可能泄露偏好信息）。
- **[error_handling/high]** [error_handling] app/infrastructure/security/__init__.py:12-16 output_guard 导入 content_filter 模块，但该文件不在仓库文件列表中，可能导致 ImportError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:12-16`
  - 依据：security/__init__.py 在包初始化时无条件执行 `from app.infrastructure.security.content_filter import (...)`。给定的 6 个文件中并不包含 content_filter.py，若该模块实际缺失（或导入链上有循环/异常），任何 `import app.infrastructure.security` 都会在包初始化阶段抛出 ImportError，导致 output_guard 也无法被导入，L4 输出审核整体失效。注意：仅凭文件列表无法 100% 断定 content_filter.py 不存在（列表可能只是抽样），因此该结论依赖“该模块确实缺失”这一前提。
- …另有 8 条未列出

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/buyer/preference.py:32-33 created_at 只判空不校验格式，非法时间字符串会被原样接受（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r1-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:32-33`
  - 依据：created_at 是 str 类型，__post_init__ 仅在为空时补默认值，传入 'not-a-date' 或本地时区字符串都会被接受。下游若按 created_at 排序或做时间窗口过滤（如“最近 30 天偏好”），非法/非 UTC 字符串会导致排序错乱或解析异常。
  - 争议对手：0bd312d8f501, 42c07692cfbd, b37acd9be768
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:45-46 to_major_units 固定除以 100，对 JPY 返回错误金额（确认存在缺陷）
  - 独立来源 1 个：reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-46`
  - 依据：与 from_major_units 对称的问题：JPY 最小单位是 1，但 to_major_units 固定 /100，导致 JPY 金额被缩小 100 倍，__str__ 输出也随之错误。
  - 争议对手：e889cf61bc77
- **[logic/medium]** [logic] app/domain/catalog/money.py:36-38 Money.add 绕过不变量校验，直接构造实例（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r1-0, reader-r1-1, reader-r2-0, reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:36-38`
  - 依据：add() 直接调用 Money(...) 构造函数而非 Money.of(...)，因此绕过了 of() 中的非负整数与币种校验。虽然 add 自身通过 _assert_same_currency 校验了币种，但金额校验被跳过。更关键的是，dataclass 的 __init__ 本身不做任何校验，任何代码都可以用 Money(-1, 'XXX') 构造非法实例，of() 的校验形同虚设。add 的返回值因此可能携带非法状态（例如 self 本身是非法构造的实例时）。
  - 争议对手：d89e7b1a01a2
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:36-38 ConversationTurn 未校验 buyer_id 与 content，与 BuyerPreference 的校验强度不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r2-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:36-38`
  - 依据：同仓库的 BuyerPreference.__post_init__ 对必填字段做了非空校验（statement required），而 ConversationTurn 只校验 session_id，buyer_id 和 content 允许为空串。空 buyer_id 会让按买家维度的追溯/客服排查查不到记录，空 content 会写入无意义的对话流水。这是值对象不变量缺失导致的边界缺陷。
  - 争议对手：fa2551799fc6
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:78-78 embed_batch 用 `vector or []` 把合法的零向量/空结果静默替换为空列表（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-78`
  - 依据：返回时 `[vector or [] for vector in results]` 会把 None 和空列表都变成 []，但也会把任何 falsy 的向量（如 []）统一成 []。更关键的是：若 inner.embed_batch 返回的条数少于 pending 条数，zip 会截断，剩余 results[index] 保持 None，最终被静默替换为 []，调用方拿到长度正确但内容为空的向量，且无任何告警。这属于边界处理缺陷。
  - 争议对手：0bf5c4871373, 5adadae35e5b, 5adadae35e5b, 6421d7b14030, 6421d7b14030, acbdca1f8d4b
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:122-140 zadd_and_count 在 Redis 故障时返回 0，限流完全失效（确认存在缺陷）
  - 独立来源 1 个：reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:122-140`
  - 依据：该方法用于跨进程限流，返回窗口内计数。Redis 不可用或 pipeline 异常时返回 0，调用方会认为窗口内无请求从而放行全部流量，限流形同虚设。与 set_if_absent 类似，把“缓存降级”策略套用到安全/配额控制上，导致保护机制在故障时反而完全打开。
  - 争议对手：8f92dbc781c3, d1b93614ea49
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:62-68 get_json 在 json.loads 失败时 await delete 未捕获异常，破坏“缓存故障不挂主链路”的承诺（确认存在缺陷）
  - 独立来源 1 个：reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:62-68`
  - 依据：get_json 的 get 调用被 try/except 包裹，但脏值分支里的 await self.delete(key) 位于 except ValueError 块内，delete 自身虽吞异常，但这里的问题在于：json.loads 只捕获 ValueError，若 raw 是合法 JSON 但结构异常不影响；真正的问题是 delete 是异步调用，若 Redis 连接在 get 成功后断开，delete 内部已吞异常所以安全。重新审视：delete 内部确实 try/except pass，因此不会抛出。此条不成立。
  - 争议对手：0c5db21f018a, 4b08c545e7f8, 5803b9ba41f7, 5803b9ba41f7, 6a8afbb08b24, c53fc98a7633
- **[logic/high]** [logic] app/infrastructure/cache/redis_cache.py:108-120 set_if_absent 在 Redis 故障时返回 True，幂等键与分布式锁退化为无保护，可能重复执行副作用（确认存在缺陷）
  - 独立来源 1 个：reader-r1-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:108-120`
  - 依据：文档声称“宁可退化成没有幂等保护，也不能因缓存故障拒绝服务”，但 set_if_absent 同时被用于幂等键与分布式锁。返回 True 表示“抢到”，在 Redis 故障时所有并发请求都会认为自己是第一个，导致幂等语义完全失效（重复下单/重复扣款）以及分布式锁互斥失效（多 worker 同时进入临界区）。这是把可用性优先策略错误地套用到正确性关键的锁语义上。
  - 争议对手：04cad3af6e9a, a061ea7d7dc0, bb20ad674b69, bb20ad674b69
- **[boundary/medium]** [boundary] app/infrastructure/cache/semantic_cache.py:158-162 remember 的 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目，与注释“保留最近条数”相反（确认存在缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:158-162`
  - 依据：注释写“单个 buyer 桶内保留的最近条数”，但 append 后取 `entries[:_BUCKET_LIMIT]` 是取前 30 条（最旧的），新追加的条目在超过 30 条后会被立刻丢弃。结果是桶永远停留在最早的 30 条，新回复永远进不了缓存，缓存逐渐失效且与设计意图相反。正确应为 `entries[-_BUCKET_LIMIT:]`。
  - 争议对手：a2dceda3286c
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:44-45 sanitize_tool_output 对 None 返回 (False, None)，与返回类型 tuple[bool, str] 不符（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:44-45`
  - 依据：`if not text: return False, text` 在 text 为 None 时返回 (False, None)，而签名声明返回 tuple[bool, str]。调用方若对第二个元素做字符串操作（如 len、拼接）会抛 TypeError。这与 output_guard 中已被确认的同类缺陷一致。
  - 争议对手：7ab2c46283a0
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:55-56 audit_output 对空字符串返回 (True, text)，但 text 为 None 时返回 (True, None)，类型与签名不符（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:55-56`
  - 依据：函数签名声明 text: str 且返回 tuple[bool, str]，但 `if not text: return True, text` 在 text 为 None 时返回 (True, None)，调用方若直接下发 cleaned 会得到 None 而非字符串。虽然类型标注为 str，但 Python 不强制，上游若传入 None（如 LLM 返回空）会静默通过并返回 None，破坏返回类型契约。
  - 争议对手：5e0ed92296aa, 7f5ea164963a, 7f5ea164963a, be4240515bc9
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:44-45 内部工具名正则未转义且缺少词边界保护，导致子串误伤（如 task_dispatch 匹配到 task_dispatch_tool 的一部分）（确认存在缺陷）
  - 独立来源 1 个：reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-45`
  - 依据：工具名列表用 \b(?:...)\b 拼接。\b 在 '_' 与字母之间不构成边界（两者都是 \w），因此 'task_dispatch' 作为前缀出现在 'task_dispatch_tool' 中时，\b 在 'h' 与 '_' 之间不成立，实际不会误匹配——这一点是安全的。但反过来，'product_search_tool' 等以 '_tool' 结尾的名字，\b 在末尾 'l' 之后成立，正常。真正的问题在于：若文本中出现 'task_dispatch' 后紧跟非 \w 字符则命中，这是预期。经核对，此处 \b 行为实际正确，不构成缺陷。
  - 争议对手：37a8e2c7edd8, 5d59785f1876, e980c9f520b7
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:38-39 SENSITIVE_PATTERNS 中 shopping_session_id 模式要求冒号或等号，纯 ID 值泄露不会被拦截（确认存在缺陷）
  - 独立来源 2 个：reader-r1-2, reader-r2-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-39`
  - 依据：模式 `shopping_session_id\s*[:=]\s*[\w-]+` 只在出现 'shopping_session_id:' 或 'shopping_session_id=' 前缀时命中。若 Agent 回复中直接以裸值形式泄露会话 ID（如 '会话是 abc-123' 或 JSON 中键名被改写），则不会被脱敏。作为 L4 最后一道闸，这属于覆盖缺口。
  - 争议对手：a991c862b226
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:43-44 SENSITIVE_PATTERNS 中工具名使用 \b 边界，下划线属于单词字符导致前后缀拼接时漏检（确认存在缺陷）
  - 独立来源 1 个：reader-r2-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-44`
  - 依据：`\b` 的边界定义基于 \w（含下划线）。若模型输出把工具名嵌入更长的标识符，例如 `my_product_search_tool_v2` 或 `product_search_toolx`，`\b` 在 `product_search_tool` 前后不成立（前一个是 `_`，后一个是 `_` 或字母），正则不会命中，内部工具名原样泄露给买家。文档声称要拦截内部工具名，但该边界选择在拼接场景下失效。
  - 争议对手：7b03a81e5b2a, a60934d898aa, cb4982bbf7ae

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.99 ≥ 0.00，归一化 33.23% ≥ 0.00%
- 有效通道：2.99｜归一化 33.2%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：14｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 36，已观测 75，估计总体 75.0
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 0.2% |
| `17da7cc20bb4` | 4 | 0 | `reader_miss` | 0.0% |
| `5249eda27566` | 2 | 0 | `reader_miss` | 0.2% |
| `538d958c9657` | 6 | 0 | `reader_miss` | 0.0% |
| `5d929055a8d9` | 6 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 6 | 0 | `reader_miss` | 0.0% |
| `6fd64302ee4f` | 6 | 0 | `reader_miss` | 0.0% |
| `797c78721ca7` | 6 | 0 | `reader_miss` | 0.0% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 0.2% |
| `9b22164343f5` | 6 | 0 | `reader_miss` | 0.0% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 4 | 0 | 4 | 2 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 5 | 0 | 0 | 0 | 0 | 3 |
| `app/domain/catalog` | 6 | 0 | 6 | 2 | 0 | 0 | 0 | 2 |
| `app/domain/session` | 3 | 0 | 4 | 0 | 1 | 0 | 0 | 2 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 6 | 2 | 6 | 6 | 0 | 3 | 2 | 1 |
| `app/infrastructure/security` | 6 | 0 | 6 | 1 | 0 | 5 | 0 | 3 |

矩阵填充率 32%（单元格值 = 独立 Agent 数）
