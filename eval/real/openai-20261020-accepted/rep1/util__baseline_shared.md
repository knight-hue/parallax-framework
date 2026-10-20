# Parallax 运行报告 `1c30a782f695`

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
- 独立性画像：有效通道 1.00 / 3，归一化 33.3%，证据重叠 100.0%，输出隔离 `violated`
- 相关性预算：`超限，已禁止自动高置信`｜证据重叠上限 100.0%
- 证据血缘：10 个节点 / 17 条边
- 去共同上游后的通道：3；共同推理上游：0；未解析血缘：0

| 轮次 | Reader 数 | 本轮新主体 | 证据覆盖 | 矩阵填充 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3 | 2 | 100% | 12% |

## 高置信结论

（无）

## 待验证（孤证）

- **[resource_leak/medium]** [resource_leak] connection.py:55-64 非 OSError 的 socket 配置异常会导致已创建套接字未显式关闭（确认存在缺陷）
  - 独立来源 1 个：reader-r0-0｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`connection.py:55-64`
  - 依据：套接字在 try 块中创建，但异常处理只捕获 OSError。传入负 timeout 时，socket.settimeout(timeout) 会抛出 ValueError，该异常会直接向上传播而不会执行 sock.close()。在支持延迟垃圾回收的 Python 实现中，或异常 traceback 持有当前栈帧时，已创建的套接字可能长期占用文件描述符。类似的非 OSError 参数错误也可能触发同样问题。
- **[resource_leak/medium]** [resource_leak] connection.py:60-63 非 OSError 的 socket 配置异常会泄漏已创建的套接字（确认存在缺陷）
  - 独立来源 2 个：reader-r0-1, reader-r0-2｜置信度 0.5
  - 反证状态：`unverified`
  - 源：`connection.py:60-63`
  - 依据：套接字创建后，_set_socket_options、settimeout 或 bind 可能抛出非 OSError 异常；当前 except 只捕获 OSError，因此异常直接向上抛出且不会执行 sock.close()，导致已创建的套接字泄漏。

## 争议（需裁决）

（无）

## 覆盖率矩阵

| 维度 \ 类型 | logic | concurrency | boundary | error_handling | resource_leak | security | performance | api_misuse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `root` | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

矩阵填充率 12%（单元格值 = 独立 Agent 数）
