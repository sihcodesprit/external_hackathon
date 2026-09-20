"""
Confidence estimation for forecasts.

Provides a confidence score for each predicted future state based on how
'active/anomalous' the predicted normalized state is (inverse distance to a
benign prototype) combined with the stage probability. Kept simple and
deterministic; no fabricated values.
"""

import logging

logger = logging.getLogger(__name__)

# Reference 'benign' prototype in normalized space is the zero vector (states
# are standardized). Higher magnitude => further from benign => more confident
# that a meaningful (attack) transition is predicted.


def confidence_from_state(state_vec, stage_prob: float, attack_prob: float) -> float:
    """
    confidence = clamp( 0.5*|state_vec|_normalized  +  0.3*stage_prob  +
                        0.2*attack_prob )
    """
    import numpy as np
    vec = np.asarray(state_vec, dtype=np.float64)
    magnitude = float(np.linalg.norm(vec))
    # normalize magnitude to [0,1] approx (15 features, unit-variance vector)
    mag_norm = min(magnitude / 10.0, 1.0)
    conf = 0.5 * mag_norm + 0.3 * float(stage_prob) + 0.2 * float(attack_prob)
    return round(min(max(conf, 0.0), 1.0), 4)


def assign_confidence(steps: list) -> list:
    """Attach confidence to each forecast step dict (in place) and return it."""
    for step in steps:
        step["confidence"] = confidence_from_state(
            step.get("state_vec", []),
            step.get("step_stage_prob", 0.0),
            step.get("risk", 0.0),
        )
    return steps
