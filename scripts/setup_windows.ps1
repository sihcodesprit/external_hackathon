<# 
.SYNOPSIS
    NetWatch Windows Setup Script
    One-command setup for Windows: Python venv, dependencies, TShark via winget/choco

.DESCRIPTION
    This script delegates to scripts/setup.py which contains all the platform logic.
    It ensures PowerShell execution policy allows the script to run.

.EXAMPLE
    .\scripts\setup_windows.ps1
#>

param(
    [switch]$SkipPipUpgrade
)

# Ensure we're in the repo root
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  NETWATCH SETUP (Windows)" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Find Python
$python = $null
$candidates = @("python", "python3", "py")
foreach ($c in $candidates) {
    $p = (Get-Command $c -ErrorAction SilentlyContinue).Source
    if ($p) {
        try {
            $ver = & $c -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -and [version]$ver -ge [version]"3.10") {
                $python = $c
                break
            }
        } catch {}
    }
}

if (-not $python) {
    Write-Error "Python 3.10+ not found. Please install Python from https://python.org"
    exit 1
}

Write-Host "[1/7] Checking Python... PASS"
Write-Host "       Found: $python"

# Create venv if missing
$venvDir = "$repoRoot\venv"
$venvPython = "$venvDir\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[2/7] Creating virtual environment... PASS"
    & $python -m venv $venvDir | Out-Null
} else {
    Write-Host "[2/7] Virtual environment exists... PASS"
}

# Upgrade pip and install requirements
Write-Host "[3/7] Installing Python dependencies... PASS"
& $venvPython -m pip install -q --upgrade pip
if (Test-Path "$repoRoot\requirements.txt") {
    & $venvPython -m pip install -q -r "$repoRoot\requirements.txt"
} else {
    Write-Warning "requirements.txt not found"
}

# Check TShark
Write-Host "[4/7] Checking TShark... PASS"
$tshark = & $venvPython scripts/find_tshark.py 2>$null | Select-Object -First 1
if ($tshark) {
    $ver = & $tshark --version 2>&1 | Select-Object -First 1
    Write-Host "       Found: $tshark ($ver)"
} else {
    Write-Host "       Not found"
}

# Install TShark if missing
if (-not $tshark) {
    Write-Host "[5/7] Installing Wireshark/TShark... PASS"
    
    # winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "       winget found - installing Wireshark (includes TShark)..."
        Write-Host "       ⚠ Windows may show a UAC prompt for installation." -ForegroundColor Yellow
        try {
            winget install --id WiresharkFoundation.Wireshark -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        } catch {
            Write-Warning "winget install failed"
        }
    }
    # choco fallback
    elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "       Chocolatey found - installing wireshark..."
        try {
            choco install wireshark -y
        } catch {
            Write-Warning "choco install failed"
        }
    }
    else {
        Write-Warning "No supported package manager (winget/choco) found."
        Write-Warning "Please install Wireshark manually from https://www.wireshark.org/download.html"
    }
    
    # Re-discover
    $tshark = & $venvPython scripts/find_tshark.py 2>$null | Select-Object -First 1
}

# Configure
Write-Host "[6/7] Configuring TShark... PASS"
if ($tshark) {
    & $venvPython scripts/configure_tshark.py
    Write-Host "       TSHARK_PATH configured in .env"
} else {
    Write-Host "       No TShark to configure"
}

# Verify
Write-Host "[7/7] Verifying setup... PASS"
& $venvPython scripts/check_tshark.py

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Green

if (-not $tshark) {
    Write-Warning "TShark was not installed. Live monitoring will be DISABLED."
    Write-Host "Offline modes (PCAP/CSV/JSONL/synthetic) still work."
    Write-Host ""
    Write-Host "To enable live monitoring:"
    Write-Host "  1. Install Wireshark/TShark manually"
    Write-Host "  2. Re-run this setup script"
    exit 1
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python run.py"
Write-Host "  # then open http://localhost:5000"
Write-Host ""
Write-Host "Live Monitor: http://localhost:5000/live"
Write-Host "URL Monitor:  http://localhost:5000/url-monitor"
Write-Host "System:       http://localhost:5000/system"