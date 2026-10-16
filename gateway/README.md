# Parallax 薄网关

**一句话**：把 Python 编排服务挡在身后，只对外暴露一个受控入口。

## 为什么需要它

`SECURITY.md` 里写了两条必须由部署方处理的风险：HTTP 服务本身**不含鉴权**，
`POST /api/v1/audits` **接受任意服务端路径**。这两条如果直接暴露，等于把
"用别人的机器读任意文件"这个能力送出去。

网关的职责就是把它们收口：

| 能力 | 实现 | 解决什么 |
|---|---|---|
| 统一入口 | 白名单转发（`ProxyController`） | 不做白名单的"/** 全转发"会把网关变成开放代理，可用来打内网其他服务 |
| 鉴权 | 共享密钥 → JWT（`AuthController` / `JwtAuthFilter`） | 上游不认识"谁在调用" |
| 限流 | Bucket4j 令牌桶，按 IP + 主体分桶 | `POST /audits` 会真实消耗模型额度，被刷的代价和读接口不是一个量级 |
| 熔断 | Resilience4j | 上游卡住时快速失败，而不是把网关的线程池一起拖死 |
| 链路追踪 | `X-Trace-Id` 贯穿 Java → Python | 出问题时能在两侧日志里对上同一次请求 |

## 三条踩过的坑（都写进了代码注释）

1. **必须强制 HTTP/1.1。** JDK 的 `HttpClient` 对明文 HTTP 会尝试 h2c 升级，
   而 uvicorn 不监听 upgrade，连接会被直接断开，报错形同"上游崩了"。
2. **重试必须区分幂等性。** 重试 `POST /audits` 会创建两个运行、烧两份额度，
   所以只有读接口走带 `@Retry` 的方法。
3. **异步超时必须放宽。** 一次审查的 SSE 流持续几分钟，而 Tomcat 异步请求
   默认 30 秒超时——不改配置的话前端会在第 30 秒莫名断流。

## 端点

| 网关端点 | 说明 |
|---|---|
| `GET /health`、`GET /ready` | 转发上游探针 |
| `GET /api/v1/meta` | 转发上游能力与默认配置 |
| `POST /api/v1/audits` | 提交审查（限流更严、**不重试**） |
| `GET /api/v1/audits[/{id}[/events\|/result\|/report]]` | 查询、SSE 进度流、结果与报告 |
| `POST /api/v1/auth/token` | 用共享密钥换 JWT |
| `GET /actuator/health` | 网关自身探针 |

SSE 是**原样透传**的：不缓冲、不聚合，并透传 `Last-Event-ID`，
所以前端断线重连仍能补发缺口事件。

## 运行

### 本地

```bash
# 1) 先起上游
cd ../backend && python -m parallax.service.app

# 2) 再起网关
cd ../gateway && mvn spring-boot:run
```

### 鉴权模式

默认 `require-auth=false`，本地与内网演示开箱即用。**公网暴露前必须打开**：

```bash
export PARALLAX_GATEWAY_REQUIRE_AUTH=true
export PARALLAX_JWT_SECRET=$(openssl rand -hex 32)      # >= 32 字节
export PARALLAX_GATEWAY_ADMIN_SECRET=$(openssl rand -hex 16)
mvn spring-boot:run

# 换令牌
curl -X POST localhost:8080/api/v1/auth/token \
     -H 'Content-Type: application/json' \
     -d '{"secret":"<ADMIN_SECRET>"}'

# 带令牌调用
curl -H "Authorization: Bearer <token>" localhost:8080/api/v1/audits
```

`PARALLAX_JWT_SECRET` 不配置时网关**不会**随机生成密钥——那会让"重启后所有令牌
失效"变成难以复现的线上问题；它选择显式不可用。

### 前端指向网关

前端默认直连 `http://localhost:8000`。改指向网关时用构建期变量：

```bash
NEXT_PUBLIC_PARALLAX_API=http://localhost:8080 npm run build
```

## 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `PARALLAX_GATEWAY_PORT` | `8080` | 网关端口 |
| `PARALLAX_UPSTREAM_URL` | `http://127.0.0.1:8000` | 上游编排服务地址 |
| `PARALLAX_GATEWAY_REQUIRE_AUTH` | `false` | 是否要求 JWT |
| `PARALLAX_JWT_SECRET` | 空 | HS256 密钥，>= 32 字节 |
| `PARALLAX_GATEWAY_ADMIN_SECRET` | 空 | 换取令牌的共享密钥 |
| `PARALLAX_RATELIMIT_ENABLED` | `true` | 限流开关 |
| `PARALLAX_RATELIMIT_EXPENSIVE_CAPACITY` | `10` | 提交审查的桶容量（次/窗口） |
| `PARALLAX_CONNECT_TIMEOUT_MS` / `PARALLAX_READ_TIMEOUT_MS` | `5000` / `30000` | 连接与响应头超时 |

## 测试

```bat
mvn test
```

10 项测试，其中 `ProxyIntegrationTest` 会**起一个真实的 HTTP 服务桩**当上游。
不 mock HTTP 的原因：这条链路上会坏的地方几乎都在 HTTP 层——协议协商、分块传输、
请求头透传、异步超时，把它们 mock 掉等于把最可能坏的那层换成"永不坏的实现"。

> 本机没有全局 Maven / JDK 21 时，用仓内便携工具链：
> ```bat
> set JAVA_HOME=%CD%\..\.toolchain\jdk
> set PATH=%JAVA_HOME%\bin;%CD%\..\.toolchain\maven\bin;%PATH%
> mvn -B test
> ```
> 详见 [../../说明材料/本地构建.md](../../说明材料/本地构建.md)。
