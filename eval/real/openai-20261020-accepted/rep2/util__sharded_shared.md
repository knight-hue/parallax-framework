# Parallax 运行报告 `ef9a79695686`

**审查目标**：找出这个代码仓库中真实存在的缺陷，并说明触发条件。

## 结论概览

| 结论 | 条数 | 含义 |
| --- | ---: | --- |
| 高置信 | 0 | 独立支持通道满足运行阈值（事实仍需验证） |
| 待验证 | 2 | 支持不足、相关性超限或尚待验证 |
| 争议 | 0 | 存在极性相反的主张，需外部裁决 |

## 运行审计

- 插件：`code_audit`｜轮次：1｜停止原因：`max_rounds_reached`
- 参与 Reader：3 个（每轮全新身份）
- 账本条目：3
- 独立性画像：有效通道 2.45 / 3，归一化 81.8%，证据重叠 33.3%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：10 个节点 / 14 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 2 | 100% | 12% |

## 高置信结论

（无）

## 待验证（孤证）

- **[resource_leak/low]** [resource_leak] connection.py:61-68 无效超时时间导致已创建的 socket 未显式关闭（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`connection.py:61-68`
  - 依据：socket 创建后，负数或其他非法 timeout 会使 sock.settimeout(timeout) 抛出 ValueError/TypeError，而后续异常处理只捕获 OSError，因此不会执行 sock.close()。在非引用计数垃圾回收环境中，这会使底层 socket 保持打开直到垃圾回收，导致资源延迟释放。
- **[logic/low]** [logic] proxy.py:35-40 HTTPS 代理的转发分支受显式配置约束，不会默认绕过 CONNECT（确认并非缺陷）
  - 独立来源 0 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`proxy.py:35-40`
  - 依据：该分支只有在代理协议为 https、proxy_config 存在且 use_forwarding_for_https 为真时才返回 False。对于 HTTPS 目标，普通 HTTP 代理或未启用转发的 HTTPS 代理都会继续执行末尾的 return True，使用 CONNECT。proxy_config 为 None 时，and 的短路求值也会避免访问其属性。因此，这里没有默认禁用 HTTPS 隧道或空对象属性访问的问题。

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `root` | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |

矩阵填充率 25%（单元格值 = 独立 Agent 数）
