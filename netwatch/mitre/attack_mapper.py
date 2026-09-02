"""
MITRE ATT&CK attack mapper.

Maps predicted attack stages (kill-chain progression) to MITRE ATT&CK
techniques/tactics so the dashboard can present industry-standard context.

Mapping is deterministic and keyed by stage. We only claim a technique when the
stage evidence (feature profile) supports it; otherwise we return UNKNOWN.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Kill-chain stage -> MITRE tactic(s) + representative technique(s)
STAGE_TO_MITRE = {
    "Reconnaissance": {
        "tactic": "Discovery",
        "technique_id": "T1046",
        "technique_name": "Network Service Discovery",
    },
    "Initial Access": {
        "tactic": "Initial Access",
        "technique_id": "T1190",
        "technique_name": "Exploit Public-Facing Application",
    },
    "Execution": {
        "tactic": "Execution",
        "technique_id": "T1059",
        "technique_name": "Command and Scripting Interpreter",
    },
    "Lateral Movement": {
        "tactic": "Lateral Movement",
        "technique_id": "T1021",
        "technique_name": "Remote Services",
    },
    "Command and Control": {
        "tactic": "Command and Control",
        "technique_id": "T1071",
        "technique_name": "Application Layer Protocol",
    },
    "Exfiltration": {
        "tactic": "Exfiltration",
        "technique_id": "T1048",
        "technique_name": "Exfiltration Over Alternative Protocol",
    },
    "Impact": {
        "tactic": "Impact",
        "technique_id": "T1499",
        "technique_name": "Endpoint Denial of Service",
    },
}


class AttackMapper:
    """Maps a stage to MITRE ATT&CK context."""

    def map(self, stage: Optional[str]) -> Dict:
        if not stage or stage == "Benign":
            return {
                "stage": stage or "Benign",
                "tactic": "None",
                "technique_id": "UNKNOWN",
                "technique_name": "No threat stage identified",
                "has_mitre": False,
            }
        m = STAGE_TO_MITRE.get(stage, {})
        if not m:
            return {
                "stage": stage,
                "tactic": "Unknown",
                "technique_id": "UNKNOWN",
                "technique_name": "Unmapped stage",
                "has_mitre": False,
            }
        return {
            "stage": stage,
            "tactic": m["tactic"],
            "technique_id": m["technique_id"],
            "technique_name": m["technique_name"],
            "has_mitre": True,
        }

    def map_trajectory(self, stages: List[Optional[str]]) -> List[Dict]:
        return [self.map(s) for s in stages]
