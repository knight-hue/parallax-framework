# Parallax 运行报告 `fec04b32e461`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 16 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：16
- 独立性画像：有效通道 3.00 / 3，归一化 100.0%，证据重叠 0.0%，输出隔离 `verified`
- 相关性预算：`满足`｜证据重叠上限 100.0%
- 证据血缘：64 个节点 / 75 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 16 | 0% | 0% |

## 高置信结论

（无）

## 待验证（孤证）

- **[api_misuse/low]** [api_misuse] app/domain/catalog/exchange_rate.py:27-29 frozen dataclass 持有 dict 字段：hash 时抛 TypeError，且不变式可被外部改写（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:27-29`
  - 依据：dataclass(frozen=True) 且 eq=True 时会自动生成 __hash__ = hash((self.rates_to_cny,))，而 dict 不可哈希，因此 hash(ExchangeRateTable()) 会抛 TypeError: unhashable type: 'dict'；这意味着该“值对象”无法放进 set、无法作为 dict 键、无法参与 functools.lru_cache 的参数哈希。同时 frozen 只阻止字段重新赋值，不阻止对 dict 内容的原地修改（table.rates_to_cny['USD']=1.0 可以成功），值对象的不可变承诺被破坏，若在多处共享同一实例会得到不稳定结果。
- **[logic/high]** [logic] app/domain/catalog/exchange_rate.py:31-35 ExchangeRateTable.rate 汇率方向写反，导致所有跨币种换算结果错误（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/exchange_rate.py:31-35`
  - 依据：表 rates_to_cny 的语义在注释中被明确定义为“1 单位外币 = N CNY”（如 rates_to_cny['USD']=7.10 表示 1 USD = 7.10 CNY）。因此 from→to 的换算率应为 rates_to_cny[from] / rates_to_cny[to]；而代码写成 rates_to_cny[to] / rates_to_cny[from]，把分子分母颠倒了。实测 rate('USD','CNY') 返回 1.0/7.10≈0.1408，而正确值应为 7.10；反之 rate('CNY','USD') 返回 7.10 而正确值约 0.1408。所有非同一币种的 convert 都会沿用它，导致金额相差约 50 倍（USD/CNY）甚至更多（JPY 相差 400 倍以上），且因 Money.of 只校验非负与币种合法，错误金额会静默通过，不会被任何后续校验拦下。
- **[boundary/medium]** [boundary] app/domain/catalog/money.py:27-30 Money.from_major_units 用 int() 截断浮点乘积，产生 1 分误差（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:27-30`
  - 依据：int(major * 100) 对浮点结果向零截断，而二进制浮点无法精确表示多数两位小数，major*100 可能略小于真实整数（例如 1.15*100 = 114.99999999999999，2.675*100 = 267.49999999999994），截断后少 1 分。由于 Money 是价格核心不变量，这类少 1 分的偏差会静默写入订单金额，且不会被 Money.of 的非负/币种校验发现。正确做法应先做十进制或 round/Decimal 再取整。
- **[logic/low]** [logic] app/domain/catalog/money.py:27-42 JPY 按 100 倍“分”记账与硬编码汇率 0.048 是自洽的，不构成换算错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/catalog/money.py:27-42`
  - 依据：from_major_units/to_major_units 对所有币种统一按 100 倍换算（JPY 未按真实 1 倍处理），初看会怀疑跨币种换算会出错。但在 ExchangeRateTable.convert 中两侧都以 100 倍最小单位参与计算，比例因子相互抵消：1000 JPY → 100000 minor，乘 0.048 = 4800 minor = 48.00 CNY，与真实值 1000×0.048=48 CNY 一致；from_major_units(1000,'JPY').to_major_units() 也回到 1000.00。因此 JPY 的“假分”处理只影响对外 ISO 语义（代码注释已声明为 demo 简化），不会导致内部换算算术错误。
- **[api_misuse/low]** [api_misuse] app/domain/order/address.py:11-24 frozen dataclass 的 __post_init__ 中未做字段赋值，不会触发 FrozenInstanceError，非缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:11-24`
  - 依据：在 @dataclass(frozen=True) 类型中，__post_init__ 里只要不写 self.x = ... 就完全合法；本实现只读取字段并可能抛 ValueError，因此不会触发 FrozenInstanceError 警告或异常。同时实现了 __eq__/__hash__（eq、frozen 为默认），Address 作为值对象在 set/dict 中可安全使用。校验失败时抛 ValueError（而非 TypeError）也符合“必填值非法”的语义。
- **[logic/low]** [logic] app/domain/order/address.py:26-27 one_line() 的格式化在字段为空时产生连续空格/空括号，仅为展示瑕疵（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/address.py:26-27`
  - 依据：one_line 用 f-string 无条件拼接 country/state/city/address_line 与收件人/电话。若 state 或 phone 为空（这是被允许的），输出会出现连续空格或空的括号样式；但这只影响文本观感，不涉及返回类型、长度上限或解析契约——没有任何代码会反向解析该字符串（仓库内无解析方），因此不判定为真实缺陷。若后续需要展示优化，应在此处做 ' '.join(x for x in ... if x) 的空值过滤。
- **[boundary/high]** [boundary] app/domain/order/order.py:50-54 Order.__post_init__ 只拦截 lines=None，空列表绕过“至少一条订单行”不变量，随后 total_amount/snapshot 抛 IndexError（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:50-54`
  - 依据：类文档声明的第一条不变量是“至少一条订单行”，但 __post_init__ 只判断 `self.lines is None`。传入空列表 `[]` 时：空集合推导得到空 currencies，`len(currencies) > 1` 为 False，构造完全通过；随后 Order.place() 会把它 confirm 成 CONFIRMED 并落入仓储，此时聚合处于违反不变量（0 条订单行）的状态。之后任何读取路径——total_amount() 的 `self.lines[0]`、以及 snapshot() 中的 `self.total_amount()`——都会抛 IndexError（未被包装成 ValueError），工具层回传快照时变成 500/未处理异常，且是发生在订单已持久化之后，属于事后崩溃而非入口拒绝。触发条件是调用方（例如 Agent 工具在用户未选中任何商品、或过滤后列表为空时）以 lines=[] 创建订单。
- **[performance/low]** [performance] app/domain/order/order.py:90-91 snapshot() 重复计算 total_amount() 属于可忽略的重复计算（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order.py:90-91`
  - 依据：snapshot() 对 total_amount() 调用了两次（一次取 major units，一次取 currency），每次都会遍历全部订单行并做 Money.add。订单行数量在业务上是个位数，重复一次遍历的开销可忽略，且不会产生错误结果（同一次 snapshot 内 lines 未被修改）。因此这是可以合并取值的写法偏好，不构成需要修复的性能缺陷。
- **[logic/critical]** [logic] app/domain/order/order_line.py:25-26 OrderLine.subtotal 少乘一件，导致订单行金额始终少计一个单位（确认存在缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/order_line.py:25-26`
  - 依据：subtotal 应等于 unit_price × quantity，但实现使用 quantity - 1 作为乘数。任何 quantity >= 1 的订单行都会少计一件；quantity=1 时 subtotal 直接为 0，造成单件订单金额归零，属于核心计价逻辑错误。
- **[concurrency/low]** [concurrency] app/domain/order/ports/order_idempotency_store.py:19-27 OrderIdempotencyStore 的 find/record 分离并不构成竞态缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/order/ports/order_idempotency_store.py:19-27`
  - 依据：初看 find + record 两步存在 TOCTOU：并发的重复消费可能都 find 到 None 然后各建一单。但端口把 record 定义为“登记键→订单号，键已存在返回 False”，实现方可以用主键/唯一约束把 record 做成原子抢占；调用方只要先生成 order_id（例如 uuid4），先 record 抢占、抢占成功再构造并持久化 Order，抢占失败方直接 find 拿回既有订单，就不会产生第二单。顺序由调用方控制，端口契约本身足以表达去重，不能仅凭缺少 claim 方法判定为缺陷。
- **[api_misuse/low]** [api_misuse] app/domain/session/ports/conversation_store.py:31-41 ConversationTurn 文档提到的 turn_index 字段并不存在，但不产生运行时错误（确认并非缺陷）
  - 独立来源 1 个：reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/domain/session/ports/conversation_store.py:31-41`
  - 依据：ConversationTurn 的文档字符串说“turn_index 由存储层按会话自增，写入时可留空”，list_turns 也声明“按 turn_index 升序返回”，但值对象上没有 turn_index 字段。这只是文档措辞与字段集合不一致：存储层自行排序即可，调用方也不会访问不存在的属性（是 dataclass，访问不存在的字段会 AttributeError，但本文件内无任何读取 turn_index 的代码）。不构成可复现的行为缺陷，属于契约描述需要与实现对齐的问题。
- **[boundary/low]** [boundary] app/infrastructure/persistence/in_memory_repositories.py:30-31 find_by_ids 对未知 id 静默跳过不构成缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:30-31`
  - 依据：find_by_ids 用 `if pid in self._products` 过滤掉不存在的商品，返回“命中集合”，与 find_by_id 返回 Optional 的契约一致，调用方本来就要处理缺失商品（如下架）。列表推导按请求顺序返回且不会因单个缺失 id 抛 KeyError，也没有掩盖其他错误类型；这是刻意设计而非越界错误。
- **[concurrency/low]** [concurrency] app/infrastructure/persistence/in_memory_repositories.py:63-72 InMemoryOrderIdempotencyStore 的 find/record 单次调用是原子的，未发现本文件内的竞态缺陷（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/in_memory_repositories.py:63-72`
  - 依据：find 与 record 各自都在 asyncio.Lock 内完成，record 用 `if key in self._keys` 实现原子的“写入或拒绝”，返回值语义正确。虽然 find 与 record 分两次调用时存在 TOCTOU 窗口，但那是调用方（UseCase）的使用方式问题，本文件提供的 record 已足以做原子的 check-and-set；docstring 也明确声明了跨进程不生效、需换 SqlOrderIdempotencyStore 的有意取舍。因此在本文件的实现范围内不构成缺陷。
- **[logic/medium]** [logic] app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30 基线迁移用 Base.metadata.create_all 建表，迁移内容会随 models 漂移，全新库升级到 head 时后续迁移会重复建表失败（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/persistence/sql/migrations/versions/0001_baseline.py:25-30`
  - 依据：upgrade() 没有冻结 0001 时刻的表结构，而是导入当前代码里的 Base 并执行 create_all，因此 0001 实际执行的内容取决于“执行迁移时的 models”。一旦 models 增加了新表或新列（文件注释本身也说明后续要用 alembic revision --autogenerate 生成显式迁移），在空库上执行 `alembic upgrade head` 时，0001 会先把当前全部表建出来，随后 0002 里 autogenerate 生成的 op.create_table / op.add_column 就会因为表/列已存在而报错，迁移链在全新环境直接断掉；同理，0001 也不再能重现历史 schema，`alembic upgrade 0001_baseline` 得到的是最新结构。downgrade() 的 drop_all 也依赖当前 metadata，而非 0001 实际建过的对象集合。
- **[api_misuse/low]** [api_misuse] app/infrastructure/settings.py:56-56 frozen dataclass 中放置 list[str] 字段不影响取值，仅在 hash(Settings) 时才会报错（确认并非缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:56-56`
  - 依据：cors_origins 没有默认值，且 load_settings 每次都新建列表，因此不存在可变默认值被共享的经典陷阱；frozen=True 也禁止外部改写该字段内容（只能整体替换，同样被禁止）。唯一潜在问题是 frozen+eq 会自动生成 __hash__，而 list 不可哈希，一旦把 Settings 放进 set/dict key 或用于 lru_cache 就会 TypeError，但在本文件与给定文件中没有任何 hash(Settings) 的用法，属于尚未触发的隐患而非已确认缺陷。
- **[logic/low]** [logic] app/infrastructure/settings.py:154-154 布尔型环境变量只识别 0/false/False，写成 FALSE/off/no 会被静默当作 true（确认存在缺陷）
  - 独立来源 1 个：reader-r0-1｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`app/infrastructure/settings.py:154-154`
  - 依据：所有布尔开关都用 `os.getenv(name, default) not in ("0", "false", "False")` 解析，白名单只覆盖三种拼写。运维或 .env 里写 SEMANTIC_CACHE_ENABLED=FALSE / HARNESS_ENABLED=off / OUTPUT_GUARD_ENABLED=no（这些都是常见的布尔环境变量写法）时，取值不会命中白名单，结果为 True，也就是“显式关闭”被静默忽略：语义缓存仍然开启（可能返回相似度误判的答案），护栏仍然生效，配置与预期行为相反且没有任何告警。该模式在文件中被复制了 8 次（semantic_cache_enabled、queue_enabled、harness_enabled、output_guard_enabled、drift_detect_enabled、breaker_shared、preference_relevance_enabled、preference_subagent_inject、queue_priority_enabled），问题具有系统性。

## 争议（需裁决）

（无）

## 独立性准入闸门

- 判定：`accept`（放行）
- 原因：独立性达标：有效通道 3.00 ≥ 0.00，归一化 100.00% ≥ 0.00%
- 有效通道：3.00｜归一化 100.0%｜重分区尝试 0 次

## 覆盖缺口归因

- 漏派（系统层）：43｜漏检候选（读者层）：0｜覆盖正常：0｜无法判定：0
- 单 Reader 检出率：无法估计（无重捕，不给伪精度）
- 待补检分组：app/infrastructure/persistence, app/domain/catalog, app, app/domain/order, app/infrastructure, app/domain/shipping, app/application/usecases, app/domain/buyer, app/domain/session, app/domain, app/application

| 证据 | Reader 数 | claim 数 | 归因 | 全员漏检概率 |
| --- | ---: | ---: | --- | ---: |
| `001a0c61fa51` | 1 | 0 | `partition_gap` | — |
| `00e2b01edb94` | 1 | 0 | `partition_gap` | — |
| `0505c2ad4786` | 1 | 0 | `partition_gap` | — |
| `1bd894600f10` | 1 | 1 | `partition_gap` | — |
| `2cc7c376f2fe` | 1 | 2 | `partition_gap` | — |
| `36316f1e43cb` | 1 | 0 | `partition_gap` | — |
| `3f29e8d0f73c` | 1 | 0 | `partition_gap` | — |
| `4662743c2106` | 1 | 0 | `partition_gap` | — |
| `477fac3ae5ae` | 1 | 0 | `partition_gap` | — |
| `48cc2d0a9307` | 1 | 1 | `partition_gap` | — |
| …另有 33 条未列出 | | | | |

> `reader_miss` 是漏检候选，不是缺陷结论；零检出同样可能是证据真的干净。

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `app` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/application/usecases` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/buyer` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/domain/catalog` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/order` | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| `app/domain/session` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/domain/shipping` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `app/infrastructure` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `app/infrastructure/persistence` | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 16%（单元格值 = 独立 Agent 数）
