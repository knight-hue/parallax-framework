# 并发实验

固定使用项目自带 JDK 21。

```powershell
powershell -File .\run.ps1
```

| 实验 | 观察点 |
|---|---|
| `AqsLockLab` | `ReentrantLock` 重入、公平模式、`Condition.await/signal`、带超时 `tryLock` |
| `ThreadPoolRejectionLab` | 2 个核心线程 + 容量 2 的队列，第 5 个任务起触发 `AbortPolicy` |
| `InterruptCancelLab` | `Future.cancel(true)` 向阻塞任务传播中断，任务自行退出 |
| `BackpressureLab` | `CallerRunsPolicy` 在提交线程执行任务，形成显式背压 |

## 源码阅读入口

JDK 21 的 AQS 实现位于 `java.util.concurrent.locks.AbstractQueuedSynchronizer`，线程池位于 `ThreadPoolExecutor`。建议沿以下路径阅读：

- `ReentrantLock.lock()` → `Sync.lock()` → `AQS.acquire(1)` → `tryAcquire` / `addWaiter` / `acquireQueued`；
- `Condition.await()` → `AQS.ConditionObject` 转移；
- `ThreadPoolExecutor.execute()` → 核心线程、入队、扩容、拒绝策略；
- `FutureTask.cancel(true)` → `Thread.interrupt()`。

本实验验证行为，不把输出当作源码级证明；`SubprocessReproductionExecutor` 和这些实验都不是敌对代码安全沙箱。
