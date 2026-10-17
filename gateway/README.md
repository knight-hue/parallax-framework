# Parallax 网关（平台层）

**一句话**：把 Python 编排服务挡在身后，管住"谁在用、用了多少、跑过什么"。

## 为什么需要它

`SECURITY.md` 里写了两条必须由部署方处理的风险：HTTP 服务本身**不含鉴权**，
`POST /api/v1/audits` **接受任意服务端路径**。这两条如果直接暴露，等于把
"用别人的机器读任意文件"这个能力送出去。

网关的职责就是把它们收口：

| 能力 | 实现 | 解决什么 |
|---|---|---|
| 统一入口 | 白名单转发（`ProxyController`） | 不做白名单的"/** 全转发"会把网关变成开放代理，可用来打内网其他服务 |
| 身份 | API Key（`X-API-Key`）+ JWT（运营人员） | 上游不认识"谁在调用"；配额也需要一个归属主体 |
| **配额** | 三重额度：日运行数 / 日 token / 月 token | 平台的成本必须可预测；额度按**提交**计数，只统计完成的话用户能在第一次完成前并发提交上千次 |
| **运行记录** | `audit_run` + `audit_event` | "上周那次审查花了多少"必须能查到 |
| **限流** | Bucket4j；配了 Redis 则多实例共享配额，**Redis 不可用时自动降级** | 限流是保护手段，不该成为单点 |
| 熔断 | Resilience4j | 上游卡住时快速失败，而不是把网关的线程池一起拖死 |
| 可观测性 | Micrometer 业务指标 + `%X{traceId}` 日志 | "一直在降级"必须能被发现，否则配额会悄悄退化成单实例口径 |
| 链路追踪 | `X-Trace-Id` 贯穿 Java → Python → 完成回调 | 出问题时能在两侧日志里对上同一次请求 |

## 约定：无编排逻辑，可有平台能力

原约定是"网关不依赖数据库，以免有人把业务逻辑写进来"。
这条理由依然成立，但它把**平台能力**一起挡在了门外——身份、配额、
记账、运行记录本来就是网关的本职。

修订后的判据只有一条：

> **新增的每个依赖都必须能回答"它服务于身份 / 配额 / 持久化 / 可观测性中的哪一项"。**
> 答不上来就不该加。

必须留在 Python 侧的东西：证据怎么装配（分区、盲读、账本、聚合、补检）。
网关**一行都不碰**它。

## 五条踩过的坑（都写进了代码注释）

1. **必须强制 HTTP/1.1。** JDK 的 `HttpClient` 对明文 HTTP 会尝试 h2c 升级，
   而 uvicorn 不监听 upgrade，连接会被直接断开，报错形同"上游崩了"。
2. **重试必须区分幂等性。** 重试 `POST /audits` 会创建两个运行、烧两份额度，
   所以只有读接口走带 `@Retry` 的方法。
3. **异步超时必须放宽。** 一次审查的 SSE 流持续几分钟，而 Tomcat 异步请求
   默认 30 秒超时——不改配置的话前端会在第 30 秒莫名断流。
4. **`Filter` 类型的 Bean 会被 servlet 容器再注册一次。** `ApiKeyAuthFilter` 与
   `QuotaFilter` 的语义要求恰好只运行一次、且必须位于 Security 链内；
   不加 `FilterRegistrationBean.setEnabled(false)` 的话，`QuotaFilter` 会跑在
   Security 链之外，取不到认证主体。
5. **`@ConditionalOnProperty` 把空字符串视为"匹配"。** `redis-url: ${X:}` 会让属性
   存在但为空，于是 `RedisClient.create("")` 抛 `URI must not be empty`，
   **没配 Redis 的部署全都起不来**。改用显式 `Condition` 判断非空，并加测试守住。

## 端点

| 网关端点 | 说明 |
|---|---|
| `GET /health`、`GET /ready` | 转发上游探针 |
| `GET /api/v1/meta` | 转发上游能力与默认配置 |
| `POST /api/v1/audits` | 提交审查（限流更严、**不重试**、**转发前校验配额**） |
| `GET /api/v1/audits[/{id}[/events\|/result\|/report]]` | 查询、SSE 进度流、结果与报告 |
| `POST /api/v1/auth/token` | 用共享密钥换 JWT（运营人员） |
| `POST\|GET /api/v1/credentials`、`DELETE /api/v1/credentials/{id}` | 签发 / 查看 / 吊销 API Key（ADMIN） |
| `GET /api/v1/usage/me` | 当前凭据的今日与本月用量 |
| `GET /api/v1/usage` | 全部凭据的用量汇总（ADMIN） |
| `GET /api/v1/runs[/{runId}]` | 运行历史（分页 + 过滤）与运行详情（含事件留痕） |
| `POST /api/v1/internal/runs/{runId}/complete` | 编排服务的完成回调（`X-Internal-Token`） |
| `GET /actuator/health`、`GET /actuator/prometheus` | 网关自身探针与指标 |
| `GET /swagger-ui.html` | 自动生成的接口文档 |

SSE 是**原样透传**的：不缓冲、不聚合，并透传 `Last-Event-ID`，
所以前端断线重连仍能补发缺口事件。
唯一的例外是 `POST /api/v1/audits`——它要有界地读一次响应体以取出 `run_id`
（该端点响应只有几十字节，且不涉及 SSE）。

## 平台能力怎么用

```bash
# 1) 换运营令牌
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/token \
        -H 'Content-Type: application/json' \
        -d "{\"secret\":\"$PARALLAX_GATEWAY_ADMIN_SECRET\"}" | jq -r .accessToken)

# 2) 建一把 API Key（明文只在这里返回一次）
curl -s -X POST localhost:8080/api/v1/credentials \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"name":"ci-bot","quotaPolicy":"default"}'
# → {"id":"...","keyPrefix":"plx_AbCdEfGh…","apiKey":"plx_...","quota":{...}}

# 3) 用这把 key 提交审查
curl -X POST localhost:8080/api/v1/audits \
     -H "X-API-Key: plx_..." -H 'Content-Type: application/json' \
     -d '{"repo_path":"/workspace/myrepo"}'

# 4) 看自己的用量
curl -H "X-API-Key: plx_..." localhost:8080/api/v1/usage/me

# 5) 吊销（立即生效，不等令牌自然过期）
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
     localhost:8080/api/v1/credentials/<id>
```

**没有"再查一次 key"的端点**，因为服务端根本不存明文——
需要再取一次的正确做法是吊销旧的、签发新的。

## 运行

### 容器（推荐，一并起 PostgreSQL 与 Redis）

```bash
docker compose --env-file ../backend/.env --profile gateway up -d
```

### 本地

```bash
# 1) 备好 PostgreSQL（Flyway 会在启动时自动建表）
# 2) 起上游
cd ../backend && python -m parallax.service.app
# 3) 起网关
cd ../gateway && mvn spring-boot:run
```

### 公网暴露前

默认 `require-auth=false`，本地与内网演示开箱即用。**公网暴露前必须打开**：

```bash
export PARALLAX_GATEWAY_REQUIRE_AUTH=true
export PARALLAX_IDENTITY_ENABLED=true
export PARALLAX_JWT_SECRET=$(openssl rand -hex 32)      # >= 32 字节
export PARALLAX_GATEWAY_ADMIN_SECRET=$(openssl rand -hex 16)
mvn spring-boot:run
```

`PARALLAX_JWT_SECRET` 不配置时网关**不会**随机生成密钥——那会让"重启后所有令牌
失效"变成难以复现的线上问题；它选择显式不可用。

### 让编排服务回传用量

网关的配额与报表依赖编排服务的完成回调：

```bash
# 编排服务侧
export PARALLAX_CALLBACK_URL=http://gateway:8080
export PARALLAX_CALLBACK_TOKEN=$PARALLAX_GATEWAY_INTERNAL_TOKEN
```

**不配也不会出错**——回调默认关闭，只是网关账本会停在 0。

## 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `PARALLAX_GATEWAY_PORT` | `8080` | 网关端口 |
| `PARALLAX_UPSTREAM_URL` | `http://127.0.0.1:8000` | 上游编排服务地址 |
| `PARALLAX_DB_URL` / `_USER` / `_PASSWORD` | `jdbc:postgresql://127.0.0.1:5432/parallax` | 平台数据存储 |
| `PARALLAX_IDENTITY_ENABLED` | `false` | 是否启用身份与配额（生产必须打开） |
| `PARALLAX_GATEWAY_INTERNAL_TOKEN` | 空 | 与上游共享的内部令牌（回调校验用） |
| `PARALLAX_GATEWAY_REQUIRE_AUTH` | `false` | 是否要求 JWT |
| `PARALLAX_JWT_SECRET` | 空 | HS256 密钥，>= 32 字节 |
| `PARALLAX_GATEWAY_ADMIN_SECRET` | 空 | 换取令牌、签发凭据的共享密钥 |
| `PARALLAX_RATELIMIT_ENABLED` | `true` | 限流开关 |
| `PARALLAX_RATELIMIT_REDIS_URL` | 空 | 留空 = 单实例内存桶；配了则多实例共享配额 |
| `PARALLAX_RATELIMIT_REDIS_TIMEOUT_MS` | `250` | Redis 命令超时（限流在关键路径上，必须短） |
| `PARALLAX_RATELIMIT_DEGRADED_COOLDOWN_SECONDS` | `30` | 降级后多久才重新尝试 Redis |
| `PARALLAX_RATELIMIT_EXPENSIVE_CAPACITY` | `10` | 提交审查的桶容量（次/窗口） |
| `PARALLAX_CONNECT_TIMEOUT_MS` / `PARALLAX_READ_TIMEOUT_MS` | `5000` / `30000` | 连接与响应头超时 |

## 测试

```bat
mvn test          :: 43 项：单元 + 集成（H2 + 内存桶，不需要 Docker）
mvn -Pit verify   :: 另加 Testcontainers 集成（真实 PostgreSQL + Redis，需要 Docker）
python tools/mutation_audit.py :: Java 关键策略变异门禁（临时副本，不修改工作树）
```

`ProxyIntegrationTest` 会**起一个真实的 HTTP 服务桩**当上游。
不 mock HTTP 的原因：这条链路上会坏的地方几乎都在 HTTP 层——协议协商、分块传输、
请求头透传、异步超时，把它们 mock 掉等于把最可能坏的那层换成"永不坏的实现"。

### 默认档为什么用 H2，以及这样做的代价

贡献者机器上不一定有 Docker（本项目的开发机就没有）。如果整套测试都要求真实 PG，
本地就只能跑单元测试，集成测试会长期处于"只有 CI 知道"的状态。

代价必须说清楚：**H2 不能替代真实 PostgreSQL 做验证**。它验证的是
"迁移脚本能被解析、JPA 映射与表结构一致、业务逻辑正确"，
而 PG 特有的行为（类型推导、`coalesce(sum(bigint))` 返回 numeric、时区往返、
并发与隔离级别）一概没测到。所以另有 `PostgresPersistenceIT` 与 `RedisRateLimitIT`
跑真库，CI 上必跑（独立的 `gateway-it` 任务）。

两个 IT 都用 `disabledWithoutDocker = true`，本地无 Docker 时自动跳过——
不让基础设施成为本地开发的阻塞项。

> 本机没有全局 Maven / JDK 21 时，用仓内便携工具链：
> ```bat
> set JAVA_HOME=%CD%\..\.toolchain\jdk
> set PATH=%JAVA_HOME%\bin;%CD%\..\.toolchain\maven\bin;%PATH%
> mvn -B test
> ```
> 详见 [../../说明材料/本地构建.md](../../说明材料/本地构建.md)。
