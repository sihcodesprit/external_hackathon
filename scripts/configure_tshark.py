#!/usr/bin/env python3
"""Configure TSHARK_PATH in .env after discovery."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from netwatch.live.tshark_locator import locate_tshark


def main() -> int:
    tshark = locate_tshark("")
    if not tshark:
        print("No TShark found to configure", file=sys.stderr)
        return 1

    env_path = REPO_ROOT / ".env"
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("TSHARK_PATH="):
                lines.append(f"TSHARK_PATH={tshark}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"TSHARK_PATH={tshark}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"TSHARK_PATH={tshark} written to .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
