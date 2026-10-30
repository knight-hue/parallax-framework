# Parallax 运行报告 `c43dd05c5ca0`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 14 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：1 个（每轮全新身份）
- 账本条目：14
- 独立性画像：有效通道 1.00 / 1，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：43 个节点 / 54 条边
- 去共同上游后的通道：1；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 14 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:33-41 PreferenceSelector 相关性排序分支被截断，无法确认；但 _cosine 对维度不一致返回 0.0 会静默降级（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:33-41`
  - 依据：_cosine 在维度不一致或零向量时返回 0.0，属于保守降级：所有候选同分时排序退化为稳定顺序，不会产生错误结果，只是相关性失效。不构成缺陷。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:78-82 PreferenceSelector.select 在 top_k<=0 时丢弃 dislike，违背“黑名单全量保留”的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:78-82`
  - 依据：模块 docstring 明确声明 dislike 全量保留、不参与 top_k 截断，理由是漏掉黑名单是安全问题。但 select 在 top_k<=0 时直接 return []，把 dislike 也一并丢弃。若调用方因预算紧张传入 top_k=0，买家“不要塑料材质”等忌口将完全不注入，模型可能推荐被明确拒绝的商品。这与文档声明的安全不变量直接冲突。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:33-36 from_major_units 用 round 处理浮点，银行家舍入导致金额偏差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:33-36`
  - 依据：Python 的 round 使用银行家舍入（round-half-to-even），且 major 是 float，0.1*100 之类的二进制浮点误差会先于舍入发生。例如 round(2.675*100) 得到 267 而非 268；round(0.5*100)=50 但 round(1.5*100)=150、round(2.5*100)=250 看似正常，而 round(0.125*100)=12（应为 13）。金额换算用 float + round 会静默产生 1 分误差，与模块文档“避免浮点误差”的目标相悖。
- **[logic/medium]** [logic] app/domain/catalog/money.py:38-46 Money.add/multiply 绕过不变量校验直接构造实例（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:38-46`
  - 依据：of() 是唯一做校验的入口（非负整数、受支持币种），但 add() 和 multiply() 直接调用 Money(...) 构造器，绕过了 of()。虽然 add 的输入来自两个已校验的 Money，结果仍非负；但 multiply 的 quantity 校验与 of 的 amount 校验并不等价——更关键的是 dataclass 本身没有 __post_init__ 校验，任何直接 Money(-1, 'USD') 或 Money(1, 'XXX') 都能构造出违反文档声明不变量的对象。add/multiply 用裸构造器强化了这条绕过路径，使不变量只在 of() 路径上成立。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:30-45 ConversationTurn 未校验 role 是否在 VALID_ROLES 内（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:30-45`
  - 依据：模块定义了 VALID_ROLES = ('buyer','agent') 并在 __post_init__ 中只校验 session_id，未校验 role。任何拼写错误（如 'Agent'、'assistant'）都会被静默接受并落库，导致对话流水按 role 过滤/回放时漏数据。VALID_ROLES 定义后完全未被使用，说明校验被遗漏。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/cached_embedding_client.py:76-82 embed_batch 中 `vector or []` 会把合法的全零/空向量与失败结果混淆，且 zip 截断导致结果错位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:76-82`
  - 依据：若 inner.embed_batch 返回的列表长度短于 pending（上游实现异常或部分失败），zip 会静默截断，剩余 results[index] 保持 None，最终被 `vector or []` 变成空列表返回给调用方，调用方拿到长度不符的批量结果却无任何异常/日志。此外 `vector or []` 对空列表向量也返回 []，无法区分“未取到”与“合法空向量”。
- **[logic/high]** [logic] app/infrastructure/cache/cached_embedding_client.py:33-35 CachedEmbeddingClient._key 未包含 model，不同模型共享同一缓存键（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:33-35`
  - 依据：模块 docstring 明确声明 key 用 sha256(model + text)，但 _key 只对 text 做哈希，model 完全没参与。若同一 Redis 实例上部署了多个模型（或切换模型后旧缓存仍在 7 天 TTL 内），新模型会读到旧模型生成的向量。向量维度不同时下游向量索引/余弦计算会出错（_cosine 长度不等返回 0.0，检索静默失效）；维度相同但语义空间不同则召回结果完全错误。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:118-130 set_if_absent 在 Redis 故障时返回 True，幂等保护静默失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-130`
  - 依据：这是文档明确声明的降级策略（fail-open）：宁可失去幂等保护也不拒绝服务。虽然对幂等键语义有风险，但属于有意的可用性取舍，且注释写清了理由，不构成实现缺陷。
- **[error_handling/medium]** [error_handling] app/infrastructure/cache/redis_cache.py:132-150 zadd_and_count 在 Redis 故障时返回 0，限流完全失效（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:132-150`
  - 依据：与 set_if_absent 一致，这是文档化的 fail-open 降级（按不限流处理），属于可用性优先的显式取舍，不是实现错误。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:66-74 get_json 在 json.loads 失败时删除键，可能误删非 JSON 数据（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-74`
  - 依据：get_json 只应被用于 JSON 值；对脏值删除是文档化的自愈行为，且 get_raw 已为裸字符串场景提供独立入口并在 docstring 中明确说明不能走 get_json。因此这不是缺陷，而是有意的设计。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:138-148 zadd_and_count 的 zremrangebyscore 与 zadd 在同一事务中，但 member 重复时计数偏大（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:138-148`
  - 依据：zadd 对已存在 member 是更新分数而非新增，zcard 统计的是唯一成员数，因此同一 member 重复调用不会重复计数，行为符合滑动窗口语义。
- **[logic/low]** [logic] app/infrastructure/cache/semantic_cache.py:47-55 SemanticCache 的 _UNSAFE_RE 未做大小写/全角归一，且“这个/那个”等单字代词会误伤大量正常咨询问句（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:47-55`
  - 依据：该正则只用于“是否可缓存”的保守判定，误判方向是“本可缓存却跳过”，只会多花一次模型调用，不会返回错误回复，属于安全侧失败。因此不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:24-32 content_filter 的 DANGEROUS_PATTERNS 使用内联 (?i) 且部分模式未加，大小写覆盖不一致（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-32`
  - 依据：所有英文模式都带了 (?i)，中文模式无需大小写。逐条检查未发现遗漏大小写敏感项，正则本身可正常编译（(?i) 位于模式开头合法）。属于可接受的实现，不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-52 output_guard 的 SENSITIVE_PATTERNS 中内部工具名用 \b 边界，中文紧邻时可能不匹配（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-52`
  - 依据：Python re 的 \b 基于 \w，中文字符在 Unicode 模式下属于 \w，因此“调用product_search_tool获取”中 tool 与中文之间不构成词边界，确实可能漏匹配。但工具名通常以英文/空格/标点分隔出现，且这是脱敏兜底而非唯一防线；影响有限，且无法从代码确证必然触发泄露。记录为观察项而非确认缺陷。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：1.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain/catalog, app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 2 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 1 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 0 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 9%（单元格值 = 独立 Agent 数）
