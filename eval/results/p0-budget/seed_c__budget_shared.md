# Parallax 运行报告 `4e7863205788`

**审查目标**：审查这个代码仓库，找出其中真实存在的缺陷。只报告你能引用具体代码作为依据的问题。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 16 | >= 2 个独立 Agent 交叉验证 |
| 待验证 | 0 | 单一来源孤证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：6 个（每轮全新身份）
- 账本条目：96

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 6 | 16 | 17% | 4% |

## 高置信结论

- **[boundary/medium]** [boundary] analytics/window_alpha.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:43-47`
  - 依据：index = int(round(ratio * (len(ordered) - 1)))。当 ratio > 1 时 index 会超过 len-1，ordered[index] 抛 IndexError；当 ratio < 0 时 index 为负，Python 负索引会静默返回错误元素（如 ratio=-0.1 返回最大值而非报错），造成难以察觉的错误结果。ratio 未做任何范围校验。
- **[logic/high]** [logic] analytics/window_alpha.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_alpha.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此当样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，结果随样本增多而单调膨胀，完全错误。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_beta.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:43-47`
  - 依据：ratio 未做 [0,1] 范围校验。当 ratio > 1 时，index = int(round(ratio*(n-1))) 会超出 ordered 的最大下标，ordered[index] 抛 IndexError；当 ratio < 0 时，index 为负，Python 负索引会静默返回从末尾数的元素（例如 ratio=-0.1 返回最大值），得到语义上错误的结果而不报错。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_beta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_beta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此当样本数超过 size 后，_total 会持续累积所有历史值，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度，分子却是全部历史之和，结果必然偏大。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_delta.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:43-47`
  - 依据：ratio 未做 [0,1] 范围校验。ratio > 1 时 index 超出 ordered 上界，ordered[index] 抛 IndexError；ratio < 0 时 index 为负，Python 负索引会静默返回错误的分位值而不报错，属于静默错误。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_delta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_delta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此一旦窗口满且继续 add，_total 会持续增长，而 len(self._values) 始终不超过 size，mean() 返回 _total/len 会远大于真实窗口均值。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_epsilon.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:43-47`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 范围校验。当 ratio > 1 时 index 超出列表上界，ordered[index] 抛 IndexError；当 ratio < 0 时 index 为负，Python 负索引会静默返回错误元素而不报错，产生难以察觉的错误结果。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_epsilon.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_epsilon.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此一旦窗口满且继续 add，_total 会持续增长，而 len(self._values) 始终不超过 size，mean() 返回 _total/len 会远大于真实窗口均值。触发条件：add 次数超过 size。
- **[boundary/medium]** [boundary] analytics/window_eta.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:43-47`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 校验。ratio>1 时 index 超出列表上界，ordered[index] 抛 IndexError；ratio<0 时 index 为负，Python 负索引会静默返回错误的分位值而非报错。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_eta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_eta.py:22-25`
  - 依据：与 window_alpha 相同：deque(maxlen=size) 自动淘汰最旧样本，但 _total 只增不减，mean() 分子为全部历史之和、分母为当前窗口长度，样本数超过 size 后均值错误。
- **[boundary/medium]** [boundary] analytics/window_gamma.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:43-47`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 校验。ratio>1 时 index 超出列表上界，ordered[index] 抛 IndexError；ratio<0 时 index 为负，Python 负索引会静默返回错误的分位值而非报错。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_gamma.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_gamma.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只累加不扣减被淘汰的值。当样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度，分子却是全部历史之和，结果随添加次数单调增大，完全错误。触发条件：添加超过 size 个样本后调用 mean()。
- **[boundary/medium]** [boundary] analytics/window_theta.py:43-47 percentile 未校验 ratio 范围，越界 ratio 返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:43-47`
  - 依据：index 由 ratio 直接计算，未做 [0,1] 范围校验。ratio > 1 导致 ordered[index] 抛 IndexError；ratio < 0 时负索引静默返回错误元素。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_theta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_theta.py:22-25`
  - 依据：与 window_beta.py 相同：deque(maxlen=size) 在 append 时自动淘汰最旧样本，但 _total 只累加不扣减，mean() 用 _total / len(self._values) 计算，分子包含已被淘汰的历史样本，分母仅为当前窗口长度，样本数超过 size 后均值错误。触发条件：add 次数 > size。
- **[boundary/medium]** [boundary] analytics/window_zeta.py:43-47 percentile 未校验 ratio 范围，越界 ratio 会返回错误值或抛 IndexError（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:43-47`
  - 依据：index = int(round(ratio * (len(ordered) - 1))) 未对 ratio 做 [0,1] 校验。ratio>1 时 index 超出列表上界，ordered[index] 抛 IndexError；ratio<0 时 index 为负，Python 负索引会静默返回错误的分位值而非报错。触发条件：调用方传入越界 ratio。
- **[logic/high]** [logic] analytics/window_zeta.py:22-25 滑动窗口淘汰旧样本时 _total 未同步扣减，导致 mean() 计算错误（确认存在缺陷）
  - 独立来源 6 个：reader-r0-0, reader-r0-1, reader-r0-2, reader-r0-3, reader-r0-4, reader-r0-5｜置信度 0.5
  - 源：`analytics/window_zeta.py:22-25`
  - 依据：deque 设置了 maxlen=size，append 超出容量时会自动淘汰最旧样本，但 _total 只做累加、从不扣减被淘汰的值。因此当样本数超过 size 后，_total 会持续累积所有历史样本之和，而 mean() 用 _total / len(self._values) 计算，分母是当前窗口长度（<=size），分子却是全部历史之和，结果随样本增多而单调膨胀，完全错误。触发条件：add 次数超过 size。

## 待验证（孤证）

（无）

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytics` | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| `persistence` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `resources` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `scheduling` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wire` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wiring` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

矩阵填充率 4%（单元格值 = 独立 Agent 数）
