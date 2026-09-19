#!/usr/bin/env bash
# ============================================================
# NetWatch Linux Setup Script
# One-command setup for Linux: Python venv, dependencies, TShark via apt/dnf/pacman
# ============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ""
echo "============================================================"
echo "  NETWATCH SETUP (Linux)"
echo "============================================================"
echo ""

# Find Python 3.10+
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "[ERROR] Python 3.10+ not found. Please install Python 3.10 or later."
    exit 1
fi

echo "[1/7] Checking Python... PASS"
echo "       Found: $($PYTHON --version)"

# Create venv if missing
VENV_DIR="$REPO_ROOT/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "[2/7] Creating virtual environment... PASS"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "[2/7] Virtual environment exists... PASS"
fi

# Upgrade pip and install requirements
echo "[3/7] Installing Python dependencies... PASS"
"$VENV_PYTHON" -m pip install -q --upgrade pip
if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    "$VENV_PYTHON" -m pip install -q -r "$REPO_ROOT/requirements.txt"
else
    echo "       [WARN] requirements.txt not found"
fi

# Check TShark
echo "[4/7] Checking TShark... PASS"
TSHARK=$("$VENV_PYTHON" scripts/find_tshark.py 2>/dev/null | head -n1)
if [[ -n "$TSHARK" ]]; then
    VER=$("$TSHARK" --version 2>&1 | head -n1)
    echo "       Found: $TSHARK ($VER)"
else
    echo "       Not found"
fi

# Install TShark if missing
if [[ -z "$TSHARK" ]]; then
    echo "[5/7] Installing TShark... PASS"
    if command -v apt-get >/dev/null 2>&1 || command -v apt >/dev/null 2>&1; then
        echo "       apt found - installing tshark..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq tshark
    elif command -v dnf >/dev/null 2>&1; then
        echo "       dnf found - installing wireshark-cli..."
        sudo dnf install -y -q wireshark-cli
    elif command -v pacman >/dev/null 2>&1; then
        echo "       pacman found - installing wireshark-cli..."
        sudo pacman -Sy --noconfirm wireshark-cli
    elif command -v zypper >/dev/null 2>&1; then
        echo "       zypper found - installing wireshark..."
        sudo zypper install -y wireshark
    else
        echo "       [WARN] No supported package manager found."
        echo "       Please install tshark/wireshark-cli via your distribution's package manager."
    fi

    # Re-discover
    TSHARK=$("$VENV_PYTHON" scripts/find_tshark.py 2>/dev/null | head -n1)
fi

# Configure
echo "[6/7] Configuring TShark... PASS"
if [[ -n "$TSHARK" ]]; then
    "$VENV_PYTHON" scripts/configure_tshark.py
    echo "       TSHARK_PATH configured in .env"
else
    echo "       No TShark to configure"
fi

# Verify
echo "[7/7] Verifying setup... PASS"
"$VENV_PYTHON" scripts/check_tshark.py

echo ""
echo "============================================================"
echo "  SETUP COMPLETE"
echo "============================================================"
echo ""

if [[ -z "$TSHARK" ]]; then
    echo "[WARN] TShark was not installed. Live monitoring will be DISABLED."
    echo "Offline modes (PCAP/CSV/JSONL/synthetic) still work."
    echo ""
    echo "To enable live monitoring:"
    echo "  1. Install tshark/wireshark-cli via your package manager"
    echo "  2. Re-run this setup script"
    exit 1
fi

echo "Next steps:"
echo "  source venv/bin/activate"
echo "  python run.py"
echo "  # then open http://localhost:5000"
echo ""
echo "Live Monitor: http://localhost:5000/live"
echo "URL Monitor:  http://localhost:5000/url-monitor"
echo "System:       http://localhost:5000/system"