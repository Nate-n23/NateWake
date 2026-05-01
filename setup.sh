#!/usr/bin/env bash
# ============================================================
#  setup.sh — NateWake development environment setup
# ============================================================
# Creates an isolated Python virtual environment, installs all
# desktop development dependencies, and prints usage instructions.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="${PYTHON:-python3}"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          NateWake — Dev Environment Setup        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python version ──────────────────────────────────
echo "▸ Checking Python version..."
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "  ✗ Python 3.10+ required. Found: $PY_VERSION"
    echo "  Install it via your package manager and retry."
    exit 1
fi
echo "  ✓ Python $PY_VERSION found."

# ── 2. Create virtual environment ───────────────────────────
echo ""
echo "▸ Creating virtual environment at .venv/ ..."
if [ -d "$VENV_DIR" ]; then
    echo "  ℹ  .venv/ already exists — skipping creation."
else
    $PYTHON -m venv "$VENV_DIR"
    echo "  ✓ Virtual environment created."
fi

# Activate
source "$VENV_DIR/bin/activate"
echo "  ✓ Virtual environment activated."

# ── 3. Upgrade pip ──────────────────────────────────────────
echo ""
echo "▸ Upgrading pip..."
pip install --quiet --upgrade pip
echo "  ✓ pip upgraded."

# ── 4. Install system-level dependencies (Linux) ────────────
echo ""
echo "▸ Checking system dependencies for Kivy on Linux..."
MISSING_PKGS=()

for pkg in \
    libgl1-mesa-dev \
    libgles2-mesa-dev \
    libmtdev-dev \
    libxmu-dev \
    libxi-dev \
    libx11-dev \
    xclip; do
    if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo ""
    echo "  ⚠  The following system packages may be needed for Kivy:"
    for p in "${MISSING_PKGS[@]}"; do echo "      - $p"; done
    echo ""
    echo "  Install them with:"
    echo "    sudo apt-get install -y ${MISSING_PKGS[*]}"
    echo ""
    read -r -p "  Install now? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        sudo apt-get install -y "${MISSING_PKGS[@]}"
    else
        echo "  ℹ  Skipping system packages. Kivy may fail to render on desktop."
    fi
else
    echo "  ✓ All required system packages are present."
fi

# ── 5. Install Python dependencies ──────────────────────────
echo ""
echo "▸ Installing Python dependencies..."

pip install --quiet \
    "kivy[base]==2.3.0" \
    "kivymd==1.2.0" \
    "pandas>=2.0" \
    "numpy>=1.24" \
    "scikit-learn>=1.3" \
    "scipy>=1.11" \
    "joblib>=1.3" \
    "pytest>=7.4" \
    "pytest-cov>=4.1"

echo "  ✓ All Python packages installed."

# ── 6. Verify imports ───────────────────────────────────────
echo ""
echo "▸ Verifying imports..."

$PYTHON - <<'PYEOF'
import importlib, sys

packages = {
    "kivy":          "kivy",
    "kivymd":        "kivymd",
    "pandas":        "pandas",
    "numpy":         "numpy",
    "sklearn":       "scikit-learn",
    "scipy":         "scipy",
    "joblib":        "joblib",
}

all_ok = True
for mod, display in packages.items():
    try:
        importlib.import_module(mod)
        print(f"  ✓ {display}")
    except ImportError as e:
        print(f"  ✗ {display}: {e}", file=sys.stderr)
        all_ok = False

sys.exit(0 if all_ok else 1)
PYEOF

echo ""
echo "▸ Running unit tests..."
cd "$PROJECT_DIR"
python -m pytest tests/test_analytics.py -v --tb=short 2>&1 || true

# ── 7. Instructions ─────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                   READY!                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  To activate the environment in a new shell:"
echo "    source .venv/bin/activate"
echo ""
echo "  ┌─ Run on DESKTOP (development) ─────────────────"
echo "  │  source .venv/bin/activate"
echo "  │  python main.py"
echo "  └────────────────────────────────────────────────"
echo ""
echo "  ┌─ Run UNIT TESTS ───────────────────────────────"
echo "  │  source .venv/bin/activate"
echo "  │  pytest tests/test_analytics.py -v"
echo "  │  # With coverage:"
echo "  │  pytest tests/ -v --cov=. --cov-report=term-missing"
echo "  └────────────────────────────────────────────────"
echo ""
echo "  ┌─ Build ANDROID APK (requires buildozer) ───────"
echo "  │  # Install buildozer first (once, globally):"
echo "  │  pip install buildozer"
echo "  │  sudo apt-get install -y \\"
echo "  │    git zip unzip openjdk-17-jdk \\"
echo "  │    autoconf libtool pkg-config zlib1g-dev \\"
echo "  │    libncurses5-dev libssl-dev"
echo "  │"
echo "  │  # Debug APK:"
echo "  │  buildozer android debug"
echo "  │"
echo "  │  # Debug + deploy to connected USB device:"
echo "  │  buildozer android debug deploy run logcat"
echo "  └────────────────────────────────────────────────"
echo ""
echo "  ┌─ Useful buildozer paths ───────────────────────"
echo "  │  APK output: .buildozer/android/platform/build-*/dists/natewake/build/outputs/"
echo "  │  Logs:       .buildozer/android/platform/build-*/dists/natewake/"
echo "  └────────────────────────────────────────────────"
echo ""
