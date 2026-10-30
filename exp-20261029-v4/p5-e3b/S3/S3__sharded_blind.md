# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 6 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 54 | 支持不足、相关性超限或尚待验证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：80
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：120 个节点 / 265 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 64 | 100% | 16% |

## 高置信结论

- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:148-151 due() 在 rounds=0 时返回 True，未观察任何动作即触发检测（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:148-151`
  - 依据：rounds 初始为 0，0 % check_interval == 0 为真，因此 start_turn 后尚未 observe_action 时 due() 就返回 True。check 会进入判定流程；虽然 computational_signals 因 recent_actions 为空不会产生原因，但若注入了 judge，会走到 judge 分支——不过 check 中还有 `if not trace.original_query or not trace.recent_actions: return report` 保护，实际不会调用 judge。因此该边界仅造成一次无意义的检测调用，不产生错误结论。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:122-126 _latest_first 同样用 `p in newest` 复原顺序，重复元素会导致返回超过 top_k 条（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:122-126`
  - 依据：与 _rank_by_relevance 相同的相等性过滤问题。sorted 取 top_k 后，用 `p in newest` 过滤原列表，若存在相等元素，原列表中所有相等项都会被保留，返回数量可能超过 top_k。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:118-126 幂等键冲突回滚后未撤销已保存的订单，导致库存与订单不一致（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-126`
  - 依据：在 idempotency.record 返回 False（并发下另一路先登记了同一个键）时，代码只回滚了库存（_rollback(reserved)），但此前第 116 行已经执行了 await self._order_repo.save(order)，把本次订单持久化了。回滚库存后，本次订单仍然存在于仓储中，其行项目对应的库存已被释放，形成“订单存在但库存未扣减”的不一致；若后续该订单被取消，CancelOrderUseCase 还会再次 release 同一批库存，造成库存超卖/虚增。正确做法应是在回滚库存的同时删除/作废已保存的订单，或先登记幂等键再保存订单。
- **[logic/medium]** [logic] app/domain/order/order.py:70-78 cancel 允许从 DRAFT 态取消，违反文档声明的状态机不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:70-78`
  - 依据：模块 docstring 明确不变量为“只有 CONFIRMED 态可以取消”，但 cancel() 只拦截了 CANCELLED 态，未校验 status 是否为 CONFIRMED。因此 DRAFT 订单也能被取消，产生 DRAFT→CANCELLED 的非法状态迁移，与声明的状态机 DRAFT→CONFIRMED→CANCELLED 不符。
- **[logic/high]** [logic] app/domain/order/order.py:88-92 total_amount 把首行小计重复计入一次（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-92`
  - 依据：total_amount 先用 lines[0].subtotal() 初始化 total，随后 for line in self.lines 又从第一条开始遍历并 add，导致第一条订单行的小计被计算两次。任何多行订单（或单行订单）的 total_amount 都会偏大：单行订单返回 2 倍小计，多行订单返回总和 + 首行小计。snapshot() 直接使用 total_amount()，因此回传给买家的总金额错误。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:196-205 语义缓存 remember 的读-改-写非原子，并发写会丢失条目（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:196-205`
  - 依据：remember 先 _load_entries 读取整个桶，append 后再 set_json 整体覆盖。两个并发请求（同一 buyer、同一 scope）同时读到相同旧列表，各自 append 后写回，后写者覆盖先写者，导致一条缓存条目丢失。虽然只影响缓存命中率不影响正确性，但属于真实的并发丢失更新缺陷。

## 待验证（孤证）

> ⚠️ 本节共 **54** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/harness/assertions.py:88-93 check_schema 对 JSON 字符串解析出非 dict（如 list）时判为失败，但工具可能合法返回数组（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:88-93`
  - 依据：TOOL_REQUIRED_FIELDS 中登记的工具（product_search_tool 等）按注释均返回含 hits/insights/order_id 的对象，要求 dict 是合理的。对未登记工具直接跳过。因此不是缺陷。
- **[error_handling/low]** [error_handling] app/application/harness/assertions.py:78-86 check_schema 中 json.loads 捕获 TypeError 但未捕获 ValueError 之外的异常，且 str 子类/bytes 处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:78-86`
  - 依据：json.loads 对 str 输入抛出的异常是 JSONDecodeError（ValueError 子类），已捕获；TypeError 覆盖非 str 情况，但此处已用 isinstance 限定 str。捕获范围足够，不会漏抛。
- **[logic/high]** [logic] app/application/harness/assertions.py:137-152 SequencingTracker.check 的硬拒分支注释声称“有观测证据才硬拒”，但代码未检查本会话是否有任何调用记录（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:137-152`
  - 依据：模块 docstring 明确说明：写路径前置校验采用“有证据才硬拒”——本会话已观测到工具调用却没有检索才硬拒；完全没有观测记录（刚恢复/首次调用）应降级为警告。但 check() 中只要 tool_name 在 HARD_REJECT_TOOLS 且 prereq 不在 history 就设置 reject_reason，完全没有判断 history 是否为空。会话从 AgentState 快照恢复后（内存记录为空）首次调用 create_order_tool 会被硬拒，正是 docstring 声称要修正的误杀场景。
- **[logic/high]** [logic] app/application/harness/assertions.py:148-163 SequencingTracker 硬拒逻辑与 docstring 承诺不符：无观测记录时仍硬拒（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:148-163`
  - 依据：模块 docstring 明确承诺：'完全没有观测记录（刚恢复/首次调用）→ 降级为警告'。但 check() 中只要 tool_name 在 HARD_REJECT_TOOLS 且前置未命中，就无条件设置 reject_reason，并未检查 history 是否为空。会话从快照恢复后 history 为空，create_order_tool 会被硬拒，正是 docstring 声称要避免的误杀。
- **[resource_leak/low]** [resource_leak] app/application/harness/assertions.py:108-110 SequencingTracker 的 _called 字典无上限，长生命周期进程下会话记录无限增长（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:108-110`
  - 依据：提供了 reset(session_id) 供调用方在会话结束时清理；是否调用属于使用方职责，且单条记录为工具名列表，规模有限。没有证据表明仓库内存在不调用 reset 的长期泄漏路径，故不确认为缺陷。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:178-186 成本失控基线包含被检测的最近 3 轮之外全部历史，但 recent_avg 用固定 3 作分母（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:178-186`
  - 依据：len(history) >= 6 保证 history[:-3] 至少 3 个元素，baseline 分母非零；recent_avg 用 history[-3:] 恰好 3 个元素除以 3 正确。逻辑自洽。
- **[logic/low]** [logic] app/application/harness/drift_detector.py:158-163 关键词命中率分母为原始关键词全集，长 query 下几乎必然误报目标遗忘（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:158-163`
  - 依据：extract_keywords 对中文按 2-gram 展开，原始 query 越长关键词集合越大，recent_actions 只保留最近 3 条摘要，命中率天然偏低。但这是文档明确设计的“目标遗忘”信号（阈值 0.2 已考虑该偏差），且 recent_actions 摘要由调用方控制，属于启发式判定的固有取舍，不构成可复现的实现缺陷。
- **[boundary/medium]** [boundary] app/application/harness/loop_detector.py:60-68 trailing_repeat 只统计窗口内尾部连续次数，窗口小于阈值时永远无法触发提示（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:60-68`
  - 依据：trailing_repeat 遍历的是 deque，其长度受 maxlen=self.window 限制。若调用方构造 LoopDetector(window=2) 而 repeat_threshold 保持默认 3，则尾部连续计数最多为 2，check 永远返回 None，收敛提示完全失效。代码没有对 window < repeat_threshold 做校验或告警，属于参数组合导致的静默失效。
- **[concurrency/low]** [concurrency] app/application/harness/loop_detector.py:47-58 LoopDetector 的 _calls 默认 maxlen 与可配置 window 不一致，重建逻辑在并发下会丢失记录（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:47-58`
  - 依据：defaultdict 的工厂固定使用 DEFAULT_WINDOW，而 _bucket 在 bucket.maxlen != self.window 时用 deque(bucket, maxlen=self.window) 重建并写回。单线程下行为正确：首次访问即重建为正确 maxlen，之后不再重建。虽然模块 docstring 强调多会话并发隔离，但 LoopDetector 本身不是线程安全的（defaultdict 写入、deque 重建均无锁），不过这是调用方需保证的同步前提，且按 session 分桶已避免跨会话污染。未发现可确证的错误行为，故记为非缺陷。
- **[logic/low]** [logic] app/application/harness/loop_detector.py:38-41 LoopDetector 的 window 参数在构造时被忽略，_calls 的 maxlen 固定为 DEFAULT_WINDOW（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:38-41`
  - 依据：default_factory 使用 DEFAULT_WINDOW 作为 maxlen，看似忽略了构造参数 window。但 _bucket 会在 bucket.maxlen != self.window 时用 deque(bucket, maxlen=self.window) 重建，因此自定义 window 在首次访问时即被纠正。重建时保留旧元素并截断到新 maxlen，行为符合预期。唯一细微之处是若 window 被改小，旧元素会被截断，但这是合理语义。
- **[logic/low]** [logic] app/application/harness/loop_detector.py:70-80 check 先记录再判断，导致首次达到阈值时提示中的 count 与阈值语义一致但重复调用会持续返回提示（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:70-80`
  - 依据：check 每次调用都 record 并返回 count>=threshold 的提示。连续第 3、4、5 次调用都会返回提示，这是设计意图（每次打转都提醒），并非缺陷。文档也说明不强制终止。
- **[api_misuse/medium]** [api_misuse] app/application/memory/preference_selector.py:108-122 _rank_by_relevance 中 embed_batch 返回的向量与 likes 顺序对齐假设未校验，若 embedder 返回顺序不同会静默错配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:108-122`
  - 依据：代码用 `zip(vectors, likes)` 假设 embed_batch 返回的向量顺序与输入顺序一致。虽然这是 EmbeddingClient 的常见契约，但代码只校验了数量（len(vectors) != len(likes)），未校验顺序。若某个 embedder 实现（如批量接口返回乱序、或去重后返回）顺序不一致，会静默把偏好与错误向量配对，导致相关性排序错误。这属于对接口契约的隐式依赖，且失败模式是静默的。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:88-91 select 中 top_k <= 0 时返回 dislikes，但 dislikes 可能为空列表，调用方若假设返回非空会出错（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：返回空列表是合理语义：没有 dislike 且 top_k<=0 时确实没有可注入的偏好。调用方应处理空列表。不构成缺陷。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:118-120 _rank_by_relevance 用 `p in picked` 复原顺序，依赖 BuyerPreference 的相等语义，若为 dataclass 且含不可比较字段或重复 statement 会出错（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-120`
  - 依据：`[p for p in likes if p in picked]` 通过相等性过滤来复原顺序。如果两条 like 偏好内容完全相同（同 kind、同 statement、同 created_at），`in` 判断会把两条都保留，导致返回数量超过 top_k；反之若 BuyerPreference 未定义 __eq__（默认身份比较）则行为正确。更关键的是：当存在重复元素时，picked 只含 top_k 条，但过滤 likes 时所有与 picked 中任一元素相等的项都会被保留，可能返回多于 top_k 条。_latest_first 同样有此问题。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:33-40 _cosine 对长度不一致返回 0.0，但 embed_batch 返回的向量维度可能与 query 不同，导致全部得分为 0 而静默退化（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-40`
  - 依据：维度不一致时返回 0.0 是防御性设计，所有得分相同则按 index 稳定排序，等价于取前 top_k 条，不会崩溃。属于可接受的降级。
- **[api_misuse/low]** [api_misuse] app/application/prompts/loader.py:17-20 load_prompts 使用 lru_cache 缓存可变 dict，调用方可修改共享状态（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-20`
  - 依据：lru_cache 返回同一个 dict 对象，若调用方修改会污染全局。但当前仓库内未见修改调用，且这是常见的只读配置加载模式，属于潜在风险而非已确认缺陷。
- **[error_handling/low]** [error_handling] app/application/prompts/loader.py:17-19 load_prompts 使用 lru_cache 缓存，文件缺失时抛异常且不缓存，但无错误处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-19`
  - 依据：open 失败会抛 FileNotFoundError，属于配置缺失的显式失败，调用方应感知；lru_cache 在异常时不会缓存结果，下次调用会重试。这不是缺陷而是合理的快速失败。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:218-226 rerank 返回分数数量与候选数不一致时 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:218-226`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标索引，假设 reranker 返回的分数列表长度与 documents 完全一致。若 reranker 实现返回较短列表（例如内部截断、过滤或返回 top_k 而非全量），会抛 IndexError。该异常会被 execute 中的 `except Exception` 捕获并降级为按向量分排序，因此不会崩溃，但会静默丢失精排结果且日志误导为“rerank 不可用”。属于对 reranker 契约的隐式假设。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:236-244 rerank 分数与候选索引错位时可能 IndexError 或静默错配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:236-244`
  - 依据：_rerank 用 rerank_scores[i] 按位置索引 scored，但未校验 rerank_scores 长度是否等于 scored 长度。若 Reranker 返回的分数条数少于候选数（部分实现会截断或过滤），会抛 IndexError；该异常被 execute 的 except 捕获后降级为按向量分排序，看似安全，但若返回条数多于候选数则多余分数被忽略——更关键的是若 Reranker 返回顺序与输入文档顺序不一致（某些实现按分数排序返回），则分数会与错误商品配对，产生静默的错误排序结果。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:118-130 关键词召回在向量召回成功但结果为空时被误触发并覆盖 recall_strategy（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-130`
  - 依据：当向量召回成功但返回空列表时，recall_strategy 已被设为 embedding_only，随后 elif not scored 分支执行关键词召回并把 recall_strategy 改为 keyword_2gram。这是有意的降级设计：向量库无结果时用关键词兜底，且如实标注策略。逻辑自洽，不构成缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:137-148 向量召回成功但结果为空时，错误地降级为关键词召回并覆盖 recall_strategy（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:137-148`
  - 依据：当向量召回成功执行但返回空列表（scored == []）时，recall_strategy 已被设为 'embedding_only'，但 `if recall_strategy == 'embedding_only' and scored:` 为假，于是进入 `elif not scored:` 分支执行关键词召回并把 recall_strategy 覆盖为 'keyword_2gram'。这本身是合理的兜底，但问题在于：向量召回成功且确实无匹配（例如库里没有相关商品）时，也会被当作 embedding 不可用而走关键词召回，掩盖了真实召回策略。更关键的是，如果向量召回抛异常，scored 被置空，同样走关键词召回——两条路径无法区分。这属于可观测性/语义标注失真，但不会导致错误结果。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:196-200 _to_rejected 与 _within_price_cap 对 primary_sku 价格做币种转换，但 _to_card 的 price_major 未转换（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:196-200`
  - 依据：商品卡 price_major 保留原币种并同时输出 currency 字段，语义自洽；landed_price 单独给出目标币种明细。过滤用目标币种比较是正确设计。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:240-250 关键词召回分数为整数计数，与向量分数语义不同但共用排序/截断（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:240-250`
  - 依据：关键词召回与向量召回不会同时出现在同一 scored 列表中（二选一），因此分数尺度不同不会造成混排问题。排序与 top_k 截断在各自召回内部自洽。
- **[api_misuse/low]** [api_misuse] app/application/usecases/order_usecases.py:27-33 OrderAccessDenied 继承 ValueError，调用方若按 ValueError 统一处理会把越权访问当作普通参数错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:27-33`
  - 依据：OrderAccessDenied 继承 ValueError 是有意为之：docstring 说明对外一律映射为 404，且与“订单不存在”的 ValueError 走同一映射路径，避免 403 信息泄露。虽然继承 ValueError 会让 except ValueError 同时捕获两者，但这正是设计意图（统一映射为 404），不构成缺陷。
- **[boundary/low]** [boundary] app/application/usecases/order_usecases.py:160-166 QueryOrderUseCase 对空 buyer_id 抛 OrderAccessDenied 而非参数错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:160-166`
  - 依据：buyer_id 为空时抛 OrderAccessDenied 并映射为 404，与“订单不属于当前买家”语义一致，且避免泄露订单存在性。这是有意的边界处理，不是缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:108-116 PlaceOrderUseCase 在库存扣减成功但 Order.place 抛异常时回滚，但若 save 抛异常则库存已扣、订单未存且未回滚（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:108-116`
  - 依据：try/except 块只覆盖了库存扣减与 Order.place，await self._order_repo.save(order) 在 try 之外。若 save 抛异常，库存已经扣减但订单未持久化，且不会触发 _rollback，导致库存永久泄漏。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:178-184 CancelOrderUseCase 先回补库存再保存订单，save 失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:178-184`
  - 依据：execute 中先调用 order.cancel(reason) 修改内存状态，然后循环 release 回补库存，最后才 save。若 save 抛异常（如仓储故障），订单在持久层仍是未取消状态，但库存已经被回补。调用方重试取消时，状态机允许再次 cancel（因为持久层订单仍是原状态），于是库存被第二次回补，造成库存虚增。库存回补与订单状态变更不是原子的，且顺序（先回补后保存）放大了失败窗口。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:196-202 取消订单先回补库存再保存，保存失败导致库存与订单状态不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-202`
  - 依据：CancelOrderUseCase.execute 先调用 order.cancel(reason) 修改内存状态，然后循环 release 库存，最后才 save。若 save 抛异常（DB 故障、乐观锁冲突等），库存已经被回补，但订单在持久层仍是未取消状态。后续重试取消会再次 release，造成库存重复回补（注释声称“重复取消会被状态机挡在上一步”，但那只在 save 成功后才成立）。
- **[logic/medium]** [logic] app/application/usecases/order_usecases.py:128-137 幂等键登记后写单前崩溃时，_replay 返回 None 会继续新建订单，导致同一键产生第二张订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:128-137`
  - 依据：_replay 的 docstring 明确说明“找不到（登记后写单前崩溃）返回 None，让调用方继续新建”。但幂等键已经登记（record 成功）而订单未保存时，后续重投会走 _replay 返回 None，然后重新扣库存、重新 save 一张新订单，再调用 record 时因键已存在返回 False，于是回滚库存并再次 _replay——此时仍找不到订单，最终抛 ValueError。结果是：库存被扣了又释放，订单可能已保存但幂等键指向的订单不存在，重投永远无法成功，且可能产生孤儿订单。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:33-34 BuyerPreference 为 frozen dataclass 却在 __post_init__ 用 object.__setattr__ 修改 created_at（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:33-34`
  - 依据：frozen dataclass 中通过 object.__setattr__ 在 __post_init__ 设置默认值是标准做法，可正常工作。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-33 BuyerPreference 的 created_at 默认空串在 __post_init__ 中填充，frozen dataclass 用 object.__setattr__ 正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：frozen dataclass 中通过 object.__setattr__ 设置字段是标准做法，行为正确。
- **[boundary/low]** [boundary] app/domain/order/address.py:24-26 Address.one_line 未校验 state/phone/postal_code 但 __post_init__ 也未校验，可能输出空字段（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:24-26`
  - 依据：__post_init__ 只强制 recipient_name/country/city/address_line，state/phone/postal_code 允许为空。one_line 会输出空 state 与空 phone，但这是文档声明的 MVP 存储展示行为，未声明这些字段必填，不构成缺陷。
- **[logic/medium]** [logic] app/domain/order/order.py:47-53 币种一致性不变量未在聚合内校验（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：docstring 声明不变量“全部订单行币种一致”，但 __post_init__ 只校验非空，注释把责任推给下单用例。聚合根自身不强制不变量，任何直接构造 Order 的路径（测试、其他用例、反序列化）都能构造出混合币种订单；随后 total_amount() 的 Money.add 若不做币种校验就会静默得到错误币种总额，若做校验则会在快照时抛异常。不变量应在聚合边界内保证。
- **[concurrency/low]** [concurrency] app/domain/order/ports/order_idempotency_store.py:20-24 OrderIdempotencyStore.record 返回 False 表示重复，但端口未定义并发下 find+record 的原子性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:20-24`
  - 依据：这是抽象端口，record 的“键已存在返回 False”语义本身可被实现为原子操作（如 SETNX）。端口未强制 find+record 组合的原子性，但调用方应依赖 record 的返回值而非 find 结果。文档已说明 record 返回 False 表示重复执行，语义完整。
- **[logic/low]** [logic] app/domain/order/ports/order_idempotency_store.py:22-24 OrderIdempotencyStore.record 返回 False 的语义依赖调用方正确处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:22-24`
  - 依据：端口文档明确 record 在键已存在时返回 False 表示重复执行，语义清晰。缺陷在于调用方（order_usecases.py，已被其他审查者报告）未正确处理，端口本身无缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:100-103 运费按 quantity 线性放大但未考虑 subtotal 已含多件，且 round 使用银行家舍入可能造成分位偏差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-103`
  - 依据：round 在 Python 3 中对 .5 采用银行家舍入，但运费计算中 (1 + 0.6*(quantity-1)) 乘以整数分，结果通常为整数或 .0/.5 结尾，偏差最多 1 分，属于可接受的简化口径。文档已声明“简化的续重逻辑”。不构成真实缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:96-112 quote 中 subtotal 与 target_currency 折算后，freight 和 tariff 分别独立折算，多次汇率转换可能引入累积舍入误差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-112`
  - 依据：每次 convert 独立进行，误差最多各 1 分，landed_total 由三个已折算值相加，总误差在可接受范围内。文档已声明“目标币种统一折算后计算”。不构成真实缺陷。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:108-112 quote 中免税额度判断使用 CNY 小计，但 de_minimis_applied 语义是“关税为 0”，当税率为 0 时（如 US 数码配件）即使超出额度也会标记为未命中免税（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:108-112`
  - 依据：de_minimis_applied 被定义为“是否命中免税额度（关税为 0）”。当目的国为 US、品类为数码配件时，tariff_rate=0.0，此时无论小计是否超出免税额度，tariff_cny 都是 0。但代码中 de_minimis_applied = taxable_minor_cny == 0，若小计超出额度则 taxable_minor_cny > 0，de_minimis_applied 为 False，而实际关税为 0。字段语义与注释“是否命中免税额度（关税为 0）”不一致，下游若据此展示“已免关税”会出错。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:33-39 免税额度常量注释与数值不一致（US/EU/JP/SG 汇率口径混乱）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:33-39`
  - 依据：这些是硬编码的简化口径常量，注释已声明“简化”。数值本身是业务配置选择，不构成代码缺陷。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:96-103 免税额度按单件小计判断，未乘以数量，多件订单关税计算偏低（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-103`
  - 依据：quote 接收 quantity 参数，运费按 quantity 递增计算，但关税部分只用 `subtotal`（单件小计）与免税额度比较，未乘以 quantity。当 quantity > 1 时，实际应税金额应为 subtotal*quantity 超出免税额度的部分，当前实现会低估关税，甚至在本应征税时判定 de_minimis_applied=True。运费考虑了数量而关税没有，口径不一致。
- …另有 14 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/harness/drift_detector.py:137-141 consecutive_empty 在非空结果时未重置，导致“连续空结果”判定失真（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:137-141`
  - 依据：observe_action 中 consecutive_empty 只在 result_empty 为 True 时自增，result_empty 为 False 时保持原值而不归零。因此“连续 3 次检索返回空候选”的语义被破坏：只要历史上累计出现过 3 次空结果（中间夹杂任意多次成功检索），就会永久触发“探索发散”信号，且该计数永不回落，造成误报并持续注入纠正提示。
  - 争议对手：9f227134f9a9
- **[error_handling/high]** [error_handling] app/infrastructure/cache/redis_cache.py:118-127 set_if_absent 在 Redis 异常时返回 True（视为抢到锁），导致幂等保护与分布式锁在缓存故障时完全失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-127`
  - 依据：set_if_absent 被文档声明用于“幂等键与分布式锁”。当 Redis 抛异常时返回 True，意味着调用方认为抢到了锁/幂等键。对于分布式锁场景，这会导致多个 worker 同时进入临界区（互斥失效）；对于幂等键场景，会导致重复请求被当作首次请求处理（幂等失效）。注释声称“宁可退化成没有幂等保护，也不能因缓存故障拒绝服务”，但返回 True 会让调用方误以为获得了保护，而不是“没有保护”。正确做法应是返回 False 或抛出可识别的异常让调用方显式选择降级策略。这是一个真实的安全/正确性缺陷。
  - 争议对手：25db3af0c24a
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:137-152 zadd_and_count 在 pipeline 中 zadd 后 zcard 计数包含本次成员，但 zremrangebyscore 与 zadd 之间无原子性保证（transaction=True 已保证），实际缺陷在于返回 0 表示不限流与真实计数 0 无法区分（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-152`
  - 依据：zadd_and_count 在 Redis 异常时返回 0，而调用方通常用 `count > limit` 判断是否限流。返回 0 意味着“窗口内无请求”，即完全放行。这与文档注释“按不限流处理”一致，但问题在于：当 Redis 短暂故障时，所有 worker 都会放行，限流完全失效。更关键的是，正常路径下返回的是 zcard 结果（包含本次），而异常路径返回 0，调用方无法区分“Redis 挂了”和“窗口内确实 0 个请求”。不过注释已明确声明这是有意的降级策略（宁可放行也不拒绝服务），因此这属于设计取舍而非缺陷。
  - 争议对手：8f92dbc781c3
- **[logic/medium]** [logic] app/infrastructure/security/output_guard.py:43-44 SENSITIVE_PATTERNS 中工具名用 \b 边界，下划线属于单词字符导致相邻文本无法匹配（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-44`
  - 依据：Python 正则中 \w 包含下划线，因此 \b 在 `_` 与字母之间不成立。若内部工具名紧邻下划线或其它单词字符出现（例如 `my_product_search_tool` 或 `product_search_tool_v2`），\b 边界不成立，模式不会命中，导致内部工具名泄露而未被脱敏。这与“命中即脱敏”的意图相悖，属于漏检缺陷。
  - 争议对手：8e18c8e862a0

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 2.45 ≥ 0.00，归一化 81.79% ≥ 0.00%
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：14｜覆盖正常：17｜无法判定：0
- 单 Reader 检出率：51.1%（重捕对 3，已观测 64，估计总体 125.2857
- 待补检分组：app, app/application/memory, app/domain/order, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/cache, app/domain, app/application/harness, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 23.9% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 23.9% |
| `2d259bcddd0a` | 2 | 0 | `reader_miss` | 23.9% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 23.9% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 23.9% |
| `4fcaf3c8939f` | 2 | 0 | `reader_miss` | 23.9% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 23.9% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 23.9% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 23.9% |
| `7d3fc36631b9` | 2 | 0 | `reader_miss` | 23.9% |
| …另有 4 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/harness` | 2 | 1 | 2 | 1 | 1 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 1 |
| `app/application/prompts` | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| `app/application/usecases` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 1 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 2 | 1 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 2 | 0 | 2 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 30%（单元格值 = 独立 Agent 数）
