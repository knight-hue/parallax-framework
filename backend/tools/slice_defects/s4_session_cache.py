"""S4-session-cache 的注入规格：11 个缺陷，落在 6 个文件。

选材原则与 S1 一致：**单看自洽、对照才矛盾**。这一批几乎全是「实现悄悄改掉了
docstring 里写死的安全约束」，而不是少写一行校验那种一眼可见的错：

    - 偏好：`dislike` 是安全底线（不参与 top_k 截断）——被「总预算」吃掉
    - 偏好：预算为 0 时不注入任何偏好——把黑名单一起丢了
    - 偏好：相关性排序后要复原原始行序——直接返回排序结果
    - Money：`bool` 是 `int` 的子类——`Money.of(True)` 会静默变成 1 分
    - CachedEmbedding：key 里必须带模型名——换模型后拿到别的模型的向量
    - CachedEmbedding：上游少返回必须炸——静默补空向量
    - 语义缓存：会话内多轮不命中——`has_history` 被漏检
    - 语义缓存：失败回复绝不进缓存——`[error]` 被存下来反复复用
    - 语义缓存：桶 key 带偏好指纹——偏好撤回后旧回复必须失效
    - 语义缓存：桶内保留最近 N 条——保留成最旧 N 条
    - 输出审核：API Key 形态要脱敏——模式表里少一条
"""

from __future__ import annotations

from slice_defects._common import Injection

INJECTIONS: list[Injection] = [
    Injection(
        defect_id="d1-dislikes-truncated-by-total-budget",
        file="app/application/memory/preference_selector.py",
        defect_class="logic",
        title="总预算截断把 dislike 一起吃掉，黑名单被降级成普通偏好",
        rationale=(
            "PreferenceSelector 的安全底线是「dislike 全量保留，不参与 top_k 截断」，"
            "否则 query「推荐个咖啡杯」与「不要塑料」相似度极低时，黑名单会被排到末尾丢掉。"
            "改成对合并结果统一取 [:top_k] 后，读起来像「尊重预算」，实际把安全底线变成可裁剪项。"
        ),
        edits=(
            ("        return dislikes + selected_likes\n", "        return (dislikes + selected_likes)[:top_k]\n"),
        ),
        triggers_test="TestD1DislikesNotTruncated::test_all_dislikes_survive_total_budget",
    ),
    Injection(
        defect_id="d2-zero-budget-drops-dislikes",
        file="app/application/memory/preference_selector.py",
        defect_class="boundary",
        title="预算为 0 时把 dislike 也一起丢掉",
        rationale=(
            "`top_k <= 0` 的语义是「正向偏好全部让位，只保留安全底线」，所以早退返回 dislikes。"
            "改成返回空列表后，注释也跟着改成「不注入任何偏好」，单看这段完全自洽。"
        ),
        edits=(
            (
                "        if top_k <= 0:\n"
                "            # 只保留安全底线，正向偏好全部让位\n"
                "            return dislikes\n",
                "        if top_k <= 0:\n"
                "            # 预算为 0 时不注入任何偏好\n"
                "            return []\n",
            ),
        ),
        triggers_test="TestD2ZeroBudgetKeepsDislikes::test_zero_top_k_still_returns_dislikes",
    ),
    Injection(
        defect_id="d3-relevance-ranking-keeps-sorted-order",
        file="app/application/memory/preference_selector.py",
        defect_class="ordering",
        title="相关性排序后直接返回排序结果，注入块行序每轮抖动",
        rationale=(
            "`_rank_by_relevance` 必须「挑出 top_k 后回到原始相对顺序」，否则同一批偏好在不同 query 下"
            "行序不同，重复注入时 Prompt Cache 前缀一直变。改成直接返回 picked 后，"
            "结果集合正确、只有顺序变了——单看返回值内容很难发现。"
        ),
        edits=(
            (
                "        return [p for p in likes if p in picked]\n",
                "        return picked\n",
            ),
        ),
        triggers_test="TestD3RankingRestoresOriginalOrder::test_output_follows_original_order",
    ),
    Injection(
        defect_id="d4-money-accepts-bool",
        file="app/domain/catalog/money.py",
        defect_class="type",
        title="Money.of 把 bool 当整数收下，金额静默变成 1 分",
        rationale=(
            "`bool` 是 `int` 的子类，`isinstance(True, int)` 为真。原实现专门挡了 `isinstance(amount, bool)`，"
            "去掉后 `Money.of(True, 'USD')` 会返回 1 分而不报错——上游若把 YAML 的 `true` 当数量传进来，"
            "错误会一路流到结算。判断语句看起来仍然「校验了类型」。"
        ),
        edits=(
            (
                "        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:\n",
                "        if not isinstance(amount, int) or amount < 0:\n",
            ),
        ),
        triggers_test="TestD4MoneyRejectsBool::test_bool_amount_is_rejected",
    ),
    Injection(
        defect_id="d5-conversation-role-unchecked",
        file="app/domain/session/ports/conversation_store.py",
        defect_class="validation",
        title="对话轮次的 role 不再校验，脏角色进流水",
        rationale=(
            "ConversationTurn 的不变量是 role ∈ (buyer, agent)。删掉这条校验后，"
            "`role='system'` 的轮次会被正常写入并被 list_turns 读出来喂回上下文，"
            "而 `__post_init__` 仍在，看起来只是「少了一个字段的检查」。"
        ),
        edits=(
            (
                "    def __post_init__(self) -> None:\n"
                "        if self.role not in VALID_ROLES:\n"
                '            raise ValueError(f"ConversationTurn.role 必须是 {VALID_ROLES}：{self.role}")\n'
                "        if not self.session_id:\n"
                '            raise ValueError("ConversationTurn.session_id required")\n',
                "    def __post_init__(self) -> None:\n"
                "        if not self.session_id:\n"
                '            raise ValueError("ConversationTurn.session_id required")\n',
            ),
        ),
        triggers_test="TestD5ConversationRoleChecked::test_invalid_role_is_rejected",
    ),
    Injection(
        defect_id="d6-embedding-key-drops-model",
        file="app/infrastructure/cache/cached_embedding_client.py",
        defect_class="cache_key",
        title="embedding 缓存 key 丢掉模型名，换模型后拿到旧模型的向量",
        rationale=(
            "key 的契约是 sha256(model + text)：embedding 是「同模型同文本才同向量」，"
            "换模型后必须全部未命中。去掉模型名后，换模型仍会命中旧向量，"
            "语义检索结果悄悄退化成上一个模型的——缓存命中率还变好看了。"
        ),
        edits=(
            (
                '        digest = hashlib.sha256(f"{self._model}\\n{text}".encode()).hexdigest()\n'
                '        return f"emb:{self._model}:{digest}"\n',
                "        digest = hashlib.sha256(text.encode()).hexdigest()\n"
                '        return f"emb:{digest}"\n',
            ),
        ),
        triggers_test="TestD6EmbeddingKeyIncludesModel::test_different_models_do_not_share_cache",
    ),
    Injection(
        defect_id="d7-embedding-missing-silently-emptied",
        file="app/infrastructure/cache/cached_embedding_client.py",
        defect_class="error_handling",
        title="上游少返回向量时静默补空列表，不报错",
        rationale=(
            "原实现刻意在最后做一次 None 检查并抛 RuntimeError——「不静默补零向量」是写在注释里的约定。"
            "改成 `vector or []` 之后，向量维度对不上只会让余弦相似度恒为 0，"
            "表现为「语义检索突然不工作」，而不是一个能定位的异常。"
        ),
        edits=(
            (
                "        # 到这里不应再有 None；若上游少返回则直接暴露，不静默补零向量\n"
                "        missing = [index for index, vector in enumerate(results) if vector is None]\n"
                "        if missing:\n"
                '            raise RuntimeError(f"embedding 结果缺失，下标={missing}")\n'
                "        return results  # type: ignore[return-value]\n",
                "        return [vector or [] for vector in results]\n",
            ),
        ),
        triggers_test="TestD7MissingVectorRaises::test_short_batch_raises",
    ),
    Injection(
        defect_id="d8-history-not-blocked",
        file="app/infrastructure/cache/semantic_cache.py",
        defect_class="logic",
        title="会话内多轮时仍走语义缓存，上下文依赖问句被跨轮复用",
        rationale=(
            "「会话内已有多轮上下文时不命中」是缓存的安全边界之一——「刚才那款多少钱」依赖上下文，"
            "跨会话复用会答错。漏检 has_history 后，调用点仍然传了参数，看起来一切正常。"
        ),
        edits=(
            (
                "        if not self._enabled or has_history or not is_cacheable_query(query):\n"
                "            return None\n",
                "        if not self._enabled or not is_cacheable_query(query):\n"
                "            return None\n",
            ),
        ),
        triggers_test="TestD8HistoryBlocksCache::test_lookup_with_history_misses",
    ),
    Injection(
        defect_id="d9-error-reply-cached",
        file="app/infrastructure/cache/semantic_cache.py",
        defect_class="error_handling",
        title="失败回复进语义缓存，错误被复用 24 小时",
        rationale=(
            "`reply` 以 `[error]` 开头说明这一轮失败了，进缓存等于把错误固化 24 小时，"
            "而且命中率会变好看。删掉 startswith 判断后只剩下「空回复不缓存」，逻辑依旧合理。"
        ),
        edits=(
            (
                '        if not reply or reply.startswith("[error]"):\n'
                "            return  # 失败回复绝不能进缓存，否则错误会被反复复用\n",
                "        if not reply:\n"
                "            return\n",
            ),
        ),
        triggers_test="TestD9ErrorReplyNotCached::test_error_reply_is_not_reusable",
    ),
    Injection(
        defect_id="d10-bucket-key-ignores-scope",
        file="app/infrastructure/cache/semantic_cache.py",
        defect_class="cache_key",
        title="桶 key 不再带偏好指纹，撤回偏好后仍命中旧回复",
        rationale=(
            "桶 key = namespace + buyer + scope，scope 是买家偏好指纹。回复是在「当时的偏好」下生成的，"
            "偏好撤回后旧回复必须自动失效，否则会向用户断言一条他自己删掉的偏好。"
            "去掉 scope 后 key 仍然随买家变化，单看这段毫无破绽。"
        ),
        edits=(
            (
                '        digest = hashlib.sha256(\n'
                '            f"{self._namespace}\\n{buyer_id}\\n{scope}".encode(),\n'
                "        ).hexdigest()[:16]\n",
                '        digest = hashlib.sha256(\n'
                '            f"{self._namespace}\\n{buyer_id}".encode(),\n'
                "        ).hexdigest()[:16]\n",
            ),
        ),
        triggers_test="TestD10BucketKeyUsesScope::test_scope_change_invalidates_bucket",
    ),
    Injection(
        defect_id="d11-bucket-keeps-oldest",
        file="app/infrastructure/cache/semantic_cache.py",
        defect_class="boundary",
        title="桶内保留的是最旧 30 条而不是最近 30 条",
        rationale=(
            "`entries[-_BUCKET_LIMIT:]` 的语义是「保留最近 N 条」。换成 `[:N]` 后仍然只保留 30 条，"
            "长度约束还成立，但留下的是最旧的——新回复全部写不进去，缓存命中率随时间单调下降。"
        ),
        edits=(
            (
                "            await self._cache.set_json(key, entries[-_BUCKET_LIMIT:], _TTL_SECONDS)\n",
                "            await self._cache.set_json(key, entries[:_BUCKET_LIMIT], _TTL_SECONDS)\n",
            ),
        ),
        triggers_test="TestD11BucketKeepsNewest::test_newest_entry_remains_reachable",
    ),
    Injection(
        defect_id="d12-output-guard-misses-api-key",
        file="app/infrastructure/security/output_guard.py",
        defect_class="security",
        title="输出审核的敏感模式表少了 API Key 形态",
        rationale=(
            "output_guard 是最后一道闸，`sk-` 开头的 API Key 是明确的敏感形态。"
            "把这一条从 SENSITIVE_PATTERNS 里去掉后，注释变成「由上游网关负责」，"
            "模式表其余项都还在，单看实现完全合理——但泄露的凭据会被原样下发。"
        ),
        edits=(
            (
                "    # API Key 形态\n"
                '    r"sk-[a-zA-Z0-9]{20,}",\n',
                "    # API Key 形态由上游网关负责，这里不再重复匹配\n",
            ),
        ),
        triggers_test="TestD12OutputGuardRedactsApiKey::test_api_key_is_redacted",
    ),
]

TEST_SOURCE = '''# -*- coding: utf-8 -*-
"""S4 注入版验真：每个缺陷一条测试，干净版全绿、注入版逐条打红。

只做客观断言，不依赖网络与 Redis：缓存类用内存假实现，向量用手写常量。
"""
from __future__ import annotations

import pytest

from app.application.memory.preference_selector import PreferenceSelector
from app.domain.buyer.preference import BuyerPreference
from app.domain.catalog.money import Money
from app.domain.session.ports.conversation_store import ConversationTurn
from app.infrastructure.cache.cached_embedding_client import CachedEmbeddingClient
from app.infrastructure.cache.semantic_cache import SemanticCache
from app.infrastructure.security.output_guard import audit_output


def pref(kind: str, statement: str, created_at: str = "2026-01-01T00:00:00+00:00") -> BuyerPreference:
    return BuyerPreference(buyer_id="b1", kind=kind, statement=statement, created_at=created_at)


class FakeCache:
    """最小 RedisCache 替身：只实现缓存层用到的那几个方法。"""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    @property
    def enabled(self) -> bool:
        return True

    async def get_json(self, key):
        return self.store.get(key)

    async def set_json(self, key, value, ttl_seconds):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)


class MapEmbedder:
    """按文本查表给向量，映射不到的给零向量。"""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.mapping = mapping

    async def embed(self, text: str) -> list[float]:
        return self.mapping.get(text, [0.0, 0.0])

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping.get(text, [0.0, 0.0]) for text in texts]


class ShortEmbedder:
    """故意少返回一条向量，模拟上游实现失约。"""

    async def embed(self, text: str) -> list[float]:
        return [1.0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts[:-1]]


class TestD1DislikesNotTruncated:
    async def test_all_dislikes_survive_total_budget(self):
        prefs = [
            pref("dislike", "不要塑料材质"),
            pref("dislike", "不要含酒精"),
            pref("dislike", "不要动物实验"),
            pref("like", "喜欢小众设计"),
            pref("like", "喜欢磨砂质感"),
        ]
        selected = await PreferenceSelector().select(prefs, "推荐个杯子", top_k=2)
        assert len([p for p in selected if p.kind == "dislike"]) == 3


class TestD2ZeroBudgetKeepsDislikes:
    async def test_zero_top_k_still_returns_dislikes(self):
        prefs = [pref("dislike", "不要塑料材质"), pref("like", "喜欢小众设计")]
        selected = await PreferenceSelector().select(prefs, "推荐个杯子", top_k=0)
        assert [p.statement for p in selected] == ["不要塑料材质"]


class TestD3RankingRestoresOriginalOrder:
    async def test_output_follows_original_order(self):
        embedder = MapEmbedder({
            "aa": [0.5, 0.5],
            "bb": [0.0, 1.0],
            "cc": [1.0, 0.0],
            "q": [1.0, 0.0],
        })
        selector = PreferenceSelector(embedder=embedder, relevance_enabled=True)
        prefs = [pref("like", "aa"), pref("like", "bb"), pref("like", "cc")]
        selected = await selector.select(prefs, "q", top_k=2)
        # 相关性前两名是 cc、aa，但输出必须回到原列表的相对顺序 aa、cc
        assert [p.statement for p in selected] == ["aa", "cc"]


class TestD4MoneyRejectsBool:
    def test_bool_amount_is_rejected(self):
        with pytest.raises(ValueError):
            Money.of(True, "USD")


class TestD5ConversationRoleChecked:
    def test_invalid_role_is_rejected(self):
        with pytest.raises(ValueError):
            ConversationTurn(session_id="s1", buyer_id="b1", role="system", content="hi")


class TestD6EmbeddingKeyIncludesModel:
    async def test_different_models_do_not_share_cache(self):
        cache = FakeCache()
        first = CachedEmbeddingClient(MapEmbedder({"x": [1.0, 0.0]}), cache, "model-a")
        second = CachedEmbeddingClient(MapEmbedder({"x": [0.0, 1.0]}), cache, "model-b")
        assert await first.embed("x") == [1.0, 0.0]
        assert await second.embed("x") == [0.0, 1.0]


class TestD7MissingVectorRaises:
    async def test_short_batch_raises(self):
        client = CachedEmbeddingClient(ShortEmbedder(), FakeCache(), "m")
        with pytest.raises(RuntimeError):
            await client.embed_batch(["a", "b"])


class TestD8HistoryBlocksCache:
    async def test_lookup_with_history_misses(self):
        cache = FakeCache()
        sc = SemanticCache(cache, MapEmbedder({"多少钱": [1.0, 0.0]}), threshold=0.9)
        await sc.remember("b1", "多少钱", "199 元", has_history=False)
        assert await sc.lookup("b1", "多少钱", has_history=True) is None


class TestD9ErrorReplyNotCached:
    async def test_error_reply_is_not_reusable(self):
        cache = FakeCache()
        sc = SemanticCache(cache, MapEmbedder({"多少钱": [1.0, 0.0]}), threshold=0.9)
        await sc.remember("b1", "多少钱", "[error] upstream timeout", has_history=False)
        assert await sc.lookup("b1", "多少钱", has_history=False) is None


class TestD10BucketKeyUsesScope:
    async def test_scope_change_invalidates_bucket(self):
        cache = FakeCache()
        sc = SemanticCache(cache, MapEmbedder({"多少钱": [1.0, 0.0]}), threshold=0.9)
        await sc.remember("b1", "多少钱", "199 元", has_history=False, scope="pref-v1")
        assert await sc.lookup("b1", "多少钱", has_history=False, scope="pref-v2") is None


class TestD11BucketKeepsNewest:
    async def test_newest_entry_remains_reachable(self):
        target = [1.0, 0.0]
        other = [0.0, 1.0]
        queries = [f"q{index}" for index in range(32)]
        mapping = {q: (target if q == "q31" else other) for q in queries}
        sc = SemanticCache(FakeCache(), MapEmbedder(mapping), threshold=0.9)
        for query in queries:
            await sc.remember("b1", query, f"reply-{query}", has_history=False)
        assert await sc.lookup("b1", "q31", has_history=False) is not None


class TestD12OutputGuardRedactsApiKey:
    def test_api_key_is_redacted(self):
        safe, text = audit_output("key=sk-" + "a" * 24)
        assert safe is False
        assert "sk-" not in text
'''
