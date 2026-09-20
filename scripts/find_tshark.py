#!/usr/bin/env python3
"""Find and print TShark executable path (for scripts/use in setup)."""

import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from netwatch.live.tshark_locator import locate_tshark


def main() -> int:
    tshark = locate_tshark("")
    if tshark:
        print(tshark)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
