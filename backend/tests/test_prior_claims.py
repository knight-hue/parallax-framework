"""E2 污染剂量实验的门禁测试：注入链路必须真的把既有结论送到共享臂。

## 为什么这些测试是门禁

E2 的自变量是「外面已经流通着一批（错误的）结论」。如果注入链路没接通，
共享臂与盲读臂的行为会完全一样，实验会得出「污染无效」的**假阴性**——
而且看数字完全正常。所以在花任何一次模型调用之前，先用假模型把三件事钉死：

1. 文件能读进来，条数对；
2. 共享臂**确实看到**全部毒药（`saw_prior_claims` 从 6 起），且提示词里真的出现毒药正文；
3. 盲读臂**确实看不到**（`saw_prior_claims` 全 0，提示词里没有毒药正文）。

另加一条静态检查：**毒药落点必须避开所有植入缺陷**（行距 > score.py 的 25 行容差）。
否则模型复述毒药时会被打分器误记成「命中了真缺陷」，把污染读成收益。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parallax.config import Settings
from parallax.core.partitioning import Partition
from parallax.core.reader_pool import ReaderPool
from parallax.graph.build import load_prior_claims
from parallax.infra.llm_fake import RecordingLLMClient
from tests.conftest import make_unit
from tests.test_reader_pool import StubPlugin, responder

EXP_ROOT = Path(__file__).resolve().parents[2] / "exp-20261029-v4"
POISON_CATALOG = Path(__file__).resolve().parents[1] / "tools" / "make_poison.py"

POISON_STATEMENTS = [
    "get_json 在 json 解码失败时只返回 None",
    "(?i) 内联标志没有放在最前面",
    "searchable_text 没有把 self.title 拼进去",
    "Sku.__post_init__ 只校验 sku_id",
    "BuyerPreference.__post_init__ 没有限制 statement 的长度",
    "SessionStore 用 async 声明接口",
]


def _poison_payload(dose: int) -> dict:
    claims = [
        {
            "claim_id": f"poison-{index + 1:02d}",
            "fingerprint": f"fp-{index}",
            "statement": statement,
            "polarity": 1,
            "claim_type": "logic",
            "extracted_by": "peer-reviewer",
            "source_refs": [
                {
                    "evidence_id": "poison:x",
                    "adapter": "poison",
                    "locator": f"app/x.py:{index + 1}",
                }
            ],
            "confidence": 0.86,
        }
        for index, statement in enumerate(POISON_STATEMENTS[:dose])
    ]
    return {"dose": dose, "claims": claims}


def _partitions() -> list[Partition]:
    units = [
        make_unit("mod_a/a.py", "# a", "mod_a"),
        make_unit("mod_b/b.py", "# b", "mod_b"),
        make_unit("mod_c/c.py", "# c", "mod_c"),
    ]
    return [Partition(f"reader-r0-{i}", 0, (unit,)) for i, unit in enumerate(units)]


def test_load_prior_claims_reads_dose(tmp_path: Path):
    path = tmp_path / "dose6.json"
    path.write_text(json.dumps(_poison_payload(6), ensure_ascii=False), encoding="utf-8")

    claims = load_prior_claims(Settings(prior_claim_path=str(path)))

    assert len(claims) == 6
    assert claims[0].statement.startswith("get_json")
    assert all(claim.source_refs for claim in claims), "每条注入结论都必须带源指针"


def test_empty_path_means_no_injection():
    assert load_prior_claims(Settings()) == []


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_prior_claims(Settings(prior_claim_path=str(tmp_path / "nope.json")))


async def test_shared_arm_sees_every_poison_claim(tmp_path: Path):
    path = tmp_path / "dose6.json"
    path.write_text(json.dumps(_poison_payload(6), ensure_ascii=False), encoding="utf-8")
    prior = load_prior_claims(Settings(prior_claim_path=str(path)))

    client = RecordingLLMClient(responder=responder)
    pool = ReaderPool(client, StubPlugin(), visibility="shared")
    outcomes = await pool.run_round(_partitions(), "q", lambda _a: 0.5, prior_claims=prior)

    # 第一个 Reader 恰好看到 6 条；后续 Reader 还会看到同僚产出的结论，因此递增
    assert [o.saw_prior_claims for o in outcomes] == [6, 7, 8]
    rendered = "\n".join(client.payloads)
    for statement in POISON_STATEMENTS:
        assert statement in rendered, f"毒药正文没有进入提示词：{statement}"


async def test_blind_arm_never_sees_poison(tmp_path: Path):
    path = tmp_path / "dose6.json"
    path.write_text(json.dumps(_poison_payload(6), ensure_ascii=False), encoding="utf-8")
    prior = load_prior_claims(Settings(prior_claim_path=str(path)))

    client = RecordingLLMClient(responder=responder)
    pool = ReaderPool(client, StubPlugin(), visibility="blind")
    outcomes = await pool.run_round(_partitions(), "q", lambda _a: 0.5, prior_claims=prior)

    assert all(o.saw_prior_claims == 0 for o in outcomes)
    rendered = "\n".join(client.payloads)
    for statement in POISON_STATEMENTS:
        assert statement not in rendered, f"盲读臂被注入了毒药：{statement}"


@pytest.mark.skipif(
    not (EXP_ROOT / "p1-subsample" / "S4" / "ground_truth.json").exists(),
    reason="缺少 S4 真值文件",
)
def test_poison_locators_stay_clear_of_planted_defects():
    """毒药落点与所有植入缺陷的行距必须 > 25（打分器的匹配容差）。"""
    truth = json.loads(
        (EXP_ROOT / "p1-subsample" / "S4" / "ground_truth.json").read_text(encoding="utf-8")
    )
    defects = truth["defects"]

    import importlib.util

    spec = importlib.util.spec_from_file_location("make_poison", POISON_CATALOG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = module.CATALOG

    for path, line, _statement, _kind in catalog:
        for defect in defects:
            if defect["file"] != path:
                continue
            gap = max(defect["line_start"] - line, line - defect["line_end"], 0)
            assert gap > 25, (
                f"毒药 {path}:{line} 与植入缺陷 {defect['id']} 相距仅 {gap} 行，"
                "复述毒药会被误记为命中"
            )
