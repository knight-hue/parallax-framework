# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 22 | 支持不足、相关性超限或尚待验证 |
| 争议 | 1 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：24
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：56 个节点 / 78 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 23 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[boundary/low]** [boundary] app/application/memory/preference_selector.py:47-57 render_preference_hint 对空偏好列表仍渲染出空块（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:47-57`
  - 依据：render_preference_hint 在 preferences 为空时会生成只含头尾的 <buyer-preferences> 块。但 select() 在 preferences 为空时返回 []，调用方通常据此跳过注入；且即便渲染空块也只是多一条无内容 hint，不构成错误行为。属于边界但非缺陷。
- **[error_handling/low]** [error_handling] app/application/memory/preference_selector.py:30-37 _cosine 对长度不一致向量返回 0.0 而非报错，可能掩盖 embedding 维度问题（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:30-37`
  - 依据：_cosine 在维度不一致或零向量时返回 0.0，是刻意的防御性降级：排序仍能进行（同分按 index 稳定），不会抛异常中断对话。虽然可能掩盖上游维度不一致，但 _rank_by_relevance 已对向量数量做校验，且降级路径有日志。不构成真实缺陷。
- **[logic/low]** [logic] app/application/memory/preference_selector.py:128-135 _rank_by_relevance 声称「回到原始相对顺序输出」但实际按分数排序输出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:128-135`
  - 依据：注释说 picked 会回到原始相对顺序以避免注入块行序抖动，但代码 `picked = [preference for _, _, preference in scored[:top_k]]` 直接按相似度降序输出，并未按原始 index 重排。结果注入块的行序随 query 变化而抖动，与注释承诺及 _latest_first 的行为不一致（后者确实复原了相对顺序）。这会导致同一批偏好在不同轮次以不同顺序注入，影响 prompt 稳定性/可测性。
- **[logic/high]** [logic] app/application/memory/preference_selector.py:88-99 select() 用 [:top_k] 截断会把 dislike 挤掉，违背「dislike 全量保留」的安全底线（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/application/memory/preference_selector.py:88-99`
  - 依据：模块文档明确承诺 dislike 全量保留、不参与 top_k 截断，但实现先构造 dislikes + selected_likes，再整体 [:top_k]。当 dislike 数量 >= top_k 时，末尾的 dislike 会被截掉；当 dislike 数量 < top_k 但 dislikes+likes 超过 top_k 时，虽然 dislike 都在前面能保留，但 top_k 预算被 dislike 占满后 like 全被丢弃（这本身符合预算语义）。真正的缺陷是 dislikes 数量超过 top_k 时黑名单被截断，直接导致「推了用户明确拒绝的东西」这一安全问题。例如 top_k=3、有 5 条 dislike，则只注入前 3 条，后 2 条忌口丢失。
- **[api_misuse/low]** [api_misuse] app/domain/buyer/preference.py:47-57 delete 按 statement 精确匹配且不区分 kind，可能误删同文不同 kind 的偏好（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:47-57`
  - 依据：文档字符串明确说明“不按 kind 区分：同 statement 的 like 与 dislike 条目会一并清除”，这是刻意设计而非缺陷。精确匹配也是为避免模糊匹配误删而刻意选择。因此不构成缺陷，但调用方需知晓该语义。
- **[boundary/low]** [boundary] app/domain/buyer/preference.py:22-31 BuyerPreference 未校验 buyer_id 非空（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：BuyerPreference 校验了 kind 和 statement，却未校验 buyer_id。空 buyer_id 的偏好可被 append 写入，list_by_buyer('') 会把这些无主偏好返回给任意空 id 查询，造成跨买家数据串扰。同模块其他字段都有校验，说明这是遗漏。
- **[logic/low]** [logic] app/domain/buyer/preference.py:22-31 created_at 使用可变默认值逻辑但通过 __post_init__ 赋值，frozen 下用 object.__setattr__ 正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/buyer/preference.py:22-31`
  - 依据：created_at 默认空串，在 __post_init__ 中通过 object.__setattr__ 赋值，这是 frozen dataclass 的标准做法，不会触发 FrozenInstanceError，也不存在可变默认值共享问题（字符串不可变）。逻辑正确。
- **[boundary/low]** [boundary] app/domain/catalog/money.py:22-27 multiply 拒绝 bool 但 of 接受 bool 作为 amount（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:22-27`
  - 依据：multiply 显式排除了 bool（isinstance(quantity, bool)），但 of() 只检查 isinstance(amount, int)，而 Python 中 bool 是 int 的子类，因此 Money.of(True, 'USD') 会成功创建 amount_in_minor_units=True 的实例，校验不一致。
- **[logic/medium]** [logic] app/domain/catalog/money.py:31-34 from_major_units 对 JPY 等零小数币种按 100 换算错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:31-34`
  - 依据：SUPPORTED_CURRENCIES 包含 JPY，而 JPY 的 ISO-4217 小数位为 0，最小单位即 1 日元。from_major_units 对所有币种统一乘 100，导致 1000 JPY 被存成 100000 minor units，to_major_units 再除以 100 虽能还原显示，但金额语义（最小单位）错误，与文档声明的『以最小货币单位（分）存储』不变量冲突。注释承认是简化，但这是真实的行为错误而非风格问题。
- **[logic/low]** [logic] app/domain/catalog/money.py:45-46 to_major_units 返回 float 丢失精度（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:45-46`
  - 依据：to_major_units 仅用于展示（__str__），内部金额始终以整数 minor units 保存，不参与计算，因此 float 精度损失不影响不变量。
- **[boundary/low]** [boundary] app/domain/catalog/product.py:47-52 Product.searchable_text 在 highlights 为空时产生多余空格（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/product.py:47-52`
  - 依据：highlight_text 为空时 join 结果末尾会多一个空格，但这对召回文本无实质影响（embedding/关键词匹配对空白不敏感）。属于格式瑕疵而非缺陷。
- **[boundary/low]** [boundary] app/domain/session/ports/conversation_store.py:41-48 ConversationEventRecord 未校验 session_id/type，与 ConversationTurn 校验不一致（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:41-48`
  - 依据：ConversationTurn 强制 session_id 非空，但同一模块的 ConversationEventRecord 没有任何 __post_init__ 校验。空 session_id 或空 type 的事件可被 append_events 批量写入，导致事件无法按会话关联、追溯数据出现孤儿记录。这是同一数据模型内校验不一致造成的边界缺陷。
- **[logic/low]** [logic] app/domain/session/ports/conversation_store.py:24-38 ConversationTurn 声明了 role 但未校验，非法角色可写入存储（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:24-38`
  - 依据：模块定义了 VALID_ROLES = ("buyer", "agent")，但 ConversationTurn.__post_init__ 只校验 session_id，完全没有使用 VALID_ROLES 校验 role。因此 role 可以是任意字符串（如 'system'、'tool'、空串），这些非法值会被 append_turn 持久化，破坏下游按 role 分类的追溯/回放逻辑。VALID_ROLES 的存在表明作者意图是校验 role，属于遗漏校验导致的逻辑缺陷。
- **[boundary/low]** [boundary] app/infrastructure/cache/cached_embedding_client.py:66-73 embed_batch 缓存命中判断 `isinstance(cached, list) and cached` 会丢弃空列表缓存（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/cached_embedding_client.py:66-73`
  - 依据：空列表缓存被当作未命中会重新回源，只是多一次调用，不会产生错误结果；且正常 embedding 不会是空列表。属于保守降级，不构成缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/redis_cache.py:66-72 get_json 在 json.loads 失败时 await delete 未捕获异常，可能向上抛出（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:66-72`
  - 依据：get_json 的其余路径都吞掉 Redis 异常并降级为未命中，但脏值分支里 `await self.delete(key)` 虽然 delete 内部吞异常，delete 本身不会抛；不过 json.loads 只捕获 ValueError，若 raw 是 bytes 且 decode_responses 未生效（例如外部传入的 client 配置不同），json.loads 可能抛 TypeError，未被捕获而向上传播，破坏“读失败按未命中”的契约。触发条件较窄，故 severity 低。
- **[logic/low]** [logic] app/infrastructure/cache/redis_cache.py:128-135 zadd_and_count 的 expire 在 pipeline 中位于 zcard 之后，结果索引正确（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:128-135`
  - 依据：pipeline 命令顺序为 zremrangebyscore、zadd、zcard、expire，results[2] 对应 zcard，索引正确；transaction=True 保证原子性。未发现缺陷。
- **[error_handling/low]** [error_handling] app/infrastructure/cache/semantic_cache.py:156-157 lookup 中 entry.get('vector', []) 若为 None 会使 _cosine 抛 TypeError（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:156-157`
  - 依据：remember 写入的 vector 来自 embedder.embed，正常为 list；若缓存被外部污染成 None，_cosine 的 len(None) 会抛异常，但该异常未被 lookup 捕获。不过写入路径受控，且 RedisCache 反序列化 JSON 的 null 才会产生 None，属于外部篡改场景，风险很低。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:118-126 语义缓存桶 key 忽略 scope，偏好变更后旧回复仍会命中（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:118-126`
  - 依据：_bucket_key 的签名接收 scope 参数，文档也明确要求桶 key 必须包含买家偏好指纹，否则偏好撤回后旧回复（含已删偏好）会被复用。但实现里 digest 只对 f"{self._namespace}\n{buyer_id}" 做哈希，scope 完全没有参与计算，导致不同 scope 落到同一个桶。lookup/remember 传入的 scope 因此完全失效，正是文档中“实测踩过”的那个缺陷。
- **[logic/high]** [logic] app/infrastructure/cache/semantic_cache.py:143-148 lookup 忽略 has_history，带上下文的多轮会话仍会命中缓存（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:143-148`
  - 依据：文档安全边界第 3 条要求“会话内已有多轮上下文时不命中”，remember 里确实检查了 has_history，但 lookup 完全没有使用该参数。因此只要历史轮次里存过条目，后续带上下文的多轮问句仍会命中并跳过 LLM，可能答非所问。
- **[logic/medium]** [logic] app/infrastructure/cache/semantic_cache.py:178-182 remember 的 entries[:_BUCKET_LIMIT] 保留最旧条目而非最近条目（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/semantic_cache.py:178-182`
  - 依据：注释称“保留最近条数”，但 entries.append 后取 entries[:_BUCKET_LIMIT] 保留的是列表头部（最旧）的 30 条，新追加的条目在超过 30 条后会被直接丢弃，导致新写入的回复永远无法命中，缓存退化为只服务最早的一批问句。
- **[security/low]** [security] app/infrastructure/security/content_filter.py:24-24 content_filter 正则 `忽略.{0,10}(之前|以上|所有).{0,10}(指令|指示|规则)` 中 `.` 不匹配换行，跨行注入可绕过（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/content_filter.py:24-24`
  - 依据：该模式确实无法匹配含换行的注入文本，但这是正则过滤层的固有局限，文档已声明语义级判断交给 L4 与漂移检测；单条模式覆盖不全不构成实现缺陷，且其他模式（如 system prompt、you are now）仍可命中。
- **[security/low]** [security] app/infrastructure/security/output_guard.py:40-40 output_guard 内部服务地址正则未覆盖带路径前缀的 URL 变体（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/security/output_guard.py:40-40`
  - 依据：该模式要求主机名紧跟协议，形如 http://vllm:8000/... 可命中；若出现 http://user@vllm 或 http://vllm.internal 等变体则漏匹配。但文档明确说明范围刻意收窄，且这些变体不属于当前部署形态，不构成确认缺陷。

## 争议（需裁决）

- **[logic/medium]** [logic] app/infrastructure/cache/redis_cache.py:118-137 zadd_and_count 在 Redis 不可用时返回 0，导致限流失效（fail-open）（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/cache/redis_cache.py:118-137`
  - 依据：zadd_and_count 的文档说明它用于跨进程限流。当 self._client is None（REDIS_URL 未配置）时直接返回 0；当 pipeline 抛异常时也返回 0。调用方通常把返回值与阈值比较（如 count > limit 则拒绝），返回 0 意味着永远不触发限流，即 Redis 故障或未配置时限流完全失效。这与 set_if_absent 的 fail-open 语义一致，但限流场景下 fail-open 会让保护机制静默消失，属于真实的行为缺陷（尤其当部署忘记配置 REDIS_URL 时，限流形同虚设且无任何告警）。
  - 争议对手：e3cf0fb18c3c

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：26｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/domain/catalog, app, app/application/memory, app/infrastructure/security, app/infrastructure, app/domain/buyer, app/domain/session, app/infrastructure/cache, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `17da7cc20bb4` | 1 | 0 | `partition_gap` | — |
| `1ea202d2ad5b` | 1 | 4 | `partition_gap` | — |
| `269088b25c46` | 1 | 0 | `partition_gap` | — |
| `3af4356ea741` | 1 | 1 | `partition_gap` | — |
| `5249eda27566` | 1 | 0 | `partition_gap` | — |
| `538d958c9657` | 1 | 0 | `partition_gap` | — |
| `570f58fa92ef` | 1 | 1 | `partition_gap` | — |
| `5d929055a8d9` | 1 | 0 | `partition_gap` | — |
| …另有 16 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/memory` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/session` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure/cache` | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| `app/infrastructure/security` | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

矩阵填充率 18%（单元格值 = 独立 Agent 数）
