# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 2 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 11 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：23
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：56 个节点 / 151 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 15 | 100% | 5% |

## 高置信结论

- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-129 _latest_first 用 `p in newest` 做值相等成员判断，重复偏好会导致返回超过 top_k 且偏向保留靠前的旧项（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-129`
  - 依据：newest 是按 created_at 倒序取的前 top_k 条，但回填时用 `p in newest` 做成员判断，走的是 BuyerPreference 的 __eq__（dataclass 默认按字段值比较）。若两条偏好的字段值完全相同（重复记忆同一句“喜欢小众设计”），newest 里只有其中一条，过滤时两条都命中，返回值长度就会超过 top_k；再经 select() 的 [:top_k] 位置截断，留下的恰是原列表中靠前（更旧）的那条，与“按时间倒序取 top_k”的语义相反。用 index 集合或先取下标再回填可避免。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:87-94 likes 的候选预算直接取 top_k 而未扣除 dislike 数，最终按“原始顺序”截断会丢掉最相关/最新的 like（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:87-94`
  - 依据：select() 用 top_k 作为 likes 的选择预算（_rank_by_relevance/_latest_first 都传 top_k），然后拼上 dislikes 再整体切 [:top_k]。由于 _rank_by_relevance 特意“回到原始相对顺序输出”，picked 是按原列表位置排的，最后 [:top_k] 切掉的是“在原列表里靠后”的那 d 条（d=len(dislikes)），而不是相似度最低/时间最旧的那几条。所以当存在 dislike 时，余弦相似度最高的 like 可能因为它在原列表里靠后而被切掉，相关性排序结果被丢弃；_latest_first 分支同理，会把最新挑出来的 like 切掉、留下旧的。真正正确的做法是先把 likes 的预算算成 top_k - len(dislikes) 再做排序/截断。

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:83-85 top_k<=0 时直接返回空列表，连 dislike 也一并丢弃（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:83-85`
  - 依据：这一分支与“dislike 全量保留”的表述看起来冲突，但紧邻的注释说明这是刻意的语义：预算为 0 表示本轮不注入任何偏好，调用方显式关闭注入时再强塞黑名单反而违反调用意图。真正的约束应由调用方保证不下发 top_k<=0（或在预算为 0 时明确拒绝注入），此处按既有注释属于有意设计而非缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:104-118 _rank_by_relevance 的异常兜底只包住了两次 await，评分阶段的异常不会被降级（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:104-118`
  - 依据：文档声称“任何异常都降级为按时间倒序，不能因为选偏好把对话搞挂”，但 try 只包住了 embed_batch 与 embed 两次调用。之后的 _cosine 遍历与 sort 都在 try 之外：若 embedding 客户端返回元素为 None/非序列（长度校验只比较外层数量，查不出元素非法），len(None) 会抛 TypeError 并从 select() 直接冒出，把整轮对话打断——这正是文档说要避免的情形。
- **[security/low]** [security] app/application/memory/preference_selector.py:51-56 偏好正文原样拼进 <buyer-preferences> 定界块，用户可控内容可提前闭合块实现注入（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:51-56`
  - 依据：render_preference_lines 把 p.statement 直接做字符串插值，render_preference_hint 再把它夹在 <buyer-preferences> ... </buyer-preferences> 之间。p.statement 是买家历史会话里产生的、经 remember_preference_tool 落库的自由文本（用户可控），其中若包含字面量 </buyer-preferences>，渲染出的块会被提前闭合，后续文本就落在定界块之外，成为与系统指令同层级的指令型内容。定界块是这里唯一的边界，却没有任何转义/剔除，属于结构性注入面。影响有限（偏好按买家隔离，只能污染该买家自己的上下文），故定级 low。
- **[api_misuse/low]** [api_misuse] app/domain/catalog/product.py:48-50 searchable_text 中 " ".join(...) 的尾随逗号只是合法语法，不构成参数错误（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:48-50`
  - 依据：`return " ".join(\n [ ... ],\n)` 中列表后的逗号属于调用括号内的尾随逗号，Python 解析为单个位置参数而非 tuple，join 被调用一次、参数是字符串列表，行为正确。highlight_text 为空时只会产生末尾多余空格，对召回文本无实质影响。唯一可见的不一致是 46 行 docstring 声称“标题 + 品牌 + 品类 + 描述 + 亮点”，而实现额外拼接了 origin_country，但这属于注释与实现对不上、不影响运行结果，不构成缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:47-50 无亮点时 searchable_text 末尾多出一个空格分隔符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-50`
  - 依据：当 self.highlights 为空时 highlight_text 为 ''，它仍作为最后一个元素参与 join，结果字符串以空格结尾（无亮点时是 'title brand ... desc '）。这只是空白冗余，后续分词/包含匹配（split() 或子串匹配）都不受影响，不构成功能性缺陷。
- **[error_handling/low]** [error_handling] app/domain/catalog/product.py:33-37 __post_init__ 只校验 product_id 与 skus，title/brand 等字段为 None 时延迟到 searchable_text 才报 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-37`
  - 依据：构造期仅对 product_id 空值与 skus 空列表做不变量校验，title/brand/category/origin_country/description 完全依赖类型声明为 str。如果从数据库/JSON 传来 NULL 并组装成 Product，构造会成功，直到 searchable_text() 里 str.join 才抛 TypeError。但这属于调用方违反字段类型契约，且当前文件内没有证据表明存在 None 数据源；按“可引用代码为据”的标准不足以判定为真实缺陷，仅作为契约脆弱点记录。
- **[logic/low]** [logic] app/domain/catalog/sku.py:22-31 Sku.stock 只在构造期校验且 dataclass 未 frozen，可在内存中绕过校验改写（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:22-31`
  - 依据：__post_init__ 只在构造时校验 stock 非负，Sku 是可变的 dataclass，运行期仍可 sku.stock = -5 绕过校验。但这不构成缺陷：按模块文档，stock 只是“初始库存/展示兜底”，真正的扣减走 StockRepository 的原子操作，内存对象被改成异常值不会写回数据库、不会造成超卖，也不会影响下单链路；把实体冻结或加 setter 校验属于设计偏好而非错误行为修正。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:47-48 内部服务地址正则缺少主机名右边界，会误伤 redis.io 等正常外链（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:47-48`
  - 依据：模式 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 在主机名后没有边界约束（既没要求紧跟 `:` 端口或 `/` 路径，也没排除 `.`），因此只要 URL 的 host 以这些前缀开头就命中。模块文档明确说要避免误伤买家可见的正常措辞，但 `https://redis.io/topics` 会被替换成 `[已脱敏].io/topics`，`https://opensearch.org` 同理，属于误脱敏导致的输出损坏。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:61-62 REDACTED 的方括号/中日文用作 re.subn 替换串是安全的（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:61-62`
  - 依据：re.subn 的 repl 是模板字符串，只有反斜杠与 \g<name> / \1 这类序列会被解释；REDACTED = "[已脱敏]" 不含反斜杠也不含 \g，因此不会被当成转义或反向引用，subn 行为符合预期，count 计数也可信。另外 SENSITIVE_PATTERNS 在模块导入时一次性编译进 _compiled，随后逐条对 cleaned 串行替换，前一条替换插入的占位符不会反过来匹配后一条模式，不存在替换互相触发的问题。
- **[security/medium]** [security] app/infrastructure/security/output_guard.py:38-38 shopping_session_id 正则在 JSON/带引号取值场景下匹配失败，敏感值原样放行（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-38`
  - 依据：模式要求 key 后面紧跟 `:` 或 `=`（可有空白），再跟 [\w-]+。但实际泄露形态几乎总是带引号：JSON 里是 "shopping_session_id": "s-123"（key 后是引号，[:=] 匹配失败），Python dict repr 是 {'shopping_session_id': 's-123'}（= 后是引号，[\w-]+ 匹配 0 字符失败）。两种写法都不会命中，audit_output 会返回 safe=True 且文本未脱敏，L4 这道“最后一道闸”被绕过。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:41-41 内网服务地址正则只匹配裸主机名，`vllm.internal:8000/...` 一类地址只被部分脱敏，后缀仍然泄露（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:41-41`
  - 依据：模式在主机名（vllm/reranker/qdrant/redis/opensearch）之后只允许可选的 `:port` 或 `/:path`，紧接着就结束匹配。若真实地址带域名后缀（容器编排里常见的 vllm.internal、qdrant.svc.cluster.local），只有 'http://vllm' 这一段被替换，输出变成 'http://[已脱敏].internal:8000/v1'，内部主机名与端口依然可见，内部服务地址这一类的脱敏目标没有达成。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:128-129 _latest_first 用 `p in newest` 做成员判断，值相等的重复偏好会突破 top_k 预算（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-129`
  - 依据：sorted(...)[:top_k] 得到的是值列表，随后用 `p in newest` 按相等性过滤。如果 BuyerPreference 是标准 dataclass（默认 eq=True），两条字段完全相同的偏好（同一 statement、同一 kind、created_at 精度不足或由 seed 数据写入相同时间戳）会同时命中 `in`，返回条数可超过 top_k；由于 select 末尾还有一次 [:top_k]，多数情况下被掩盖，但会在 _latest_first 这一层破坏「最多返回 top_k 条」的契约，并使这条路径的返回集合与实际「最新 top_k」不再一致。另外 `in` 是线性扫描，整体是 O(n*top_k)。
  - 争议对手：9d321b3d47c9
- **[boundary/low]** [boundary] app/domain/catalog/product.py:31-40 primary_sku() 依赖仅在 __post_init__ 校验的非空不变式，skus 被外部清空后会抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:31-40`
  - 依据：Product 是普通（非 frozen）dataclass，skus 是暴露在外的可变 list，聚合根没有提供带不变式保护的 add_sku/remove_sku 方法；“至少一个 Sku”只在 __post_init__ 构造时校验一次（36-37 行）。任何后续代码（例如按上架状态过滤 `product.skus = [s for s in product.skus if s.active]`、或 `product.skus.remove(sku)`）都可以在不报错的情况下把列表变为空，此时 primary_sku() 直接 `self.skus[0]` 会抛 IndexError，而不是抛出领域错误。TradeAgent 以 Sku 粒度结算时调用 primary_sku() 就会在运行时崩溃，且崩溃点与真正的违约点（清空列表处）相距很远，难以定位。
  - 争议对手：0cc5fb33ceb6, 518dea6583f7

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：22｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：90.9%（重捕对 3，已观测 15，估计总体 16.5
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.1% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.1% |
| `269088b25c46` | 3 | 0 | `reader_miss` | 0.1% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.1% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.1% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.1% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.1% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.1% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.1% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.1% |
| …另有 12 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 3 | 1 | 0 | 1 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 3 | 1 | 0 | 0 | 0 | 2 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

矩阵填充率 14%（单元格值 = 独立 Agent 数）
