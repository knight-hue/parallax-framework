# Seata AT / TCC 实验

对**真实 Seata 服务端**和**真实 MySQL** 运行，不是协议模拟。同一套代码里跑通 AT 与 TCC 两条路径。

## 前置条件

| 组件 | 版本 | 地址 |
| --- | --- | --- |
| Seata Server | 2.6.0，file 模式 | `127.0.0.1:8091` |
| MySQL | 8.4 | `127.0.0.1:3307`，库 `seata_lab` |
| JDK | 21 | — |

数据库表必须**先于应用启动**创建：Seata 在代理数据源时会校验 `undo_log` 是否存在，应用内初始化来不及。

```powershell
$env:PARALLAX_MYSQL_CLIENT = 'E:\tools\mysql-8.4.0-winx64\bin\mysql.exe'   # 可选，默认取 PATH 里的 mysql
powershell -File .\run.ps1
```

`run.ps1` 会先执行 `sql/schema.sql`，再跑 `mvn test`。

## 覆盖的行为

### AT 模式（`SeataAtLabTest`）

- 全局提交：下单 + 扣库存两笔本地事务一起生效；
- 扣库存之后抛异常：`undo_log` 把库存回滚回原值，订单行也被撤销；
- 回滚路径自己清理本次分支的 `undo_log` 行。

AT 的关键点在于业务代码只写普通 SQL，回滚镜像由 Seata 代理数据源生成。

### TCC 模式（`SeataTccLabTest`）

- try 冻结库存并写 `TRY` 预留记录，全局提交后 confirm 消费冻结量；
- try 之后抛异常：cancel 把冻结量还回可用库存，预留记录变 `CANCELLED`；
- 二阶段幂等由 `TRY -> CONFIRMED/CANCELLED` 的条件更新保证，重复回调不会重复扣减。

TCC 的补偿语义由业务自己写，Seata 只负责驱动 confirm/cancel。

## 可配置项

| 环境变量 | 默认值 |
| --- | --- |
| `PARALLAX_SEATA_DB_URL` | `jdbc:mysql://127.0.0.1:3307/seata_lab?...` |
| `PARALLAX_SEATA_DB_USER` | `parallax` |
| `PARALLAX_SEATA_DB_PASSWORD` | `parallax` |
| `PARALLAX_SEATA_SERVER` | `127.0.0.1:8091` |
| `PARALLAX_MYSQL_CLIENT` | `mysql` |

## 已知限制

- 只有一个数据源，未验证跨库（多 RM）分支；
- 未做 TC 宕机、分支重试、悬挂事务等故障注入；
- 观察到提交后 `undo_log` 行在默认配置下仍会留存（`log_status=0`），本次未把"自动清理"纳入断言，生产需要单独监控 `undo_log` 增长；
- TCC 三阶段的业务资源（库存冻结）用条件更新做幂等，没有引入 Seata 的 TCC fence 表。
