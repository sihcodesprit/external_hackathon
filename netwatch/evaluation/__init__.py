"""
Evaluation package: metrics, baselines runner, unseen-attack test, ablation studies.

Modules:
- metrics: Continuous and classification metrics
- baselines: Baseline model evaluation runner
- unseen_attack: Unseen attack generalization test
- ablation: Ablation study framework
"""

from netwatch.evaluation.ablation import (
    AblationConfig,
    AblationResult,
    AblationStudy,
    run_ablation_study_from_pipeline,
)
from netwatch.evaluation.baselines import ModelEvaluator
from netwatch.evaluation.metrics import (
    classification_metrics,
    evaluate_state_predictions,
    regression_metrics,
)
from netwatch.evaluation.unseen_attack import UnseenAttackTest

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
