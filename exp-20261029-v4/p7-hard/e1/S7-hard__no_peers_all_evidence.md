# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 1 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 6 | 支持不足、相关性超限或尚待验证 |
| 争议 | 2 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：19
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：52 个节点 / 150 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 9 | 100% | 5% |

## 高置信结论

- **[logic/high]** [logic] app/application/memory/preference_selector.py:118-124 相关性排序取的是相似度最低的 top_k 而非最高（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:118-124`
  - 依据：scored 中元素为 (相似度, index, preference)，随后按 (item[0], item[1]) 升序排序并取 scored[:top_k]。升序排序后前 top_k 是相似度最低的偏好，即最不相关的那些被选中，与函数文档“按余弦相似度取 top_k”完全相反。触发条件是 relevance_enabled=True 且 len(likes) > top_k，此时注入的恰好是最不相关的 like 偏好，最相关的被丢弃。

## 待验证（孤证）

- **[logic/low]** [logic] app/application/memory/preference_selector.py:96-98 top_k<=0 时仍返回全部 dislike，符合安全底线设计（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:96-98`
  - 依据：模块注释明确 dislike 全量保留、不参与截断，top_k<=0 时返回 dislikes 是刻意的安全底线行为，不是缺陷。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:33-42 Product 为可变 dataclass，frozen 仅作用于 ProductHighlight，primary_sku 直接取 skus[0] 依赖 __post_init__ 校验（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:33-42`
  - 依据：__post_init__ 已保证 skus 非空，primary_sku 取 skus[0] 安全；但 Product 非 frozen，构造后仍可 skus.clear() 使 primary_sku 抛 IndexError。这是可变聚合根的常见权衡，且当前仓库内无清空 skus 的调用点，不构成可确认缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:22-38 Product 为可变 dataclass，frozen 仅作用于 ProductHighlight，skus 列表可被外部修改绕过不变量（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:22-38`
  - 依据：__post_init__ 校验 skus 非空，但 Product 非 frozen，skus 是可变 list，外部可在构造后 clear() 使 primary_sku() 抛 IndexError。不过这是聚合根常见设计（允许后续添加 SKU），且没有代码在本仓库内清空 skus；属于潜在风险而非已确认缺陷。
- **[logic/low]** [logic] app/domain/catalog/product.py:47-52 Product.searchable_text 对 highlight.detail 为空时产生多余空格，且未包含 skus 信息（确认并非缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：searchable_text 用空格拼接 title/brand/category/origin_country/description/highlight_text，当 highlights 为空时 highlight_text 为空字符串，join 会产生尾部空格；当 detail 为空时 f"{h.label} {h.detail}" 也会产生尾部空格。这只是文本格式上的冗余空白，不影响召回语义（分词/embedding 对多余空格不敏感），不构成真实缺陷。skus 未纳入检索文本是设计选择，注释明确说明可检索文本为标题+品牌+品类+描述+亮点。
- **[error_handling/medium]** [error_handling] app/infrastructure/security/__init__.py:12-20 security 包 __init__ 从子模块导入符号，但给定文件列表中不存在这些子模块（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/__init__.py:12-20`
  - 依据：该 __init__ 导入 content_filter 与 output_guard 子模块。审查文件列表未包含这两个文件，但仓库可能确实存在（列表只给了 6 个文件，不代表仓库只有这些）。无法从给定代码确认导入失败，故不判定为缺陷。
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:36-36 sk- 模式可能误伤普通文本中的长字母数字串（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:36-36`
  - 依据：`sk-[a-zA-Z0-9]{20,}` 要求 20 位以上字母数字，普通中文回复中几乎不会出现该形态；即便误伤也只是脱敏不阻断回复（docstring 已说明脱敏不阻断）。属于可接受的保守匹配，不构成真实缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/application/memory/preference_selector.py:125-126 用 `p in picked` 做成员判断依赖对象相等性，可能误删/重复（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:125-126`
  - 依据：`[p for p in likes if p in picked]` 使用 `in` 判断，依赖 BuyerPreference 的 __eq__。若 BuyerPreference 是 dataclass 且未设置 eq=False，则两个内容相同（同 kind、同 statement、同 created_at）但实际不同的偏好对象会被视为相等，导致本应被选中的偏好被过滤掉、或未被选中的同值偏好被误保留，最终返回条数可能少于 top_k 或包含未选中项。_latest_first 中同样使用该模式。
  - 争议对手：bd07e17ea662
- **[boundary/low]** [boundary] app/infrastructure/security/output_guard.py:40-40 output_guard 的 URL 正则未锚定主机名边界，可能误伤合法域名（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-40`
  - 依据：模式 `https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?` 在主机名后没有边界约束（如 `(?![\w.-])`），因此 `https://redis.example.com/docs` 这类合法外部域名会被匹配并脱敏为 `[已脱敏]`，破坏正常回复内容。虽然模块注释强调「避免把买家可见的正常措辞误伤」，但该正则对以内部服务名开头的公网域名仍会误伤。触发条件：回复中出现以 vllm/reranker/qdrant/redis/opensearch 开头后接 `.` 或其它字符的 URL。
  - 争议对手：7f5ea164963a, 7f5ea164963a, be4240515bc9, be4240515bc9

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：22｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 9，估计总体 9.0
- 待补检分组：app, app/application/memory, app/infrastructure, app/domain/buyer, app/domain/session, app/domain/catalog, app/infrastructure/cache, app/domain, app/infrastructure/security, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `5249eda27566` | 3 | 0 | `reader_miss` | 0.0% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.0% |
| `5d929055a8d9` | 3 | 0 | `reader_miss` | 0.0% |
| `63c335dd31c2` | 3 | 0 | `reader_miss` | 0.0% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.0% |
| `73fcc31c85be` | 3 | 0 | `reader_miss` | 0.0% |
| `797c78721ca7` | 3 | 0 | `reader_miss` | 0.0% |
| `7c06a9ebea13` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 12 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 3 | 2 | 0 | 0 | 0 | 0 |

矩阵填充率 6%（单元格值 = 独立 Agent 数）
