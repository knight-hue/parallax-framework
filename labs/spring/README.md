# Spring 实验

独立 Maven 项目，固定 Spring Boot 3.5.16 / JDK 21；只使用本机 `.m2` 缓存，离线运行。

```powershell
powershell -File .\run.ps1
```

实验：

| 主题 | 位置 | 观察 |
|---|---|---|
| 自动配置 | `GreetingAutoConfiguration` + `AutoConfiguration.imports` | 无用户 Bean 时生效；用户 Bean 覆盖默认实现 |
| Bean 生命周期 | `LifecycleBean` + `RecordingPostProcessor` | `beforeInitialization → @PostConstruct → afterPropertiesSet → afterInitialization → destroy` |
| AOP 代理/自调用 | `ProxyFactory` + `Target` | 通过代理调用 outer 被拦截；`this.inner()` 绕过代理 |

## 边界

- 这是最小 Spring Boot 上下文，不是完整平台启动；
- `ProxyFactory` 展示代理链和自调用边界，不替代阅读 Spring AOP 源码；
- 未测试真实事务、传播、异步线程或数据库代理；这些由网关业务测试和 MySQL 实验覆盖。
