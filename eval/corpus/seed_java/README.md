# Java 缺陷样例（seed_java）

用于验证「发现问题 → 修复 → 隔离回归」这条闭环在 **Java** 上同样成立。不是模拟：缺陷是真实代码，
回归测试也是真实 JUnit 测试，缺陷代码上必须失败，参考修复后必须全绿。

## 结构

| 路径 | 内容 |
| --- | --- |
| `pom.xml`、`src/` | 带 4 个植入缺陷的小型 Java 服务片段（Spring Boot 3.5.16 父 POM，仅用测试依赖） |
| `reference/` | 4 个文件的参考修复，验收脚本会把它们覆盖到临时副本上 |
| `ground_truth.json` | 缺陷清单：文件、行号、类别、标题、标记、判断理由 |
| `run_acceptance.py` | 验收脚本：临时副本上先跑缺陷版本，再打参考修复重跑，落证据 |

## 四个植入缺陷

| ID | 类别 | 位置 | 问题 |
| --- | --- | --- | --- |
| J1 | business_invariant | `Account.transfer` | 先扣款后校验，余额可被扣成负数，收款方已入账 |
| J2 | atomicity | `ReportExporter.export` | 先写目标文件再做内容校验，校验失败会写坏已有报告 |
| J3 | concurrency | `TokenBucket.tryAcquire` | 每次调用重置时间基准，连续的亚秒调用丢掉时间片，桶永不补充 |
| J4 | error_handling | `ConfigLoader.getInt` | 缺键/格式错误静默返回 0，漏配与真实零值不可区分 |

四个缺陷都刻意避开"一眼可见"的问题（硬编码密钥、SQL 注入），考验的是从代码行为推断后果。

## 运行

```powershell
backend/.venv/Scripts/python.exe eval/corpus/seed_java/run_acceptance.py ^
  --maven .toolchain/maven/bin/mvn.cmd --java-home .toolchain/jdk ^
  --out eval/acceptance/20261022/java-defect
```

## 期望结果

- 缺陷版本：10 个测试，**5 个失败**，4 个测试类全部命中，构建失败；
- 覆盖参考修复后：10 个测试，**0 失败**，构建成功；
- 证据：`eval/acceptance/20261022/java-defect/java-defect-sample.json`（含两轮 `maven` 日志）。

## 边界

- 这是可重复的**回归验证**，不是模型能力评测：参考修复由人给出，脚本只证明测试能区分好坏代码；
- 缺陷数量与类别是人工设计的，不代表真实仓库的缺陷分布；
- 只覆盖单模块、单进程；没有引入构建工具差异或跨模块依赖问题。
