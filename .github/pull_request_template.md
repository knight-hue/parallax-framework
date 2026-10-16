<!-- 感谢贡献。请把下面几项填完整——评审最关心的是「怎么验证的」。 -->

## 改了什么

<!-- 一句话概括。涉及机制行为的改动，请说明影响哪一条机制。 -->

## 为什么这么改

<!-- 动机与取舍。如果有别的方案，说明为什么不选。 -->

## 怎么验证的

- [ ] `pytest` 全绿
- [ ] `ruff check .` 与 `ruff format --check .` 无告警
- [ ] 新增/修改的行为有对应测试
- [ ] 修的是 bug 时，先写出了能复现它的测试

<!-- 涉及机制行为时，请附对照实验的前后数字：
     python -m parallax.cli experiment --tasks <id> --out eval/results/<name>
-->

## 复选框

- [ ] 未提交任何密钥、凭据或私有代码
- [ ] 未破坏盲读隔离（`ReaderPlugin.build_messages()` 只传本 Reader 的分片）
- [ ] 涉及对外行为时已更新文档（README / docs / CHANGELOG）
- [ ] 新增的随机性或阈值是可控且已记录在 run manifest 中的
