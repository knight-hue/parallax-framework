"""S3-orchestration 的注入规格：10 个缺陷，落在 3 个文件。

S3 的代码主体是护栏（harness）与订单聚合，契约都写在 docstring 里，
所以这一批全是「实现悄悄放宽了写下来的约定」：

    - Schema 断言：`[error]` 文本不是 JSON，不算违约——去掉后错误返回全被判违约
    - 顺序断言：硬拒的前提是「有观测证据」——去掉后恢复态的合法下单被误杀
    - 必需字段表：product_search 要回 hits 与 recall_strategy——少一条就放过
    - 漂移轨迹：只留最近 3 轮动作——写成删前 3 条
    - 检测节拍：0 轮不该判漂移——去掉轮次判断后一开局就说你漂了
    - 探索发散：连续空结果在成功时必须归零——不归零会累积成假发散
    - 订单不变量：全部订单行币种一致——校验删掉后混币订单能建出来
    - 取消：reason 不能是纯空白——放宽成「非空」后空格也算理由
    - 取消：只有 CONFIRMED 可以取消——改成只挡已取消，草稿单也能取消
    - 合计：每条订单行只累加一次——首行被重复累加，总额虚高
"""

from __future__ import annotations

from slice_defects._common import Injection

INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-error-text-counted-as-schema-violation",
        file="app/application/harness/assertions.py",
        defect_class="logic",
        title="工具错误返回被当成 JSON 解析失败，Schema 断言误报",
        rationale=(
            "工具失败时返回的是 `[error] ...` 文本，模块 docstring 明确「不算 schema 违约」。"
            "去掉这段特判后，任何一次工具报错都会追加一条「返回结构异常」，"
            "模型下一轮会以为是自己参数写错，而不是上游失败——误导方向刚好相反。"
        ),
        edits=(
            (
                "    if isinstance(tool_result, str):\n"
                '        # 工具错误返回是 "[error] ..." 文本，不是 JSON——不算 schema 违约\n'
                '        if tool_result.lstrip().startswith("[error]"):\n'
                "            return outcome\n"
                "        try:\n",
                "    if isinstance(tool_result, str):\n        try:\n",
            ),
        ),
        triggers_test="TestD1ErrorTextNotSchemaViolation::test_error_text_has_no_failures",
    ),
    Injection(
        defect_id="d2-hard-reject-without-evidence",
        file="app/application/harness/assertions.py",
        defect_class="logic",
        title="写路径前置校验不再要求「有观测证据」，恢复态下单被误杀",
        rationale=(
            "docstring 说明：会话可能从快照恢复，内存里没有任何调用记录，硬拒会把合法下单误杀，"
            "所以规则是「有观测到调用却没检索过才硬拒」。去掉 `and history` 后，"
            "刚恢复的会话第一次下单会被直接硬拒，而判断语句本身看起来仍然合理。"
        ),
        edits=(
            (
                "            if tool_name in HARD_REJECT_TOOLS and history:\n",
                "            if tool_name in HARD_REJECT_TOOLS:\n",
            ),
        ),
        triggers_test="TestD2HardRejectNeedsEvidence::test_no_history_only_warns",
    ),
    Injection(
        defect_id="d3-required-field-dropped",
        file="app/application/harness/assertions.py",
        defect_class="config",
        title="product_search 的必需字段少了一个，凭 recall_strategy 造假无人发现",
        rationale=(
            "`recall_strategy` 是检索降级链的自述字段，模型据此判断这次召回是向量还是关键词。"
            "从必需字段表里删掉后，缺这个字段的返回会被判「结构完整」，"
            "模型拿不到降级信息却仍以为结果可信。表里其余项都在，很难察觉少了一行。"
        ),
        edits=(
            (
                '    "product_search_tool": ("hits", "recall_strategy"),\n',
                '    "product_search_tool": ("hits",),\n',
            ),
        ),
        triggers_test="TestD3RecallStrategyRequired::test_missing_recall_strategy_fails",
    ),
    Injection(
        defect_id="d4-recent-actions-window-wrong",
        file="app/application/harness/drift_detector.py",
        defect_class="boundary",
        title="漂移轨迹保留的是最早 3 轮而不是最近 3 轮",
        rationale=(
            "`del trace.recent_actions[:-3]` 的语义是「只留最近 3 轮」。写成 `[:3]` 后，"
            "列表长度约束仍然成立（不会无限增长），但留下的是会话开头的动作，"
            "于是「目标遗忘」信号永远在看最久远的行为，漂移永远检测不出来。"
        ),
        edits=(
            (
                "        del trace.recent_actions[:-3]  # 只留最近 3 轮\n",
                "        del trace.recent_actions[:3]  # 只留最近 3 轮\n",
            ),
        ),
        triggers_test="TestD4RecentActionsWindow::test_keeps_last_three_actions",
    ),
    Injection(
        defect_id="d5-due-before-any-round",
        file="app/application/harness/drift_detector.py",
        defect_class="boundary",
        title="还没跑任何一轮就判定该做漂移检测",
        rationale=(
            "`due()` 的口径是「跑过轮次且到了检测节拍」。去掉 `trace.rounds > 0` 后，"
            "0 % 3 == 0 成立，于是会话刚开始就说「你已偏离原始诉求」，"
            "把纠正提示塞进第一轮，直接污染模型的初始行为。"
        ),
        edits=(
            (
                "        return trace.rounds > 0 and trace.rounds % self.check_interval == 0\n",
                "        return trace.rounds % self.check_interval == 0\n",
            ),
        ),
        triggers_test="TestD5DueNeedsRounds::test_fresh_session_is_not_due",
    ),
    Injection(
        defect_id="d6-consecutive-empty-never-resets",
        file="app/application/harness/drift_detector.py",
        defect_class="logic",
        title="检索成功不清零「连续空结果」，发散信号会累积成假阳性",
        rationale=(
            "`consecutive_empty` 的语义是「连续」——一旦有非空结果就必须归零。"
            "把 else 分支改成保持原值后，整个会话里累计 3 次空结果就会触发「探索发散」，"
            "哪怕中间有大量成功检索。三元表达式依旧成立，很难一眼看出。"
        ),
        edits=(
            (
                "        trace.consecutive_empty = trace.consecutive_empty + 1 if result_empty else 0\n",
                "        trace.consecutive_empty = (\n"
                "            trace.consecutive_empty + 1 if result_empty else trace.consecutive_empty\n"
                "        )\n",
            ),
        ),
        triggers_test="TestD6EmptyStreakResets::test_success_resets_streak",
    ),
    Injection(
        defect_id="d7-order-currency-consistency-dropped",
        file="app/domain/order/order.py",
        defect_class="validation",
        title="订单行币种一致性校验被删，混币订单可以直接建出来",
        rationale=(
            "不变量里写明「全部订单行币种一致」，否则合计金额没有意义。删掉这段校验后，"
            "`__post_init__` 里仍有 order_id / buyer_id / lines 三项检查，"
            "看起来只是「少了一条不常用的规则」，直到 `total_amount()` 抛币种不一致才暴露。"
        ),
        edits=(
            (
                "        currencies = {line.unit_price.currency for line in self.lines}\n"
                "        if len(currencies) > 1:\n"
                '            raise ValueError(f"Order 订单行币种不一致：{currencies}")\n',
                "        # 币种一致性由下单用例在组装订单行时保证\n",
            ),
        ),
        triggers_test="TestD7OrderLinesSingleCurrency::test_mixed_currency_is_rejected",
    ),
    Injection(
        defect_id="d8-cancel-blank-reason-accepted",
        file="app/domain/order/order.py",
        defect_class="validation",
        title="取消理由允许纯空白",
        rationale=(
            "`cancel(reason)` 要求理由非空且非纯空白——纯空白理由会让运营侧无法判断取消原因。"
            "把 `not reason or not reason.strip()` 放宽成 `not reason` 后，"
            "`cancel('   ')` 会被接受，而校验语句看上去依然是在拦空值。"
        ),
        edits=(
            (
                "        if not reason or not reason.strip():\n",
                "        if not reason:\n",
            ),
        ),
        triggers_test="TestD8CancelReasonNotBlank::test_whitespace_reason_rejected",
    ),
    Injection(
        defect_id="d9-cancel-allowed-from-draft",
        file="app/domain/order/order.py",
        defect_class="state_machine",
        title="状态机放宽成「只有已取消不能取消」，草稿单也能取消",
        rationale=(
            "状态机是 DRAFT → CONFIRMED → CANCELLED，只有 CONFIRMED 可以取消。"
            "把守卫改成「已取消的不能再取消」后，语义听起来更宽松也更合理，"
            "于是未确认的草稿单也能被取消并写入 cancelled_at，库存与事件口径全乱。"
        ),
        edits=(
            (
                "        if self.status is not OrderStatus.CONFIRMED:\n"
                '            raise ValueError(f"仅 CONFIRMED 态可取消，当前={self.status.value}：{self.order_id}")\n',
                "        if self.status is OrderStatus.CANCELLED:\n"
                '            raise ValueError(f"已取消的订单不能重复取消，当前={self.status.value}：{self.order_id}")\n',
            ),
        ),
        triggers_test="TestD9CancelRequiresConfirmed::test_draft_cannot_be_cancelled",
    ),
    Injection(
        defect_id="d10-total-double-counts-first-line",
        file="app/domain/order/order.py",
        defect_class="logic",
        title="合计金额把第一条订单行算了两遍",
        rationale=(
            "`total_amount` 先取首行小计，再从第二行开始累加。把 `self.lines[1:]` 改成 "
            "`self.lines` 后，循环体与初值都没动、代码更简短，只有金额虚高——"
            "而快照里的总额是模型唯一允许引用的数字，错了会直接报给买家。"
        ),
        edits=(
            (
                "        total = self.lines[0].subtotal()\n        for line in self.lines[1:]:\n",
                "        total = self.lines[0].subtotal()\n        for line in self.lines:\n",
            ),
        ),
        triggers_test="TestD10TotalCountsEachLineOnce::test_two_lines_sum_exactly",
    ),
]

TEST_SOURCE = '''# -*- coding: utf-8 -*-
"""S3 注入版验真：每个缺陷一条测试，干净版全绿、注入版逐条打红。

护栏与漂移检测都是纯逻辑，订单聚合是纯领域对象——全部零 I/O、零模型调用。
"""
from __future__ import annotations

import pytest

from app.application.harness.assertions import SequencingTracker, check_schema
from app.application.harness.drift_detector import DriftDetector
from app.domain.catalog.money import Money
from app.domain.order.address import Address
from app.domain.order.order import Order, OrderStatus
from app.domain.order.order_line import OrderLine


def make_address() -> Address:
    return Address(
        recipient_name="Li Lei",
        country="US",
        state="CA",
        city="SF",
        address_line="1 Market St",
        postal_code="94105",
        phone="000",
    )


def make_line(product_id: str = "P1", currency: str = "CNY", price: int = 1000, quantity: int = 1) -> OrderLine:
    return OrderLine(
        product_id=product_id,
        sku_id=f"{product_id}-S1",
        title="alpha cup",
        unit_price=Money.of(price, currency),
        quantity=quantity,
    )


class TestD1ErrorTextNotSchemaViolation:
    def test_error_text_has_no_failures(self):
        outcome = check_schema("create_order_tool", "[error] upstream timeout")
        assert outcome.failures == []


class TestD2HardRejectNeedsEvidence:
    def test_no_history_only_warns(self):
        tracker = SequencingTracker()
        outcome = tracker.check("fresh-session", "create_order_tool")
        assert outcome.rejected is False
        assert outcome.warnings


class TestD3RecallStrategyRequired:
    def test_missing_recall_strategy_fails(self):
        outcome = check_schema("product_search_tool", '{"hits": []}')
        assert outcome.failures and "recall_strategy" in outcome.failures[0]["reason"]


class TestD4RecentActionsWindow:
    def test_keeps_last_three_actions(self):
        detector = DriftDetector()
        for index in range(5):
            detector.observe_action("s1", f"act-{index}")
        trace = detector._traces["s1"]
        assert trace.recent_actions == ["act-2", "act-3", "act-4"]


class TestD5DueNeedsRounds:
    def test_fresh_session_is_not_due(self):
        detector = DriftDetector()
        detector.start_turn("s1", "旅行三件套")
        assert detector.due("s1") is False


class TestD6EmptyStreakResets:
    def test_success_resets_streak(self):
        detector = DriftDetector()
        detector.observe_action("s1", "a", result_empty=True)
        detector.observe_action("s1", "b", result_empty=True)
        detector.observe_action("s1", "c", result_empty=False)
        detector.observe_action("s1", "d", result_empty=True)
        assert detector._traces["s1"].consecutive_empty == 1


class TestD7OrderLinesSingleCurrency:
    def test_mixed_currency_is_rejected(self):
        with pytest.raises(ValueError):
            Order(
                order_id="O1",
                buyer_id="B1",
                shipping_address=make_address(),
                lines=[make_line("P1", "CNY"), make_line("P2", "USD")],
            )


class TestD8CancelReasonNotBlank:
    def test_whitespace_reason_rejected(self):
        order = Order.place(
            order_id="O1",
            buyer_id="B1",
            shipping_address=make_address(),
            lines=[make_line()],
        )
        with pytest.raises(ValueError):
            order.cancel("   ")


class TestD9CancelRequiresConfirmed:
    def test_draft_cannot_be_cancelled(self):
        order = Order(
            order_id="O1",
            buyer_id="B1",
            shipping_address=make_address(),
            lines=[make_line()],
        )
        assert order.status is OrderStatus.DRAFT
        with pytest.raises(ValueError):
            order.cancel("买家反悔")


class TestD10TotalCountsEachLineOnce:
    def test_two_lines_sum_exactly(self):
        order = Order.place(
            order_id="O1",
            buyer_id="B1",
            shipping_address=make_address(),
            lines=[make_line("P1", price=1000), make_line("P2", price=2000)],
        )
        assert order.total_amount().amount_in_minor_units == 3000
'''
