# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 3 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 14 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：24
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：92 个节点 / 255 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 17 | 100% | 2% |

## 高置信结论

- **[boundary/low]** [boundary] app/application/usecases/catalog_search.py:182-186 价格上限使用严格小于，等于预算的商品被误判为超预算（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:182-186`
  - 依据：`price_max_major` 从命名与语义上都是「预算上限」，即价格 ≤ 上限应当通过；但这里用的是 `<`，价格恰好等于上限（例如换算后 100.0 对上限 100.0）的商品会被 `_reject_reason` 判为 `over_price_cap` 并从 hits 中剔除，还会出现在 filtered_out 里、以「over_price_cap」原因回传给模型，导致模型向用户报告「这些商品超预算」，与用户表达的预算语义相反。汇率换算后的浮点值也会让边界更容易落在等值附近。
- **[logic/medium]** [logic] app/application/usecases/catalog_search.py:144-147 排序注释承诺按 product_id 兜底破平，但实际 sort key 只用分数（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:144-147`
  - 依据：注释明确说明并列分数时要“按 product_id 兜底排序”，目的是消除后端返回顺序带来的不确定性，让同一 query 的结果与评测指标可复现。但实际代码 `filtered.sort(key=lambda item: -item[0])` 只按分数排序，Python 的稳定排序会把并列分数的相对顺序保持为召回时的顺序：向量召回路径下该顺序由 Qdrant 分片/版本决定，因此并列分数时同问句仍可能给出不同 hits 顺序，注释声称解决的问题原样存在。
- **[logic/high]** [logic] app/application/usecases/catalog_search.py:225-227 关键词兜底召回用 score >= 0 过滤，未命中的商品(得分 0.0)也会全部进入结果（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:225-227`
  - 依据：_keyword_score 在 `matched` 为空时显式返回 0.0（第 235-236 行），而非负分；因此调用方用 `if score >= 0` 判断时条件恒为真，目录中每一条商品都会被加入候选。这使 embedding 异常的降级路径（以及未配置 embedder 时的默认路径）退化为“返回整个目录”，recall_strategy 声称是关键词匹配，但实际没有任何关键词过滤效果；top_k 截断后给出的商品与 query 无关，并且 total_candidates/filtered_out 也会基于全量商品计算，向模型传递错误的“召回到了”信号。

## 待验证（孤证）

- **[api_misuse/low]** [api_misuse] app/application/tools/order_tools.py:24-28 _ok / tool.result 直接把 usecase 返回的 snapshot 交给 json.dumps 与事件总线（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/tools/order_tools.py:24-28`
  - 依据：`json.dumps(payload, ensure_ascii=False)` 在 snapshot 是 dataclass/ORM 对象或含 Decimal/datetime 字段时会抛 TypeError。但这属于推测：函数签名 `_ok(payload: dict)`、product_search_tool 里同样对 result 直接 json.dumps，说明 UseCase 的契约是返回纯 dict（通常已是 model_dump 结果）。在给定文件内没有证据表明返回非可序列化对象，故不判为缺陷，仅记录该隐式契约：一旦 PlaceOrderUseCase/QueryOrderUseCase 改为返回领域对象，这里会在 try 之外抛未捕获的 TypeError 且丢失 tool.result 事件。
- **[error_handling/medium]** [error_handling] app/application/tools/order_tools.py:61-87 create_order_tool 的参数转换只捕获 ValueError/KeyError，quantity 为 null 或 items 元素非 dict 时抛出未捕获的 TypeError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/tools/order_tools.py:61-87`
  - 依据：工具层在 try 内用 item["product_id"]、item["sku_id"] 和 int(item.get("quantity", 1)) 搬运模型入参，但 except 只写了 (ValueError, KeyError)。items 在 schema 里只是 list[dict]，dict 内部没有字段约束，因此模型给出 {"product_id": "P1001", "sku_id": "P1001-S1", "quantity": null} 时 item.get("quantity", 1) 返回 None（默认值不会生效，因为键存在且值为 null），int(None) 抛 TypeError；同理 items 里混入字符串/None（如把 items 误传成 ["P1001"]）时 item["product_id"] 抛 TypeError（字符串下标是整数）。TypeError 不在捕获列表里，异常会穿透工具函数：既不会走 bus.publish 的 "tool.result" 事件路径，也不会返回 ToolResultState.ERROR 的 ToolChunk，模型拿到的是异常而不是可自纠的 [error] 文本，前端也收不到这次调用的结果事件。其它同类入口（Address 构造、shipping_address.get）在 shipping_address 为 null 时会抛 AttributeError，同样未被覆盖。
- **[logic/low]** [logic] app/application/tools/order_tools.py:58-59 idempotency_key 只由 task_id+buyer_id 组成，task_id 缺失时退化为空串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/tools/order_tools.py:58-59`
  - 依据：审查过这条幂等键的构造：`f"order:{task_id}:{buyer_id}" if task_id else ""`。潜在风险有两点：(1) task_id 为空时传入空串做幂等键，若 PlaceOrderUseCase 把任何传入值都当作有效 key 存储，那么所有无 task 的下单会命中同一条记录，第二单会静默返回第一单的快照；(2) 键里不含 items/address，同一 task 内改单会命中旧单。但由于代码注释已明确说明设计意图是「按任务+买家幂等，同一会话另说一次会拿到新 task_id」，且常见实现是 `if idempotency_key:` 才查重（空串等同于不幂等），在本文件可见范围内无法证明存在错误行为，故不判为缺陷，仅记录此依赖前提。
- **[boundary/low]** [boundary] app/application/tools/product_search_tool.py:60-67 price_max_major 字符串强转接受 nan/inf，预算硬约束会被静默失效或误判为空结果（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/tools/product_search_tool.py:60-67`
  - 依据：这段代码的意图是把模型给的数字字符串规整成 float 再进检索链路做结构化过滤，但 float() 会接受 "nan"、"inf"、"Infinity"、"1e999"（后者溢出为 inf）而不抛 ValueError。于是价格上限变成 nan 时，下游 `price <= nan` 恒为 False，检索会返回 0 条命中，模型据此告诉买家「预算内无商品」；变成 inf 时 `price <= inf` 恒为 True，预算硬约束被完全绕过，可能给买家推荐超预算商品。工具层在这里就是把关点（注释称 schema 层已放宽为接受字符串），因此缺少 math.isfinite 校验会把非法数值放行到检索链路。
- **[error_handling/low]** [error_handling] app/application/tools/product_search_tool.py:52-67 product_search_tool 中数字参数强转失败时提前返回，跳过 tool.invoke/tool.result 事件发布（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/tools/product_search_tool.py:52-67`
  - 依据：同一个函数里两条错误路径的事件行为不一致：第 78 行之后的 ValueError 路径在 tool.invoke 之后执行，会同时发布 tool.invoke 与带 error 的 tool.result；而第 52-67 行的 top_k / price_max_major 强转失败路径发生在 session_id 获取（第 68 行）和 bus.publish("tool.invoke")（第 77 行）之前，直接 return 错误 ToolChunk，事件总线上既没有 invoke 也没有 result。该文件的注释明确说明商品卡与调用过程都通过事件下发给前端渲染（"商品卡随事件下发，前端无需再调接口即可渲染"），所以这类调用在事件流里会完全消失：模型收到了 [error] 文本，但前端/审计链路看不到发生过这次工具调用，也无法显示错误原因。
- **[api_misuse/low]** [api_misuse] app/application/usecases/catalog_search.py:298-301 在 frozen dataclass 上修改嵌套可变对象不会抛错，库存覆盖按预期生效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:298-301`
  - 依据：`ProductCard` 虽为 `@dataclass(frozen=True)`，但 frozen 只禁止重新绑定属性，不禁止修改字段引用的可变对象。`card.skus` 里的 dict 是 `_to_card` 新建的、未与其他对象共享，`sku["stock"] = ...` 修改的正是这些 dict，因此 `_overlay_authoritative_stock` 会正确覆盖库存；且覆盖发生在 `to_dict()` 之前，回传 JSON 中展示的是权威库存。不存在失效或读到陈旧值的问题。
- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:114-120 向量召回与库存查询的宽泛 except 属于有意的降级路径，不构成缺陷（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:114-120`
  - 依据：这里用 `except Exception` 包住向量召回，并在异常时把 scored 清空、把 recall_strategy 保持为 keyword_2gram，让后续 `elif not scored` 分支接管关键词兜底，同时打 warning 日志。这是模块 docstring 明确声明的降级链（embedding_rerank → embedding_only → keyword_2gram），不会静默失败，也不会破坏状态。_overlay_authoritative_stock 中的宽泛 except 同样只是退化为展示初始库存并记日志，不改变扣减链路。
- **[error_handling/medium]** [error_handling] app/application/usecases/catalog_search.py:171-186 过滤摘要路径上的汇率转换未做异常保护，与商品卡路径的降级策略不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:171-186`
  - 依据：`_to_card` 中明确对计价失败做了保护（`except ValueError` → landed_price 标注 unavailable_reason），说明货币/目的国不在规则表内是预期内的可恢复情况；`_vector_recall`/`_rerank` 也都有降级。但 `_to_rejected`（以及 `_within_price_cap`）直接调用 `self._tariff.rates.convert(..., spec.target_currency)`，没有任何 try/except。一旦目标币种不在 ExchangeRateTable 中（或 convert 对未知币种抛 ValueError/KeyError），只要本轮有任意一个候选被 ship_to 或价格约束挡掉，异常就会从 execute 里抛出，整次检索失败——而同一请求里支持币种的商品卡本来是能正常组装的。相比之下 `_to_card` 的保护反而说明这条路径的失败被遗漏了。
- **[error_handling/low]** [error_handling] app/application/usecases/catalog_search.py:211-216 rerank 返回分数条数不足会 IndexError，但被上层 try/except 兜住并降级（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/usecases/catalog_search.py:211-216`
  - 依据：`rerank_scores[i]` 假设 Reranker 返回与 documents 等长的分数列表；若实现返回短列表会抛 IndexError。核对调用方确认这是被显式设计的：execute 中 `scored = await self._rerank(...)` 包在 `except Exception` 内，异常时不重新赋值 scored（保持向量分顺序）、recall_strategy 停在 embedding_only、rerank_applied 保持 False，属于文档描述的降级链，不会让整个检索失败。
- **[boundary/low]** [boundary] app/domain/catalog/product_search_spec.py:25-28 ProductSearchSpec 未校验 top_k / price_max_major（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product_search_spec.py:25-28`
  - 依据：__post_init__ 只校验 normalized_query 非空，注释明确写了「top_k 由调用方保证为正」，这是刻意的契约划分，而不是实现遗漏；price_max_major 作为可选硬约束，None 即无约束，也不存在需要在本对象内拒绝的非法取值。在本文件范围内没有可复现的错误行为，若检索链路真的传入非正 top_k，缺陷点在调用方而非此处。
- **[logic/low]** [logic] app/domain/catalog/sku.py:19-30 Sku 是可变的非 frozen dataclass，理论上可在内存中改写 stock（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:19-30`
  - 依据：虽然 @dataclass 未加 frozen=True，外部可以 sku.stock = 0，但本类刻意不提供 deduct_stock/restore_stock 之类的变更方法，__post_init__ 也只做构造期校验，因此文件本身没有引入「读-判断-写」超卖路径；属性直接赋值属于调用方违规，不是该实体实现的缺陷。要彻底防止需 frozen=True + 对外只读，但那是设计增强，不是本文件里可复现的 bug。
- **[boundary/low]** [boundary] app/infrastructure/resilience.py:76-76 用 `now or time.monotonic()` 取时间：显式传入 0.0 时间戳会被当成 falsy 丢弃（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:76-76`
  - 依据：now: Optional[float] 的语义是「外部注入的时钟值」，但 `now or time.monotonic()` 在 now == 0.0 时会退回到真实单调时钟。若测试或上层用 0.0 作为基准时间（例如把 opened_at 也设为 0.0 的假时钟），elapsed 会变成 time.monotonic() - 0.0（一个巨大的正数），从而跳过冷却期直接进入半开，判定结果完全反转。同一模式在 record_failure 的第 89、94 行重复出现，行为一致。正确写法应是 `now if now is not None else time.monotonic()`。
- **[concurrency/high]** [concurrency] app/infrastructure/resilience.py:71-80 半开状态不限制并发探测：冷却期一过，所有排队调用同时被放行，熔断形同失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:71-80`
  - 依据：allow() 只在 opened_at 非空且 elapsed < reset_seconds 时返回 False；一旦冷却期届满，它无条件把 half_open_probing 置 True 并返回 True，完全没有检查 half_open_probing 是否已经为 True（即已有探测在飞行中）。因此冷却期满后这段时间内所有并发到达的调用都会拿到 True 一起打向故障下游，与方法 docstring 声明的「放一次探测请求」以及文件头注释「冷却期满转半开，放一次探测请求」直接矛盾。更严重的是若那次探测的协程被取消（CancelledError 继承自 BaseException，on_tool_call 的 except Exception 捕不到）或进程内异常路径没有走到 _record_success/_record_failure，half_open_probing 会永久停留在 True、opened_at 也不再更新，之后每次 allow() 都返回 True，熔断器彻底失效，永远不会再打开。这在高并发下表现为：下游刚恢复或仍故障时，一个 reset_seconds 窗口结束后整批请求同时涌入。
- **[error_handling/medium]** [error_handling] app/infrastructure/resilience.py:119-126 降级路径上同步发布事件未做异常隔离，bus.publish 抛错会把异常抛穿到 Agent 循环（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/resilience.py:119-126`
  - 依据：_publish_circuit 直接调用 self._bus.publish(...)，没有任何 try/except；而它在 on_tool_call 中被调用在 yield 降级 ToolChunk(ERROR) 之前（短线路径第 139 行、超时路径第 162 行、异常路径）。一旦 publish 自身抛异常（事件总线未初始化、payload 序列化失败、发布时访问了已关闭的下游、或在无事件循环/session 上下文时抛 KeyError 等），异常会在 yield error chunk 之前逸出 async 生成器，直接违背文件头承诺的「返回结构化 error chunk，不把异常抛穿到 Agent 循环」，调用方拿不到任何 ERROR chunk，只能看到异常。同一行里 ShoppingContext.current_session_id() 若在无上下文时抛错，效果相同。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：57｜覆盖正常：6｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 17，估计总体 17.0
- 待补检分组：app, app/application/tools, app/application/memory, app/infrastructure, app/domain/order, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/application/agents, app/infrastructure/vector, app/domain/catalog, app/infrastructure/rerank, app/domain, app/infrastructure/rag, app/infrastructure/embedding, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `08f643c1885f` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `24481c1442d8` | 3 | 0 | `reader_miss` | 0.0% |
| `27d90514a9b4` | 3 | 0 | `reader_miss` | 0.0% |
| `2cc7c376f2fe` | 3 | 0 | `reader_miss` | 0.0% |
| `2d259bcddd0a` | 3 | 0 | `reader_miss` | 0.0% |
| `31d1e54cf47c` | 3 | 0 | `reader_miss` | 0.0% |
| `3f170c308b9a` | 3 | 0 | `reader_miss` | 0.0% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 47 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/agents` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/tools` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| `app/application/usecases` | 3 | 0 | 2 | 3 | 0 | 0 | 0 | 1 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/embedding` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rag` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/rerank` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/vector` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 10%（单元格值 = 独立 Agent 数）
