# Parallax 独立实验

这些实验用于原理验证和故障排查训练，**独立启动、独立数据，不接入平台默认生产拓扑**。

| 实验 | 状态 | 运行方式 |
| --- | --- | --- |
| `labs/jvm` | 已运行验证 | `powershell -File labs/jvm/run.ps1` |
| `labs/concurrency` | 已运行验证 | `powershell -File labs/concurrency/run.ps1` |
| `labs/mysql` | 已运行验证（真实 MySQL 8.4：执行计划/隔离级别/锁与死锁） | `powershell -File labs/mysql/run.ps1` |
| `labs/redis` | 已运行验证 | `powershell -File labs/redis/run.ps1` |
| `labs/spring` | 已运行验证 | `powershell -File labs/spring/run.ps1` |
| `labs/distributed-tx` | 2PC/TCC 模拟已运行验证 | `powershell -File labs/distributed-tx/run.ps1` |
| `labs/seata` | 已运行验证（真实 Seata 2.6.0 + MySQL 8.4，AT/TCC） | `powershell -File labs/seata/run.ps1` |
| `labs/flash-sale` | 已运行验证 | `powershell -File labs/flash-sale/run.ps1` |

固定版本、命令、观察结果和限制写在各自 README。未实际运行的环境或性能数字不会写成已验收。
