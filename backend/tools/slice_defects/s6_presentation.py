"""S6-presentation 的注入规格：10 个缺陷，落在 2 个持久化文件。

S6 的主题是「持久化与迁移」，所以缺陷全部选在**表结构与文件存储的契约**上：
每一条都写在 docstring 或注释里，改完代码仍然自洽，只有对照契约或用真实
SQLite / 临时目录跑一遍才会暴露。

    - 自增主键必须带 sqlite variant——去掉后 SQLite 上主键不能自增
    - 偏好唯一约束是 buyer+kind+statement——少一列就撞车
    - 对话消息索引要覆盖 (session_id, turn_index)——少一列等于只按会话查
    - order_items 必须外键到 orders——去掉后可以插入孤儿订单行
    - sku_stocks.version 默认 0——去掉后插入即违反非空
    - 文件名清洗防路径穿越——不清洗就能写出目录外
    - 偏好追加要按 (statement, kind) 去重——只看 statement 会把另一面吃掉
    - JSONL 必须追加写——用 "w" 会让每次追加覆盖掉整份流水
    - list_turns 必须跳过事件行——不跳就把事件当对话解析
    - delete 按 statement 精确匹配、不分 kind——只删 dislike 会留下 like
"""

from __future__ import annotations

from slice_defects._common import Injection

TABLES = "app/infrastructure/persistence/sql/tables.py"
STORES = "app/infrastructure/persistence/json_file_stores.py"

INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-auto-pk-loses-sqlite-variant",
        file=TABLES,
        defect_class="migration",
        title="自增主键丢掉 SQLite 变体，内存库上主键不能自增",
        rationale=(
            "注释写明：SQLite 的 AUTOINCREMENT 只能用于 INTEGER PRIMARY KEY，故用 "
            "`BigInteger().with_variant(Integer, \"sqlite\")`。去掉 variant 后建表仍然成功，"
            "但 SQLite 里该列是 BIGINT，不是 rowid 别名，插入不带 id 就会违反非空——"
            "生产库（PG）完全正常，只有单测与本地 SQLite 会炸，极易被当成环境问题。"
        ),
        edits=(
            (
                '_AutoPk = BigInteger().with_variant(Integer, "sqlite")\n',
                "_AutoPk = BigInteger\n",
            ),
        ),
        triggers_test="TestD1AutoPkOnSqlite::test_message_row_gets_an_id",
    ),
    Injection(
        defect_id="d2-preference-unique-key-narrowed",
        file=TABLES,
        defect_class="constraint",
        title="偏好唯一约束少了 kind 列，同一句话记不成 like 与 dislike",
        rationale=(
            "口径是 buyer+kind+statement 唯一：同一句话可以既是「喜欢」也是「不能接受」"
            "（例如「要静音的」既可喜欢也可当硬约束）。约束缩成 buyer+statement 后，"
            "建表、迁移、单测都照常通过，只有真的同时记两面时才撞唯一键。"
        ),
        edits=(
            (
                '        UniqueConstraint("buyer_id", "kind", "statement", name="uq_pref_buyer_kind_statement"),\n',
                '        UniqueConstraint("buyer_id", "statement", name="uq_pref_buyer_kind_statement"),\n',
            ),
        ),
        triggers_test="TestD2PreferenceUniqueKey::test_same_statement_two_kinds_allowed",
    ),
    Injection(
        defect_id="d3-message-index-drops-turn",
        file=TABLES,
        defect_class="index",
        title="对话消息索引只剩 session_id，按轮次取流水退化成全表扫",
        rationale=(
            "索引名 `ix_msg_session_turn` 与建表语句都表明它覆盖 (session_id, turn_index)，"
            "这正是 list_turns 的查询形态。少一列后索引仍然建得出来、名字也仍然贴切，"
            "只是「按会话取最近 N 轮」变成先捞全量再过滤——数据量小完全看不出来。"
        ),
        edits=(
            (
                '    __table_args__ = (Index("ix_msg_session_turn", "session_id", "turn_index"),)\n',
                '    __table_args__ = (Index("ix_msg_session_turn", "session_id"),)\n',
            ),
        ),
        triggers_test="TestD3MessageIndexCoversTurn::test_index_has_both_columns",
    ),
    Injection(
        defect_id="d4-order-line-loses-foreign-key",
        file=TABLES,
        defect_class="constraint",
        title="订单行不再外键到订单，孤儿行可以静默写入",
        rationale=(
            "order_items.order_id 指向 orders.order_id 是这张表唯一的引用完整性保障。"
            "去掉 ForeignKey 后列名、类型、索引都在，建表与读写全部正常，"
            "只有删除订单或写入错误 order_id 时才会留下无法追溯的孤儿行。"
        ),
        edits=(
            (
                '    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), index=True)\n',
                "    order_id: Mapped[str] = mapped_column(String(32), index=True)\n",
            ),
        ),
        triggers_test="TestD4OrderLineForeignKey::test_foreign_key_exists",
    ),
    Injection(
        defect_id="d5-sku-stock-version-no-default",
        file=TABLES,
        defect_class="default",
        title="库存行的 version 不再默认 0，插入即违反非空",
        rationale=(
            "`version` 用于乐观锁观测，注释说明「每次变更 +1」，所以新行必须从 0 起。"
            "去掉 default 后列定义依旧存在，只有真的插入一条库存行才会因为 NULL 失败——"
            "而失败点在下单链路深处，看起来像是库存服务的问题。"
        ),
        edits=(
            (
                "    version: Mapped[int] = mapped_column(Integer, default=0)\n",
                "    version: Mapped[int] = mapped_column(Integer)\n",
            ),
        ),
        triggers_test="TestD5SkuStockVersionDefault::test_new_row_starts_at_zero",
    ),
    Injection(
        defect_id="d6-path-traversal-not-sanitized",
        file=STORES,
        defect_class="security",
        title="文件名清洗被取消，买家 ID 里的路径片段会写到目录外",
        rationale=(
            "`_safe_name` 的白名单过滤是唯一的路径穿越防线（买家 ID 来自请求参数）。"
            "改成直接返回原值后，函数还在、还被调用，签名也没变，"
            "但 `../../x` 这样的 ID 会把偏好文件写到数据目录之外。"
        ),
        edits=(
            (
                '    safe = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")\n'
                '    return safe or "anonymous"\n',
                '    return raw or "anonymous"\n',
            ),
        ),
        triggers_test="TestD6SafeNameStripsPath::test_path_separators_removed",
    ),
    Injection(
        defect_id="d7-preference-dedupe-ignores-kind",
        file=STORES,
        defect_class="logic",
        title="偏好追加只按 statement 去重，把另一面吃掉",
        rationale=(
            "去重口径是 (statement, kind)：同一句话允许同时是 like 与 dislike。"
            "去掉 kind 后，「我要静音的」先记为 dislike 再记为 like 会被静默丢弃，"
            "买家看到的偏好列表少了一半，而代码只是少了一个 and 条件。"
        ),
        edits=(
            (
                "        if any(p.statement == preference.statement and p.kind == preference.kind for p in existing):\n",
                "        if any(p.statement == preference.statement for p in existing):\n",
            ),
        ),
        triggers_test="TestD7DedupeKeepsBothKinds::test_same_statement_two_kinds_both_stored",
    ),
    Injection(
        defect_id="d8-jsonl-append-becomes-overwrite",
        file=STORES,
        defect_class="io",
        title="JSONL 流水改成覆盖写，每次追加都把历史抹掉",
        rationale=(
            "模块 docstring 写明「一行一条记录，追加写不覆盖」。把 `open(\"a\")` 改成 "
            "`open(\"w\")` 后，方法名 `_append_line` 与调用点都没变，"
            "单次写入的测试也照常通过，只有连续两轮对话才会发现只剩最后一条。"
        ),
        edits=(
            (
                '        with self._path(session_id).open("a", encoding="utf-8") as handle:\n',
                '        with self._path(session_id).open("w", encoding="utf-8") as handle:\n',
            ),
        ),
        triggers_test="TestD8JsonlAppends::test_two_turns_both_persisted",
    ),
    Injection(
        defect_id="d9-list-turns-includes-events",
        file=STORES,
        defect_class="filter",
        title="list_turns 不再跳过事件行，把过程事件当对话解析",
        rationale=(
            "同一个 JSONL 里混着 turn 与 event 两类记录，list_turns 只应收录 turn。"
            "把 `kind != \"turn\"` 放宽成「只要 kind 存在就继续」后，事件行会走到 "
            "`record[\"role\"]` 直接 KeyError——表现为「有事件就没法恢复对话」。"
        ),
        edits=(
            (
                '            if record.get("kind") != "turn":\n                continue\n',
                '            if record.get("kind") is None:\n                continue\n',
            ),
        ),
        triggers_test="TestD9ListTurnsSkipsEvents::test_events_are_not_turns",
    ),
    Injection(
        defect_id="d10-delete-only-removes-dislike",
        file=STORES,
        defect_class="logic",
        title="按 statement 删除退化成「只删 dislike」，like 那条被留下",
        rationale=(
            "docstring 明确：按 statement 精确匹配、**不分 kind**——买家说「以后别管塑料了」"
            "表达的是忘掉这条说法，而不是只忘掉负向那一面。改成只删 dislike 后，"
            "函数仍然返回 True、仍然写回文件，只是列表里悄悄剩下了同名的 like。"
        ),
        edits=(
            (
                "        remaining = [p for p in existing if p.statement != statement]\n",
                '        remaining = [\n'
                "            p\n"
                "            for p in existing\n"
                '            if not (p.statement == statement and p.kind == "dislike")\n'
                "        ]\n",
            ),
        ),
        triggers_test="TestD10DeleteRemovesAllKinds::test_delete_by_statement_only",
    ),
]

TEST_SOURCE = '''# -*- coding: utf-8 -*-
"""S6 注入版验真：每个缺陷一条测试，干净版全绿、注入版逐条打红。

表结构用真实 sqlite 内存库验，文件存储用 pytest 的 tmp_path 验——不走 mock。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.domain.buyer.preference import BuyerPreference
from app.domain.session.ports.conversation_store import (
    ConversationEventRecord,
    ConversationTurn,
)
from app.infrastructure.persistence.json_file_stores import (
    JsonFileConversationStore,
    JsonFilePreferenceStore,
    _safe_name,
)
from app.infrastructure.persistence.sql.tables import (
    Base,
    BuyerPreferenceRow,
    ConversationMessageRow,
    SkuStockRow,
)


def make_engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


class TestD1AutoPkOnSqlite:
    def test_message_row_gets_an_id(self):
        engine = make_engine()
        with Session(engine) as session:
            session.add(
                ConversationMessageRow(session_id="s1", turn_index=0, role="buyer", content="hi")
            )
            session.commit()
            row = session.scalar(select(ConversationMessageRow))
            assert row is not None and row.id is not None


class TestD2PreferenceUniqueKey:
    def test_same_statement_two_kinds_allowed(self):
        engine = make_engine()
        with Session(engine) as session:
            session.add(BuyerPreferenceRow(buyer_id="b1", kind="like", statement="要静音的", created_at="t"))
            session.add(BuyerPreferenceRow(buyer_id="b1", kind="dislike", statement="要静音的", created_at="t"))
            session.commit()


class TestD3MessageIndexCoversTurn:
    def test_index_has_both_columns(self):
        engine = make_engine()
        indexes = inspect(engine).get_indexes("conversation_messages")
        target = next(i for i in indexes if i["name"] == "ix_msg_session_turn")
        assert target["column_names"] == ["session_id", "turn_index"]


class TestD4OrderLineForeignKey:
    def test_foreign_key_exists(self):
        engine = make_engine()
        foreign_keys = inspect(engine).get_foreign_keys("order_items")
        assert any(fk["referred_table"] == "orders" for fk in foreign_keys)


class TestD5SkuStockVersionDefault:
    def test_new_row_starts_at_zero(self):
        engine = make_engine()
        with Session(engine) as session:
            session.add(SkuStockRow(sku_id="S1", stock=5))
            session.commit()
            row = session.get(SkuStockRow, "S1")
            assert row is not None and row.version == 0


class TestD6SafeNameStripsPath:
    def test_path_separators_removed(self):
        cleaned = _safe_name("../../etc/passwd")
        assert "/" not in cleaned
        assert ".." not in cleaned


class TestD7DedupeKeepsBothKinds:
    async def test_same_statement_two_kinds_both_stored(self, tmp_path):
        store = JsonFilePreferenceStore(tmp_path)
        await store.append(BuyerPreference(buyer_id="b1", kind="like", statement="要静音的"))
        await store.append(BuyerPreference(buyer_id="b1", kind="dislike", statement="要静音的"))
        assert len(await store.list_by_buyer("b1")) == 2


class TestD8JsonlAppends:
    async def test_two_turns_both_persisted(self, tmp_path):
        store = JsonFileConversationStore(tmp_path)
        await store.append_turn(
            ConversationTurn(session_id="s1", buyer_id="b1", role="buyer", content="第一句")
        )
        await store.append_turn(
            ConversationTurn(session_id="s1", buyer_id="b1", role="buyer", content="第二句")
        )
        assert len(await store.list_turns("s1")) == 2


class TestD9ListTurnsSkipsEvents:
    async def test_events_are_not_turns(self, tmp_path):
        store = JsonFileConversationStore(tmp_path)
        await store.append_turn(
            ConversationTurn(session_id="s1", buyer_id="b1", role="buyer", content="第一句")
        )
        await store.append_events(
            [
                ConversationEventRecord(
                    session_id="s1", type="tool.result", payload={"tool": "product_search_tool"}
                )
            ]
        )
        turns = await store.list_turns("s1")
        assert [t.content for t in turns] == ["第一句"]


class TestD10DeleteRemovesAllKinds:
    async def test_delete_by_statement_only(self, tmp_path):
        store = JsonFilePreferenceStore(tmp_path)
        await store.append(BuyerPreference(buyer_id="b1", kind="like", statement="要静音的"))
        await store.append(BuyerPreference(buyer_id="b1", kind="dislike", statement="要静音的"))
        assert await store.delete("b1", "要静音的") is True
        assert await store.list_by_buyer("b1") == []
'''
