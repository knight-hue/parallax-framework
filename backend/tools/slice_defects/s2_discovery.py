"""S2-discovery 的注入规格：10 个缺陷，落在 5 个文件。

这一批集中在「检索链路的可复现性与硬约束」上——都是实现悄悄放宽了 docstring
里写明的约定，单看代码完全合理：

    - 同分兜底排序：并列时按 product_id 排——没了就每次运行结果不同
    - 价格硬约束：小于等于上限应当通过——写成小于就把「刚好等于」判成超预算
    - 关键词兜底：0 分候选不进候选集——写成 >= 0 就把全库带进来
    - 上下文压缩：触发比例 0.75 / 保留 0.15——两个值互换了
    - Product：primary_sku 是第一个 Sku——取成最后一个
    - 检索规格：top_k 必须为正——校验没了，top_k=0 静默返回空
    - Token 账本：剩余比例 50% 属 lite 档——边界改成「大于等于」就变 main
    - Token 账本：剩余不能为负——不夹到 0 就会负数
    - Token 账本：总量 <= 0 表示不启用——只在 < 0 时禁用，0 会建出死账本
    - Token 账本：负消耗不计账——校验去掉后可以「刷回」预算
"""

from __future__ import annotations

from slice_defects._common import Injection

INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-tie-break-lost",
        file="app/application/usecases/catalog_search.py",
        defect_class="ordering",
        title="同分候选不再按 product_id 兜底排序，同一问句两次运行结果不同",
        rationale=(
            "注释写明「分数相同时按 product_id 兜底排序」，否则 Qdrant 版本/分片不同就会让召回"
            "指标无法复现。去掉第二个排序键后排序语句依然成立（仍按分数降序），"
            "只有并列时的顺序变回后端内部顺序——单看这行几乎无懈可击。"
        ),
        edits=(
            (
                "        filtered.sort(key=lambda item: (-item[0], item[1].product_id))\n",
                "        filtered.sort(key=lambda item: -item[0])\n",
            ),
        ),
        triggers_test="TestD1TieBreakByProductId::test_equal_scores_sorted_by_product_id",
    ),
    Injection(
        defect_id="d2-price-cap-boundary",
        file="app/application/usecases/catalog_search.py",
        defect_class="boundary",
        title="价格上限把「刚好等于上限」判成超预算",
        rationale=(
            "`price_max_major` 是买家的预算上限，等于上限应当通过。把 `<=` 改成 `<` 之后，"
            "语句仍是在比较价格与上限，读起来没有任何异常，只有边界值会被悄悄挡掉，"
            "而且会被记进 filtered_out 说明「超预算」。"
        ),
        edits=(
            (
                "        return primary_in_target.to_major_units() <= spec.price_max_major\n",
                "        return primary_in_target.to_major_units() < spec.price_max_major\n",
            ),
        ),
        triggers_test="TestD2PriceCapInclusive::test_price_equal_to_cap_is_kept",
    ),
    Injection(
        defect_id="d3-zero-score-candidates",
        file="app/application/usecases/catalog_search.py",
        defect_class="filter",
        title="关键词兜底把 0 分商品也带进候选集",
        rationale=(
            "关键词召回只应收录有命中的商品。`score > 0` 改成 `score >= 0` 后，全库商品都会进候选，"
            "再被 top_k 截断——表现为「搜索不到时会返回一堆无关商品」，而不是空结果。"
            "两行差异只有半个符号。"
        ),
        edits=(
            (
                "            if score > 0:\n                candidates.append((score, product))\n",
                "            if score >= 0:\n                candidates.append((score, product))\n",
            ),
        ),
        triggers_test="TestD3NoZeroScoreHits::test_unrelated_query_returns_nothing",
    ),
    Injection(
        defect_id="d4-context-ratios-swapped",
        file="app/application/agents/context_policy.py",
        defect_class="config",
        title="上下文压缩的触发比例与保留比例互换",
        rationale=(
            "口径是「占用达 75% 触发压缩、保留末段 15% 原文」。把两个值对调后，"
            "上下文刚到 15% 就压缩、且要保留 75% 原文，压缩几乎不做任何事。"
            "两个字段名都还在、类型也对，只有对照 docstring 才知道数值反了。"
        ),
        edits=(
            (
                "        trigger_ratio=0.75,\n        reserve_ratio=0.15,\n",
                "        trigger_ratio=0.15,\n        reserve_ratio=0.75,\n",
            ),
        ),
        triggers_test="TestD4ContextRatios::test_trigger_and_reserve_ratios",
    ),
    Injection(
        defect_id="d5-primary-sku-is-last",
        file="app/domain/catalog/product.py",
        defect_class="logic",
        title="primary_sku 取到了最后一个 Sku",
        rationale=(
            "`primary_sku()` 的语义是「首个 Sku」，商品卡的展示价、运费与关税都按它算。"
            "改成 `skus[-1]` 后，多规格商品（同一 SPU 下价格不同）会展示最贵那档的价格，"
            "而单规格商品完全看不出来——所以测试与日常都很难发现。"
        ),
        edits=(
            (
                "    def primary_sku(self) -> Sku:\n        return self.skus[0]\n",
                "    def primary_sku(self) -> Sku:\n        return self.skus[-1]\n",
            ),
        ),
        triggers_test="TestD5PrimarySkuIsFirst::test_primary_sku_is_the_first_one",
    ),
    Injection(
        defect_id="d6-top-k-validation-dropped",
        file="app/domain/catalog/product_search_spec.py",
        defect_class="validation",
        title="检索规格不再校验 top_k，top_k=0 静默返回空结果",
        rationale=(
            "`top_k` 必须为正整数，否则 `filtered[:0]` 会返回空列表——上层拿到的是"
            "「搜索成功但没有商品」，而不是一个能定位的参数错误。去掉这条校验后"
            "`__post_init__` 仍在，看起来只是「少检查了一个字段」。"
        ),
        edits=(
            (
                "        if self.top_k <= 0:\n"
                '            raise ValueError("ProductSearchSpec.top_k 必须为正整数")\n',
                "        # top_k 由调用方保证为正\n",
            ),
        ),
        triggers_test="TestD6TopKValidated::test_zero_top_k_is_rejected",
    ),
    Injection(
        defect_id="d7-budget-tier-boundary",
        file="app/infrastructure/budget.py",
        defect_class="boundary",
        title="剩余恰好 50% 被判成 main 档而不是 lite 档",
        rationale=(
            "档位表的下界是闭区间语义：剩余 50% 属于 lite（20%–50%）。把 `ratio > lower_bound` "
            "改成 `>=` 后，恰好落在 50% / 20% / 5% 的点会升一档，于是「预算刚好用掉一半」时"
            "仍走最贵的主模型。循环与阈值表都没动，只有比较符差一个字符。"
        ),
        edits=(
            (
                "        for lower_bound, tier in TIER_THRESHOLDS:\n            if ratio > lower_bound:\n",
                "        for lower_bound, tier in TIER_THRESHOLDS:\n            if ratio >= lower_bound:\n",
            ),
        ),
        triggers_test="TestD7BudgetTierBoundary::test_half_remaining_is_lite",
    ),
    Injection(
        defect_id="d8-budget-remaining-negative",
        file="app/infrastructure/budget.py",
        defect_class="boundary",
        title="已超支时剩余额度变成负数",
        rationale=(
            "`remaining` 的口径是「剩余不小于 0」。去掉 `max(0, ...)` 后超支会得到负数，"
            "而 `remaining_ratio` 仍会把它除成负数——`ratio > 0.50` 之类判断全部落空，"
            "表现是「超支后档位一直停在 fallback」，看起来像是设计如此。"
        ),
        edits=(
            (
                "        return max(0, self.total_limit - self.used)\n",
                "        return self.total_limit - self.used\n",
            ),
        ),
        triggers_test="TestD8RemainingNeverNegative::test_overdraft_clamps_to_zero",
    ),
    Injection(
        defect_id="d9-budget-zero-not-disabled",
        file="app/infrastructure/budget.py",
        defect_class="boundary",
        title="TOKEN_BUDGET_TOTAL=0 不再表示「不启用」，建出一个永远 fallback 的死账本",
        rationale=(
            "约定是「total_limit <= 0 表示不启用」，默认配置就是 0。改成 `< 0` 后，默认配置会"
            "建出一个 total=0 的账本，`remaining_ratio` 恒为 1.0 但 `charge` 立刻超支，"
            "于是所有请求都被降级。语句仍然是「小于等于/小于」的边界判断，很难一眼看出。"
        ),
        edits=(
            (
                "    if total_limit <= 0:\n        _budget_var.set(None)\n        return None\n",
                "    if total_limit < 0:\n        _budget_var.set(None)\n        return None\n",
            ),
        ),
        triggers_test="TestD9ZeroBudgetMeansDisabled::test_zero_total_returns_none",
    ),
    Injection(
        defect_id="d10-negative-charge-accepted",
        file="app/infrastructure/budget.py",
        defect_class="validation",
        title="负数 Token 消耗也记账，可以把预算「刷」回去",
        rationale=(
            "`charge` 只接受正数消耗，`tokens <= 0` 直接忽略。改成 `tokens == 0` 后，"
            "任何算出负数用量的调用方都会把 `used` 减下去——预算永不耗尽，"
            "四档降级形同虚设。函数签名与累加逻辑都没变。"
        ),
        edits=(
            (
                "    def charge(self, source: str, tokens: int) -> None:\n"
                "        if tokens <= 0:\n"
                "            return\n",
                "    def charge(self, source: str, tokens: int) -> None:\n"
                "        if tokens == 0:\n"
                "            return\n",
            ),
        ),
        triggers_test="TestD10NegativeChargeIgnored::test_negative_tokens_do_not_credit",
    ),
]

TEST_SOURCE = '''# -*- coding: utf-8 -*-
"""S2 注入版验真：每个缺陷一条测试，干净版全绿、注入版逐条打红。

全部走内存替身，不碰 Qdrant / 模型网关。
"""
from __future__ import annotations

import pytest

from app.application.agents.context_policy import build_context_config
from app.application.usecases.catalog_search import CatalogSearchUseCase
from app.domain.catalog.money import Money
from app.domain.catalog.product import Product
from app.domain.catalog.product_search_spec import ProductSearchSpec
from app.domain.catalog.sku import Sku
from app.infrastructure.budget import TokenBudget, init_budget


def make_product(product_id: str, price_minor: int = 10000, title: str = "alpha cup") -> Product:
    return Product(
        product_id=product_id,
        title=title,
        brand="globex",
        category="drinkware",
        origin_country="CN",
        description="stainless steel cup",
        highlights=[],
        ships_to=["US"],
        skus=[Sku(sku_id=f"{product_id}-S1", spec="std", price=Money.of(price_minor, "CNY"), stock=5)],
    )


class StubRepo:
    def __init__(self, products: list[Product]) -> None:
        self._products = products

    async def list_all(self) -> list[Product]:
        return list(self._products)

    async def find_by_ids(self, ids: list[str]) -> list[Product]:
        wanted = set(ids)
        return [p for p in self._products if p.product_id in wanted]


class TestD1TieBreakByProductId:
    async def test_equal_scores_sorted_by_product_id(self):
        # 两个商品可检索文本完全相同 → 关键词得分并列；仓储按 P2、P1 的顺序返回
        repo = StubRepo([make_product("P2"), make_product("P1")])
        result = await CatalogSearchUseCase(product_repo=repo).execute(
            ProductSearchSpec(normalized_query="alpha cup", top_k=2)
        )
        assert [hit["product_id"] for hit in result["hits"]] == ["P1", "P2"]


class TestD2PriceCapInclusive:
    async def test_price_equal_to_cap_is_kept(self):
        # 10000 分 = 100.0 主单位，上限也是 100.0 → 应当通过
        repo = StubRepo([make_product("P1", price_minor=10000)])
        result = await CatalogSearchUseCase(product_repo=repo).execute(
            ProductSearchSpec(normalized_query="alpha cup", top_k=1, price_max_major=100.0)
        )
        assert [hit["product_id"] for hit in result["hits"]] == ["P1"]


class TestD3NoZeroScoreHits:
    async def test_unrelated_query_returns_nothing(self):
        repo = StubRepo([make_product("P1", title="alpha cup")])
        result = await CatalogSearchUseCase(product_repo=repo).execute(
            ProductSearchSpec(normalized_query="zzz", top_k=3)
        )
        assert result["hits"] == []


class TestD4ContextRatios:
    def test_trigger_and_reserve_ratios(self):
        config = build_context_config(context_size=100_000, tool_result_limit=4_000)
        assert config.trigger_ratio == 0.75
        assert config.reserve_ratio == 0.15


class TestD5PrimarySkuIsFirst:
    def test_primary_sku_is_the_first_one(self):
        product = Product(
            product_id="P1",
            title="alpha cup",
            brand="globex",
            category="drinkware",
            origin_country="CN",
            description="d",
            skus=[
                Sku(sku_id="S-CHEAP", spec="basic", price=Money.of(1000, "CNY"), stock=1),
                Sku(sku_id="S-PREMIUM", spec="pro", price=Money.of(9000, "CNY"), stock=1),
            ],
        )
        assert product.primary_sku().sku_id == "S-CHEAP"


class TestD6TopKValidated:
    def test_zero_top_k_is_rejected(self):
        with pytest.raises(ValueError):
            ProductSearchSpec(normalized_query="alpha cup", top_k=0)


class TestD7BudgetTierBoundary:
    def test_half_remaining_is_lite(self):
        budget = TokenBudget(total_limit=1000, used=500)
        assert budget.remaining_ratio == 0.5
        assert budget.tier == "lite"


class TestD8RemainingNeverNegative:
    def test_overdraft_clamps_to_zero(self):
        budget = TokenBudget(total_limit=100, used=150)
        assert budget.remaining == 0


class TestD9ZeroBudgetMeansDisabled:
    def test_zero_total_returns_none(self):
        assert init_budget(0) is None


class TestD10NegativeChargeIgnored:
    def test_negative_tokens_do_not_credit(self):
        budget = TokenBudget(total_limit=1000)
        budget.charge("upstream", -500)
        assert budget.used == 0
'''
