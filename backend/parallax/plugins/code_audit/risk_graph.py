"""Bounded Python import, configuration and permission context; never executes source.

This syntax approximation is not a sound whole-program dataflow analysis.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import PurePosixPath

from parallax.domain.models import EvidenceUnit


def annotate_risk_dependencies(units: list[EvidenceUnit]) -> list[EvidenceUnit]:
    modules: dict[str, str] = {}
    for unit in units:
        path = PurePosixPath(unit.locator)
        if path.suffix == ".py":
            parts = list(path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            modules[".".join(parts)] = unit.evidence_id
    edges: dict[str, set[str]] = defaultdict(set)
    shared: dict[str, set[str]] = defaultdict(set)
    parsed: set[str] = set()
    for unit in units:
        if not unit.locator.endswith(".py"):
            continue
        try:
            tree = ast.parse(unit.content)
        except (SyntaxError, ValueError, RecursionError):
            continue
        parsed.add(unit.evidence_id)
        package = list(PurePosixPath(unit.locator).parent.parts)
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[: len(package) - node.level + 1] if node.level else []
                module = ".".join([*prefix, *([node.module] if node.module else [])])
                imports = [module, *(f"{module}.{alias.name}" for alias in node.names)]
            for module in imports:
                if module in modules:
                    other = modules[module]
                    edges[unit.evidence_id].add(other)
                    edges[other].add(unit.evidence_id)
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if (
                    name in {"os.getenv", "os.environ.get", "getenv"}
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    shared[f"config:{node.args[0].value}"].add(unit.evidence_id)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    name = ast.unparse(decorator)
                    if any(
                        word in name.lower() for word in ("permission", "authorize", "require_role")
                    ):
                        shared[f"guard:{name}"].add(unit.evidence_id)
    for ids in shared.values():
        for eid in ids:
            edges[eid].update(ids - {eid})
    return [
        unit.model_copy(
            update={
                "metadata": {
                    **unit.metadata,
                    "risk_dependencies": sorted(edges[unit.evidence_id] - {unit.evidence_id}),
                    "risk_graph_status": "syntax_approximation"
                    if unit.evidence_id in parsed
                    else "unavailable",
                }
            }
        )
        for unit in units
    ]
