# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 3 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 12 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：23
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：55 个节点 / 145 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 16 | 100% | 8% |

## 高置信结论

- **[logic/low]** [logic] app/application/memory/preference_selector.py:121-124 _rank_by_relevance 注释声称“回到原始相对顺序输出”，实际按相关性顺序返回（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:121-124`
  - 依据：第 121 行按 `(-相似度, index)` 排序，第 122 行 `picked = [preference for _, _, preference in scored[:top_k]]` 直接取排序后的前 top_k，第 123 行注释写的是“回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入”，第 124 行却原样 `return picked`。代码没有做任何“恢复原始相对顺序”的步骤（正确做法是在 likes 中按原索引过滤，正如 `_latest_first` 第 130 行的写法）。后果是注入块里 like 行的顺序随本轮 query 的相似度每轮变化，任何依赖行序稳定做去重/幂等（如按文本判断“该偏好已注入”）的上层都会被打破；同时两条选择路径（_latest_first 顺序稳定、_rank_by_relevance 顺序抖动）行为不一致，测试也难以断言。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:83-85 top_k<=0 时直接返回空列表，连 dislike 黑名单也被丢弃（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:83-85`
  - 依据：第 83-85 行在 `top_k <= 0` 时无条件 `return []`，注释写的是“预算为 0 时不注入任何偏好”。但同文件第 8 行的安全底线是 dislike 不参与 top_k 截断——预算为 0 属于最极端的截断，效果是把所有忌口/黑名单一起丢掉，正是因为预算为 0 这类边界最容易在配置里被误触发（例如调用方按剩余上下文算出 0 或负数），结果就是整轮推荐完全没有黑名单保护。至少应当返回全部 dislikes 或抛错/告警，而不是静默清空。
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:41-41 内部主机名正则缺少右边界，只脱敏前缀导致内网主机名剩余部分泄漏（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:41-41`
  - 依据：模式 https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)? 在主机名交替组之后没有任何边界（没有 (?=[/:\s]|$) 或后接 \. 的约束）。因此像 http://redis-cache.svc.cluster.local:6379 这样的内网地址只会匹配到 http://redis 这一段，替换后留下 "[已脱敏]-cache.svc.cluster.local:6379"：内部主机名、命名空间和后缀端口全部原样外泄，L4 这道闸在最典型的容器网络主机名场景下失效。反向也会误伤 http://rediscovery.example.com 这类正常链接，只截掉前缀、把剩余部分留在买家可见文本里。

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:128-129 _latest_first 用 p in newest 做相等性过滤，重复偏好会撑破 top_k 并可能挤掉真正最新的条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-129`
  - 依据：newest 是 sorted(...)[:top_k] 选出的「最新 top_k 条」，随后用 [p for p in likes if p in newest] 复原顺序。in 走的是 __eq__ 而不是身份：若 BuyerPreference 是默认 eq=True 的 dataclass，两条字段完全相同的偏好会互相「代表」，于是所有副本都会通过过滤，返回长度可能超过 top_k；再叠加 select 里的 [:top_k] 切片，被切掉的可能是排在原始顺序末尾的真正最新条目。同时该写法是 O(n·k) 的重复扫描，属于同一处实现的副作用。
- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:29-37 _cosine 对维度不一致与零向量的处理不会抛异常（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:29-37`
  - 依据：初看 `dot / (norm_left * norm_right)` 有除零风险，但第 35 行已对 norm 为 0 提前返回 0.0；维度不一致也在第 30 行返回 0.0。因此任意向量输入都返回有限浮点数，不会把 ZeroDivisionError 抛到 select() 之外，与「选偏好失败不阻断对话」的降级设计一致。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:119-123 _rank_by_relevance 注释声称复原原始相对顺序，实际直接按相关性降序返回（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:119-123`
  - 依据：select 的 docstring 承诺返回「稳定顺序」，_latest_first 也确实做了复原（[p for p in likes if p in newest]），并且 _rank_by_relevance 里紧挨 return 的注释写着「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」。但代码返回的 picked 就是 scored[:top_k] 的顺序，即按 (-cosine, index) 排出来的相关性降序，完全没有任何复原步骤。结果是同一个买家、同一批 like，在不同 query 下 <buyer-preferences> 块内 like 行的顺序每轮都会抖动，注释里声称要避免的「行序抖动」恰恰没有被避免，注释与实现不一致。
- **[performance/low]** [performance] app/application/memory/preference_selector.py:129-130 _latest_first 用 `p in newest` 做集合过滤，依赖 __eq__ 且为 O(n·k)，但顺序语义正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:129-130`
  - 依据：`newest = sorted(likes, key=lambda p: p.created_at, reverse=True)[:top_k]` 后 `[p for p in likes if p in newest]` 的意图是“取最新的 top_k 条，但按原相对顺序输出”，这个语义是正确的，返回值长度和顺序都符合注释（`_latest_first` 的输出顺序是稳定的，这一点与 `_rank_by_relevance` 形成对照）。需要留意的是 `in` 走 `BuyerPreference.__eq__`：如果它不是按身份比较的对象，且存在所有字段（含 created_at）完全相同的两条偏好，则两条都会被保留，返回值会多于 top_k；但在同一个 store 里通常由 id/created_at 唯一化，正常路径不会触发。复杂度 O(n·k) 在偏好条数为几十的量级下没有实际影响，因此不认定为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/product.py:48-50 searchable_text 中 join 调用后的尾随逗号不是参数错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:48-50`
  - 依据：`" ".join([...],)` 是合法的 Python 写法：尾随逗号位于唯一的列表实参之后，join 仍然只收到一个列表参数，不会被解释为传入多个参数。因此这里不会因尾随逗号产生 TypeError，方法行为符合预期。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:45-50 searchable_text 在 highlights 为空时向 join 传入空字符串元素，产生尾部空格（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:45-50`
  - 依据：当 self.highlights 为空时，生成器表达式产出空串，highlight_text == ""，但它仍作为最后一个元素参与 " ".join，因此结果以单个空格结尾；同理当 ProductHighlight.detail 为默认空串时会出现连续两个空格。这只影响字符串的空白形态，不影响分词/召回，也不会抛异常，因此不构成行为缺陷（属于可忽略的空白噪声）。
- **[logic/low]** [logic] app/domain/catalog/product.py:39-43 primary_sku() 返回列表首元素，是否等于业务主推 SKU 无法从本文件确认（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:39-43`
  - 依据：primary_sku() 以 list 的第 0 个元素作为“主 SKU”，find_sku() 则按 sku_id 线性查找。仅从本文件看，没有证据表明 Sku 具有 is_default/primary 之类的标记字段，也没有证据表明调用方依赖“首个即主推”造成结算错误；字段定义在未提供审查的 app/domain/catalog/sku.py 中。因此按现有证据不判定为缺陷，仅记录该假设：若 Sku 存在显式主推标记，则此处语义应与该标记保持一致。
- **[logic/low]** [logic] app/domain/catalog/product.py:46-49 searchable_text 的文档字符串漏写 origin_country，与实际拼接内容不一致（确认并非缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:46-49`
  - 依据：docstring 声明可检索文本为“标题 + 品牌 + 品类 + 描述 + 亮点”，而实现额外拼接了 self.origin_country。这是文档与实现的不一致，但实际输出是文档所述集合的超集，不会导致任何运行时错误或召回缺失；因此不判为缺陷，仅提示维护者同步文档。
- **[logic/low]** [logic] app/domain/catalog/sku.py:28-36 Sku.stock 的“只读”约束未被强制，__post_init__ 校验可被后续赋值绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:28-36`
  - 依据：这里怀疑的点是：@dataclass 未加 frozen=True，所以 sku.stock = -1 这类后续赋值会绕过 __post_init__ 的非负校验，模块 docstring 声称的「只读」只是约定而非强制。确认后认为不构成缺陷：stock 在设计中仅作首次播种与展示兜底，扣减/回补一律走 StockRepository 的原子操作，没有代码路径拿 Sku.stock 做「读-判断-写」的库存裁决，因此篡改该字段不会引发超卖或金额错误；把 dataclass 改成 frozen 会影响其它地方对该实体的构造/赋值习惯，属于设计取舍而非 bug。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/output_guard.py:22-22 REDACTED 作为 re.subn 的替换串不会触发反向引用解释（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:22-22`
  - 依据：`pattern.subn(REDACTED, cleaned)` 中替换串会被解析反斜杠转义，容易踩 `\1` 之类的坑；但 REDACTED 是 `[已脱敏]`，不含反斜杠与分组引用，`[`、`]` 在替换串中不是元字符，因此输出就是字面量占位符，不会抛错也不会注入意外内容。这一点确认安全，虽属脆弱写法但不构成缺陷。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/output_guard.py:59-65 audit_output 用 REDACTED 作为 subn 替换串不会触发转义问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:59-65`
  - 依据：检查点是 re.subn 的 repl 参数会解释 \\ 与 \1 这类转义序列，若 REDACTED 含反斜杠或分组引用就会抛错或产生意外文本。确认后安全：REDACTED 常量是 "[已脱敏]"，不含反斜杠与 $，作为替换串没有任何特殊语义；循环中 cleaned 逐轮被覆盖、safe 用 count 累积，逻辑等价于一次全量替换，命中后返回的处理后文本可直接下发。另外空文本早退返回 (True, "") 也符合「安全」语义。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:50-51 audit_output 对空文本直接返回 (True, text) 属合理短路（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:50-51`
  - 依据：第 50-51 行对空串（以及 None/空容器等假值）直接返回 `(True, text)`，返回的仍是原对象而非新字符串。空回复本身不含任何内部信息，判为“安全”符合语义；且原样返回空串不会给下游渲染制造额外分支。唯一需要注意的是调用方若传 None，返回的文本也是 None（类型上不是 str），但函数签名声明为 `text: str`，调用方按契约不会传 None，因此不构成缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-40 skus 为可变列表，构造后清空可绕过 __post_init__ 的不变量并让 primary_sku() 抛 IndexError（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-40`
  - 依据：类的不变量“至少一个 Sku”只在 __post_init__ 中检查一次，而 skus 字段是普通的可变 list（field(default_factory=list)），外部持有引用后仍可执行 skus.clear()/pop()/remove()。此后 primary_sku() 直接取 self.skus[0]，会抛出 IndexError 而不是得到一个可解释的领域错误；此时 find_sku 返回 None，但 primary_sku 崩溃，同一对象上的两个访问器行为不一致。触发条件是构造 Product 后对 skus 列表做原地修改（包括把列表从外部传入并共享、再被上游清空）。
  - 争议对手：0cc5fb33ceb6

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：22｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：83.1%（重捕对 3，已观测 16，估计总体 19.25
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.5% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.5% |
| `269088b25c46` | 3 | 0 | `reader_miss` | 0.5% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.5% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.5% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.5% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.5% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.5% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.5% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.5% |
| …另有 12 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 2 | 0 | 0 | 0 | 1 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 2 |

矩阵填充率 11%（单元格值 = 独立 Agent 数）
