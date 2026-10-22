# 分布式事务实验

独立运行，不需要平台服务；使用多个独立 SQLite 数据库模拟两个资源分支和一个协调器。

```powershell
powershell -File .\run.ps1
```

## 2PC 模拟

- `try_reserve` 在两个资源上持久化 TRY/预占记录（预占库存）；
- 协调器写入 `COMMITTED`/`ABORTED` 决策；
- `recover` 在协调器崩溃后：
  - `PREPARING` 无决策 → 回滚两个分支；
  - `COMMITTED` 已落盘 → 幂等提交两个分支；
- 覆盖正常提交、第二个资源准备失败、决策前崩溃、决策后崩溃和重复提交。

这是**协议级模拟**：SQLite 没有跨库 XA prepared transaction 和全局锁，不能当作真实 XA 的锁/阻塞/恢复证明。

## TCC 模拟

- `try_reserve` 预占库存并写 TRY；
- `confirm` 只从 TRY → COMMITTED；
- `cancel` 只从 TRY → CANCELED，重复 cancel 幂等；
- 空回滚（没有 TRY 直接 cancel）不产生库存变化；
- 悬挂的 TRY 可由超时任务 cancel，释放预占。

## Seata

本目录只是**协议级模拟**，不能当作 Seata 验收。

真实的 Seata AT/TCC 实验在 `labs/seata`：对真实 Seata 2.6.0 服务端（`127.0.0.1:8091`）和真实 MySQL 8.4 运行，覆盖全局提交、AT 回滚还原库存、TCC confirm/cancel 与二阶段幂等。
