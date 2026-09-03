"""
Evaluation package: metrics, baselines runner, unseen-attack test, ablation studies.

Modules:
- metrics: Continuous and classification metrics
- baselines: Baseline model evaluation runner
- unseen_attack: Unseen attack generalization test
- ablation: Ablation study framework
"""

from netwatch.evaluation.metrics import (
    regression_metrics,
    classification_metrics,
    evaluate_state_predictions,
)
from netwatch.evaluation.baselines import ModelEvaluator
from netwatch.evaluation.unseen_attack import UnseenAttackTest
from netwatch.evaluation.ablation import (
    AblationStudy,
    AblationConfig,
    AblationResult,
    run_ablation_study_from_pipeline,
)

__all__ = [
    "regression_metrics",
    "classification_metrics",
    "evaluate_state_predictions",
    "ModelEvaluator",
    "UnseenAttackTest",
    "AblationStudy",
    "AblationConfig",
    "AblationResult",
    "run_ablation_study_from_pipeline",
]