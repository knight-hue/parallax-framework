# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 44 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：46
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：83 个节点 / 127 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 45 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

> ⚠️ 本节共 **44** 条，此处**仅列出前 40 条**（按置信度降序）。完整清单见同目录的 `.claims.json`。

- **[error_handling/low]** [error_handling] app/application/harness/assertions.py:88-100 check_schema 对非字符串非 dict 的合法 JSON 标量（如数字/列表）报"不是 JSON 对象"，但字符串解析失败分支已覆盖；实际缺陷是 json.loads 对 bytes 的处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:88-100`
  - 依据：当 tool_result 是 str 时 json.loads 可能抛 JSONDecodeError 或 TypeError，两者都被捕获并记为 schema 失败；当 tool_result 是 dict 时直接通过；其他类型（list/int/None）走 `not isinstance(data, dict)` 分支记为失败。这是符合预期的行为，不构成缺陷。
- **[logic/high]** [logic] app/application/harness/assertions.py:137-152 SequencingTracker.check 的硬拒逻辑与 docstring 声明的"有证据才硬拒"不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/assertions.py:137-152`
  - 依据：模块 docstring 明确声明：create_order_tool 只有在"本会话已观测到工具调用、却没有一次检索"时才硬拒；完全没有观测记录（刚恢复/首次调用）应降级为警告。但 check() 的实现只判断 `prereq in history`，history 为空时同样进入 `tool_name in HARD_REJECT_TOOLS` 分支并设置 reject_reason，即首次调用 create_order_tool（history 为空）会被硬拒。这与文档声明的恢复场景（AgentState 快照恢复后内存记录为空）直接冲突，会把合法下单误杀。代码中没有任何对 `history` 是否为空的判断。
- **[boundary/low]** [boundary] app/application/harness/drift_detector.py:148-151 check_interval 为 0 时 due() 抛 ZeroDivisionError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:148-151`
  - 依据：check_interval 是公开可配置字段，若装配层误配为 0，trace.rounds % 0 会抛 ZeroDivisionError，且该异常不在 check() 的 try 保护范围内（try 只包住 judge 调用），会直接打断主链路。缺少对非正整数的校验。
- **[logic/low]** [logic] app/application/harness/drift_detector.py:176-184 成本失控基线计算在 history 长度恰为 6 时 baseline 只含 3 个样本，与“历史均值”语义偏差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:176-184`
  - 依据：len(history) >= 6 时 history[:-3] 至少 3 个元素，baseline 分母非零，recent_avg 与 baseline 分别取最后 3 个和之前所有样本，逻辑自洽；baseline > 0 的保护也避免了除零。虽然样本少时统计不稳，但不构成确定性缺陷。
- **[boundary/low]** [boundary] app/application/harness/loop_detector.py:72-80 trailing_repeat 只统计窗口尾部连续次数，窗口长度小于阈值时永远无法触发（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:72-80`
  - 依据：若 window < repeat_threshold，尾部连续计数最多为 window，永远达不到阈值，检测失效。但默认 window=6、threshold=3，且这是构造参数组合问题；在默认配置下行为正确。作为可配置组合的边界风险记录，但默认路径不构成缺陷。
- **[logic/low]** [logic] app/application/harness/loop_detector.py:62-70 LoopDetector._bucket 重建 deque 时 maxlen 变更会丢弃旧记录，但重建后仍保留旧元素顺序，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:62-70`
  - 依据：deque(bucket, maxlen=self.window) 会保留 bucket 中现有元素（若超过新 maxlen 则保留最右侧的 maxlen 个），符合滑动窗口语义；重建后写回 self._calls[session_id]，后续调用拿到新 deque。逻辑正确。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:108-112 PreferenceSelector._rank_by_relevance 中 embed_batch 返回空列表时 len(vectors)!=len(likes) 判断正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:108-112`
  - 依据：若 embed_batch 返回空列表而 likes 非空，len(vectors) != len(likes) 成立，降级为 _latest_first。判断正确。不是缺陷。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:33-40 _cosine 对零向量返回 0.0，但未处理 NaN/Inf 输入（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-40`
  - 依据：embedding 服务通常返回有限浮点数。若返回 NaN，dot/norm 会产生 NaN，排序时 NaN 比较行为未定义（Python 中 NaN 比较总是 False，sort 可能产生不稳定顺序）。但这是 embedding 服务契约问题，且实际中极少发生。判定为 not_a_defect（低概率）。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:118-120 偏好相关性排序用 `p in picked` 依赖对象相等性，可能误删/重复（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-120`
  - 依据：`[p for p in likes if p in picked]` 使用 `in` 判断，依赖 BuyerPreference 的 __eq__。若 BuyerPreference 是 dataclass（frozen 或非 frozen），相等性按字段比较；两条内容完全相同的偏好（同 kind、同 statement、同 created_at）会被视为相等，导致两条都被保留或都被丢弃。但这是极端边界，且实际偏好通常有唯一 id 字段。需要确认 BuyerPreference 定义才能定性；在无法看到该文件的情况下，不将其作为确认缺陷报告。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:96-98 top_k<=0 时返回 dislikes 但未按稳定顺序，且忽略 likes 的语义正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-98`
  - 依据：top_k<=0 时只返回 dislikes，符合文档声明的安全底线（dislike 全量保留）。dislikes 保持原相对顺序，稳定。不是缺陷。
- **[error_handling/low]** [error_handling] app/application/prompts/loader.py:18-20 yaml.safe_load 可能返回 None 或非 dict，与返回类型 dict 不符（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:18-20`
  - 依据：yaml.safe_load 在文件为空、仅含注释或仅含文档分隔符时返回 None；若顶层是列表则返回 list。函数签名声明 -> dict 但未做任何校验，调用方按 dict 使用（如 .get / []）会抛 AttributeError/TypeError，且该异常会被 lru_cache 缓存吗——不会缓存异常，但每次调用都会重复失败。属于缺少对解析结果的校验。
- **[logic/low]** [logic] app/application/prompts/loader.py:17-20 load_prompts 使用 lru_cache 缓存可变 dict，调用方可污染全局提示词（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/prompts/loader.py:17-20`
  - 依据：load_prompts 返回的是被 lru_cache 缓存的同一个 dict 对象。任何调用方对返回值做原地修改（例如 prompts['x'] = ... 或 prompts.pop(...)）都会永久污染缓存，后续所有调用者拿到被篡改的提示词，且没有任何重新加载的途径（maxsize=1 且无 cache_clear 封装）。这是缓存可变对象导致的真实缺陷，而非风格问题。
- **[boundary/medium]** [boundary] app/application/usecases/catalog_search.py:175-184 _to_rejected 中 spec.target_currency 可能为 None 导致 convert 失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:175-184`
  - 依据：_to_rejected 与 _within_price_cap 都调用 `self._tariff.rates.convert(product.primary_sku().price, spec.target_currency)`。若 spec.target_currency 为 None 或空字符串（ProductSearchSpec 未强制要求），ExchangeRateTable.convert 可能抛异常。_within_price_cap 在 _reject_reason 中被调用，若抛异常会中断整个 execute（该路径没有 try/except 包裹）。_to_rejected 同样无保护。需要确认 ProductSearchSpec 是否保证 target_currency 非空；若 spec 允许 target_currency 为空（例如仅做关键词搜索不关心币种），则这是真实缺陷。由于无法看到 ProductSearchSpec 定义，标记为疑似缺陷。
- **[boundary/high]** [boundary] app/application/usecases/catalog_search.py:213-222 rerank 返回分数数量与候选数不一致时索引越界（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:213-222`
  - 依据：_rerank 中 `rerank_scores[i]` 直接按 scored 的索引取值，未校验 rerank_scores 长度是否等于 len(scored)。若 Reranker 实现返回的分数少于候选数（例如截断、过滤、或返回空列表），会抛 IndexError。该异常会被 execute 中的 except 捕获并降级为按向量分排序，因此不会导致请求失败——但 rerank_applied 保持 False，且日志会记录误导性的'rerank 不可用'。更严重的是：若 rerank_scores 比 scored 长，多余分数被静默丢弃，不会报错。整体上异常被吞掉，功能降级而非崩溃，因此实际影响是'rerank 静默失效'而非崩溃。但 IndexError 被当作'rerank 不可用'处理，掩盖了 Reranker 实现的真实 bug。判定为缺陷（error_handling 更贴切，但边界越界是直接触发点）。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:128-140 向量召回成功但返回空列表时不会走关键词兜底（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:128-140`
  - 依据：当 embedder 与 vector_index 都存在且 _vector_recall 成功返回空列表（例如 Qdrant 中确实没有匹配、或 find_by_ids 全部落空）时，recall_strategy 被设为 'embedding_only'，scored 为空。随后 `if recall_strategy == 'embedding_only' and scored:` 为 False，进入 `elif not scored:` 分支执行关键词召回。这一分支实际上会兜底。但注意：如果向量召回返回非空、rerank 抛异常，则 recall_strategy 保持 'embedding_only'，scored 保留向量分排序——这是设计意图。真正的问题在于：向量召回成功但为空时，recall_strategy 最终被覆盖为 'keyword_2gram'，可观测性上无法区分'向量召回为空后兜底'与'向量服务异常兜底'。这属于可观测性瑕疵而非功能错误，降级为 not_a_defect。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:232-240 关键词召回分数并列时排序不稳定，与向量路径的确定性承诺不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:232-240`
  - 依据：_keyword_recall 中 `candidates.sort(key=lambda pair: pair[0], reverse=True)` 只按分数排序，分数并列时依赖 list_all() 的返回顺序。虽然 execute 后续有 `filtered.sort(key=lambda item: (-item[0], item[1].product_id))` 做兜底，但该兜底发生在过滤之后，且 filtered 只包含通过硬约束的项——被过滤掉的 filtered_out 顺序仍不稳定。更重要的是：_keyword_recall 的排序结果在 execute 中会先经过 _reject_reason 过滤再排序，最终 hits 顺序是稳定的。因此实际输出稳定。判定为 not_a_defect。
- **[logic/low]** [logic] app/application/usecases/catalog_search.py:258-270 _to_card 中 landed_price 计算用 primary.price 但未考虑 quantity 与多 SKU（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:258-270`
  - 依据：商品卡展示的是单件到手价，quantity=1 是合理默认。多 SKU 时只展示主 SKU 的到手价，符合'商品卡'语义。不是缺陷。
- **[performance/low]** [performance] app/application/usecases/catalog_search.py:296-310 _overlay_authoritative_stock 中 sku_ids 可能包含重复项，get_many 返回 dict 覆盖无问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:296-310`
  - 依据：sku_ids 可能有重复（不同商品共享 SKU 不太可能，但同一商品多卡不会重复）。get_many 返回 dict，重复 key 无影响。不是缺陷。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:124-130 幂等回放命中他人订单时抛异常但未回滚已扣库存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:124-130`
  - 依据：claimed 为 False 分支中先 _rollback(reserved)，随后调用 _replay；_replay 在 order.buyer_id != buyer_id 时抛 OrderAccessDenied。此时库存已回滚，但异常路径没有保存订单（订单已 save 在仓库中），仍留下无库存支撑的订单。更一般地，该分支的 _replay 抛异常会跳过后续 raise ValueError，异常类型与预期不一致。
- **[error_handling/medium]** [error_handling] app/application/usecases/order_usecases.py:178-184 取消订单先回补库存再保存，保存失败会导致重复回补（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:178-184`
  - 依据：execute 中先 order.cancel(reason)（内存态），随后逐行 release 库存，最后才 save(order)。若 save 抛异常（DB 故障/乐观锁冲突），订单在持久层仍是未取消状态，但库存已经被回补。调用方重试取消时状态机允许再次 cancel，于是库存被二次回补，造成库存虚增。注释“重复取消会被状态机挡在上一步”只在 save 成功时成立。
- **[logic/high]** [logic] app/application/usecases/order_usecases.py:118-130 幂等键冲突回滚后未撤销已保存的订单，导致库存与订单不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:118-130`
  - 依据：execute 在 save(order) 之后才调用 idempotency.record。若并发下另一路先登记了同一键，claimed 为 False，代码只回滚库存（_rollback(reserved)），却没有删除/作废刚刚 save 的订单。结果：库存被释放，但订单仍留在 order_repo 中，形成“订单存在但库存未扣”的超卖/脏数据；且该订单号未被幂等键引用，后续无法通过幂等回放发现。
- **[logic/low]** [logic] app/application/usecases/order_usecases.py:178-184 取消订单未校验订单当前状态是否可取消即回补库存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/order_usecases.py:178-184`
  - 依据：order.cancel(reason) 由 Order 聚合的状态机负责，非法状态会抛异常，因此 release 不会在非法状态下执行。此处依赖聚合内状态机是正确的分层做法，不构成缺陷。
- **[logic/low]** [logic] app/domain/buyer/preference.py:27-33 BuyerPreference 的 created_at 默认空串在 __post_init__ 中填充，frozen dataclass 用 object.__setattr__ 绕过，行为正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:27-33`
  - 依据：frozen dataclass 中通过 object.__setattr__ 设置默认值是标准做法，__post_init__ 在实例构造时执行，created_at 会被正确填充为 UTC ISO 时间。kind 与 statement 校验也正确。不构成缺陷。
- **[boundary/low]** [boundary] app/domain/order/address.py:24-26 Address 未校验 state/postal_code/phone，one_line 可能输出 None 字面量（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:24-26`
  - 依据：__post_init__ 只校验 recipient_name/country/city/address_line 四个字段，state、postal_code、phone 允许为空字符串或 None。one_line() 直接把这些字段插值进字符串，若 phone 为 None 会输出 'None' 字面量；若 state 为空则产生多余空格。文档称 phone 是必填展示信息，但未纳入校验，属于校验边界不一致。
- **[logic/medium]** [logic] app/domain/order/order.py:47-53 币种一致性不变量未在聚合内校验（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:47-53`
  - 依据：文档声明不变量“全部订单行币种一致”，但 __post_init__ 只校验非空，注释把责任推给用例层。聚合根自身可被直接构造出混合币种的订单，随后 total_amount() 在 Money.add 处才会失败或产生错误结果，不变量在领域层没有被守住。
- **[logic/medium]** [logic] app/domain/order/order.py:74-81 cancel 允许取消 DRAFT 态订单，违反文档声明的状态机（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:74-81`
  - 依据：模块文档明确不变量为“只有 CONFIRMED 态可以取消”，但 cancel() 只拒绝已 CANCELLED 的状态，对 DRAFT 态不做校验，因此 DRAFT 订单也能被取消并写入 cancelled_at/cancel_reason，状态机被绕过。
- **[logic/high]** [logic] app/domain/order/order.py:84-88 total_amount 重复累加第一条订单行的小计（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:84-88`
  - 依据：total_amount() 先用 lines[0].subtotal() 初始化 total，随后 for 循环又遍历了包含 lines[0] 在内的全部订单行，导致第一条订单行的小计被计算两次。只要订单有至少一条行（__post_init__ 强制要求），总额就会偏大；单行订单的总额会变成实际金额的 2 倍。snapshot() 直接使用该结果，因此对外回传的 total_amount_major 也是错的。
- **[boundary/low]** [boundary] app/domain/order/order_line.py:22-24 OrderLine 未校验 unit_price 非空/类型（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:22-24`
  - 依据：OrderLine 只校验 quantity，未校验 unit_price。但 unit_price 的类型标注为 Money，若传入 None 会在 subtotal() 调用 multiply 时抛 AttributeError，属于调用方违约而非本类静默错误；且 dataclass 不做运行时类型检查是 Python 常规行为，不构成可确认缺陷。
- **[concurrency/low]** [concurrency] app/domain/order/ports/order_idempotency_store.py:22-24 OrderIdempotencyStore.record 的返回值语义依赖实现，端口未约束并发原子性（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:22-24`
  - 依据：record 文档明确要求键已存在返回 False，即实现需保证 check-and-set 原子性。端口本身只是抽象声明，不包含可执行逻辑，无法在此文件内构成并发缺陷；真正的竞态取决于具体实现（未在本次审查文件列表中）。因此不判定为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/order/ports/order_repository.py:15-25 OrderRepository 抽象方法使用 ... 而非 raise NotImplementedError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_repository.py:15-25`
  - 依据：抽象方法体为 ...，但类继承 ABC 且方法带 @abstractmethod，未实现这些方法的子类无法实例化，因此不会出现静默返回 None 的情况；这是标准写法，不是缺陷。
- **[boundary/low]** [boundary] app/domain/shipping/tariff_schedule.py:100-102 TariffSchedule.quote 中 freight 计算用 round() 对浮点乘法取整，可能偏差（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/shipping/tariff_schedule.py:100-102`
  - 依据：freight_minor_cny = round(base * (1 + 0.6*(q-1)))。base 是整数分，乘数可能是 x.6 等，round 银行家舍入可能偏差 1 分。与关税同理，低影响。不是缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/cache/redis_cache.py:74-82 RedisCache.get_json 中 json.loads 可能返回非预期类型，调用方无类型校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:74-82`
  - 依据：get_json 返回 Any，调用方负责类型校验。这是通用缓存封装的设计。不是缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:130-140 set_if_absent 在 Redis 异常时返回 True，破坏幂等语义（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:130-140`
  - 依据：文档明确说明这是有意的设计：Redis 不可用时返回 True（视为抢到），宁可退化成'没有幂等保护'也不拒绝服务。这是权衡后的显式决策，不是缺陷。但需注意：若调用方用此方法做分布式锁，Redis 故障时所有请求都'抢到锁'，会导致并发冲突。这是设计取舍，已在 docstring 中声明。判定为 not_a_defect。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:148-162 zadd_and_count 在 Redis 不可用时返回 0，调用方可能误判为'窗口内无请求'（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:148-162`
  - 依据：返回 0 表示'不限流'，与 set_if_absent 的放行策略一致，是显式设计。调用方若用 `count > limit` 判断，0 不会触发限流，符合'缓存故障不拒绝服务'的意图。不是缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:78-82 get_json 遇到脏值时 await self.delete(key) 在异常路径中可能再次抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:78-82`
  - 依据：delete 方法内部已 try/except 吞掉所有异常，因此 get_json 中调用 delete 不会抛出。不是缺陷。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:152-160 zadd_and_count 的 pipeline 中 zcard 在 zadd 之后执行，但 expire 在 zcard 之后，results[2] 是 zcard 结果（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:152-160`
  - 依据：pipeline 命令顺序：zremrangebyscore(0)、zadd(1)、zcard(2)、expire(3)。results[2] 确实是 zcard 结果，索引正确。不是缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:148-156 lookup 中 entry 向量维度不一致时静默视为不相似（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-156`
  - 依据：_cosine 对长度不一致返回 0.0，低于阈值即未命中，行为安全（宁可多一次调用）。换 embedding 模型时 namespace 应变化，旧向量不会与新向量比较。不构成缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:88-90 is_cacheable_query 对空查询返回可缓存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:88-90`
  - 依据：空字符串不匹配任何 _UNSAFE_PATTERNS，返回 True。但空查询在 lookup/remember 中会走 embed，且 _normalize 后为空串，可能与其他空串互相命中。实际调用方通常不会传空查询；即便命中，回复也是同一空查询的回复，不构成安全或正确性问题。
- **[concurrency/medium]** [concurrency] app/infrastructure/cache/semantic_cache.py:176-186 语义缓存桶读改写非原子，并发 remember 会丢失条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:176-186`
  - 依据：remember 先 _load_entries 读取整个列表，append 后 set_json 整体覆盖。两个并发请求（同一 buyer、同一 scope）各自读到旧列表，后写者覆盖先写者，导致先写入的缓存条目丢失。虽然只影响缓存命中率不影响正确性，但属于真实的并发写丢失。
- **[boundary/low]** [boundary] app/infrastructure/security/content_filter.py:22-30 DANGEROUS_PATTERNS 中 `system\s*prompt` 等模式缺少词边界，可能误伤正常商品描述（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：这些模式确实可能误伤（如商品标题含 "system prompt" 字样），但这是安全过滤层刻意的保守取舍：docstring 明确说明命中即替换为占位符而非丢弃整条，保留其余内容。误伤代价是局部文本被替换，不是错误行为，属于设计选择而非缺陷。
- …另有 4 条未列出

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/harness/drift_detector.py:137-139 consecutive_empty 只增不减，非空结果不会重置计数（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/drift_detector.py:137-139`
  - 依据：observe_action 中 consecutive_empty 只在 result_empty=True 时自增，result_empty=False 时保持原值而不归零。因此“连续空结果”语义被破坏：只要历史上累计出现过 3 次空结果（中间夹杂任意多次成功检索），之后每次检测都会命中“探索发散”信号，导致漂移误报并持续注入纠正提示。正确实现应为 result_empty 时 +1，否则置 0。
  - 争议对手：d8fcca54f1f3

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

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
| `32d2dfd314a0` | 1 | 3 | `partition_gap` | — |
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
| `app/application/harness` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/shipping` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/infrastructure/security` | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 27%（单元格值 = 独立 Agent 数）
