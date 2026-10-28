"""共享测试夹具。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from parallax.config import Settings, load_settings
from parallax.domain.models import EvidenceUnit
from parallax.ports.llm import ChatMessage
from parallax.util import content_hash, stable_id

FILE_BLOCK_RE = re.compile(r"===== FILE: (\S+) =====")


@pytest.fixture(autouse=True)
def _isolate_llm_credentials(monkeypatch):
    """让所有单测都**不可能**意外调用真实模型。

    起因是一次真实教训：`.env` 里配好 key 之后，一个「缺 key 应当报错」的测试
    不再抛错，于是它顺着一路跑下去真的发起了付费请求。
    自动清空凭据可以从结构上杜绝这类事故，而不是靠每个测试自觉。
    """
    monkeypatch.setenv("PARALLAX_LLM_API_KEY", "")
    monkeypatch.delenv("PARALLAX_LLM_BASE_URL", raising=False)
    # 必须显式置空而不是删除：删除后 pydantic 会回退到 .env 里的旧 OPENAI_API_KEY，
    # 于是「无凭据」测试拿到一个真实 key——这正是这条夹具要防的事故。
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    """三文件两模块的演示仓库。

    pkg/mod_a/a.py   含 run() 的并发缺陷
    pkg/mod_a/c.py   辅助（无缺陷）
    pkg/mod_b/b.py   含边界缺陷
    """
    repo = tmp_path / "repo"
    (repo / "pkg" / "mod_a").mkdir(parents=True)
    (repo / "pkg" / "mod_b").mkdir(parents=True)

    (repo / "pkg" / "mod_a" / "a.py").write_text(
        "import threading\n"
        "\n"
        "COUNTER = 0\n"
        "\n"
        "\n"
        "def run():\n"
        "    global COUNTER\n"
        "    for _ in range(100):\n"
        "        COUNTER += 1  # 非原子自增，多线程下会丢更新\n"
        "\n"
        "\n"
        "def start():\n"
        "    threads = [threading.Thread(target=run) for _ in range(4)]\n"
        "    for t in threads:\n"
        "        t.start()\n"
        "    for t in threads:\n"
        "        t.join()\n"
        "    return COUNTER\n",
        encoding="utf-8",
    )
    (repo / "pkg" / "mod_a" / "c.py").write_text(
        "def helper(x):\n    return x + 1\n",
        encoding="utf-8",
    )
    (repo / "pkg" / "mod_b" / "b.py").write_text(
        "def head(items):\n"
        "    return items[0]  # 空列表会 IndexError\n"
        "\n"
        "\n"
        "def safe_head(items):\n"
        "    return items[0] if items else None\n",
        encoding="utf-8",
    )
    return repo


def make_unit(path: str, content: str, group: str) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=stable_id("test", path, content_hash(content)),
        adapter="test",
        locator=path,
        content=content,
        content_hash=content_hash(content),
        group=group,
        metadata={"path": path},
    )


def make_responder(defects_by_path: dict[str, list[dict]]):
    """按提示词里出现的文件列表返回缺陷——模拟一个守规矩的审查者。"""

    def respond(messages: list[ChatMessage]):
        text = "\n".join(m.content for m in messages)
        paths = FILE_BLOCK_RE.findall(text)
        findings = []
        for path in paths:
            for defect in defects_by_path.get(path, []):
                findings.append({"path": path, **defect})
        return {"findings": findings, "notes": ""}

    return respond


@pytest.fixture
def defects() -> dict[str, list[dict]]:
    """演示仓库里「已植入」的两个缺陷。

    放在 conftest 而不是某个测试模块：多个测试模块都要用它，
    而跨模块导入 fixture 会改变它在 pytest 里的可见名字。
    """
    return {
        "pkg/mod_a/a.py": [
            {
                "title": "COUNTER 非原子自增",
                "defect_class": "concurrency",
                "line_start": 9,
                "line_end": 9,
                "severity": "high",
                "rationale": "多线程下 +1 会丢更新",
                "quote": "        COUNTER += 1",
            }
        ],
        "pkg/mod_b/b.py": [
            {
                "title": "head() 未处理空列表",
                "defect_class": "boundary",
                "line_start": 2,
                "line_end": 2,
                "severity": "medium",
                "rationale": "空列表会 IndexError",
                "quote": "    return items[0]",
            }
        ],
    }


def make_settings(**overrides) -> Settings:
    """构造测试用配置。"""
    base = {
        "n_readers": 3,
        "redundancy": 2,
        "support_threshold": 2,
        "max_rounds": 3,
        "seed": 1,
        "coverage_min_support": 2,
        "min_evidence_fill_rate": 1.0,
        "max_dispute_rate": 1.0,
    }
    base.update(overrides)
    return load_settings(**base)
