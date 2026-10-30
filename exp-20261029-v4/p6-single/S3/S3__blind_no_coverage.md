# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 38 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：38
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：72 个节点 / 107 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 38 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/harness/assertions.py:88-92 check_schema 对非字符串非 dict 的 tool_result（如 list）报'不是 JSON 对象'，但若工具合法返回 list 会被误判（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:88-92`
  - 依据：TOOL_REQUIRED_FIELDS 中登记的工具（product_search/category_insight/订单三工具）按约定都返回 dict，list 返回本就不符合契约，报错是正确行为。不构成缺陷。
- **[logic/high]** [logic] app/application/harness/assertions.py:128-148 SequencingTracker.check 对 create_order_tool 的硬拒逻辑与模块 docstring 声明的'有证据才硬拒'不一致：无观测记录时也会硬拒（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:128-148`
  - 依据：模块 docstring 明确声明：'本会话已观测到工具调用、却没有一次检索 → 硬拒；完全没有观测记录（刚恢复/首次调用）→ 降级为警告'。但 check() 的实现中，只要 tool_name 在 HARD_REJECT_TOOLS 且 prereq 不在 history 中，就无条件设置 reject_reason，完全没有检查 history 是否为空（即是否有观测证据）。当会话从 AgentState 快照恢复、内存记录为空时，history 为空，prereq 不在其中，代码直接硬拒 create_order_tool——这正是 docstring 说要避免的'把合法下单误杀'。实现与声明的核心设计意图直接矛盾，是真实缺陷。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:141-144 due() 在 rounds 为 0 时返回 True，未观察任何动作即触发检测（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:141-144`
  - 依据：0 % check_interval == 0，due 返回 True。但 check 中 computational_signals 在无 recent_actions 时不会产生目标遗忘信号，且 judge 分支前有 `if not trace.original_query or not trace.recent_actions: return report` 保护，因此不会误判漂移，只是多一次空判定。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:168-176 成本失控信号在 history 长度恰为 6 时 baseline 只含 3 个样本，且 recent 与 baseline 重叠判断口径不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:168-176`
  - 依据：len(history) >= 6 时 history[:-3] 至少 3 个元素，baseline 不会除零；recent 取最后 3 个、baseline 取之前所有，二者不重叠。虽然样本少时统计不稳，但不构成确定性错误，属可接受设计。
- **[logic/high]** [logic] app/application/harness/drift_detector.py:133-135 recent_actions 用 del [:3] 截断，保留的是最旧而非最近 3 轮（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:133-135`
  - 依据：注释写“只留最近 3 轮”，但 del trace.recent_actions[:3] 删除的是列表头部（最旧的元素）。当列表长度超过 3 时，每次 append 后删除前 3 个，实际保留的是最后追加的少数元素，行为随长度变化：长度 4 时删掉前 3 个只剩最新 1 个；长度 5 时删前 3 剩 2 个；长度 6 时删前 3 剩 3 个……即保留数量在 1~3 之间抖动，且丢弃的是历史而非最旧。这直接污染“目标遗忘”关键词命中率与 LLM 终审输入（recent_actions 拼接），使漂移判定基于错误的窗口。正确应为 trace.recent_actions = trace.recent_actions[-3:]。
- **[boundary/medium]** [boundary] app/application/harness/loop_detector.py:47-55 LoopDetector 的 window 参数在首次分桶时被忽略（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:47-55`
  - 依据：_calls 的 default_factory 固定使用 DEFAULT_WINDOW 作为 maxlen。当构造 LoopDetector(window=N) 且 N != DEFAULT_WINDOW 时，_bucket 首次访问会通过 defaultdict 创建 maxlen=DEFAULT_WINDOW 的 deque，随后 if bucket.maxlen != self.window 成立并重建为 maxlen=N——这一步本身能纠正。但重建时用 deque(bucket, maxlen=self.window)，若 N < DEFAULT_WINDOW 且 bucket 已含元素，会截断；更关键的是 record() 先 append 再在下次访问时重建，第一次 append 发生在 maxlen=DEFAULT_WINDOW 的桶上，若 N < DEFAULT_WINDOW 且此前已积累超过 N 条记录，重建会保留尾部 N 条（deque 截断保留右侧），行为尚可。真正的问题是：window 被设为 0 或负数时 deque(maxlen=0) 会丢弃所有记录，trailing_repeat 恒为 0，检测完全失效且无任何报错。
- **[logic/low]** [logic] app/application/harness/loop_detector.py:57-64 trailing_repeat 只统计尾部连续重复，与文档「窗口内出现次数」语义不符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:57-64`
  - 依据：模块 docstring 说「同一工具在窗口内连续出现达此次数即判定打转」，trailing_repeat 从尾部反向遍历、遇到不同工具即 break，正是「尾部连续」语义，与常量注释一致。虽然窗口内非连续的交替调用（A,B,A,B,A）不会被判为打转，但这是设计取舍（避免误杀正常重试），不构成缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:88-91 select 中 top_k <= 0 时返回 dislikes，但未处理 dislikes 为空且 likes 非空的情况——行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-91`
  - 依据：top_k<=0 时只保留 dislike 是文档声明的安全底线，返回空列表也符合语义。不是缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-37 _cosine 对零向量返回 0.0，但 embed_batch 返回的向量若含 None 会在 sum 中抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：_cosine 只在 _rank_by_relevance 的 try 块之外被调用（scored 列表推导在 try 之后），若向量含 None 会抛 TypeError 且不被捕获。但 embed_batch 的契约应返回 float 列表，且 len 检查已过滤数量不一致。属于对上游契约的信任，不是本文件缺陷。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:118-120 _rank_by_relevance 用 `p in picked` 复原顺序，依赖 BuyerPreference 的相等语义，若为 dataclass 且含不可比较字段或重复 statement 会出错（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-120`
  - 依据：`[p for p in likes if p in picked]` 依赖 `in` 的相等比较。若 BuyerPreference 是 dataclass（默认 eq=True），两条 statement 相同但 created_at 不同的偏好会被视为不同对象，这没问题；但若两条偏好完全相等（同 kind、同 statement、同 created_at），`p in picked` 对两条都返回 True，导致输出条数超过 top_k。更关键的是：若 BuyerPreference 未定义 __eq__（普通类），`in` 退化为身份比较，此时 picked 中的对象来自 likes 本身，身份比较仍成立，所以这条路径安全。真正的风险在于重复对象导致输出膨胀。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:122-126 _latest_first 同样用 `p in newest` 复原顺序，重复对象会导致输出超过 top_k（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:122-126`
  - 依据：与 _rank_by_relevance 相同的问题：`[p for p in likes if p in newest]` 在存在完全相等对象时会把所有相等对象都保留，输出条数超过 top_k。这是相关性关闭时的默认路径，触发面更大。
- **[error_handling/low]** [error_handling] app/application/prompts/loader.py:17-19 load_prompts 用 lru_cache 缓存，文件缺失或 YAML 为空时返回 None 而非 dict（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-19`
  - 依据：yaml.safe_load 对空文件返回 None，与返回类型 dict 不符，但这是配置错误场景；文件缺失会抛 FileNotFoundError 属预期失败。未发现确定性缺陷。
- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:175-186 _to_rejected 与 _within_price_cap 用 primary_sku 价格做价格上限判断，但商品卡展示的是 primary_sku 价格，多 SKU 商品可能因主 SKU 超预算被整体过滤（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:175-186`
  - 依据：价格上限过滤基于 primary_sku 价格是产品设计选择（用主 SKU 代表商品价格档位），并非缺陷。多 SKU 商品若主 SKU 超预算但其他 SKU 在预算内会被过滤，这是有意的简化，且 filtered_out 会如实回传原因，模型可据此判断。不构成真实缺陷。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:118-133 关键词召回分支在向量召回成功但结果为空时被错误触发，且 recall_strategy 标注与实际不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:118-133`
  - 依据：当 embedder 与 vector_index 均存在且 _vector_recall 成功返回空列表时，recall_strategy 被设为 'embedding_only'，但 scored 为空。随后 `if recall_strategy == "embedding_only" and scored:` 为假，进入 `elif not scored:` 分支执行关键词召回并把 recall_strategy 改为 'keyword_2gram'。这本身是合理的降级，但问题在于：如果向量召回成功返回非空、rerank 抛异常，recall_strategy 保持 'embedding_only'，这是对的。真正的缺陷是当向量召回成功但为空时，代码会静默走关键词召回，而 recall_strategy 被标为 keyword_2gram——这掩盖了'向量索引里确实没有匹配'这一事实，与模块 docstring 声明的降级链（embedding 服务异常时才兜底 keyword）不一致。更关键的是：向量召回成功但为空，说明语义检索无结果，此时用 2-gram 关键词召回可能召回语义不相关但字面重叠的商品，且 recall_strategy 谎报为 keyword_2gram 让调用方无法区分'embedding 挂了'与'embedding 正常但无命中'。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:66-74 tokenize 对含 CJK 的 chunk 生成 2-gram 时，若 chunk 混有非 CJK 字符（如 'iphone手机'）会生成跨字符边界的 2-gram（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:66-74`
  - 依据：对 'iphone手机' 生成 'ip','ph','ho','on','ne','e手','手机' 等 2-gram，其中 'e手' 是跨语言边界的噪声 term，但查询与文档用同一 tokenize 函数，噪声 term 在两侧对称产生，不会导致召回错误，只是略微增加匹配面。不构成真实缺陷。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:296-312 _overlay_authoritative_stock 中 sku_ids 可能含重复 sku_id，get_many 返回后按 sku_id 覆盖，重复不影响正确性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-312`
  - 依据：sku_ids 列表可能含重复（不同商品卡共享 SKU 不太可能，但即使重复也只是多查一次），get_many 通常按 id 去重查询，覆盖逻辑按 sku_id 匹配，重复不影响结果正确性。不构成缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:196-201 取消订单先回补库存再保存，save 失败会导致库存重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:196-201`
  - 依据：CancelOrderUseCase.execute 先调用 order.cancel(reason) 修改内存状态，然后循环 release 库存，最后才 save。若 save 抛异常（DB 故障等），库存已经回补但订单状态未持久化仍为原状态；调用方重试取消时，order.cancel 会再次成功（因为持久化状态仍是未取消），从而再次 release 库存，造成库存虚增。注释声称“重复取消会被状态机挡在上一步”，但该保证只在 save 成功后才成立。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:118-126 幂等键冲突回滚后未撤销已保存的订单，导致重复扣减/孤儿订单（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-126`
  - 依据：在 idempotency.record 返回 False（并发下另一路先登记同一键）时，代码执行 _rollback(reserved) 释放库存，但此时 order 已经通过 self._order_repo.save(order) 持久化。回滚只释放库存，没有删除/作废已保存的订单，于是留下一个库存已释放但订单仍存在的孤儿订单；若随后 _replay 返回赢家订单，本次订单仍残留在仓储中。更严重的是，若 _replay 返回 None（赢家登记后尚未写单），代码抛 ValueError，但本次已保存的订单依然存在且库存已释放，后续该订单被查询/取消时会再次 release 库存，造成库存虚增。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-30 BuyerPreference 的 created_at 默认值在 frozen dataclass 中通过 object.__setattr__ 设置，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-30`
  - 依据：frozen dataclass 的 __post_init__ 中用 object.__setattr__ 修改字段是标准做法，created_at 为空时补当前时间，逻辑正确。
- **[boundary/low]** [boundary] app/domain/order/address.py:22-25 Address.__post_init__ 未校验 state/postal_code/phone，one_line 可能输出 None（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:22-25`
  - 依据：校验列表刻意只含 recipient_name/country/city/address_line，state/postal_code/phone 允许为空（部分国家无州/邮编）。one_line 会输出空串而非 None（dataclass 字段无默认值，调用方必须传值，传 None 才会出现 None）。属设计取舍，非确定性缺陷。
- **[logic/medium]** [logic] app/domain/order/order.py:76-84 cancel 允许从 DRAFT 态取消，违反文档声明的状态机（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:76-84`
  - 依据：模块 docstring 明确不变量为「只有 CONFIRMED 态可以取消」，但 cancel() 只拦截了 CANCELLED 态，DRAFT 态订单也能被取消，并写入 cancelled_at/cancel_reason。这使状态机 DRAFT → CONFIRMED → CANCELLED 被绕过，产生 DRAFT→CANCELLED 的非法迁移。
- **[logic/high]** [logic] app/domain/order/order.py:88-92 Order.total_amount 把首行小计重复计入一次（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:88-92`
  - 依据：total_amount 先用 lines[0].subtotal() 初始化 total，随后又对 lines 全量（包含 lines[0]）循环累加，导致第一条订单行的小计被计算两次。任何多行订单（以及单行订单）的 total_amount 都会偏大，snapshot() 回传给买家的 total_amount_major 也随之错误。正确写法应是 total = lines[0].subtotal() 后从 lines[1:] 开始累加，或从零值 Money 开始累加。
- **[logic/low]** [logic] app/domain/order/order_line.py:20-24 OrderLine 未校验 unit_price 币种/非负，币种一致性仅靠调用方（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:20-24`
  - 依据：Order 的 docstring 明确写「币种一致性由下单用例在组装订单行时保证」，OrderLine 只校验 quantity 为正。这是有意的分层取舍，且 Money.multiply 的语义由 Money 自身保证，本文件内没有可引用的错误行为，故不判为缺陷。
- **[concurrency/low]** [concurrency] app/domain/order/ports/order_idempotency_store.py:22-24 OrderIdempotencyStore.record 的返回值语义依赖实现，端口未约束并发原子性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:22-24`
  - 依据：端口只声明 record 在键已存在时返回 False，未要求 find+record 原子。这是端口契约层面的抽象，具体实现（如 Redis SETNX）可保证原子性；端口本身不构成缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:118-120 关税计算用 round() 对分单位做四舍五入，但 taxable_minor_cny * tariff_rate 可能产生浮点误差导致分位偏差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:118-120`
  - 依据：round() 对浮点乘积取整，在极端边界（如 x.5）可能因银行家舍入产生 1 分偏差，但这是金额计算的常见可接受误差，且 Money 以分为最小单位，1 分偏差不构成真实业务缺陷。不报告为缺陷。
- **[logic/medium]** [logic] app/domain/shipping/tariff_schedule.py:100-122 quote 中运费按 quantity 递增但 subtotal 未乘 quantity，导致多件下单时到手价小计与运费口径不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-122`
  - 依据：quote 接收 quantity 参数，运费按 '首件全价 + 续件 60%' 随 quantity 增长，但 subtotal 直接使用传入的 subtotal 不做 quantity 乘法，关税也基于未乘 quantity 的 subtotal_cny 计算。若调用方传入的是单件小计（catalog_search 中确实传 quantity=1 且 subtotal=primary.price，暂时一致），但接口语义上 quantity 与 subtotal 的关系未定义：当 quantity>1 时，运费按多件算而小计/关税按单件算，到手价会严重偏低。这是接口契约缺陷——quantity 参数只影响运费不影响小计与关税，任何 quantity>1 的调用都会得到错误到手价。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:137-152 zadd_and_count 在 pipeline 中 zadd 后 zcard 计数包含本次成员，但 zremrangebyscore 用 now-window 作为上界，边界成员被重复计入/漏计（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-152`
  - 依据：zremrangebyscore(key, 0, now - window_seconds) 是闭区间，恰好等于 now-window_seconds 的成员会被删除，而窗口语义通常应为 (now-window, now]。这会导致边界处少计一个请求，属于限流偏宽松而非偏严格，不会造成拒绝服务；且时间戳为浮点，精确命中的概率极低。不构成实际缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:92-96 get_json 的 delete 在 json.loads 失败时被 await，但 delete 是 async 且吞异常——正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:92-96`
  - 依据：delete 已 await，异常被吞，行为正确。
- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:122-135 set_if_absent 在 Redis 异常时返回 True，可能破坏幂等语义导致重复执行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:122-135`
  - 依据：这是文档明确声明的设计取舍：Redis 不可用时宁可退化为无幂等保护也不能拒绝服务。属于有意的降级策略，不是缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:143-152 zadd_and_count 的 pipeline 使用 transaction=True，但 zcard 在 zadd 之后执行，计数包含本次请求——限流语义应为包含本次（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:143-152`
  - 依据：先 zadd 再 zcard 使返回值包含本次请求，这是滑动窗口限流的常见语义（当前请求计入窗口）。调用方据此判断是否超限。不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:190-196 lookup 中 entry.get('vector', []) 与查询向量维度不一致时静默返回 0 相似度（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:190-196`
  - 依据：_cosine 在长度不等时返回 0.0，低于阈值即视为未命中，行为安全（宁可多花一次调用）。这是有意的防御而非缺陷。
- **[concurrency/low]** [concurrency] app/infrastructure/cache/semantic_cache.py:213-219 语义缓存 remember 的读-改-写非原子，并发写会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:213-219`
  - 依据：remember 先 _load_entries 读取整个桶，append 后再 set_json 整体覆盖。两个并发 remember 对同一 buyer/scope 会各自读到旧列表，后写者覆盖先写者，导致先写入的条目丢失。虽然只是缓存命中率下降而非正确性错误，但属于真实的并发缺陷。
- **[security/low]** [security] app/infrastructure/cache/semantic_cache.py:96-98 is_cacheable_query 仅对原始 query 做正则，未对归一化后文本检查（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:96-98`
  - 依据：_UNSAFE_RE 匹配的是原始 query，而 _normalize 只压空白和去尾部标点，不会引入新的敏感词；因此对原始 query 检查已足够覆盖归一化后的文本。不构成绕过。
- **[logic/low]** [logic] app/infrastructure/security/content_filter.py:47-55 sanitize_tool_output 逐条正则替换，前一条替换插入的占位符可能被后续模式再次匹配或破坏上下文（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:47-55`
  - 依据：占位符 '[内容已过滤：疑似注入]' 不含任何危险模式的关键词（ignore/system prompt/you are now 等），后续正则不会匹配它。逐条 subn 是标准做法，不会造成重复替换或破坏。不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:41-41 内部工具名正则使用 \b 边界，下划线连接的更长标识符可能漏判（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:41-41`
  - 依据：\b 在 Python 正则中把下划线视为单词字符，因此 \bproduct_search_tool\b 能正确匹配独立出现的工具名，但不会匹配 product_search_tool_v2 这类更长标识符。考虑到 _INTERNAL_TOOLS 已按真实工具集逐个列出，且文档明确说明刻意不用宽泛模式以避免误伤，这一行为符合设计意图，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:52-53 audit_output 对 None 之外的空串返回安全，但非字符串输入会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:52-53`
  - 依据：函数签名声明 text: str，调用方按契约应传字符串。if not text 只处理空串/None，若传入非字符串（如 list）会在 pattern.subn 处抛 TypeError。但这是类型契约内的正常行为，且本文件内无证据表明调用方会传非字符串，故不认定为缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:38-38 内部服务地址正则未加词边界，可能误伤正常 URL 或漏判带路径的地址（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-38`
  - 依据：该模式 r"https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?" 没有前置边界，理论上会匹配 https://redisfoo 这类以内部主机名开头的域名。但实际影响有限：一是这类域名在买家回复中极少出现；二是即便误判，也只是把一段 URL 替换成 [已脱敏]，并把 safe 置为 False 触发告警，不会阻断回复（文档已声明脱敏不阻断）。因此不构成需要修复的缺陷，仅记录为已知的收窄取舍。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:57-62 多模式顺序替换可能产生二次匹配或破坏已脱敏文本（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:57-62`
  - 依据：循环按顺序对 cleaned 反复 subn。REDACTED 为 "[已脱敏]"，不含任何敏感模式可匹配的子串（不含 sk-、http://、内部工具名等），因此后续模式不会再次命中已替换内容，也不会造成重复脱敏或无限增长。顺序替换在此场景下是安全的。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：31｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app, app/application/harness, app/application/memory, app/infrastructure/security, app/domain/order, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `0ca665a578e5` | 1 | 2 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `2d259bcddd0a` | 1 | 1 | `partition_gap` | — |
| `32d2dfd314a0` | 1 | 2 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `4ad98b411bb7` | 1 | 0 | `partition_gap` | — |
| `4fcaf3c8939f` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| …另有 21 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/harness` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 0 |
| `app/infrastructure/security` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
