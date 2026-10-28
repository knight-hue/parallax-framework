"""在切片副本上注入已知缺陷，并生成可复核的 ground_truth.json。

设计约束（与语料生成器一致）：
1. 每个缺陷都能让既有测试变红——这是“这是真缺陷”的唯一客观证据；
2. marker 是只有被改那几行才出现的片段，用来在测试失败后反查行号；
3. 只改切片副本，绝不动源项目。
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Injection:
    defect_id: str
    file: str
    defect_class: str
    title: str
    rationale: str
    old: str
    new: str
    triggers_test: str


INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-currency-guard",
        file="app/domain/catalog/money.py",
        defect_class="business_invariant",
        title="Money.add 丢失币种一致性校验",
        rationale=(
            "add() 不再调用 _assert_same_currency，跨币种金额会被直接相加。"
            "Order 侧只在构造时比较 currency 字符串，聚合后没有任何防线。"
        ),
        old='    def add(self, other: "Money") -> "Money":\n        self._assert_same_currency(other)\n',
        new='    def add(self, other: "Money") -> "Money":\n',
        triggers_test="TestMoney::test_reject_currency_mismatch",
    ),
    Injection(
        defect_id="d2-blank-reason",
        file="app/domain/order/order.py",
        defect_class="input_validation",
        title="取消订单只拒绝空字符串，放过全空白 reason",
        rationale=(
            "条件从 `not reason or not reason.strip()` 退化成 `not reason`，"
            "传入 '  ' 会被当成有效原因写入审计字段。"
        ),
        old="        if not reason or not reason.strip():\n",
        new="        if not reason:\n",
        triggers_test="TestOrderStateMachine::test_cancel_requires_reason",
    ),
    Injection(
        defect_id="d3-currency-threshold",
        file="app/domain/order/order.py",
        defect_class="boundary",
        title="订单币种一致性阈值写成 >2，两种币种被放行",
        rationale=(
            "`len(currencies) > 1` 被改成 `> 2`，只有三种以上币种才会抛错；"
            "而 total_amount() 的 add() 依赖这个前置校验，二者叠加后总额静默错算。"
        ),
        old="        if len(currencies) > 1:\n",
        new="        if len(currencies) > 2:\n",
        triggers_test="TestOrderStateMachine::test_reject_mixed_currency_lines",
    ),
    Injection(
        defect_id="d4-subtotal-off-by-one",
        file="app/domain/order/order_line.py",
        defect_class="off_by_one",
        title="订单行小计少算一件",
        rationale=(
            "subtotal() 用 quantity - 1 做乘法，看起来像“首件已含”，"
            "实际让任何 multi-quantity 订单的小计与总额都少一件。"
        ),
        old="        return self.unit_price.multiply(self.quantity)\n",
        new="        return self.unit_price.multiply(self.quantity - 1)\n",
        triggers_test="TestOrderStateMachine::test_total_amount",
    ),
    Injection(
        defect_id="d5-confirmed-at",
        file="app/domain/order/order.py",
        defect_class="state_machine",
        title="confirm() 不再记录确认时间",
        rationale=(
            "CONFIRMED 分支删掉 confirmed_at 赋值，状态与时间戳不一致；"
            "snapshot() 仍会输出 created_at，下游无法判断是否已确认。"
        ),
        old="        self.status = OrderStatus.CONFIRMED\n        self.confirmed_at = _now()\n",
        new="        self.status = OrderStatus.CONFIRMED\n",
        triggers_test="TestOrderStateMachine::test_place_enters_confirmed",
    ),
]


def locate(text: str, snippet: str) -> tuple[int, int]:
    index = text.find(snippet)
    if index < 0:
        raise SystemExit(f"找不到待替换片段：{snippet[:60]!r}")
    start = text.count("\n", 0, index) + 1
    end = start + snippet.rstrip("\n").count("\n")
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="干净的切片目录（含 repo/）")
    parser.add_argument("--out", type=Path, required=True, help="输出目录（新的任务目录）")
    args = parser.parse_args()

    source_repo = args.source / "repo"
    if not source_repo.is_dir():
        raise SystemExit(f"{source_repo} 不存在")

    task_dir = args.out
    if task_dir.exists():
        shutil.rmtree(task_dir)
    repo = task_dir / "repo"
    shutil.copytree(source_repo, repo)

    # 验证测试放在 repo 外、与 repo 同级：conftest 靠同级路径定位 repo，
    # 既保证验真跑的是**注入版**，又不会让断言进入证据池。
    source_verify = args.source / "tests_verify"
    if source_verify.is_dir():
        shutil.copytree(source_verify, task_dir / "tests_verify")

    defects = []
    for injection in INJECTIONS:
        path = repo / injection.file
        text = path.read_text(encoding="utf-8")
        if text.count(injection.old) != 1:
            raise SystemExit(f"{injection.file} 中待替换片段出现次数 != 1")
        path.write_text(text.replace(injection.old, injection.new, 1), encoding="utf-8")

    # 行号必须在**全部注入完成后**再算：前面的注入会改变后面缺陷的行号，
    # 逐次计算会让 ground_truth 的行区间漂移（自检会直接拦下）。
    for injection in INJECTIONS:
        text = (repo / injection.file).read_text(encoding="utf-8")
        start, end = locate(text, injection.new)
        defects.append(
            {
                "id": injection.defect_id,
                "file": injection.file,
                "line_start": start,
                "line_end": end,
                "defect_class": injection.defect_class,
                "title": injection.title,
                "marker": injection.new.strip().splitlines()[-1].strip(),
                "rationale": injection.rationale + f"（触发测试：{injection.triggers_test}）",
            }
        )

    ground_truth = {
        "task_id": task_dir.name,
        "description": "真实电商项目切片（下单链路）注入缺陷",
        "repo": "repo",
        "planted_defect_count": len(defects),
        "defects": defects,
    }
    (task_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已注入 {len(defects)} 个缺陷 -> {task_dir}")
    for defect in defects:
        print(f"  {defect['id']:26s} {defect['file']}:{defect['line_start']}  {defect['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
