# 用户兼容模型的小子集验收

2026-10-20，gpt-6.1-sol，urllib3/util 三文件，5 臂 × 3 次重复，15 次有效、Reader 失败 0。

- acceptance.json：模型、输入哈希、种子与预算边界。
- implementation.zip：运行开始时的 Parallax 源码，便于复核；不含密钥。
- rep1..rep3：原始 metrics、报告和完整 Claim 清单。
- analysis.json：离线补充实际分配 Reader 分母及反方观察计数；原 metrics 不改写。原 writer 遗漏的零 Claim 文件已补为 [] 并记录清单。
- variance.md：运行时生成的历史口径，仅计产出者的 K*/N 不能当作全部 Reader 的效率或正确率。

没有人工 ground truth，不宣称准确率、完整仓库审查或统计稳定收益。原报告早于最终反方支持元数据修复；保留原件，不用错误字段做收益结论。具体对照公平性、模型别名边界和失败尝试见仓库 ACCEPTANCE.md。
