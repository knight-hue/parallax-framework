# JVM 实验

固定使用项目自带 JDK 21（`../../.toolchain/jdk`），不下载依赖。

```powershell
powershell -File .\run.ps1
```

| 实验 | 观察点 |
|---|---|
| `JmmVisibilityLab` | 普通布尔读不保证观察到另一线程的写入；`volatile` 提供 happens-before |
| `VolatileCounterRace` | `volatile++` 是读-改-写复合操作，会丢失更新；它不保证原子性 |
| `SafePublicationLab` | `volatile` 引用 + `final` 字段的安全发布 |
| `ClassLoaderLab` | 两个隔离加载器加载同名类得到不同 `Class` 对象；双亲委派入口 |
| `GcLab` | GC 收集器、内存占用；配合 `-Xlog:gc*` 观察 Young/Mixed/Full |
| `OomLab` | `-Xmx32m` 下受控 Heap OOM；捕获后释放引用，不用于生产实例 |

## 源码阅读入口

JDK 21 的 AQS、线程池、GC 实现位于 JDK 源码归档 `lib/src.zip`；本实验只验证可观察行为，不把运行输出当作源码级证明。`ClassLoaderLab` 使用 `URLClassLoader` 和 JDK Compiler API，展示的是现代 JDK 的加载器命名空间，不是 JDK 8 的 ExtClassLoader 图。
