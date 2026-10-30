# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 3 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 8 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：24
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：55 个节点 / 162 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 11 | 100% | 6% |

## 高置信结论

- **[logic/low]** [logic] app/application/memory/preference_selector.py:137-141 _rank_by_relevance 注释声称回到原始相对顺序，实际按相关性排序输出（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:137-141`
  - 依据：注释写「回到原始相对顺序输出，避免注入块的行序每轮抖动导致重复注入」，但代码 picked = [preference for _, _, preference in scored[:top_k]] 直接按相关性得分顺序输出，并未按原始 index 重排。这导致注入块行序随 query 变化而抖动，与注释意图相反，可能造成 prompt cache 命中率下降或重复注入。虽然不影响正确性，但注释与实现不符，且实现未达成其声明的稳定性目标。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:145-149 _latest_first 用 `p in newest` 依赖 dataclass 相等性，重复偏好会被重复保留（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:145-149`
  - 依据：_latest_first 通过 `[p for p in likes if p in newest]` 复原顺序，`in` 使用 BuyerPreference 的相等性（dataclass 默认按字段比较）。若存在两条字段完全相同的偏好（同一 statement、同一 created_at、同一 kind），newest 只包含其中一条（sorted 后切片），但列表推导会把 likes 中所有相等对象都保留，导致返回条数超过 top_k，进而使 select 中 `len(selected_likes) <= top_k` 的假设被打破，最终切片可能挤掉 dislike。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:96-108 dislike 偏好被 top_k 截断，违反「黑名单全量保留」的安全底线（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-108`
  - 依据：模块文档明确声明 dislike 必须全量保留、不参与 top_k 截断，但 select() 最后返回 (dislikes + selected_likes)[:top_k]。当 dislike 数量 >= top_k 时，dislikes 自身会被截断；当 dislikes 与 selected_likes 之和超过 top_k 时，selected_likes 会被截断（这部分是预期），但更关键的是：当 len(dislikes) > top_k 时，部分 dislike 被丢弃，直接违反安全底线。此外，当 len(likes) <= top_k 时 selected_likes = likes 全量，再与 dislikes 拼接后截断，会优先保留 dislike、丢弃 like，行为与「like 走相关性排序」的语义不一致，但主要缺陷是 dislike 被截断。触发条件：dislikes 数量大于 top_k（例如 top_k=3 而买家有 5 条忌口）。

## 待验证（孤证）

- **[boundary/medium]** [boundary] app/application/memory/preference_selector.py:92-94 top_k<=0 时连 dislike 也一并丢弃，与“黑名单全量保留”矛盾（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:92-94`
  - 依据：当 top_k <= 0 时直接 return []，把 dislike 也全部丢弃。虽然注释说“预算为 0 时不注入任何偏好”，但模块核心安全约束是 dislike 全量保留、不参与截断。若调用方因配置错误或预算计算得到 top_k=0，黑名单将完全失效，可能推荐用户明确拒绝的商品。这是边界条件与安全约束的冲突。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-37 embed_batch 返回向量维度与 query 向量不一致时静默按 0 分处理（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：_cosine 在维度不一致或零向量时返回 0.0，属于防御性降级而非崩溃；排序仍能完成，只是该条偏好得分为 0。虽然可能掩盖 embedding 服务异常，但不会产生错误的安全后果（dislike 不参与该路径），且注释说明选偏好失败不应阻断对话。判定为可接受设计。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:38-39 primary_sku 直接取 skus[0]，依赖 __post_init__ 保证非空（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:38-39`
  - 依据：__post_init__ 已强制 skus 非空，构造后 skus 不会被清空（dataclass 非 frozen 但无删除接口），因此 primary_sku 不会 IndexError。属于可接受的不变式依赖。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-51 searchable_text 中 highlight_text 为空时产生多余空格（非缺陷）（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-51`
  - 依据：当 highlights 为空时 highlight_text 为空字符串，join 结果末尾会多一个空格。这只是可检索文本中的冗余空白，不影响召回语义，也不构成错误行为。
- **[boundary/low]** [boundary] app/domain/catalog/sku.py:30-34 Sku.stock 非负校验正确，无缺陷（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/sku.py:30-34`
  - 依据：__post_init__ 校验 sku_id 非空与 stock 非负，逻辑正确。stock 作为只读初始库存，文档明确不提供扣减方法，符合设计。未发现缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:62-63 audit_output 对空字符串返回 True 但未处理 None 之外的非字符串（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:62-63`
  - 依据：if not text: return True, text 对空字符串和 None 都返回安全，符合「无内容即安全」的语义。虽然类型标注为 str，但传入 None 时不会崩溃，行为合理。不构成缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:70-76 audit_output 逐模式 subn 可能因脱敏文本再次命中后续模式而重复处理（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:70-76`
  - 依据：REDACTED 占位符为「[已脱敏]」，不含任何敏感模式可匹配的字符（无 URL、无工具名、无 session id 形态），因此后续模式不会再次命中已脱敏文本。逐模式处理是安全的。不构成缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:44-45 SENSITIVE_PATTERNS 中内部工具名正则未转义，但工具名均为安全字符（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:44-45`
  - 依据：_INTERNAL_TOOLS 中所有名称仅含字母和下划线，拼接进正则后无需转义，不会产生正则注入或误匹配。\b 边界确保不会匹配到更长标识符的子串。不构成缺陷。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：22｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 11，估计总体 11.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `269088b25c46` | 3 | 0 | `reader_miss` | 0.0% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.0% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.0% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.0% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.0% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.0% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 12 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 1 | 2 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 1 | 0 | 3 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 10%（单元格值 = 独立 Agent 数）
