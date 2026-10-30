# E4 人工核实（部分范围）

> **范围声明**：本次只对 **S2 切片的分散臂**做逐条人工核实（10 条植入缺陷）。
> 其余切片未做，原因与影响见文末。

## 为什么要人工核实

框架的召回靠「**路径 + 行号 ±25**」匹配。植入缺陷在同一文件里是密集分布的
（例如 `budget.py` 里 4 条缺陷集中在 L57–L94），所以**行号接近不等于说的是同一件事**。
这不是匹配 bug，是「接近 ≠ 同一缺陷」——只能人看。

## 核实结果（S2 / `blind_no_coverage`，框架报 8/10）

| 缺陷 | 植入 | 模型最近的 claim | 人工判定 |
| --- | --- | --- | --- |
| d1-tie-break-lost | 同分候选不再按 product_id 兜底排序 | 「注释声称按 product_id 兜底排序但实际只按分数排序」 | ✅ 真命中 |
| d2-price-cap-boundary | 价格上限把「刚好等于」判成超预算 | 「价格上限使用严格小于，等于上限的商品被误判为超预算」 | ✅ 真命中 |
| d3-zero-score-candidates | 关键词兜底把 0 分商品带入候选 | 「_keyword_score 对无匹配返回 0.0 但调用方用 score > …」 | ✅ 真命中 |
| d4-context-ratios-swapped | trigger 与 reserve 比例互换 | 「trigger_ratio 0.15 与 reserve_ratio … 互换」 | ✅ 真命中 |
| d5-primary-sku-is-last | primary_sku 取到最后一个 Sku | 「primary_sku 返回 skus[-1] 而非首个，语义与命名不符」 | ✅ 真命中 |
| d6-top-k-validation-dropped | 不再校验 top_k | 「ProductSearchSpec 未校验 top_k 为正，注释把责任外推」 | ✅ 真命中 |
| **d7-budget-tier-boundary** | 剩余恰好 50% 判成 main 档 | 最接近的是一条讲 `remaining_ratio` **返回负值**的 claim | ❌ **邻近误配**（那条对应 d8） |
| d8-budget-remaining-negative | 已超支时剩余额度变负 | 「remaining_ratio 在 used 超过 total_limit 时返回负值」 | ✅ 真命中 |
| d9-budget-zero-not-disabled | `TOTAL=0` 不再表示「不启用」 | 「init_budget 对 total_limit == 0 的处理与文档约定不一致」 | ✅ 真命中 |
| d10-negative-charge-accepted | 负数 token 也记账 | 「charge 接受负数 token，可反向充值预算」 | ✅ 真命中 |

**人工核实：8 条框架命中里 7 条为真，1 条是邻近误配。**

## 这不改变什么，改变什么

- **不改变**：同一套匹配器同时用于两臂，误配率对两臂方向一致，因此
  「分散 > 集中」的方向结论不受影响。
- **改变**：**绝对召回率被高估**。S2 分散臂应从 8/10 读作 **7/10（人工核实）**，
  即高估约 10 个百分点。任何引用绝对召回的地方都必须标注「邻近匹配口径」。

## 未做的部分（必须如实说明）

其余 4 片（S1/S3/S4/S6）与集中臂**未做**逐条人工核实。原因：

1. 每片需人工比对 10–12 条缺陷与对应 claim，且相邻缺陷会互相抢匹配，
   没有自动化替代方案；
2. 在未完成前，**任何「precision / 准确率」的说法都不成立**，只能报「邻近匹配口径的召回」。

如果要补完，只需对每片重复上表流程——**不需要任何模型调用，¥0**。
