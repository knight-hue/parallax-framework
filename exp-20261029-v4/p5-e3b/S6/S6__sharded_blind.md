# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 5 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 77 | 支持不足、相关性超限或尚待验证 |
| 争议 | 7 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：107
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：150 个节点 / 332 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 89 | 100% | 18% |

## 高置信结论

- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:175-181 CancelOrder 先回补库存再保存订单，save 失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:175-181`
  - 依据：order.cancel(reason) 修改内存对象后立即 release 库存，然后才 save。若 save 抛异常（DB 故障），订单状态未持久化为 cancelled，但库存已经回补。调用方重试取消时，内存中重新加载的订单仍是未取消状态，会再次通过状态机并再次 release，造成库存重复回补（超卖）。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:76-84 delete 只删除 kind==dislike 的条目，与文档声明的“同 statement 一并清除”不符（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:76-84`
  - 依据：docstring 明确说“按 statement 而不分 kind……同 statement 的条目一并清除”，但过滤条件额外要求 p.kind == "dislike"，导致 kind 为 like 的同 statement 条目不会被删除。买家说“以后别管塑料了”时，正向偏好仍残留，与设计意图相反。
- **[security/high]** [security] app/infrastructure/persistence/json_file_stores.py:30-32 _safe_name 未做任何清洗，路径穿越防护失效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:30-32`
  - 依据：_safe_name 的 docstring 声称“文件名清洗，避免路径穿越”，但实现只是 raw or "anonymous"，对 "../"、"/" 等完全不做处理。buyer_id/session_id 若来自外部输入（如请求参数），可构造 "../../etc/xxx" 使 _path 逃逸出 data_dir，造成任意路径读写。
- **[performance/low]** [performance] app/infrastructure/persistence/sql/tables.py:76-76 ConversationMessageRow 的索引只含 session_id，与命名 ix_msg_session_turn 不符（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/tables.py:76-76`
  - 依据：索引名为 ix_msg_session_turn，暗示按 (session_id, turn_index) 复合索引，但实际只索引 session_id。list_turns 按 session_id 过滤并按 turn_index 排序/取最近 N 条时，无法利用索引完成排序，需额外 sort。同时 session_id 列上已有 index=True，产生重复索引。属于索引定义与意图不符导致的性能问题。
- **[logic/low]** [logic] app/infrastructure/rag/category_knowledge.py:76-80 bootstrap_category_knowledge 用 document_id 去重，但文件内容变更后不会重新入库（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/rag/category_knowledge.py:76-80`
  - 依据：以 md_file.stem 作为 document_id，existing 集合来自 list_documents。只要文件名已存在就跳过，即使文件内容已更新也不会重新切块入库，知识库会长期停留在旧内容。注释声称“幂等”，但实际是“只增不改”，更新知识文件后需手动删库。

## 待验证（孤证）

> ⚠️ 本节共 **77** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:122-126 _latest_first 同样用 `p in newest` 过滤，重复条目会突破 top_k（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:122-126`
  - 依据：与 _rank_by_relevance 相同的相等性过滤问题：sorted(...)[:top_k] 取到 top_k 条，但 `[p for p in likes if p in newest]` 对完全相等的重复条目会全部保留，返回条数可能大于 top_k。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:33-41 _cosine 对 NaN/Inf 向量不做防护，排序键可能产生不确定结果（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-41`
  - 依据：embedding 客户端返回 NaN/Inf 属于上游契约违约，且即使出现 NaN，sort 仍能完成（NaN 比较返回 False，顺序由 index 次序键兜底），不会抛异常。降级路径已覆盖异常。不构成可确认缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:33-34 embed_batch 返回向量维度与 query 不一致时 _cosine 静默返回 0，全部同分退化为原始顺序（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-34`
  - 依据：维度不一致时 _cosine 返回 0.0，所有候选同分，sort 由 index 次序键稳定排序，最终取前 top_k 条原始顺序偏好。这是可接受的降级行为，不会崩溃也不会注入错误内容，只是相关性失效。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:118-120 _rank_by_relevance 用 `p in picked` 依赖 dataclass 相等性，重复 statement 的偏好会被错误过滤（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-120`
  - 依据：BuyerPreference 是 frozen dataclass，相等性按字段比较。若两条 like 偏好 statement 相同但 created_at 不同，它们不相等，问题不大；但若两条偏好所有字段都相同（同 buyer、同 kind、同 statement、同 created_at，例如从存储中重复加载或 created_at 精度截断到秒导致相同），`p in picked` 会把两条都保留，导致返回条数超过 top_k。更关键的是 `_latest_first` 同样用 `p in newest`，当存在完全相等的重复条目时，`in` 判断对两条都返回 True，返回列表长度可能超过 top_k，破坏 top_k 截断语义。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:132-136 _latest_first 同样用 `p in newest` 复原顺序，存在与相关性路径相同的相等性越界问题（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:132-136`
  - 依据：`return [p for p in likes if p in newest]` 与 _rank_by_relevance 末尾同样依赖 __eq__。若 BuyerPreference 是值相等类型，newest 中一条会匹配 likes 中所有相等项，导致返回数量超过 top_k，破坏 top_k 截断契约。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:88-91 select 中 top_k<=0 分支丢弃全部 like 偏好，但未记录日志，且与 docstring 的『安全底线』语义一致——非缺陷（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：top_k<=0 时返回 dislikes 是文档明确声明的安全底线行为（只保留黑名单），符合设计意图，不是缺陷。
- **[api_misuse/low]** [api_misuse] app/application/prompts/loader.py:17-20 load_prompts 使用 lru_cache 缓存可变 dict，调用方修改会污染全局缓存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-20`
  - 依据：lru_cache 返回同一 dict 对象，若调用方原地修改会污染缓存。但本文件只负责加载，未展示调用方修改行为；且这是常见模式，在无证据表明调用方修改的情况下不构成确认缺陷。
- **[logic/low]** [logic] app/application/prompts/loader.py:16-19 load_prompts 使用 lru_cache 缓存，文件缺失时抛异常且不缓存，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:16-19`
  - 依据：lru_cache 在函数抛异常时不缓存结果，下次调用会重试。yaml.safe_load 对空文件返回 None，调用方若期望 dict 可能出错，但本文件无调用方证据。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:196-205 rerank 返回分数数量与候选数不一致时 IndexError 或错位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-205`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标索引，但未校验 rerank_scores 长度是否等于 len(scored)。若 Reranker 实现返回的分数少于候选数（例如网关截断、部分失败、返回空列表），会抛 IndexError；该异常被 execute 中的 `except Exception` 捕获后降级为按向量分排序，看似安全，但若返回分数多于候选数则多余分数被静默丢弃，且若实现返回顺序与输入不一致（未按 index 回位）则分数与商品错配，导致精排结果错误且无任何告警。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:236-244 _rerank 未校验 rerank_scores 长度，索引越界会抛 IndexError 并被静默降级（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:236-244`
  - 依据：`rerank_scores[i]` 直接按 scored 的下标索引，未检查 rerank_scores 长度是否等于 len(scored)。若 Reranker 实现返回的分数数量少于文档数（例如截断、过滤或实现 bug），会抛 IndexError；该异常被 execute 中的 `except Exception` 捕获并降级为按向量分排序，表面上不崩溃，但 rerank 结果被整体丢弃且只记一条 warning，掩盖了 Reranker 契约违约。若返回多于文档数则多余分数被忽略，同样无告警。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:78-86 tokenize 对含 CJK 的 chunk 生成 2-gram，但单字符 CJK 查询无法命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:78-86`
  - 依据：单字符 CJK chunk 仍会被 `terms.add(chunk)` 加入词集合，只是不生成 2-gram；文档侧若含该单字也会命中。因此单字查询并非完全无法召回，只是召回粒度粗，属于简化分词的可接受行为。
- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:322-330 库存覆盖失败时静默退化为初始库存，可能展示过期库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:322-330`
  - 依据：库存查询失败时记录 warning 并保留初始库存展示，是文档明确声明的降级策略（“库存查询失败退化为初始库存展示”），且扣减永远走 StockRepository，不会因展示值导致超卖。属于有意的可用性取舍，不是缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-130 向量召回成功但结果为空时，错误地降级为关键词召回并覆盖 recall_strategy（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-130`
  - 依据：当 embedder 与 vector_index 均可用且 _vector_recall 正常返回空列表（例如向量库中确实没有匹配项，或所有命中 product_id 在 repo 中都不存在）时，scored 为空，recall_strategy 被设为 'embedding_only'。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支，执行关键词召回并把 recall_strategy 覆盖为 'keyword_2gram'。这导致：(1) 向量检索正常但无结果时被误报为『embedding 服务异常兜底』，recall_strategy 语义失真；(2) 关键词召回可能返回与向量检索完全不同的结果，掩盖了向量库为空/索引未建的真实问题。正确行为应是：向量召回成功但为空时保持 embedding_only 并返回空 hits，而不是静默切换到另一套召回。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:137-152 向量召回成功但结果为空时，会错误地降级为关键词召回，并覆盖 recall_strategy（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:137-152`
  - 依据：当 embedder 与 vector_index 均存在且 _vector_recall 成功返回空列表时，recall_strategy 被设为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支执行关键词召回并把 recall_strategy 改为 'keyword_2gram'。这本身是设计上的兜底，但问题在于：向量检索正常返回“无匹配”是合法结果，此时用关键词召回替换会改变语义（可能召回向量索引认为不相关的商品），且 recall_strategy 标注为 keyword_2gram 掩盖了向量检索其实可用的事实。更关键的是，若向量召回成功但为空，rerank 分支被跳过，rerank_applied 恒为 false，与文档描述的降级链（embedding_rerank → embedding_only → keyword_2gram，仅 embedding 服务异常时兜底）不一致：空结果并非服务异常。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:154-163 filtered_out 只保留前 3 条，且是在排序前按召回顺序截取，摘要可能不代表最相关被过滤项（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:154-163`
  - 依据：filtered_out 的用途是告知“有候选被硬约束挡掉”，并非精确排名；上限 3 条是刻意的上下文控制。虽然截取发生在全局排序之前，但 scored 在向量/关键词召回后已按分数降序，顺序基本合理，且该字段仅作提示用途，不构成缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:196-200 _to_rejected 与 _within_price_cap 对 primary_sku 价格做币种折算，但 _to_card 的 price_major 未折算，展示口径不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-200`
  - 依据：商品卡 price_major 保留原币种并同时返回 currency 字段，属于“原价+币种”的显式口径；filtered_out 摘要则统一折算到 target_currency 并标注 currency。两者都自带 currency 字段，消费方可区分，不构成错误。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:218-226 关键词召回分数并列时排序不稳定，与向量路径的确定性排序不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:218-226`
  - 依据：_keyword_recall 用 `candidates.sort(key=lambda pair: pair[0], reverse=True)` 仅按分数排序，未加 product_id 兜底。Python 的 sort 是稳定的，但 list_all() 的返回顺序取决于仓储实现（如 dict/set 遍历、DB 无 ORDER BY），同一 query 在不同进程/不同数据加载顺序下会得到不同结果。而 execute 中后续的 `filtered.sort(key=lambda item: (-item[0], item[1].product_id))` 只对通过硬约束的候选生效，被 filtered_out 截断的候选顺序仍不稳定，且注释明确强调确定性排序的重要性，此处遗漏。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:258-268 关键词召回在 category 槽位命中时对不相关商品也加分，导致召回噪声（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:258-268`
  - 依据：`_keyword_score` 先要求 `matched` 非空才继续，因此 category 加权只作用于至少有一个词命中的商品，不会把完全无关商品拉进结果。加权 3.0 是刻意的槽位优先策略，属于设计选择而非缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:277-288 运费按 quantity 线性递增但 quote 调用方固定传 quantity=1，多件到手价不准确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:277-288`
  - 依据：检索链路内联到手价固定按单件（quantity=1）计算，这是商品卡展示口径，注释与文档均说明是“小计+运费+关税”的单件到手价；多件计价不在检索链路职责内。因此不构成缺陷。
- **[boundary/low]** [boundary] app/composition.py:1-1 use_database 判定仅排除 'file'，空串或 None 会被当作数据库 URL（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-1`
  - 依据：use_database = settings.database_url != "file"。若 database_url 为空串或 None，会走 create_engine 分支。但 Settings 的默认值（文档说明 DATABASE_URL 未配 → SQLite）应由 load_settings 保证非空，且 create_engine 对空串会抛错而非静默错误。缺少 Settings 定义无法确认，故不判定为缺陷。
- **[error_handling/low]** [error_handling] app/composition.py:1-1 _prompt_fingerprint 读不到文件时返回固定值导致缓存不失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-1`
  - 依据：读不到 prompt 文件时返回 'noprompt'，语义缓存 namespace 不再随 prompt 变化。但这是文档明确声明的降级设计（'读不到文件时返回固定值，不因此阻断启动'），且仅在文件缺失时发生，属于有意的权衡而非缺陷。
- **[logic/low]** [logic] app/composition.py:1-1 composition.py 被截断，无法完整审查装配逻辑（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-1`
  - 依据：提供的文件内容在约 300 行处被截断（'... [已截断，原文件共 300 行，此处仅显示开头部分]'），因此无法对 build_container 的后半部分（偏好选取、orchestrator 装配、limiter 构造、Container 返回等）做完整审查。这不是代码缺陷，而是审查输入不完整。
- **[resource_leak/low]** [resource_leak] app/composition.py:1-1 shutdown 未关闭 task_queue/backplane 等资源（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/composition.py:1-1`
  - 依据：shutdown 只关闭 vector_index、cache、db_engine。task_queue 与 backplane 复用 cache.client，随 cache.close() 一并释放；bus 无显式关闭接口。因此不构成确定的资源泄漏。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:24-31 BuyerPreference 未校验 buyer_id 非空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-31`
  - 依据：__post_init__ 校验了 kind 与 statement，未校验 buyer_id。但 buyer_id 为空是否构成缺陷取决于上层调用契约；本文件内没有证据表明空 buyer_id 会导致错误行为（存储层按 buyer_id 分组，空串仍可工作）。属于契约缺失而非可证实的缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:30-31 BuyerPreference.created_at 默认值在 __post_init__ 中设置，frozen dataclass 用 object.__setattr__ 是正确做法——非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：frozen dataclass 中通过 object.__setattr__ 设置默认值是标准做法，行为正确。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:96-110 关税计算中免税额度与运费按 CNY 口径但 subtotal 已折算，币种口径混用风险（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-110`
  - 依据：代码显式把 subtotal 折算回 CNY 再与 CNY 口径的免税额度比较，运费也先按 CNY 计算再折算到目标币种，口径一致。虽然汇率表若缺少 CNY 或目标币种会抛错，但这是 ExchangeRateTable 的契约，不属于本文件缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/embedding/openai_embedding_client.py:55-63 embed_batch 串行分片且未校验返回条数，部分分片失败会丢失已获取向量（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:55-63`
  - 依据：分片串行请求中任一分片抛异常会向上传播，调用方（bootstrap_product_index）会整体降级，不会出现部分向量被误用的情况；vectors 是局部变量，异常时不会返回半成品。_embed_chunk 已校验空 body 与 data 缺失。属于可接受的失败语义。
- **[error_handling/medium]** [error_handling] app/infrastructure/embedding/openai_embedding_client.py:66-70 _embed_chunk 未校验返回向量条数与 chunk 长度一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:66-70`
  - 依据：只检查了 'data' 键存在，未检查 len(body['data']) == len(chunk)。若网关截断或去重返回少于请求条数的向量，embed_batch 会静默返回长度不足的列表，调用方按位置 zip 会把向量错配到错误的文本上（PreferenceSelector 用 zip(vectors, likes)），导致偏好相关性排序错位而不报错。
- **[performance/low]** [performance] app/infrastructure/embedding/openai_embedding_client.py:48-55 embed_batch 分片串行请求，大批量时延迟线性增长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:48-55`
  - 依据：串行分片是注释中明确的设计选择（网关批量上限约束），且偏好选择场景 likes 数量通常很小，不构成实际缺陷。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_repositories.py:62-78 InMemoryOrderIdempotencyStore 跨进程不生效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:62-78`
  - 依据：类 docstring 已明确声明仅够单进程开发态使用，跨进程必须换 SqlOrderIdempotencyStore。这是有意的设计约束而非隐藏缺陷，且实现本身在单进程内用 asyncio.Lock 保证了 find/record 的原子性。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_stock_repository.py:51-55 seed 使用 setdefault，无法为已存在但库存为 0 的 SKU 重新补货（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:51-55`
  - 依据：注释明确说明设计意图是“只登记缺失项，已有值代表真实扣减结果，不能被 seed 重置”。库存被扣到 0 后仍保留 key（值为 0），setdefault 不会覆盖，符合“不重置真实扣减结果”的语义。这是有意的取舍而非缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_stock_repository.py:20-22 InMemoryStockRepository 的 asyncio.Lock 绑定到创建时的事件循环（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:20-22`
  - 依据：asyncio.Lock 在 Python 3.10+ 已不再在构造时绑定事件循环，而是在首次 await 获取时绑定；只要仓储实例在单一事件循环内使用（单进程 asyncio 服务的常规用法），不会出现跨循环错误。文件 docstring 也明确限定为单进程内并发安全。
- **[logic/low]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:47-49 get_many 在持锁期间构造字典，返回的是快照而非视图（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:47-49`
  - 依据：返回新 dict 是快照语义，调用方拿到后不会被后续 reserve/release 影响，符合仓储读取的常规预期；不存在共享可变状态泄漏。
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/json_file_stores.py:47-53 JsonFilePreferenceStore.append 的读-改-写非原子，并发 append 会丢失偏好（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:47-53`
  - 依据：append 先 list_by_buyer 读全量，再在内存追加，最后 _write 覆盖整个文件。两个协程并发 append 时都读到旧列表，后写者覆盖先写者，导致一条偏好丢失。文件实现没有锁，与 InMemoryStockRepository 显式加锁的约定不一致。
- **[error_handling/low]** [error_handling] app/infrastructure/persistence/json_file_stores.py:118-126 JsonFileSessionStore.save 非原子写，进程崩溃可能留下半截 JSON 导致 load 失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:118-126`
  - 依据：save 直接 write_text 覆盖目标文件，没有临时文件 + rename 的原子替换。若写入过程中进程被杀或磁盘满，文件被截断，后续 load 返回损坏 JSON，调用方解析 AgentState 会抛异常且无降级路径（load 本身不捕获）。
- **[error_handling/high]** [error_handling] app/infrastructure/persistence/json_file_stores.py:178-192 list_turns 未过滤 kind，会把 session/event 记录当作 turn 解析并因缺 role 抛 KeyError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:178-192`
  - 依据：list_turns 只跳过 kind 为 None 的行，但文件里同时存在 kind="session"（touch_session 写入）和 kind="event"（append_events 写入）的记录。这些记录没有 role 字段，record["role"] 会抛 KeyError，且该异常不在 try 块内（try 只包住 json.loads），导致整个 list_turns 崩溃，而不是跳过非 turn 记录。
- **[error_handling/high]** [error_handling] app/infrastructure/persistence/json_file_stores.py:186-200 JsonFileConversationStore.list_turns 未过滤 kind，会把 event/session 记录当作 turn 解析并因缺少 role 抛 KeyError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:186-200`
  - 依据：循环里只跳过 kind 为 None 的行，但 event 记录 kind=="event"、session 记录 kind=="session"，都会进入 ConversationTurn 构造；event 记录没有 role 字段，record["role"] 直接抛 KeyError，未被捕获，导致 list_turns 整体失败。即便不抛异常，event 也会被错误地当成对话轮次返回。
- **[logic/critical]** [logic] app/infrastructure/persistence/json_file_stores.py:137-139 JSONL 追加写使用 "w" 模式，每次写入都会覆盖整个文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:137-139`
  - 依据：_append_line 的文档与类注释都声称是“追加写不覆盖”，但实际用 open("w") 打开文件，会截断已有内容。因此每次 append_turn / append_events / touch_session 都会把该 session 的整个 JSONL 文件重写为仅包含本次一条记录，历史对话与事件全部丢失。list_turns 只能看到最后一条记录，多轮对话恢复、事件轨迹、find_session 的 session 元信息（首轮写入后会被后续 turn 覆盖掉）都会失效。
- **[logic/critical]** [logic] app/infrastructure/persistence/json_file_stores.py:148-150 JsonFileConversationStore._append_line 用 "w" 模式打开文件，每次追加都会覆盖整个文件（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:148-150`
  - 依据：方法名为 _append_line，docstring 也声明「一行一条记录，追加写不覆盖」，但 open("w") 会截断文件。因此每次 append_turn / append_events / touch_session 都会把该 session 之前的所有记录清空，只留下最后一条。list_turns 因此永远只能看到最后一条记录，多轮对话历史完全丢失。正确应为 open("a")。
- **[logic/medium]** [logic] app/infrastructure/persistence/json_file_stores.py:202-209 JsonFileConversationStore.touch_session 依赖文件存在性判断，但 _append_line 覆盖写导致元信息丢失（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/json_file_stores.py:202-209`
  - 依据：touch_session 在文件已存在时直接 return，认为 session 元信息已写入；但 _append_line 用 "w" 覆盖写，后续任何 append_turn/append_events 都会把先前写入的 session 行清掉。于是 find_session 在首轮之后返回的 dict 不再包含 buyer_id/locale/currency，只剩 session_id。
- …另有 37 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:116-126 幂等键冲突回滚后已保存的订单未删除，留下孤儿订单（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:116-126`
  - 依据：在 record 返回 False 的分支里，代码只回滚库存（_rollback），但此前第 114 行已经执行了 await self._order_repo.save(order)，把失败方的订单写入了订单库。回滚库存后该订单仍然存在，且其库存已被释放，形成“订单存在但库存未扣”的孤儿订单，后续查询/取消会基于错误状态操作。
  - 争议对手：b0b523e050ef, b0b523e050ef
- **[boundary/medium]** [boundary] app/infrastructure/embedding/openai_embedding_client.py:41-42 embed() 在 embed_batch 返回空列表时抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/embedding/openai_embedding_client.py:41-42`
  - 依据：embed() 直接取 embed_batch([text])[0]。embed_batch 对非空输入理论上返回等长向量，但 _embed_chunk 在网关返回 data 为空数组时（body 有 'data' 键但为空）会返回 []，此时 embed() 抛 IndexError 而非受控异常。另外若网关返回的 data 条数少于 chunk 条数，embed_batch 返回的向量数会少于输入数，embed() 仍取 [0] 但调用方（PreferenceSelector._rank_by_relevance）用 len(vectors) != len(likes) 检查，而 embed(query) 单独调用时不会检查长度，可能拿到错误向量。
  - 争议对手：a0ad47353a6c
- **[concurrency/medium]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:47-53 InMemoryOrderRepository.next_order_id 与 save 非原子，并发下单可能产生重复单号（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:47-53`
  - 依据：next_order_id 用 itertools.count 取号，save 单独写入 dict，两者之间没有锁也没有原子性保证。虽然 CPython 下 next() 本身线程安全，但取号与 save 之间若发生 await（save 是 async），多个协程可交错；更关键的是取号后若 save 前抛异常，号被消耗但订单不存在，且没有唯一性校验。相比 InMemoryStockRepository 显式加锁，这里缺少并发保护，与同目录其他实现的约定不一致。
  - 争议对手：481fa92b7e11
- **[logic/medium]** [logic] app/infrastructure/persistence/in_memory_stock_repository.py:36-42 release 对未登记 SKU 直接补登记为 quantity，可能凭空造出库存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_stock_repository.py:36-42`
  - 依据：release 的语义是归还此前 reserve 扣掉的量。若 SKU 从未登记（current is None），说明它从未被 seed 也从未被成功 reserve，此时把库存设为 quantity 等于凭空增加库存。注释称“避免库存凭空消失”，但实际效果是“凭空出现”。触发路径：对不存在的 SKU 调用 release（例如上层在 reserve 返回 False 后仍执行补偿释放，或重复释放），随后 get 会返回一个本不存在的正库存，后续 reserve 可成功，造成超卖。
  - 争议对手：aa18133ffdac
- **[logic/medium]** [logic] app/infrastructure/persistence/seed_products.py:40-42 P1011 竞品描述含“轻便”等词，但注释声称避开与 P1001 在“旅行三件套 抗造”query 上正面相撞，实际 P1011 标题含“旅行三件套”且描述含“轻便”，可能影响已有单测 top-1 断言（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/seed_products.py:40-42`
  - 依据：文件头注释明确声明新增语料刻意避开与 P1001 在“旅行三件套 抗造”这条 query 上正面相撞，以免推翻已有单测的 top-1 断言。但 P1011 的标题就是“Voyager 旅行三件套 记忆棉款”，描述含“轻便 长途飞行 出差 旅行必备”，与 P1001 的“旅行三件套（收纳袋+颈枕+眼罩）… 抗造 轻便”高度重合。虽然 P1011 未写“抗造”，但关键词召回通常按词命中计分，P1011 命中“旅行三件套”“轻便”等词，若 P1001 的“抗造”权重不足以拉开差距，top-1 断言可能被推翻。这是注释承诺与实际数据不一致导致的潜在测试脆弱性。
  - 争议对手：291b6b753a06, 291b6b753a06, bd9429cc9e8b
- **[concurrency/low]** [concurrency] app/infrastructure/queue/redis_stream_queue.py:143-160 consume 中 xreadgroup 的 count 参数按流而非总量限制，可能一次领取超过 free_slots 条消息（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/queue/redis_stream_queue.py:143-160`
  - 依据：xreadgroup 的 count 是每个 stream 的限制，传入 {_STREAM: '>', _LARGE_STREAM: '>'} 且 count=free_slots 时，两条流各最多返回 free_slots 条，合计最多 2*free_slots 条。随后为每条消息 create_task 加入 in_flight，实际并发可能达到配置 concurrency 的两倍，削弱削峰上限。
  - 争议对手：32d016756bff
- **[error_handling/low]** [error_handling] app/infrastructure/rag/category_knowledge.py:84-87 bootstrap 捕获所有异常返回 0，部分入库后重试会重复插入已成功文档（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/rag/category_knowledge.py:84-87`
  - 依据：循环中逐篇 insert_document，若第 k 篇失败，前面 k-1 篇已入库，但异常被整体捕获返回 0，调用方无法区分「完全失败」与「部分成功」。下次启动时 existing 会包含已成功的文档，跳过它们，这本身没问题；但返回值 0 会误导监控/日志，且若失败发生在 insert 内部（部分 chunk 已写入），重试可能产生重复 chunk。属于错误处理粒度问题。
  - 争议对手：09d1e14a9961

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.79% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：17｜无法判定：0
- 单 Reader 检出率：49.7%（重捕对 3，已观测 89，估计总体 179.0
- 待补检分组：app, app/application/memory, app/infrastructure/persistence, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/infrastructure/queue, app/infrastructure/rerank, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 25.3% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 25.3% |
| `36316f1e43cb` | 2 | 0 | `reader_miss` | 25.3% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 25.3% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 25.3% |
| `4fcaf3c8939f` | 2 | 0 | `reader_miss` | 25.3% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 25.3% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 25.3% |
| `84f86f29ed0c` | 2 | 0 | `reader_miss` | 25.3% |
| `9bf6060729dc` | 2 | 0 | `reader_miss` | 25.3% |
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/application/usecases` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 0 | 0 | 2 | 2 | 0 | 0 | 1 | 0 |
| `app/infrastructure/persistence` | 2 | 2 | 2 | 2 | 0 | 2 | 2 | 1 |
| `app/infrastructure/queue` | 2 | 2 | 0 | 1 | 0 | 0 | 1 | 0 |
| `app/infrastructure/rag` | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 2 | 1 | 0 | 0 | 1 | 0 |

矩阵填充率 33%（单元格值 = 独立 Agent 数）
