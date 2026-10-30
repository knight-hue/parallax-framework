# Parallax 运行报告 `7a9fee882d07`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 54 | 支持不足、相关性超限或尚待验证 |
| 争议 | 5 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：87
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：128 个节点 / 311 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 59 | 100% | 22% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **54** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[boundary/low]** [boundary] app/application/harness/assertions.py:98-102 check_schema 对字符串解析出的非 dict 合法 JSON（如 list）报“不是 JSON 对象”，但工具可能合法返回列表（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:98-102`
  - 依据：TOOL_REQUIRED_FIELDS 中登记的工具（product_search_tool 等）按注释均返回含 hits/insights/order_id 的对象，因此要求 dict 是合理的。列表返回不在约定范围内，报错符合预期。
- **[error_handling/low]** [error_handling] app/application/harness/assertions.py:88-96 check_schema 对非字符串非 dict 的合法 JSON 标量（如数字/列表）报错，但更关键的是 json.loads 对 bytes 输入会抛 TypeError 未被捕获（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:88-96`
  - 依据：json.loads 在 Python 3 中接受 str/bytes/bytearray；except 捕获了 (json.JSONDecodeError, TypeError)，因此 bytes 输入不会导致未捕获异常。虽然 bytes 会被解析，但这是可接受的。此处不构成缺陷。
- **[logic/high]** [logic] app/application/harness/assertions.py:137-152 SequencingTracker.check 的硬拒逻辑与模块 docstring 声明的“有观测证据才硬拒”不一致：只要本会话没有检索记录就硬拒，包括完全无观测记录的情况（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:137-152`
  - 依据：模块 docstring 明确说明：规则应为“本会话已观测到工具调用、却没有一次检索 → 硬拒；完全没有观测记录（刚恢复/首次调用）→ 降级为警告”。但 check() 中只要 prereq 不在 history 就进入 HARD_REJECT_TOOLS 分支设置 reject_reason，完全没有检查 history 是否为空。因此会话从 AgentState 快照恢复后（内存记录为空）首次调用 create_order_tool 会被硬拒，正是 docstring 声称要修正的误杀场景。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:141-144 check_interval 为 0 时 due() 抛 ZeroDivisionError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:141-144`
  - 依据：check_interval 是公开可配置字段，若装配层传入 0（或负数语义异常），rounds % 0 会抛 ZeroDivisionError，且该异常不在 check() 的 try 保护范围内，会中断主链路。缺少对配置值的校验。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:168-176 成本失控信号在 token_history 长度恰为 6 时 baseline 与 recent 划分正确，无缺陷（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:168-176`
  - 依据：len(history) >= 6 时 history[:-3] 至少 3 个元素，baseline 分母非零；recent_avg 用固定 /3 与 history[-3:] 长度一致。检查后确认无除零或索引问题，故不是缺陷。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:60-70 extract_keywords 对单字中文 token 不产生任何关键词（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:60-70`
  - 依据：正则 [\u4e00-\u9fff]{2,} 只匹配连续 2 个及以上汉字，单字中文不会进入 token，因此不会产生 2-gram。这是刻意的“极简关键词抽取”，单字信息量低，不构成缺陷；且 keywords 为空时目标遗忘信号被 trace.keywords 判空跳过，不会误报。
- **[boundary/medium]** [boundary] app/application/harness/loop_detector.py:65-79 window 小于 repeat_threshold 时收敛检测永远不会触发（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:65-79`
  - 依据：trailing_repeat 最多只能返回 deque 的 maxlen（即 window）个元素，而 check 要求 count >= repeat_threshold。若构造时 window < repeat_threshold（例如 window=2, repeat_threshold=3），count 最大为 2，永远达不到阈值，护栏静默失效。构造参数未做任何校验或约束。
- **[logic/low]** [logic] app/application/harness/loop_detector.py:65-70 trailing_repeat 只读查询会创建桶，与 reset 语义不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:65-70`
  - 依据：trailing_repeat 通过 _bucket 访问 defaultdict 确实会创建空桶，但这是与上一条内存增长同源的表现，本身不产生错误结果（空桶返回 0）。单独看它不构成独立缺陷，故标记为非缺陷。
- **[resource_leak/medium]** [resource_leak] app/application/harness/loop_detector.py:55-63 LoopDetector._calls 使用 defaultdict，读取路径会写入空桶导致内存无界增长（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:55-63`
  - 依据：_bucket 通过 self._calls[session_id] 访问 defaultdict，即使只是查询（trailing_repeat 调用 _bucket）也会为未知 session_id 创建空 deque 并永久保留。trailing_repeat 是只读语义的查询方法，但会污染 _calls。若调用方对任意/大量 session_id 调用 trailing_repeat（或 check 后未 reset），字典条目只增不减，形成无界内存增长。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:116-118 _rank_by_relevance 中 embed_batch 返回的向量长度与 likes 不一致时降级，但未校验单个向量维度（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:116-118`
  - 依据：_cosine 内部已处理 len(left) != len(right) 返回 0.0，维度不一致不会抛异常，只是相似度为 0。属于安全降级。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:30-32 _cosine 对长度不一致向量返回 0.0，静默降级而非报错，可能导致相关性排序失真（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-32`
  - 依据：长度不一致返回 0.0 是防御性处理，避免 zip 截断产生错误相似度。虽然会静默降级，但 _rank_by_relevance 中已检查 len(vectors) != len(likes)，单条向量维度不一致时返回 0 分排到末尾，属于可接受的降级。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-98 select 中 top_k<=0 时直接返回 dislikes，但 dislikes 未做任何截断，可能超出调用方预期（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-98`
  - 依据：docstring 明确声明 dislike 全量保留、不参与 top_k 截断，这是安全底线。top_k<=0 时只保留 dislikes 符合设计。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:132-136 PreferenceSelector._latest_first 用 `p in newest` 过滤，重复偏好会突破 top_k（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:132-136`
  - 依据：newest 已按 created_at 倒序截断到 top_k，但返回时用 `[p for p in likes if p in newest]`。若 likes 中存在与 newest 中某条相等的重复偏好，`in` 判定为 True，所有相等项都会被保留，输出条数超过 top_k。这是关闭相关性排序（默认路径）时也会触发的缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:96-99 PreferenceSelector.select 在 top_k <= 0 时返回 dislikes，但未对 dislikes 去重或截断，符合安全底线设计（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-99`
  - 依据：docstring 明确 dislike 全量保留不参与截断，top_k<=0 时只保留 dislikes 是符合设计的安全底线。不是缺陷。
- **[logic/low]** [logic] app/application/prompts/loader.py:17-20 load_prompts 的 lru_cache 使提示词修改后进程内不生效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-20`
  - 依据：lru_cache(maxsize=1) 缓存首次读取结果，运行期修改 globex.yml 不会重新加载。但提示词文件是随代码发布的静态资源，正常部署流程是重启进程，缓存正是设计意图（避免每轮 IO）。不构成缺陷。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:213-220 rerank 返回分数数量与候选数不一致时 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-220`
  - 依据：_rerank 用 `rerank_scores[i]` 按 scored 的下标索引。若 Reranker 实现返回的分数列表长度小于 scored（例如后端截断、只返回 top 部分、或返回空列表），会抛 IndexError。该异常在 execute 中被 `except Exception` 捕获并降级为按向量分排序，因此不会导致整轮失败——但降级路径会静默吞掉 rerank 结果，且 rerank_applied 保持 False。这属于边界处理不严谨，但被上层捕获，影响有限。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:76-84 tokenize 对 CJK chunk 生成 2-gram 时未去重单字，短 chunk 边界处理正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:76-84`
  - 依据：range(len(chunk)-1) 对 len>=2 的 chunk 生成 len-1 个 2-gram，边界正确；len<2 时被 len(chunk)>=2 条件挡住。set 自动去重。无缺陷。
- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:175-186 _to_rejected 与 _within_price_cap 对 primary_sku 价格做币种换算，但未处理换算异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:175-186`
  - 依据：ExchangeRateTable.convert 若目标币种不支持可能抛异常，但该异常会向上冒泡使整个检索失败。不过 _to_card 中对 tariff.quote 的 ValueError 做了捕获，而价格换算路径未捕获，二者不一致。然而 spec.target_currency 通常由上游校验，且 convert 的具体行为不在本文件可见范围内，无法确认会抛异常，故不判定为缺陷。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:124-132 关键词召回在向量召回成功但为空时被跳过（实际不会，elif 覆盖）（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:124-132`
  - 依据：审查者怀疑向量召回成功但为空时不回退关键词。实际代码 `elif not scored:` 会在 scored 为空时执行关键词召回并覆盖 recall_strategy，因此不存在该缺陷。
- **[error_handling/high]** [error_handling] app/application/usecases/order_usecases.py:178-184 CancelOrderUseCase 先回补库存再保存订单，save 失败会导致重复回补（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:178-184`
  - 依据：execute 先调用 order.cancel(reason) 修改内存状态，然后循环 release 库存，最后才 save(order)。若 save 抛异常（DB 故障等），库存已回补但订单状态未持久化仍为未取消；调用方重试取消时，状态机允许再次 cancel 并再次 release，导致库存被重复回补（虚增）。正确顺序应是先持久化状态变更再回补，或使用事务/补偿。
- **[logic/low]** [logic] app/application/usecases/order_usecases.py:138-148 PlaceOrderUseCase 幂等回放路径未校验订单归属前先返回快照，且 _replay 在 buyer 不匹配时抛 OrderAccessDenied 而非返回 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:138-148`
  - 依据：_replay 中先 find 到 order_id，再 find_by_id，再比较 buyer_id，不匹配时抛 OrderAccessDenied。这是有意的安全设计（防止跨买家回放），并非缺陷。
- **[logic/low]** [logic] app/application/usecases/order_usecases.py:158-168 CancelOrderUseCase 未使用 product_repo，但这不是缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:158-168`
  - 依据：构造函数接收 product_repo 但 execute 未使用，属于冗余依赖，不影响行为正确性，不报告为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:30-31 BuyerPreference 为 frozen dataclass 却在 __post_init__ 用 object.__setattr__ 写 created_at（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:30-31`
  - 依据：frozen dataclass 中通过 object.__setattr__ 在 __post_init__ 设置默认值是标准做法，能正常工作且不破坏不可变性（构造后仍不可改）。不构成缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:24-30 BuyerPreference 的 created_at 默认空串在 __post_init__ 中填充，但 frozen dataclass 用 object.__setattr__ 正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:24-30`
  - 依据：frozen dataclass 中通过 object.__setattr__ 修改字段是标准做法，可正常工作。不是缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:47-55 PreferenceStore.delete 抽象方法只有 docstring 无 ... 或 pass，方法体为空（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-55`
  - 依据：方法体仅含 docstring 是合法的 Python（docstring 即语句），配合 @abstractmethod 子类必须实现，不会导致运行时错误。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-30 Address.one_line 未校验 state/phone/postal_code，缺失时输出空串（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-30`
  - 依据：__post_init__ 只强制 recipient_name/country/city/address_line，state/phone/postal_code 允许为空。one_line 会输出“US  CA ...（张三 ）”这类带空位的字符串。但 docstring 明确 MVP 仅存储与展示，且空 state 在部分国家（如无州省的国家）是合法的，不构成缺陷。
- **[logic/low]** [logic] app/domain/order/order.py:47-53 Order.__post_init__ 未校验币种一致性，与 docstring 不变量不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：docstring 声明“全部订单行币种一致”为不变量，但 __post_init__ 只检查非空，注释称由下单用例保证。聚合根自身不强制该不变量属于设计取舍（用例层保证），在给定文件内无法证明会产生错误行为；若 Money.add 对跨币种会抛错，则 total_amount 会失败而非静默出错。故不判定为缺陷。
- **[logic/medium]** [logic] app/domain/order/order.py:76-84 cancel 允许从 DRAFT 态取消，违反状态机不变量（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:76-84`
  - 依据：模块 docstring 声明“只有 CONFIRMED 态可以取消”，但 cancel 只拒绝已 CANCELLED 的状态，DRAFT 态订单也能被取消并写入 cancelled_at/cancel_reason。这使 DRAFT → CANCELLED 成为合法迁移，与声明的状态机 DRAFT → CONFIRMED → CANCELLED 不符，且绕过 confirm 流程。
- **[logic/high]** [logic] app/domain/order/order.py:88-92 total_amount 将首行小计重复计入一次（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-92`
  - 依据：total_amount 先用 lines[0].subtotal() 初始化 total，随后 for 循环又遍历全部 lines（包含 lines[0]）再次累加，导致第一条订单行的金额被计算两次。任何多行订单的 total_amount 都会偏大，snapshot() 回传给买家的 total_amount_major 也随之错误。
- **[boundary/low]** [boundary] app/domain/order/order_line.py:20-24 OrderLine 未校验 unit_price 类型/币种，subtotal 依赖 Money.multiply 行为（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:20-24`
  - 依据：OrderLine 只校验 quantity 为正，未校验 unit_price 非空或币种；但 Money 是值对象，multiply 的合法性由 Money 自身保证，且币种一致性由下单用例负责（order.py 注释明确说明）。在给定文件范围内无法证明存在错误行为，故不判定为缺陷。
- **[concurrency/medium]** [concurrency] app/domain/order/ports/order_idempotency_store.py:20-26 OrderIdempotencyStore.record 返回 False 表示重复，但 find/record 非原子，存在并发竞态（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:20-26`
  - 依据：端口设计为 find 后 record 两步，record 的“键已存在返回 False”暗示期望原子性，但接口未要求实现方原子化，也未提供 compare-and-set 语义。调用方若按 find→创建订单→record 的顺序使用，两个并发消费者（at-least-once 重投）可能都 find 到 None，各自创建订单，随后一个 record 返回 False 但订单已重复创建。文档强调“同一任务的重复消费必须只留一单”，而该端口契约无法保证。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:100-102 freight 计算用 round 对 CNY 分做四舍五入，quantity 很大时可能溢出或精度问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-102`
  - 依据：quantity 为正整数，round 对整数运算结果取整，Python int 无溢出。quantity 极大时运费线性增长，属于业务上不合理的输入但不会导致程序错误。
- **[boundary/medium]** [boundary] app/domain/shipping/tariff_schedule.py:99-102 免税额度判断用单件小计，多件时 de_minimis_applied 误判（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:99-102`
  - 依据：与上一条同源：taxable_minor_cny 基于单件 subtotal 计算，quantity > 1 时即使总价超过免税额度，也可能被判定为 de_minimis_applied=True，导致关税为 0。
- **[error_handling/low]** [error_handling] app/domain/shipping/tariff_schedule.py:105-106 quote 未校验 category 是否在费率表中，未知品类走 "*" 兜底但若目的国表缺 "*" 会 KeyError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:105-106`
  - 依据：当前 _TARIFF_RATES 中所有目的国都定义了 "*"，rate_table["*"] 不会 KeyError。属于数据完整性依赖，当前数据满足。
- **[logic/low]** [logic] app/domain/shipping/tariff_schedule.py:112-114 免税额度判断只看商品小计，未计入运费，与「到手价」口径可能不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:112-114`
  - 依据：docstring 明确写「关税 = 商品小计超出免税额度部分 × 费率」，即免税额度只针对商品小计，不含运费。实现与 docstring 一致，属于业务口径选择而非缺陷。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:96-104 关税计算用 subtotal 而非 subtotal*quantity，多件时关税基数错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:96-104`
  - 依据：quote 接收 quantity 参数，运费按 quantity 递增计算，但关税基数 `subtotal_cny` 只用了单件 subtotal，没有乘以 quantity。当 quantity > 1 时，关税只按一件商品的小计计算，导致到手价偏低。运费逻辑明确考虑了 quantity，说明 quantity 语义是件数，关税也应乘以件数。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:140-150 RedisCache.zadd_and_count 的 pipeline 中 zcard 结果索引依赖命令顺序，若 zremrangebyscore 返回类型变化不影响，但 results[2] 假设固定（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:140-150`
  - 依据：pipeline 按顺序执行 zremrangebyscore、zadd、zcard、expire，execute 返回结果列表顺序与命令顺序一致，results[2] 确实是 zcard 的结果。索引正确。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-126 set_if_absent 在 Redis 异常时返回 True，破坏幂等语义（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-126`
  - 依据：docstring 明确说明这是有意的降级策略：Redis 不可用时返回 True（视为抢到），宁可退化成没有幂等保护也不能因缓存故障拒绝服务。这是显式的设计取舍，不是缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:132-152 RedisCache.zadd_and_count 在 Redis 故障时返回 0，导致限流失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:132-152`
  - 依据：docstring 说明“按不限流处理”，这是有意的 fail-open 策略。返回 0 表示窗口内计数为 0，调用方通常判断 count > limit 才限流，因此故障时放行。属于设计取舍，不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:145-148 zadd_and_count 在 Redis 异常时返回 0，等于不限流（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:145-148`
  - 依据：docstring 明确说明「按不限流处理」，是有意的 fail-open 降级。返回 0 表示窗口内计数为 0，调用方据此放行。属于设计取舍，不是缺陷。
- …另有 14 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/harness/drift_detector.py:137-139 consecutive_empty 在非空结果时不会重置，导致探索发散信号误报（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:137-139`
  - 依据：observe_action 中 consecutive_empty 只在 result_empty=True 时自增，result_empty=False 时保持原值不变（else 分支返回 trace.consecutive_empty 本身）。因此只要历史上累计出现过 3 次空结果（不必连续），该计数器就永久 >= EMPTY_RESULT_LIMIT，之后每次 computational_signals 都会误报“连续 N 次检索无候选”，即使中间穿插了大量成功检索。这与 docstring 声明的“连续 3 次检索返回空候选”语义不符。
  - 争议对手：9f227134f9a9
- **[error_handling/low]** [error_handling] app/application/prompts/loader.py:17-20 yaml.safe_load 可能返回 None，调用方按 dict 使用会出错（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-20`
  - 依据：若 globex.yml 为空文件或仅含注释，yaml.safe_load 返回 None，而函数签名声明返回 dict，调用方随后做 prompts['xxx'] 会抛 TypeError。缺少对 None 的兜底。
  - 争议对手：c01d23dc4802
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-132 向量召回成功但结果为空时 recall_strategy 仍标 embedding_only 且不回退关键词（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-132`
  - 依据：当 embedder 与 vector_index 均存在且 _vector_recall 正常返回空列表时，recall_strategy 被置为 'embedding_only'，scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 因 scored 为空而跳过精排；`elif not scored:` 分支会执行关键词召回并把 recall_strategy 覆盖为 'keyword_2gram'。等等——需要仔细看：elif 确实会在 scored 为空时执行关键词召回。因此空结果时实际会回退关键词。但若向量召回返回非空、精排抛异常，则 recall_strategy 保持 embedding_only 且不回退关键词，这是设计意图（按向量分排序）。真正的问题在于：向量召回返回空列表时，虽然会走 elif 关键词召回，但 recall_strategy 被覆盖为 keyword_2gram，这是正确的。所以此处并非缺陷。
  - 争议对手：780735c9972b
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:116-116 PlaceOrderUseCase 在 record 冲突回滚后未删除已保存订单（与第一条同源，单独标注 save 位置）（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:116-116`
  - 依据：save 在幂等登记之前执行，导致任何 record 失败路径都无法撤销已持久化的订单；OrderRepository 端口也没有 delete 方法，无法补偿。
  - 争议对手：48a44f16c9be, 48a44f16c9be
- **[api_misuse/medium]** [api_misuse] app/domain/order/ports/order_repository.py:14-25 OrderRepository 端口缺少删除/作废方法，使 PlaceOrder 的补偿逻辑无法完整回滚（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_repository.py:14-25`
  - 依据：端口只暴露 save/find_by_id/next_order_id，没有 delete 或 mark_failed。PlaceOrderUseCase 在幂等冲突时需要撤销已 save 的订单，但端口能力不足，导致调用方只能释放库存而留下幽灵订单。这是端口设计与用例需求不匹配导致的真实缺陷。
  - 争议对手：e22a8a8fe325

## 独立性准入闸门

- 判定：`observe`（仅报告（observe））
- 原因：输出隔离已被破坏：Reader 看到了其他 Reader 的结论，重分区无法撤销污染
- 有效通道：2.45｜归一化 81.8%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：12｜覆盖正常：19｜无法判定：0
- 单 Reader 检出率：56.3%（重捕对 3，已观测 59，估计总体 104.7778
- 待补检分组：app, app/application/memory, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/cache, app/domain, app/domain/order, app/application/harness, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 2 | 0 | `reader_miss` | 19.1% |
| `17da7cc20bb4` | 2 | 0 | `reader_miss` | 19.1% |
| `477fac3ae5ae` | 2 | 0 | `reader_miss` | 19.1% |
| `4ad98b411bb7` | 2 | 0 | `reader_miss` | 19.1% |
| `4fcaf3c8939f` | 2 | 0 | `reader_miss` | 19.1% |
| `538d958c9657` | 2 | 0 | `reader_miss` | 19.1% |
| `6fd64302ee4f` | 2 | 0 | `reader_miss` | 19.1% |
| `7c2ab632b69d` | 2 | 0 | `reader_miss` | 19.1% |
| `87535cbc08cd` | 2 | 0 | `reader_miss` | 19.1% |
| `931849f6e1d6` | 2 | 0 | `reader_miss` | 19.1% |
| …另有 2 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/harness` | 2 | 0 | 2 | 2 | 2 | 0 | 0 | 0 |
| `app/application/memory` | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 2 |
| `app/domain/shipping` | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 2 | 1 | 2 | 0 | 0 | 0 | 1 |
| `app/infrastructure/security` | 1 | 0 | 0 | 2 | 0 | 2 | 0 | 2 |

矩阵填充率 30%（单元格值 = 独立 Agent 数）
