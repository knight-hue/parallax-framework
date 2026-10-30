# Parallax 运行报告 `4e13e8318dde`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 2 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 5 | 支持不足、相关性超限或尚待验证 |
| 争议 | 4 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：25
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：65 个节点 / 194 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 11 | 100% | 8% |

## 高置信结论

- **[logic/medium]** [logic] app/domain/order/order.py:74-82 cancel 允许从 DRAFT 态取消，违反状态机不变量（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:74-82`
  - 依据：文档声明状态机为 DRAFT → CONFIRMED → CANCELLED，且不变量写明「只有 CONFIRMED 态可以取消」。但 cancel() 只拒绝已 CANCELLED 的情况，DRAFT 态订单也能被取消，产生 DRAFT→CANCELLED 的非法迁移，并写入 cancelled_at/cancel_reason。
- **[logic/high]** [logic] app/domain/order/order.py:84-88 total_amount 把首行小计重复计入一次（确认存在缺陷）
  - 独立来源 3 个：reader-r0-0, reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:84-88`
  - 依据：total_amount 先用 lines[0].subtotal() 初始化 total，随后 for 循环又遍历了包含 lines[0] 在内的全部订单行并再次 add，导致第一条订单行的小计被计算两次。任何含至少一条订单行的订单（__post_init__ 强制非空）都会得到错误总额；单行订单的总额恰好是正确值的两倍。snapshot() 直接使用 total_amount()，因此回传给 Agent/买家的金额也是错的。

## 待验证（孤证）

- **[logic/low]** [logic] app/domain/order/order.py:44-49 OrderLine 未校验 unit_price 币种/非负，币种一致性仅靠注释保证（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:44-49`
  - 依据：__post_init__ 注释明确说明币种一致性由下单用例保证，属于分层设计取舍；OrderLine 自身只校验 quantity。虽然聚合根不变量「全部订单行币种一致」没有在 Order 内强制，但这是文档化的约定，且 Money.add 在币种不一致时通常会抛错（取决于 Money 实现，未在给定文件中）。无法从给定代码确认存在错误行为，故不报为缺陷。
- **[boundary/low]** [boundary] app/domain/order/order_line.py:20-24 OrderLine 未校验 unit_price 币种/非负，币种一致性仅靠注释保证（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:20-24`
  - 依据：Order.__post_init__ 注释称币种一致性由下单用例保证，OrderLine 只校验 quantity。这属于分层职责划分，Money.multiply 自身应保证金额合法性；在给定文件范围内无法证明存在可触发的错误行为，故不判为缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/security/output_guard.py:55-56 audit_output 对空字符串返回安全，但未处理非 str 输入（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:55-56`
  - 依据：函数签名声明 text: str，调用方按契约传入字符串；if not text 已覆盖 None 与空串的短路返回。若传入非字符串（如 None 之外的 int），pattern.subn 会抛 TypeError，但这属于违反类型契约的调用，不是本函数缺陷。
- **[logic/low]** [logic] app/infrastructure/security/output_guard.py:38-38 内部服务地址正则未加词边界，可能误伤正常 URL 或漏匹配带路径的地址（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:38-38`
  - 依据：该模式 r"https?://(?:vllm|reranker|qdrant|redis|opensearch)(?::\d+)?(?:/\S*)?" 没有前置边界，理论上会匹配 https://redis.example.com 这类外部域名中的 'redis' 前缀，从而把合法外部链接脱敏。但结合上下文，这是刻意收窄的内部主机名列表，且外部域名场景在本项目中并不出现；同时 (?:/\S*)? 已覆盖路径。经确认，该模式对文档声明的内部地址形态（如 http://vllm:8000/v1/chat）能正确匹配，对 https://redis.io 这类会误伤但属于低概率边界，不构成确认缺陷。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:34-34 shopping_session_id 正则要求冒号或等号，纯 ID 值不会被脱敏（确认并非缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:34-34`
  - 依据：该模式针对 `shopping_session_id: xxx` 或 `shopping_session_id=xxx` 形式。若 Agent 直接输出裸 ID 值（无字段名），确实不会被脱敏。但裸 ID 通常无上下文，且模块文档声明判据是“买家侧无需知道且泄露有害”，裸 ID 是否敏感取决于 ID 格式。无法从代码确认裸 ID 会泄露，故不判定为缺陷。

## 争议（需裁决）

- **[boundary/low]** [boundary] app/application/harness/loop_detector.py:47-55 LoopDetector 的 window 参数在首次分桶时被忽略（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:47-55`
  - 依据：_calls 的 default_factory 固定使用 DEFAULT_WINDOW 作为 maxlen。当构造时传入 window != DEFAULT_WINDOW，_bucket 首次访问会通过 defaultdict 创建 maxlen=6 的 deque，随后 maxlen != self.window 触发重建，逻辑上能纠正；但重建时用 deque(bucket, maxlen=self.window)，若新 window 小于已有元素数，会静默丢弃最旧元素——这在首次访问时 bucket 为空，无影响。真正的问题是：若 window 被设为 0 或负数，deque(maxlen=0) 会丢弃所有记录，trailing_repeat 恒为 0，检测完全失效且无任何报错。
  - 争议对手：d4049e1079d0
- **[logic/low]** [logic] app/application/harness/loop_detector.py:47-55 LoopDetector 的 window 参数在首次访问后无法生效（确认存在缺陷）
  - 独立来源 2 个：reader-r0-0, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/harness/loop_detector.py:47-55`
  - 依据：_calls 的 default_factory 用 DEFAULT_WINDOW 固定 maxlen，_bucket 在 maxlen 与 self.window 不一致时重建。但重建后的 deque 仍以 self.window 为 maxlen，看似正确；问题在于 defaultdict 的 default_factory 在每次新 session 首次访问时创建 maxlen=DEFAULT_WINDOW 的桶，若构造时传入 window != DEFAULT_WINDOW，则每个新会话第一次 record 时桶被创建为 DEFAULT_WINDOW，随后 _bucket 检测到不一致并重建——这一步本身能纠正。真正的缺陷是：重建发生在 append 之前，deque(bucket, maxlen=self.window) 会保留旧元素，逻辑上可接受。经核对，该路径实际能正确收敛到 self.window，不构成缺陷。
  - 争议对手：985721c25172, 9f7e496d4550
- **[boundary/medium]** [boundary] app/infrastructure/security/output_guard.py:43-43 SENSITIVE_PATTERNS 中工具名正则使用 \b 边界，对下划线连接的标识符可能失效（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:43-43`
  - 依据：Python 正则中 \w 包含下划线，因此 \b 只在下划线与非单词字符之间成立。工具名如 product_search_tool 前后若紧邻下划线（例如被拼接成 my_product_search_tool_x 或 product_search_tool_v2），\b 不会在 _ 与 p 之间形成边界，导致该内部工具名未被脱敏而泄露。文档声称按真实工具名逐个列出以避免误伤，但边界选择使带后缀/前缀的变体逃逸。
  - 争议对手：7f5ea164963a
- **[logic/medium]** [logic] app/infrastructure/security/output_guard.py:42-42 内部工具名正则使用 \b 边界，但工具名含下划线，\b 在 _ 与字母间不成立（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:42-42`
  - 依据：Python 正则中 `\b` 是单词边界，单词字符为 [A-Za-z0-9_]。工具名如 `product_search_tool` 以 `_` 结尾，`\b` 在 `l` 与 `_` 之间不成立（两者都是单词字符），因此 `\bproduct_search_tool\b` 实际要求工具名后紧跟非单词字符。若输出为 `product_search_tool` 后跟空格或标点，`\b` 成立，能匹配；但若输出为 `product_search_tool_v2` 或 `product_search_tool.` 中前者不应匹配而后者应匹配——实际 `product_search_tool.` 中 `l` 与 `.` 之间 `\b` 成立，能匹配。真正问题在于：若工具名后紧跟另一个单词字符（如 `product_search_toolx`），`\b` 不成立，不匹配，这是期望行为。因此 `\b` 在此处行为正确，不构成缺陷。
  - 争议对手：84b9664bbccd, 8e18c8e862a0

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 1.00 ≥ 0.00，归一化 33.33% ≥ 0.00%
- 有效通道：1.00｜归一化 33.3%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：0｜漏检候选（读者层）：27｜覆盖正常：4｜无法判定：0
- 单 Reader 检出率：95.0%（重捕对 3，已观测 11，估计总体 11.0
- 待补检分组：app, app/application/memory, app/infrastructure/security, app/application/usecases, app/domain/shipping, app/application/prompts, app/domain/buyer, app/infrastructure/cache, app/domain, app/domain/order, app/application/harness, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `0505c2ad4786` | 3 | 0 | `reader_miss` | 0.0% |
| `17da7cc20bb4` | 3 | 0 | `reader_miss` | 0.0% |
| `269088b25c46` | 3 | 0 | `reader_miss` | 0.0% |
| `477fac3ae5ae` | 3 | 0 | `reader_miss` | 0.0% |
| `4ad98b411bb7` | 3 | 0 | `reader_miss` | 0.0% |
| `4fcaf3c8939f` | 3 | 0 | `reader_miss` | 0.0% |
| `538d958c9657` | 3 | 0 | `reader_miss` | 0.0% |
| `6fd64302ee4f` | 3 | 0 | `reader_miss` | 0.0% |
| `7c2ab632b69d` | 3 | 0 | `reader_miss` | 0.0% |
| `7d3fc36631b9` | 3 | 0 | `reader_miss` | 0.0% |
| …另有 17 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/harness` | 3 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/prompts` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/order` | 3 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/shipping` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 3 | 0 | 2 | 2 | 0 | 2 | 0 | 0 |

矩阵填充率 8%（单元格值 = 独立 Agent 数）
