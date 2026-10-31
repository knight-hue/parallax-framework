"""在切片副本上注入已知缺陷，并生成可复核的 ground_truth.json。

设计约束（与语料生成器一致）：
1. 每个缺陷都能让既有测试变红——这是"这是真缺陷"的唯一客观证据；
2. marker 是只有被改那几行才出现的片段，用来在测试失败后反查行号；
3. 只改切片副本，绝不动源项目。

## 这一版的缺陷为什么"必须对照才能判定"

上一版（5 个）全部是**局部可判定**的：少一行校验、`quantity - 1`、阈值写错。
任何人只要拿到那个文件就能看出来，于是单个 Reader 就能全中，测不出聚合的价值。

这一版刻意选择三类"单看自洽、对照才矛盾"的缺陷：

    - 契约漂移：端口 docstring 写明的约束，被实现悄悄改掉（d1/d2/d3）
    - 语义错位：同文件内两处对同一个键的口径不一致（d4）
    - 精度/方向/系数偏移：改完注释读起来完全自洽，只有算一遍或对照常量才知道错
      （d7/d8/d9）

并且按分片结构**均匀铺开**：9 个缺陷落在 3 个 Reader 各自的互斥分片里，
单个 Reader 最多只能看到其中 3 个。这是"覆盖广度"能被度量的前提。

## 行号为什么必须在全部注入完成后再算

前面的注入会改变后面缺陷的行号。逐次计算会让 ground_truth 的行区间漂移，
而 `marker` 自检会直接把这个漂移拦下来（上一版就踩过）。
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
    edits: tuple[tuple[str, str], ...]
    """(原文, 替换) 序列。最后一项用于定位 ground truth 的行区间。"""
    triggers_test: str
    reader_owner: str
    """在 R=3 / redundancy=1 分区下唯一能看到该缺陷的 Reader，便于事后归因。"""


INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-stock-seed-overwrite",
        file="app/infrastructure/persistence/in_memory_stock_repository.py",
        defect_class="logic",
        title="库存播种覆盖已有值，重启即抹掉真实扣减",
        rationale=(
            "StockRepository.seed 的契约是「仅登记尚不存在的 SKU，已存在的不覆盖」，"
            "否则每次重启都把扣减过的库存重置回初值。实现把 setdefault 换成直接赋值，"
            "并同步改写注释使其自洽——单看这个文件毫无破绽，必须对照端口 docstring。"
        ),
        edits=(
            (
                "            for sku_id, stock in entries:\n"
                "                # 只登记缺失项：已有值代表真实扣减结果，不能被 seed 重置\n"
                "                self._stock.setdefault(sku_id, stock)\n",
                "            for sku_id, stock in entries:\n"
                "                # 以 seed 为准对齐库存，保证每次启动的库存与配置一致\n"
                "                self._stock[sku_id] = stock\n",
            ),
        ),
        triggers_test="TestD1SeedDoesNotResetStock::test_repeated_seed_keeps_deducted_stock",
        reader_owner="reader-r0-0",
    ),
    Injection(
        defect_id="d2-get-many-missing-zero",
        file="app/infrastructure/persistence/in_memory_stock_repository.py",
        defect_class="api_misuse",
        title="批量查库存把未登记 SKU 补成 0，与「卖光」无法区分",
        rationale=(
            "端口规定未登记的 SKU 返回 None（未知），get_many 的 Mapping 里也不应出现该键。"
            "改成 .get(sku_id, 0) 后，调用方拿到的 0 既可能是缺货也可能是 SKU 不存在，"
            "商品卡会把「未知库存」渲染成「售罄」。写法本身符合直觉，只有对照端口才知道错。"
        ),
        edits=(
            (
                "            return {sku_id: self._stock[sku_id] for sku_id in sku_ids if sku_id in self._stock}\n",
                "            return {sku_id: self._stock.get(sku_id, 0) for sku_id in sku_ids}\n",
            ),
        ),
        triggers_test="TestD2GetManyKeepsMissingAbsent::test_missing_sku_is_absent",
        reader_owner="reader-r0-0",
    ),
    Injection(
        defect_id="d3-list-turns-earliest",
        file="app/infrastructure/persistence/json_file_stores.py",
        defect_class="boundary",
        title="对话流水取最早 N 轮而非最近 N 轮",
        rationale=(
            "ConversationStore.list_turns 的 limit 语义是「最近 N 轮」（按 turn_index 升序返回尾部）。"
            "写成 turns[:limit] 后返回的是会话开头，多轮对话恢复出来的上下文永远是陈年旧话。"
            "[:limit] 在列表上看起来是最自然的截断写法，必须读端口才暴露。"
        ),
        edits=(
            (
                "        return turns[-limit:]\n",
                "        return turns[:limit]\n",
            ),
        ),
        triggers_test="TestD3ListTurnsReturnsLatest::test_limit_returns_most_recent",
        reader_owner="reader-r0-0",
    ),
    Injection(
        defect_id="d4-idempotency-key-scope",
        file="app/application/usecases/order_usecases.py",
        defect_class="logic",
        title="幂等回放给键加了买家前缀，与登记时用的裸键不一致",
        rationale=(
            "OrderIdempotencyStore 的口径是「任务号 + 买家」由调用方拼好传入，存储层原样存取。"
            "_replay 里改成 f'{buyer_id}:{key}' 去查，而 record 仍用裸键登记——"
            "读起来像是「加了一层买家作用域」的加固，实际让 find 永远返回 None，"
            "队列重投会重复下单并重复扣库存。必须把同文件两处用法对照起来才能判定。"
        ),
        edits=(
            (
                "        order_id = await self._idempotency.find(idempotency_key)\n",
                '        order_id = await self._idempotency.find(f"{buyer_id}:{idempotency_key}")\n',
            ),
        ),
        triggers_test="TestD4IdempotentReplayUsesSameKey::test_second_call_with_same_key_reuses_order",
        reader_owner="reader-r0-1",
    ),
    Injection(
        defect_id="d5-empty-lines-allowed",
        file="app/domain/order/order.py",
        defect_class="logic",
        title="「至少一条订单行」的不变量退化成「不是 None」",
        rationale=(
            "Order 聚合根不变量要求 lines 非空。写成 `if self.lines is None` 后，"
            "空列表可以构造出订单，total_amount() 随即在 lines[0] 上 IndexError；"
            "而 `is None` 看起来比 `not` 更严谨，很容易被当成无害的防御性写法放过。"
        ),
        edits=(
            (
                "        if not self.lines:\n"
                '            raise ValueError(f"Order 至少要有一条订单行：{self.order_id}")\n',
                "        if self.lines is None:\n"
                '            raise ValueError(f"Order 至少要有一条订单行：{self.order_id}")\n',
            ),
        ),
        triggers_test="TestD5EmptyLinesRejected::test_empty_line_list_raises",
        reader_owner="reader-r0-1",
    ),
    Injection(
        defect_id="d6-subtotal-off-by-one",
        file="app/domain/order/order_line.py",
        defect_class="off_by_one",
        title="订单行小计按 quantity - 1 计价",
        rationale=(
            "subtotal() 用 quantity - 1 做乘法。quantity=1 时小计为 0，"
            "看起来像「首件已含在运费里」的合理假设，实际让所有订单金额少算一件。"
        ),
        edits=(
            (
                "        return self.unit_price.multiply(self.quantity)\n",
                "        return self.unit_price.multiply(self.quantity - 1)\n",
            ),
        ),
        triggers_test="TestD6SubtotalCountsEveryUnit::test_subtotal_uses_full_quantity",
        reader_owner="reader-r0-1",
    ),
    Injection(
        defect_id="d7-freight-renewal-40",
        file="app/domain/shipping/tariff_schedule.py",
        defect_class="logic",
        title="续件运费系数从 60% 改成 40%（注释同步改写）",
        rationale=(
            "续件递增系数被改成 0.4，同时把两处注释一并改成 40%，改动后文件内部完全自洽。"
            "只有把它和运费常量表的口径（首件全价、续件 60%）对照、或按 3 件算一遍才看得出偏差。"
        ),
        edits=(
            (
                "# 目的国基础运费（CNY 分，单件；多件按 60% 递增，简化的续重逻辑）\n",
                "# 目的国基础运费（CNY 分，单件；多件按 40% 递增，简化的续重逻辑）\n",
            ),
            (
                "        # 运费：首件全价 + 续件 60%\n"
                '        base_freight_cny = Money.of(_BASE_FREIGHT_CNY_MINOR[ship_to], "CNY")\n'
                "        freight_minor_cny = round(base_freight_cny.amount_in_minor_units * (1 + 0.6 * (quantity - 1)))\n",
                "        # 运费：首件全价 + 续件 40%\n"
                '        base_freight_cny = Money.of(_BASE_FREIGHT_CNY_MINOR[ship_to], "CNY")\n'
                "        freight_minor_cny = round(base_freight_cny.amount_in_minor_units * (1 + 0.4 * (quantity - 1)))\n",
            ),
        ),
        triggers_test="TestD7FreightRenewalRate::test_renewal_items_charge_sixty_percent",
        reader_owner="reader-r0-2",
    ),
    Injection(
        defect_id="d8-exchange-rate-inverse",
        file="app/domain/catalog/exchange_rate.py",
        defect_class="logic",
        title="汇率换算方向取反（除与被除颠倒）",
        rationale=(
            "rate() 返回 from/to 的比值，被写成 to/from。USD→CNY 得到 0.14 而不是 7.10，"
            "所有跨境金额折算全部按其平方级偏离。两个下标对调后代码依旧整洁，只能靠算一遍发现。"
        ),
        edits=(
            (
                "        return self.rates_to_cny[from_currency] / self.rates_to_cny[to_currency]\n",
                "        return self.rates_to_cny[to_currency] / self.rates_to_cny[from_currency]\n",
            ),
        ),
        triggers_test="TestD8ExchangeRateDirection::test_usd_to_cny_rate",
        reader_owner="reader-r0-2",
    ),
    Injection(
        defect_id="d9-from-major-truncates",
        file="app/domain/catalog/money.py",
        defect_class="boundary",
        title="元转分把四舍五入改成截断，隐藏的分位被抹掉",
        rationale=(
            "from_major_units 用 int(major * 100) 取代 round(...)。int() 截断在小数位上看起来"
            "像「规范化为整数」，实际把 0.29 元算成 28 分；所有从报价单进入系统的金额都可能少一分，"
            "且这种偏差在整数金额上完全不可见。"
        ),
        edits=(
            (
                "        return Money.of(round(major * 100), currency)\n",
                "        return Money.of(int(major * 100), currency)\n",
            ),
        ),
        triggers_test="TestD9FromMajorUnitsRounds::test_fractional_major_units_round",
        reader_owner="reader-r0-2",
    ),
]


def locate(text: str, snippet: str) -> tuple[int, int]:
    index = text.find(snippet)
    if index < 0:
        raise SystemExit(f"找不到待替换片段：{snippet[:60]!r}")
    start = text.count("\n", 0, index) + 1
    end = start + snippet.rstrip("\n").count("\n")
    return start, end


def compute_reader_map(repo: Path, n_readers: int = 3, redundancy: int = 1) -> dict[str, str]:
    """用与实验完全相同的分区器算出每个文件归属哪个 Reader。

    必须在**注入之后**算：evidence_id 含内容哈希，内容一变、组内排序就变，
    切块归属随之改变。预先写死的归属会与真实实验不符（这一版已经踩过一次：
    原以为 order.py 归 reader-1，注入后实测归 reader-2）。
    """
    from parallax.core.partitioning import BlindPartitioner
    from parallax.plugins.code_audit import RepoAdapter

    units = RepoAdapter(repo, extensions=(".py",), group_depth=2).load("审查代码中的缺陷")
    parts = BlindPartitioner(n_readers=n_readers, redundancy=redundancy, seed=0).partition(
        units, round_index=0
    )
    mapping: dict[str, str] = {}
    for part in parts:
        for unit in part.units:
            mapping.setdefault(unit.metadata.get("path", unit.locator), part.reader_id)
    return mapping


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

    for injection in INJECTIONS:
        path = repo / injection.file
        text = path.read_text(encoding="utf-8")
        for old, new in injection.edits:
            if text.count(old) != 1:
                raise SystemExit(
                    f"{injection.file} 中片段出现次数 != 1（{text.count(old)}）：{old[:50]!r}"
                )
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")

    # 行号必须在**全部注入完成后**再算：前面的注入会改变后面缺陷的行号，
    # 逐次计算会让 ground_truth 的行区间漂移（自检会直接拦下）。
    reader_map = compute_reader_map(repo)
    defects = []
    for injection in INJECTIONS:
        text = (repo / injection.file).read_text(encoding="utf-8")
        _old, new = injection.edits[-1]
        start, end = locate(text, new)
        marker = new.strip().splitlines()[-1].strip()
        defects.append(
            {
                "id": injection.defect_id,
                "file": injection.file,
                "line_start": start,
                "line_end": end,
                "defect_class": injection.defect_class,
                "title": injection.title,
                "marker": marker,
                "rationale": injection.rationale + f"（触发测试：{injection.triggers_test}）",
                "reader_owner": reader_map.get(injection.file, "unassigned"),
                "reader_owner_expected": injection.reader_owner,
                "requires_cross_reference": True,
            }
        )

    ground_truth = {
        "task_id": task_dir.name,
        "description": (
            "真实电商项目切片（下单链路），9 个「单看自洽、对照才矛盾」的注入缺陷，"
            "在 R=3/redundancy=1 下均匀落在三个互斥分片里"
        ),
        "repo": "repo",
        "planted_defect_count": len(defects),
        "defects": defects,
    }
    (task_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已注入 {len(defects)} 个缺陷 -> {task_dir}")
    for defect in defects:
        print(
            f"  {defect['id']:26s} {defect['reader_owner']:12s} "
            f"{defect['file']}:{defect['line_start']}  {defect['title']}"
        )
    # 分片均衡性是“覆盖广度能被度量”的前提：9 个缺陷若全落在同一个分片，
    # 这次注入就白做了——要在这里就发现，而不是等实验跑完。
    spread: dict[str, int] = {}
    for defect in defects:
        spread[defect["reader_owner"]] = spread.get(defect["reader_owner"], 0) + 1
    print("分片分布：" + "，".join(f"{k}={v}" for k, v in sorted(spread.items())))
    thin = [k for k, v in spread.items() if v == 0]
    if len(spread) < 3 or thin:
        print("⚠️ 分布不均衡：至少一个分片没有缺陷，覆盖广度不可度量")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
