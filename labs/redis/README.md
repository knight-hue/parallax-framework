# Redis 实验

使用本机已缓存的 `redis:latest` 启动单节点容器，**不拉取镜像**；脚本在结束时删除容器。

```powershell
powershell -File .\run.ps1
```

实验内容：

| 主题 | 观察 |
| --- | --- |
| 编码 | `int`、`embstr`、`raw`、`listpack`、`intset` |
| 穿透 | 无负缓存 50 次回源；`SET EX` 负缓存后 0 次回源 |
| 击穿 | 8 个并发 Reader，`SET NX PX` 单飞锁只产生 1 次数据库加载 |
| 雪崩 | TTL 抖动，20 个 key 的 TTL 分布展开 |
| 锁过期 | 旧持有者过期后不能用朴素 `DEL` 删除新持有者的锁；Lua 比对删除返回 0 |
| Redis 故障 | 连接失败抛错，调用方必须回源 MySQL，不把缓存当权威 |

单节点实验不能证明集群、网络分区、主从切换或容量；Redisson 的 Java 行为另有网关真实 Redis IT 覆盖。`Resp` 是实验用最小客户端，不是生产客户端。
