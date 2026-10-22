# 秒杀实验

独立启动，使用 SQLite 作为本地数据库、单节点 Redis 作为预扣层；不接入平台生产拓扑。

```powershell
powershell -File .\run.ps1
```

## 基线：SQLite 条件扣减

`BEGIN IMMEDIATE` + `UPDATE ... WHERE quantity>0` + 唯一订单表。200 个线程争抢 100 件库存，结果为成功 100、库存 0、订单 100。

## Redis Lua 预扣

Lua 原子执行：

1. `SET user-marker NX EX 60`；已存在返回重复；
2. 读取库存；小于等于 0 返回售罄并删除 marker；
3. `DECR` 并返回成功。

结果：首轮 100 个用户成功；同一批用户重试 100 次全部重复；新用户 100 次全部售罄；库存 0。随后把成功用户异步确认到 SQLite 订单表，订单 100，Redis 库存与订单对账一致。

## 边界

- 这是单节点 Redis + 本地 SQLite 的可复现实验，不是生产秒杀系统；
- 没有 MQ 投递、消费者重试、Redis 主从切换、网络分区、热点 key 容量或 MySQL InnoDB 压测；
- Redis 成功只表示预受理，最终事实仍应以持久订单/对账为准；
- `Resp` 是最小实验客户端，不是生产 Redis 客户端。
