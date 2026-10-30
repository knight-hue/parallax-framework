"""E4 人工核实：把「匹配上的 claim」逐条摊开，供人工判断真假。

## 为什么要做这个

现在报的是「召回 3 vs 10」。评审第一句就会问：「那 10 条里有几条是真的？」

自动匹配只看「路径 + 行号接近」，行号接近不等于说的是同一件事。所以要把
每条匹配对（植入缺陷的标题 vs 模型 claim 的标题）并排打出来，人工判断：

- **真命中**：claim 说的是那条植入缺陷本身；
- **邻近误配**：路径行号对上了，但描述的是别的问题（假阳性）。

同时统计各臂**未匹配**的 claim 数，并按比例抽样供判断误报率。

用法：
    python e4_dump.py > e4-pairs.txt
"""

from __future__ import annotations

import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP / "p4-chat"
GT_ROOT = EXP / "p1-subsample"

CENTRAL = "no_peers_all_evidence"
DISPERSED = "blind_no_coverage"
TOLERANCE = 25  # 与 score.py 一致


def load_gt(task: str) -> dict[str, dict]:
    path = GT_ROOT / task / "ground_truth.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {d["id"]: d for d in data["defects"]}


def norm(path: str) -> str:
    """归一化 claim 的 locator。

    ⚠️ `locator` 形如 `app/domain/order/order_line.py:27-28:27`——路径后面跟了
    行区间与再次行号。早先直接比较整串，导致**全部 claim 匹配失败**，
    25~55 条 claim 一律显示「匹配 0」。这里按第一个冒号截断取路径。
    """
    head = (path or "").split(":")[0]
    return head.replace("\\", "/").strip().lstrip("./")


def claim_line(claim: dict) -> int:
    line = claim.get("line_start")
    if isinstance(line, int):
        return line
    locator = claim.get("locator") or ""
    tail = locator.split(":")[-1]
    digits = "".join(ch for ch in tail if ch.isdigit())
    return int(digits) if digits else -1


def main() -> int:
    for shard in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        task = shard.name
        gt = load_gt(task)
        if not gt:
            continue
        print("=" * 100)
        print(f"切片 {task}｜植入缺陷 {len(gt)} 条")
        print("=" * 100)

        for arm in (CENTRAL, DISPERSED):
            path = next(shard.glob(f"*__{arm}.claims.json"), None)
            if path is None:
                continue
            claims = json.loads(path.read_text(encoding="utf-8"))

            matched: list[tuple[str, dict, dict]] = []
            unmatched: list[dict] = []
            for claim in claims:
                cpath = norm(claim.get("locator"))
                cline = claim_line(claim)
                hit = None
                for defect_id, defect in gt.items():
                    if norm(defect["file"]) != cpath:
                        continue
                    if defect["line_start"] - TOLERANCE <= cline <= defect["line_end"] + TOLERANCE:
                        hit = defect
                        break
                if hit:
                    matched.append((hit["id"], hit, claim))
                else:
                    unmatched.append(claim)

            print(f"\n--- {arm}｜claim {len(claims)} 条：匹配 {len(matched)}、未匹配 {len(unmatched)} ---")
            for defect_id, defect, claim in matched:
                d_title = defect["title"].replace("\n", " ")[:58]
                c_title = (claim.get("title") or claim.get("statement") or "").replace("\n", " ")[:58]
                print(f"  [{defect_id}]")
                print(f"     植入：{d_title}")
                print(f"     模型：{c_title}")
            if unmatched:
                print(f"  —— 未匹配 claim 样本（前 6 条）——")
                for claim in unmatched[:6]:
                    c_title = (claim.get("title") or claim.get("statement") or "").replace("\n", " ")[:70]
                    print(f"     {norm(claim.get('locator'))}:{claim_line(claim)}  {c_title}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
