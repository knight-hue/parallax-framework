"""实验评测层：把一次运行的结果换算成可比较的数字。"""

from parallax.eval.corpus import (
    DEFAULT_QUESTION,
    GroundTruth,
    PlantedDefect,
    Task,
    load_corpus,
    load_task,
    verify_task,
)
from parallax.eval.experiment import (
    ARMS,
    Arm,
    ArmResult,
    render_summary,
    run_arm,
    run_experiment,
)
from parallax.eval.metrics import (
    ArmMetrics,
    DefectOutcome,
    MatchReport,
    compute_metrics,
    effective_channels,
    match_claims,
)

__all__ = [
    "ARMS",
    "DEFAULT_QUESTION",
    "Arm",
    "ArmMetrics",
    "ArmResult",
    "DefectOutcome",
    "GroundTruth",
    "MatchReport",
    "PlantedDefect",
    "Task",
    "compute_metrics",
    "effective_channels",
    "load_corpus",
    "load_task",
    "match_claims",
    "render_summary",
    "run_arm",
    "run_experiment",
    "verify_task",
]
