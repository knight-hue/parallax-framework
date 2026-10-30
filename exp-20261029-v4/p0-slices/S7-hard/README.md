# S7-hard：加难缺陷切片（E-9）

## 为什么要有这一片

S1–S6 的召回全部贴着天花板：S1 盲读 9/9、S6 盲读 10/10、S4 读全 10/12 且三条臂互相重合。
天花板效应会把**机制层面的效应（K\*、冗余率）**和**结果层面的效应（召回）**混在一起：
「共享同伴结论损害独立性」只能在 K\*/冗余率上看到，看不到召回损失。于是
「是我们不行，还是题目太简单」这个问题永远只能用推测回答（见 `REMAINING_PLAN.md` §E-9）。

S7-hard 就是为这个问题造的：**同一份 26 文件语料、同一个目录结构、只把缺陷换难的**。

## 设计约束

1. **文件集与 `p1-subsample/S4` 逐字节相同**（26 个 .py，路径一一对应），
   因此可以和历史 S4 各臂结果直接对照，不需要再跑一遍易缺陷基线。
2. **只有 5 条缺陷，且两两行号相距 ≥ 25 行**（`score.py` 的匹配容差就是 25）。
   易缺陷版的 S4 在 `semantic_cache.py` 里 110~167 行挤了 4 条缺陷，
   近距离缺陷会互相「借用」命中，污染难度归因；这里刻意避开。
3. **每条缺陷一条独立测试**，路径 `tests_verify/test_injected.py::TestH*`，
   干净代码全绿、注入版逐条打红（实测 12 绿 / 5 红，见下）。
4. 缺陷必须**仅凭切片内文件即可发现**。不可发现的缺陷测不出能力，只会制造噪声，
   因此不做「需要看切片外代码才知道」的注入。

## 五条难缺陷

| id | 类别 | 位置 | 为什么难 |
| --- | --- | --- | --- |
| `h1-relevance-sort-direction-inverted` | 无显眼标记的语义错 | `preference_selector.py:120` | 排序键少一个负号。仍在排序、仍取前 k、仍复原相对顺序，注释依旧成立；只有理解「负号是为了降序」才看得出。 |
| `h2-sliding-window-lower-bound-off-by-one` | 边界条件 | `redis_cache.py:122` | 滑窗清理上界多减 1 秒。只在「恰好满一个窗口」这一刻错，读起来像给时钟漂移留余量。 |
| `h3-cosine-drops-dimension-guard` | **跨文件不一致** | `semantic_cache.py:58-59` | `_cosine` 在本项目里有两份，原本逐字相同。只删掉其中一份的维度守卫后函数照样能跑（`zip` 按短边截断、不抛异常），返回一个看起来合法的相似度。必须两文件并排比对才发现其中一份少了这段。 |
| `h4-similarity-threshold-exclusive` | 边界条件 | `semantic_cache.py:140` | `>=` 改 `>`。差异只出现在相似度恰好等于阈值的样本上；而 `>` 比 `>=` 更常见，不刺眼。 |
| `h5-sku-rejects-zero-stock` | 不变量被收紧 | `sku.py:29-30` | `< 0` 改 `<= 0`，异常文案同步改成「必须为正」，代码与文案自洽、零错误痕迹；只有把「售罄」当成必须存在的业务状态才看得出。 |

## 验真结果（2026-10-30 实测）

| 代码状态 | 命令 | 结果 |
| --- | --- | --- |
| 全部回退到干净版 | `pytest tests_verify/test_injected.py` | **17 passed** |
| 仅植入 5 条难缺陷 | 同上 | **5 failed / 11 passed**（失败项恰为 H1–H5） |

> 注：`TestD3RankingRestoresOriginalOrder` 在 S7-hard 上也会红，因为 h1 与 d3 改的是
> 同一个函数（`_rank_by_relevance`）的选取结果。**d3 不在 S7-hard 的真值里**，
> 它变红只是 h1 的副产物，不影响打分口径。

## 用法

```powershell
# 运行（与历史 S4 各臂可直接对照）
python tools/run_slice.py --task S7 --corpus p1-subsample --out p7-hard/e1 --arms no_peers_all_evidence,blind_no_coverage
```

真值：`ground_truth.json`（5 条，`difficulty=hard`）。
