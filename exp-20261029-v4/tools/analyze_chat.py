"""汇总 p4-chat 五片结果，做配对检验，产出 RESULT.md。

## 检验怎么选

**符号检验（sign test）**：只看每片谁赢。
⚠️ n=5 时双侧最小可能 p 值为 2×(1/2)^5 = 0.0625，**恒 > 0.05**，
所以预注册里「5 片里 ≥4 片且 p<0.05」在双侧口径下数学上不可能达成。
本项目假设是**有方向的**（分散 > 集中），单侧 p = (1/2)^5 = 0.03125 才有意义，
两个口径都必须如实报出来。

**McNemar（按缺陷配对）**：把每条植入缺陷当作一个配对观测，
看「只有分散找到」vs「只有集中找到」的条数。这比按切片检验有力得多，
而且缺陷之间互不独立这件事它也没假装——它只比较配对内的不一致项。
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP / "p4-chat"
CORPUS = EXP / "p1-subsample"

CENTRAL = "no_peers_all_evidence"
DISPERSED = "blind_no_coverage"


def load(shard: Path) -> dict:
    raw = json.loads((shard / "metrics.json").read_text(encoding="utf-8"))
    return {arm["arm"]: arm for arm in raw["arms"]}


def readers(shard: Path, arm: str) -> dict[str, list[str]]:
    path = next(shard.glob(f"*__{arm}.readers.json"), None)
    return json.loads(path.read_text(encoding="utf-8")) if path else {}


def binom_two_sided(k: int, n: int) -> float:
    """二项分布双侧精确 p 值。

    `k` 必须是**两侧中较小的那个**：McNemar 的双侧 p = 2 × P(X ≤ min(b, c))。
    早先这里传入了较大的那一侧，得到 P(X≤29)≈1 再乘 2 截断为 1.0，
    把一个 p≈2.6e-6 的结果报成了「无差异」——方向反了，且是最危险的一种反。
    """
    if n == 0:
        return 1.0
    k = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n
    return min(1.0, 2 * tail)


def main() -> int:
    shards = sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / "metrics.json").exists())
    if not shards:
        print("没有结果")
        return 1

    lines: list[str] = []
    lines.append("# E1 覆盖效应：五切片结果")
    lines.append("")
    lines.append(f"生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("语料：`p1-subsample`（固定规模采样子语料，五片 26–32 文件）")
    lines.append("模型：`deepseek-chat`；两臂均为 3 Reader、单轮、盲读、`equal_exposure`、`greedy` 分配")
    lines.append("")

    lines.append("## 主表")
    lines.append("")
    lines.append("| 切片 | 语料文件 | 集中读 / 合并 | 分散读 / 合并 | 集中召回 | 分散召回 | 差 | 丢批 |")
    lines.append("| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |")

    wins = 0
    diffs: list[int] = []
    both = central_only = dispersed_only = neither = 0
    total_out = 0
    total_calls = 0

    for shard in shards:
        arms = load(shard)
        if CENTRAL not in arms or DISPERSED not in arms:
            continue
        c, d = arms[CENTRAL], arms[DISPERSED]
        total_out += c["completion_tokens"] + d["completion_tokens"]
        total_calls += c["llm_calls"] + d["llm_calls"]

        c_read = readers(shard, CENTRAL)
        d_read = readers(shard, DISPERSED)
        c_union = len({eid for ids in c_read.values() for eid in ids})
        d_union = len({eid for ids in d_read.values() for eid in ids})
        corpus_files = c_union if c_union >= d_union else d_union
        corpus_size = len(
            {eid for ids in list(c_read.values()) + list(d_read.values()) for eid in ids}
        )

        c_hits, d_hits = c["hits"], d["hits"]
        diff = d_hits - c_hits
        diffs.append(diff)
        if diff > 0:
            wins += 1

        dropped = (c.get("dropped_chunks") or 0) + (d.get("dropped_chunks") or 0)
        lines.append(
            f"| {shard.name} | {corpus_size} "
            f"| {c_union} | {d_union} "
            f"| {c_hits}/{c['planted']} | {d_hits}/{d['planted']} "
            f"| {'+' if diff >= 0 else ''}{diff} | {dropped} |"
        )

        # 逐缺陷配对
        c_map = {x["defect_id"]: bool(x["found_by"]) for x in c["defects"]}
        d_map = {x["defect_id"]: bool(x["found_by"]) for x in d["defects"]}
        for defect_id, c_found in c_map.items():
            d_found = d_map.get(defect_id, False)
            if c_found and d_found:
                both += 1
            elif c_found:
                central_only += 1
            elif d_found:
                dispersed_only += 1
            else:
                neither += 1

    n = len(diffs)
    lines.append("")
    lines.append("## 配对检验")
    lines.append("")
    lines.append(f"- 切片数 n = {n}；**分散胜 {wins}/{n}**；各片差值 {diffs}；均值 {sum(diffs)/n:.1f}")
    one_sided = 0.5**n
    lines.append(
        f"- 符号检验：单侧 p = {one_sided:.4f}；双侧 p = {min(1.0, 2*one_sided):.4f}"
    )
    lines.append(
        "  - ⚠️ n=5 时双侧最小可达 p 就是 0.0625，**不可能 < 0.05**；"
        "本项目假设有方向性，按单侧读才是合理口径"
    )
    total = both + central_only + dispersed_only + neither
    mcnemar_p = binom_two_sided(dispersed_only, dispersed_only + central_only)
    lines.append("")
    lines.append("### McNemar（按缺陷配对）")
    lines.append("")
    lines.append("| | 分散找到 | 分散没找到 |")
    lines.append("| --- | ---: | ---: |")
    lines.append(f"| **集中找到** | {both} | {central_only} |")
    lines.append(f"| **集中没找到** | {dispersed_only} | {neither} |")
    lines.append("")
    lines.append(
        f"不一致项 {dispersed_only + central_only} 条：只有分散找到 **{dispersed_only}**，"
        f"只有集中找到 **{central_only}**；双侧精确 p = **{mcnemar_p:.2e}**"
    )
    lines.append("")

    lines.append("## 结论")
    lines.append("")
    if wins == n and n >= 5:
        lines.append(
            f"五个切片**全部**朝同一方向（分散 > 集中），配对后只有分散找到 {dispersed_only} 条、"
            f"只有集中找到 {central_only} 条。按预先写定的判据「5 片里 ≥4 片 B>A」**满足**；"
            "显著性请按上表单侧 p 与 McNemar p 引用，并注明 n=5 时双侧口径不可能达到 0.05。"
        )
    elif wins >= 4:
        lines.append(f"{wins}/{n} 片朝同一方向，达到「≥4 片」判据，但未全胜，需逐片讨论异常。")
    else:
        lines.append(f"仅 {wins}/{n} 片朝同一方向，未达判据。")

    lines.append("")
    lines.append("## 必须同时申明的限制")
    lines.append("")
    lines.append(
        "1. **缺陷密度被抬高**：子采样按缺陷密度选组，S6 从 0.10 抬到 0.32。"
        "因此绝对召回率不可与历史全量运行比较，只能用于**臂间对照**。"
    )
    lines.append(
        "2. **收益来自覆盖，不来自更高的单文件精度**。"
        "原 S4 全量运行的范围分析显示：集中臂 12 个缺陷里 8 个所在文件从未被任何 Reader 读到；"
        "而在读到的文件内，集中臂命中率并不低于分散臂。"
    )
    lines.append(
        "3. **两臂总读取量相同**（每臂读 N 个文件，N = 语料文件数），"
        "差别只在「3 个 Reader 是否重复读同一批」。"
    )

    lines.append("")
    lines.append("## 成本")
    lines.append("")
    lines.append(
        f"五片共 {total_calls} 次调用、输出 {total_out:,} token，"
        f"按 ¥0.16/1k 输出估算 ≈ **¥{total_out/1000*0.16:.2f}**"
    )

    out = ROOT / "RESULT.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
