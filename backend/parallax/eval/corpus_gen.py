"""语料生成器：从带标记的模板批量产出植入缺陷的语料仓库。

## 为什么用生成器而不是手写

1. **行号不可能手工写对。** 模板里用 `@@D <类目> <标题>` 标出缺陷行，
   生成器自己算出准确行号并写进 ground_truth.json。
2. **可复现。** 同一份模板永远产出同一份语料，实验才能被第三方复现。
3. **标记会被剥离。** 生成出的源码里不会留下任何"这里是缺陷"的痕迹——
   否则等于直接泄题。

## 缺陷的选择标准（P0-3）

刻意**避开教科书式模式**（可变默认参数、比较符写反、`except: pass`）——
这些模式大模型在训练里见过无数次，一眼就能认出来，测不出任何区分度。

这里选的是"读起来合情合理、跑起来才出错"的类型：

    scheduler  就地修改堆元素的比较键 → 破坏堆不变量
    journal    压缩后内存与磁盘状态不同步 → 被丢弃的记录复活
    pool       归还连接时不校验归属 → 同一连接被两个调用方同时持有
    codec      版本相关的字段回退写错 → v2 记录静默丢数据
    registry   无同步的惰性初始化 → 同名对象出现两个实例
    window     环形缓冲淘汰时不回退累计和 → 均值无限漂移
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

MARKER_RE = re.compile(r"\s*#\s*@@D\s+(?P<cls>\w+)\s+(?P<title>.+?)\s*$")


@dataclass
class Archetype:
    """一种代码形态（含若干植入缺陷点）。"""

    key: str
    group: str
    template: str
    variants: dict[str, dict[str, str]] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class GeneratedDefect:
    id: str
    file: str
    line: int
    defect_class: str
    title: str
    marker: str
    instance: str


# ────────────────────────────── 模板 ──────────────────────────────
# 占位符用 $name（string.Template），避免 str.format 的花括号转义地狱。

SCHEDULER = '''\
"""按优先级调度待处理作业，支持运行中调整优先级。"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class _Item:
    priority: int
    seq: int
    name: str = field(compare=False)
    payload: Any = field(compare=False, default=None)


class $cls:
    """小顶堆调度器。

    add() 入队；reprioritize() 在作业尚未出队前调整优先级；
    take() 取出当前优先级最高的作业。
    """

    def __init__(self) -> None:
        self._heap: list[_Item] = []
        self._items: dict[str, _Item] = {}
        self._counter = itertools.count()

    def add(self, name: str, priority: int, payload: Any = None) -> None:
        if name in self._items:
            raise KeyError(f"作业已存在: {name}")
        item = _Item(priority, next(self._counter), name, payload)
        heapq.heappush(self._heap, item)
        self._items[name] = item

    def reprioritize(self, name: str, priority: int) -> None:
        """调整队列中作业的优先级。

        调用方用它实现饥饿缓解：等待过久的作业会被逐步提权。
        """
        item = self._items[name]
        item.priority = priority  # @@D logic 就地修改堆元素优先级破坏堆不变量
        return None

    def take(self) -> _Item | None:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.name in self._items:
                del self._items[item.name]
                return item
        return None

    def cancel(self, name: str) -> bool:
        if name not in self._items:
            return False
        del self._items[name]
        return True

    def pending(self) -> int:
        return len(self._items)

    def drain(self) -> list[_Item]:
        out: list[_Item] = []
        while True:
            item = self.take()
            if item is None:
                break
            out.append(item)
        return out

    def peek_priority(self, name: str) -> int:
        return self._items[name].priority
'''

JOURNAL = '''\
"""追加式记录日志：写入、重放、按保留量压缩。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class $cls:
    """以 JSON Lines 落盘的记录日志。

    append() 追加一条并重写文件；
    compact() 只保留最近 keep 条；
    replay() 按写入顺序返回当前全部记录。
    """

    def __init__(self, path: str | Path, keep: int = $keep) -> None:
        self.path = Path(path)
        self.keep = keep
        self._records: list[dict[str, Any]] = []
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                self._records.append(json.loads(line))

    def _serialise(self, records: list[dict[str, Any]]) -> str:
        return "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\\n"
            for record in records
        )

    def _flush(self) -> None:
        self.path.write_text(self._serialise(self._records), encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        self._records.append(record)
        self._flush()

    def compact(self) -> int:
        """只保留最近 keep 条记录，返回被丢弃的条数。"""
        surplus = len(self._records) - self.keep
        if surplus <= 0:
            return 0
        kept = self._records[surplus:]
        self.path.write_text(self._serialise(kept), encoding="utf-8")  # @@D logic 压缩只改了磁盘，内存 _records 未同步，后续 append 触发 _flush 会把已丢弃的记录全部写回
        return surplus

    def replay(self) -> list[dict[str, Any]]:
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def disk_count(self) -> int:
        return sum(
            1
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
'''

POOL = '''\
"""定长资源池：借出、归还、超时等待。"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class $cls:
    """定长资源池。

    acquire() 借出一个资源（必要时新建或等待）；release() 归还。
    池内资源总数不超过 size。
    """

    def __init__(self, factory: Callable[[], Any], size: int = $size) -> None:
        self._factory = factory
        self._size = size
        self._free: list[Any] = []
        self._in_use: set[int] = set()
        self._created = 0
        self._lock = threading.Lock()
        self._available = threading.Condition(self._lock)

    def acquire(self, timeout: float = 5.0) -> Any:
        deadline = time.monotonic() + timeout
        with self._available:
            while True:
                if self._free:
                    resource = self._free.pop()
                    self._in_use.add(id(resource))
                    return resource
                if self._created < self._size:
                    resource = self._factory()
                    self._created += 1
                    self._in_use.add(id(resource))
                    return resource
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("资源池已耗尽")
                self._available.wait(remaining)

    def release(self, resource: Any) -> None:
        with self._available:
            self._free.append(resource)  # @@D resource_leak 归还前未校验资源确实在借出集合中，重复归还导致同一资源被重复分配
            self._available.notify()

    def stats(self) -> dict[str, int]:
        return {
            "created": self._created,
            "free": len(self._free),
            "in_use": len(self._in_use),
        }

    def close(self) -> None:
        with self._available:
            closer = getattr(self._factory, "close", None)
            for resource in self._free:
                if callable(closer):
                    closer(resource)
            self._free.clear()
'''

CODEC = '''\
"""带版本号的记录编解码。"""

from __future__ import annotations

from typing import Any

CURRENT_VERSION = 2


class $cls:
    """把记录字典编码为线格式，并从线格式解码回字典。

    v1 字段：name、size
    v2 字段：name、size_bytes、tags
    """

    def encode(self, record: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "v": CURRENT_VERSION,
            "name": record["name"],
            "size_bytes": int(record.get("size", 0)),
            "tags": list(record.get("tags", [])),
        }
        return out

    def decode(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = int(payload.get("v", 1))
        out: dict[str, Any] = {"name": payload.get("name", "")}

        if version >= 1:
            out["size"] = payload.get("size", 0)
            out["tags"] = []

        if version >= 2:
            out["size"] = payload.get("size", 0)  # @@D logic v2 记录的体量字段是 size_bytes，回退读 size 导致静默归零
            out["tags"] = list(payload.get("tags", []))

        return out

    def decode_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.decode(payload) for payload in payloads]

    def total_size(self, payloads: list[dict[str, Any]]) -> int:
        return sum(self.decode(payload)["size"] for payload in payloads)
'''

REGISTRY = '''\
"""具名组件注册表：按名字惰性构造并复用实例。"""

from __future__ import annotations

from typing import Any, Callable


class $cls:
    """注册工厂函数，首次取用时构造实例并缓存。

    约定：同名组件在进程内只应存在一个实例。
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Any]] = {}
        self._instances: dict[str, Any] = {}
        self._build_count = 0

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        if name in self._factories:
            raise KeyError(f"组件已注册: {name}")
        self._factories[name] = factory

    def get(self, name: str) -> Any:
        if name not in self._instances:
            self._instances[name] = self._build(name)  # @@D concurrency 检查-构造-写入未加锁，并发下同名组件会被构造出两个实例
        return self._instances[name]

    def _build(self, name: str) -> Any:
        self._build_count += 1
        return self._factories[name]()

    def has(self, name: str) -> bool:
        return name in self._factories

    def names(self) -> list[str]:
        return sorted(self._factories)

    def build_count(self) -> int:
        return self._build_count

    def clear(self) -> None:
        self._instances.clear()
'''

WINDOW = '''\
"""滑动窗口统计：均值、极值、分位。"""

from __future__ import annotations

from collections import deque
from typing import Iterable


class $cls:
    """保留最近 size 个样本的滑动窗口。

    样本按到达顺序入窗，超出容量的最旧样本自动淘汰。
    """

    def __init__(self, size: int = $size) -> None:
        self.size = size
        self._values: deque[float] = deque(maxlen=size)
        self._total = 0.0
        self._added = 0

    def add(self, value: float) -> None:
        self._values.append(value)
        self._total += value  # @@D logic 环形缓冲自动淘汰最旧样本时未从累计和中扣除，均值随样本数持续漂移
        self._added += 1

    def extend(self, values: Iterable[float]) -> None:
        for value in values:
            self.add(value)

    def mean(self) -> float:
        if not self._values:
            return 0.0
        return self._total / len(self._values)

    def maximum(self) -> float:
        return max(self._values) if self._values else 0.0

    def minimum(self) -> float:
        return min(self._values) if self._values else 0.0

    def percentile(self, ratio: float) -> float:
        if not self._values:
            return 0.0
        ordered = sorted(self._values)
        index = int(round(ratio * (len(ordered) - 1)))
        return ordered[index]

    def count(self) -> int:
        return len(self._values)

    def total_added(self) -> int:
        return self._added
'''

CONTRACT_PRODUCER = '''\
"""跨文件记录生产者：返回 v2 记录格式。"""

from __future__ import annotations


def build_record(name: str, size: int) -> dict[str, object]:
    return {"name": name, "size_bytes": size, "tags": ["stable"]}
'''

CONTRACT_CONSUMER = '''\
"""跨文件记录消费者：读取生产者返回的记录。"""

from __future__ import annotations

from .$producer import build_record


def record_size(name: str, size: int) -> int:
    record = build_record(name, size)
    return int(record["size"])  # @@D integration 生产者返回 size_bytes，消费者读取旧字段导致跨文件静默归零
'''


ARCHETYPES: list[Archetype] = [
    Archetype("scheduler", "scheduling", SCHEDULER),
    Archetype("journal", "persistence", JOURNAL),
    Archetype("pool", "resources", POOL),
    Archetype("codec", "wire", CODEC),
    Archetype("registry", "wiring", REGISTRY),
    Archetype("window", "analytics", WINDOW),
    Archetype(
        "contract",
        "cross_file",
        "",
        files={
            "contract_$suffix_producer.py": CONTRACT_PRODUCER,
            "contract_$suffix_consumer.py": CONTRACT_CONSUMER,
        },
    ),
]

# 每个原型实例化的变体：改类名与关键常量，让每个文件看起来是独立的模块
SUFFIXES: list[str] = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
]


def make_variants(count: int) -> list[dict[str, str]]:
    """按数量生成变体定义（类名后缀 + 序号）。"""
    if count < 1:
        raise ValueError("变体数量至少为 1")
    if count > len(SUFFIXES):
        raise ValueError(f"变体数量最多 {len(SUFFIXES)}（受 SUFFIXES 限制）")
    return [{"suffix": s, "num": str(i + 1)} for i, s in enumerate(SUFFIXES[:count])]


VARIANTS: list[dict[str, str]] = make_variants(3)

DEFAULTS = {
    "keep": "200",
    "size": "32",
}


def render(template: str, *, cls: str, suffix: str, num: str) -> str:
    values = dict(DEFAULTS)
    values.update({"cls": cls, "suffix": suffix, "num": num})
    return string.Template(template).safe_substitute(values)


def class_name(archetype: Archetype, variant: dict[str, str]) -> str:
    base = "".join(part.capitalize() for part in archetype.key.split("_"))
    return f"{base}{variant['suffix'].capitalize()}"


def generate_instance(
    archetype: Archetype,
    variant: dict[str, str],
) -> tuple[str, list[tuple[int, str, str, str]]]:
    """渲染一个实例。

    Returns:
        (源码, [(行号, 类目, 标题, marker)])
    """
    cls = class_name(archetype, variant)
    source = render(archetype.template, cls=cls, suffix=variant["suffix"], num=variant["num"])

    kept_lines: list[str] = []
    found: list[tuple[int, str, str, str]] = []
    for raw in source.splitlines():
        match = MARKER_RE.search(raw)
        if not match:
            kept_lines.append(raw)
            continue
        code = MARKER_RE.sub("", raw).rstrip()
        kept_lines.append(code)
        found.append((len(kept_lines), match.group("cls"), match.group("title"), code.strip()))

    return "\n".join(kept_lines) + "\n", found


def generate_files(
    archetype: Archetype,
    variant: dict[str, str],
) -> dict[str, tuple[str, list[tuple[int, str, str, str]]]]:
    """渲染一个原型实例可能包含的多个相互协作的文件。"""
    if not archetype.files:
        source, found = generate_instance(archetype, variant)
        return {f"{archetype.key}_{variant['suffix']}.py": (source, found)}
    rendered: dict[str, tuple[str, list[tuple[int, str, str, str]]]] = {}
    producer = f"contract_{variant['suffix']}_producer"
    for filename_template, template in archetype.files.items():
        filename = filename_template.replace("$suffix", variant["suffix"])
        source = render(
            template,
            cls=class_name(archetype, variant),
            suffix=variant["suffix"],
            num=variant["num"],
        ).replace("$producer", producer)
        kept_lines: list[str] = []
        found: list[tuple[int, str, str, str]] = []
        for raw in source.splitlines():
            match = MARKER_RE.search(raw)
            if not match:
                kept_lines.append(raw)
                continue
            code = MARKER_RE.sub("", raw).rstrip()
            kept_lines.append(code)
            found.append((len(kept_lines), match.group("cls"), match.group("title"), code.strip()))
        rendered[filename] = ("\n".join(kept_lines) + "\n", found)
    return rendered


def build_corpus(
    *,
    out_dir: Path,
    task_id: str,
    description: str = "",
    archetypes: list[Archetype] | None = None,
    variants: list[dict[str, str]] | None = None,
) -> dict:
    """生成整个语料并写出 ground_truth.json。"""
    archetypes = archetypes or ARCHETYPES
    variants = variants or VARIANTS

    repo = out_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    defects: list[GeneratedDefect] = []
    for archetype in archetypes:
        group_dir = repo / archetype.group
        group_dir.mkdir(parents=True, exist_ok=True)
        for variant in variants:
            for filename, (source, found) in generate_files(archetype, variant).items():
                (group_dir / filename).write_text(source, encoding="utf-8")

                rel = f"{archetype.group}/{filename}"
                for index, (line, defect_class, title, marker) in enumerate(found, start=1):
                    instance_tag = f"{archetype.key}-{variant['suffix']}"
                    defects.append(
                        GeneratedDefect(
                            id=f"{archetype.key.upper()}{index}-{variant['suffix']}",
                            file=rel,
                            line=line,
                            defect_class=defect_class,
                            title=title,
                            marker=marker,
                            instance=instance_tag,
                        )
                    )

    payload = {
        "task_id": task_id,
        "description": description,
        "repo": "repo",
        "planted_defect_count": len(defects),
        "defects": [
            {
                "id": d.id,
                "file": d.file,
                "line_start": d.line,
                "line_end": d.line,
                "defect_class": d.defect_class,
                "title": d.title,
                "marker": d.marker,
                "rationale": "",
            }
            for d in defects
        ],
    }
    (out_dir / "ground_truth.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


DEFAULT_DESCRIPTION = (
    "由 7 种代码形态 × 3 个变体生成，共 21 个模块、21 个植入缺陷；其中包含跨文件契约缺陷。"
    "缺陷刻意避开教科书式模式，均为「读起来合理、跑起来出错」的类型。"
)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="生成植入缺陷语料")
    parser.add_argument("--out", required=True, help="输出目录（如 eval/corpus/seed_b）")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument(
        "--variants", type=int, default=len(VARIANTS), help="每个原型的实例数（默认 3）"
    )
    args = parser.parse_args(argv)

    out = Path(args.out)
    task_id = args.task_id or out.name
    payload = build_corpus(
        out_dir=out,
        task_id=task_id,
        description=args.description,
        variants=make_variants(args.variants),
    )

    total_lines = sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in (out / "repo").rglob("*.py")
    )
    files = len(list((out / "repo").rglob("*.py")))
    print(f"语料已生成：{out}")
    print(f"  文件 {files} 个｜总行数 {total_lines}｜植入缺陷 {payload['planted_defect_count']} 个")
    for defect in payload["defects"]:
        print(
            f"  - {defect['id']:16s} {defect['file']:32s} :{defect['line_start']:<4d} {defect['defect_class']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
