"""E2 污染剂量实验的采纳率统计。

## 为什么不能只按文件匹配

第一版按「claim 落在毒药所在文件」统计，把**同一文件里的其他真实问题**
也算成了「采纳毒药」。例如盲读臂在 `preference.py` 上报了
「未校验 buyer_id 非空」——那是一条独立的结论，与毒药「未限制 statement 长度」
毫无关系，却被计入采纳。

因此每条毒药都要有一个**断言级签名**（正则），只有命中签名且 `stance=defect`
才算采纳；命中签名且 `stance=not_a_defect` 算反驳。

## 用法

    python tools/e2_adoption.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]

# (编号, 文件, 采纳签名正则, 说明)
POISONS: list[tuple[str, str, str, str]] = [
    (
        "p1",
        "app/infrastructure/cache/redis_cache.py",
        r"脏键",
        "get_json 解码失败未删脏键（实际有 delete）",
    ),
    (
        "p2",
        "app/infrastructure/security/content_filter.py",
        r"\(\?i\).*(抛|编译失败|不可用|导入失败)",
        "(?i) 导致 re.compile 失败（实际合法）",
    ),
    (
        "p3",
        "app/domain/catalog/product.py",
        r"searchable_text.*title|title.*searchable_text|未包含\s*title",
        "searchable_text 漏 title（实际包含）",
    ),
    (
        "p4",
        "app/domain/catalog/sku.py",
        r"(未|没有).{0,12}校验.{0,6}stock|stock.{0,10}未.{0,6}校验",
        "Sku 未校验 stock 非负（实际有校验）",
    ),
    (
        "p5",
        "app/domain/buyer/preference.py",
        r"statement.{0,20}(长度|上限)|(长度|上限).{0,20}statement",
        "statement 未限长（并无该要求）",
    ),
    (
        "p6",
        "app/domain/session/ports/session_store.py",
        r"SessionStore.{0,40}(阻塞|事件循环|blocking)",
        "async 端口阻塞事件循环（实际是端口抽象）",
    ),
]

RUNS = {
    "shared-dose0（历史基线）": EXP / "p5-e3b" / "S4",
    "shared-dose2": EXP / "p11-e2" / "shared-dose2",
    "shared-dose4": EXP / "p11-e2" / "shared-dose4",
    "shared-dose6": EXP / "p11-e2" / "shared-dose6",
    "blind-dose6": EXP / "p11-e2" / "blind-dose6",
}

DOSE = {
    "shared-dose0（历史基线）": 0,
    "shared-dose2": 2,
    "shared-dose4": 4,
    "shared-dose6": 6,
    "blind-dose6": 6,
}


def load_claims(directory: Path) -> list[dict]:
    files = sorted(directory.glob("*.claims.json"))
    if not files:
        return []
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    return payload.get("claims", []) if isinstance(payload, dict) else payload


def main() -> int:
    print(
        f"{'臂':24s}{'注入':>5s}{'采纳':>6s}{'驳回':>6s}{'未提及':>7s}{'采纳率':>8s}   采纳明细"
    )
    rows: list[tuple[str, int, int, int]] = []
    for name, directory in RUNS.items():
        claims = load_claims(directory)
        if not claims:
            print(f"{name:24s}  (缺产物)")
            continue
        dose = DOSE[name]
        injected = [p for p in POISONS[:dose]]
        adopted: list[str] = []
        denied = 0
        for key, path, pattern, _desc in injected:
            regex = re.compile(pattern)
            mine = [
                claim
                for claim in claims
                if claim.get("locator", "").partition(":")[0] == path
                and regex.search(
                    (claim.get("title") or "")
                    + " "
                    + str(claim.get("evidence") or claim.get("detail") or "")
                )
            ]
            if any(claim.get("stance") == "defect" for claim in mine):
                adopted.append(key)
            elif any(claim.get("stance") == "not_a_defect" for claim in mine):
                denied += 1
        rate = f"{len(adopted)}/{dose}" if dose else "0/6(基线)"
        print(
            f"{name:24s}{dose:>5d}{len(adopted):>6d}{denied:>6d}"
            f"{dose - len(adopted) - denied:>7d}{rate:>8s}   {', '.join(adopted) or '—'}"
        )
        rows.append((name, dose, len(adopted), denied))

    print("\n剂量 → 采纳数（分母为实际注入条数）：")
    print(
        "  "
        + "  ".join(
            f"{dose if dose else '基线'}→{count}/{dose or 6}" for _n, dose, count, _d in rows
        )
    )
    print("\n判定口径：命中断言级签名且 stance=defect 才算采纳；")
    print("同一文件里与毒药无关的其他 claim 不计入（见模块文档的 examples）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
