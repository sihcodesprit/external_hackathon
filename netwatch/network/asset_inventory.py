"""
Asset inventory — loads and manages asset configurations.

Assets are optionally defined in configs/assets.yaml to enrich
discovered entities with hostname, type, and criticality.
The system works with automatic node discovery even when no config exists.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ASSETS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "assets.yaml"


class AssetInventory:
    """Manages the asset inventory from configuration."""

    def __init__(self, config: Optional[Dict] = None):
        if config is None:
            config = self._load_config()
        self.networks = config.get("networks", [])
        self.assets = config.get("assets", [])
        self._ip_map: Dict[str, Dict] = {}
        for a in self.assets:
            if "ip" in a:
                self._ip_map[a["ip"]] = a

    def _load_config(self) -> Dict:
        try:
            import yaml
            if ASSETS_CONFIG_PATH.exists():
                with open(ASSETS_CONFIG_PATH) as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logger.debug(f"Could not load assets config: {e}")
        return {}

    def lookup(self, ip: str) -> Optional[Dict]:
        return self._ip_map.get(ip)

    def get_all_assets(self) -> List[Dict]:
        return self.assets

    def get_networks(self) -> List[Dict]:
        return self.networks
