"""Shared pytest configuration for the netwatch Counterfactual Cyber World Model."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `netwatch` can be imported.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
