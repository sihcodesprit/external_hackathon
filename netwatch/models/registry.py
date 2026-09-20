"""
Model checkpoint and registry system.

Every trained model has metadata:
  name, version, dataset, feature schema, training timestamp,
  metrics, configuration, checkpoint path.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = Path(__file__).resolve().parents[2] / "models" / "checkpoints"


class ModelRegistry:
    """Manages model checkpoints and metadata."""

    def __init__(self, checkpoints_dir: Optional[Path] = None):
        self.checkpoints_dir = checkpoints_dir or CHECKPOINTS_DIR
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self.checkpoints_dir / "registry.json"
        self._entries = self._load_registry()

    def _load_registry(self) -> Dict:
        if self._registry_path.exists():
            try:
                with open(self._registry_path) as f:
                    return json.load(f)
            except Exception:
                return {"models": []}
        return {"models": []}

    def _save_registry(self):
        with open(self._registry_path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    def register(self, name: str, version: str, checkpoint_path: str,
                 dataset: str = "unknown", feature_count: int = 0,
                 sequence_length: int = 10, metrics: Dict = None,
                 config: Dict = None) -> Dict:
        """Register a trained model checkpoint."""
        entry = {
            "name": name,
            "version": version,
            "dataset": dataset,
            "feature_count": feature_count,
            "sequence_length": sequence_length,
            "created_at": datetime.now().isoformat(),
            "metrics": metrics or {},
            "config": config or {},
            "checkpoint_path": str(checkpoint_path),
        }
        self._entries["models"].append(entry)
        self._save_registry()
        logger.info(f"Registered model: {name} v{version} at {checkpoint_path}")
        return entry

    def get_latest(self, name: str = None) -> Optional[Dict]:
        """Get the latest registered model, optionally filtered by name."""
        models = self._entries.get("models", [])
        if name:
            models = [m for m in models if m["name"] == name]
        if not models:
            return None
        return models[-1]

    def get_all(self, name: str = None) -> List[Dict]:
        models = self._entries.get("models", [])
        if name:
            models = [m for m in models if m["name"] == name]
        return models

    def list_models(self) -> List[Dict]:
        """List all registered models with summary info."""
        return [
            {
                "name": m["name"],
                "version": m["version"],
                "dataset": m["dataset"],
                "created_at": m["created_at"],
                "checkpoint_path": m["checkpoint_path"],
            }
            for m in self._entries.get("models", [])
        ]
