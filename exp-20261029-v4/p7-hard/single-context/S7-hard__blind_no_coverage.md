# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 14 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：16
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：46 个节点 / 62 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 15 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:96-99 top_k<=0 时返回 dislikes 但未做去重/上限，且忽略 likes 的语义边界（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-99`
  - 依据：top_k<=0 时直接返回 dislikes 是文档明确声明的安全底线（dislike 全量保留、不参与截断），行为与 docstring 一致，不是缺陷。仅记录以免被误判。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:113-124 embed_batch 返回空列表时 len 校验通过但 zip 产生空 scored，静默返回空结果（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:113-124`
  - 依据：当 likes 非空时 len(vectors) != len(likes) 会捕获空列表并降级；likes 为空时 select 已在前面返回 []，不会进入此分支。因此该路径实际不可达，不构成缺陷。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:118-124 相关性排序取的是相似度最低的 top_k（排序方向反了）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：_cosine 返回的是相似度，越大越相关。但 scored.sort(key=lambda item: (item[0], item[1])) 是升序排序，scored[:top_k] 取到的是相似度最低的 top_k 条，即与本轮 query 最不相关的偏好被注入，而最相关的被丢弃。这与函数 docstring「按 statement 与 query 的余弦相似度取 top_k」完全相反。触发条件：relevance_enabled=True 且 embedder 可用且 len(likes) > top_k。此时注入的恰好是最不相关的正向偏好，个性化推荐质量反而比关闭开关（按时间倒序）更差。修复：sort 时对分数取负，或 reverse=True 并保持 index 次序键稳定（如 key=lambda item: (-item[0], item[1])）。
- **[logic/medium]** [logic] app/application/memory/preference_selector.py:125-126 用 `p in picked` 复原顺序依赖 dataclass 值相等，重复偏好会被重复输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:125-126`
  - 依据：`[p for p in likes if p in picked]` 用 `in` 做的是值相等比较（BuyerPreference 若为 dataclass 则按字段比较），而不是身份比较。若 likes 中存在两条字段完全相同的偏好（同一买家重复 remember 同一句偏好是常见情形），picked 里只含其中一条，但列表推导会把两条都保留，导致输出条数超过 top_k，且重复注入同一行。同理 _latest_first 也有相同问题。触发条件：likes 中存在字段完全相同的重复项，且该值被选中。
- **[boundary/medium]** [boundary] app/domain/catalog/sku.py:27-31 Sku.stock 校验拒绝 0 库存，导致售罄商品无法建模（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:27-31`
  - 依据：stock 被定义为“初始库存（只读参考数据）”，但 __post_init__ 要求 stock > 0。一个已售罄或尚未备货的 SKU 初始库存为 0 是完全合法的业务状态，构造 Sku(stock=0) 会抛 ValueError，导致商品目录无法加载售罄商品。注释说 stock 用于“库存服务不可用时的展示兜底”，售罄恰恰是最需要展示的状态。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:66-72 CachedEmbeddingClient 缓存命中判定 isinstance(cached, list) and cached 会拒绝空向量，但空向量本身非法（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-72`
  - 依据：空列表被当作未命中回源，符合预期（空向量无意义），不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:78-82 CachedEmbeddingClient.embed_batch 中 zip 截断导致上游少返回时结果缺失但被后续检查捕获（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:78-82`
  - 依据：zip(pending, fresh) 在上游少返回时会截断，但随后 missing 检查会抛 RuntimeError，不会静默补零向量，行为符合注释意图。
- **[boundary/low]** [boundary] app/infrastructure/cache/redis_cache.py:137-148 RedisCache.zadd_and_count 清理边界多减 1 秒，窗口内计数偏小（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:137-148`
  - 依据：zremrangebyscore(key, 0, now - window_seconds - 1) 把窗口下界多减了 1 秒，导致恰好落在 [now-window-1, now-window) 区间内的成员被提前清除，滑窗计数偏小，限流会放行本应被限的请求。虽然影响仅 1 秒，但这是限流正确性问题。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-130 RedisCache.set_if_absent 在 Redis 异常时返回 True，幂等键失效导致重复执行（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：注释明确说明这是刻意的降级策略：宁可退化成无幂等保护也不能因缓存故障拒绝服务。这是有意的可用性权衡而非缺陷，虽然会带来重复下单风险，但属于设计决策。
- **[boundary/low]** [boundary] app/infrastructure/cache/semantic_cache.py:148-156 语义缓存 remember 的 scope 参数被截断无法确认，但 lookup 的阈值比较使用严格大于导致等于阈值时不命中（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:148-156`
  - 依据：lookup 用 similarity > self._threshold，文档说“低于阈值视为未命中”，等于阈值时按未命中处理，与文档“低于阈值”措辞略有出入，但这是保守方向（宁可多花一次调用），不构成错误行为。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:150-156 SemanticCache.lookup 对 entry 的 vector 缺失时 _cosine 返回 0，安全（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:150-156`
  - 依据：entry.get('vector', []) 缺失时 _cosine 因 norm 为 0 返回 0.0，不会误命中，安全。
- **[api_misuse/low]** [api_misuse] app/infrastructure/security/content_filter.py:22-30 content_filter 正则 (?i) 内联标志在 Python 3.11+ 仍可用但 re.compile 对含内联标志的模式在部分位置会报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:22-30`
  - 依据：所有模式都以 (?i) 开头，位于模式起始处，Python re 允许全局内联标志在开头，编译正常，不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:24-24 content_filter 的“忽略...指令”模式要求中间有 10 字符内内容，可能漏过短注入（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-24`
  - 依据：正则覆盖有限是已知的纵深防御设计（注释说明语义级判断交给 L4），单条正则覆盖不全不构成可复现缺陷，且其他模式可补充。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:47-47 内部服务地址正则未锚定主机名边界，可能误伤含该子串的合法域名（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:47-47`
  - 依据：模式 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 在主机名后紧跟 `(?::\d+)?` 或 `(?:/\S*)?`，两者都可为空，因此 `https://redis.example.com` 会匹配到 `https://redis` 部分并被替换为 `[已脱敏]`，留下 `.example.com` 残片。这属于过度脱敏（误伤），但方向是安全侧（宁可多脱敏），且 docstring 已声明脱敏不阻断回复。判定为可接受的收窄，不作为缺陷上报，仅记录。

## 争议（需裁决）

- **[logic/medium]** [logic] app/domain/catalog/money.py:30-33 Money.from_major_units 对 JPY 等零小数币种统一乘 100，金额放大 100 倍（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:30-33`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 最小单位就是 1 日元（无小数）。from_major_units(1000, 'JPY') 会得到 100000 minor units，to_major_units 再除以 100 得 1000，看似自洽，但任何按 ISO-4217 exponent 解释 minor units 的下游（支付网关、库存价格展示）都会把 1000 日元当成 100000 日元。注释承认“demo 暂统一”，但这是真实的价格不变量缺陷，跨境业务中价格错误是核心风险。
  - 争议对手：e43fdf0c37f2

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/catalog, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 0 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| `5e837c68a39e` | 1 | 1 | `partition_gap` | — |
| `62b74df5111f` | 1 | 4 | `partition_gap` | — |
| `63c335dd31c2` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |

矩阵填充率 12%（单元格值 = 独立 Agent 数）
