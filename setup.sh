#!/usr/bin/env bash
# Mouse Axis Remapper — One-time setup
# Installs dependencies, creates a virtual environment, and fixes
# system permissions so the app can read/write input devices.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

echo "========================================"
echo "  Mouse Axis Remapper — Setup"
echo "========================================"
echo ""

# ── 1. Find Python 3.9+ ──────────────────────────────────────────────────────
echo "[1/4] Finding a compatible Python (3.9+)..."
PYTHON=""

# Prefer pyenv-managed 3.12 when available
if command -v pyenv &>/dev/null; then
    PYENV_VER=$(pyenv versions --bare 2>/dev/null | grep -E '^3\.(1[2-9]|[2-9][0-9])\.' | sort -V | tail -1)
    if [[ -n "$PYENV_VER" ]]; then
        PYTHON="$(pyenv prefix "$PYENV_VER")/bin/python3"
        echo "      Found pyenv Python $PYENV_VER"
    fi
fi

# Fall back to a system Python
if [[ -z "$PYTHON" ]]; then
    for PY_CANDIDATE in python3.12 python3.11 python3.10 python3.9; do
        if command -v "$PY_CANDIDATE" &>/dev/null; then
            PYTHON=$(command -v "$PY_CANDIDATE")
            echo "      Found system $PY_CANDIDATE"
            break
        fi
    done
fi

# Generic 'python3' as last resort (only if >=3.9)
if [[ -z "$PYTHON" ]] && command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print("%d%02d" % sys.version_info[:2])' 2>/dev/null || echo 0)
    if (( PY_VER >= 309 )); then
        PYTHON=$(command -v python3)
        echo "      Found $(python3 --version)"
    fi
fi

if [[ -z "$PYTHON" ]]; then
    echo ""
    echo "ERROR: Python 3.9 or newer is required and was not found."
    echo ""
    echo "Install via pyenv:"
    echo "  curl https://pyenv.run | bash"
    echo "  pyenv install 3.12.3"
    echo "  pyenv local 3.12.3     # run from this folder"
    exit 1
fi
echo "      Using: $PYTHON ($($PYTHON --version))"
echo ""

# ── 2. Create virtual environment ────────────────────────────────────────────
echo "[2/4] Creating virtual environment..."
if [[ -d "$VENV" ]]; then
    echo "      Existing venv found at $VENV"
else
    "$PYTHON" -m venv "$VENV"
    echo "      Created: $VENV"
fi
echo ""

# ── 3. Install system libraries + Python packages ────────────────────────────
echo "[3/4] Installing packages..."

# libxcb-cursor0 is required by Qt 6.5+ on Linux
if command -v apt-get &>/dev/null; then
    sudo apt-get install -y libxcb-cursor0 -qq && echo "      ✓ libxcb-cursor0 installed"
elif command -v dnf &>/dev/null; then
    sudo dnf install -y xcb-util-cursor -q && echo "      ✓ xcb-util-cursor installed"
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm xcb-util-cursor && echo "      ✓ xcb-util-cursor installed"
fi

"$VENV/bin/pip" install --upgrade pip --quiet
# PyQt6 must be installed as a pre-built binary wheel (no qmake needed)
"$VENV/bin/pip" install --only-binary :all: PyQt6
"$VENV/bin/pip" install evdev
echo "      ✓ PyQt6 + evdev ready"
echo ""

# ── 4. System permissions ─────────────────────────────────────────────────────
echo "[4/4] Configuring system permissions (requires sudo)..."

# Load uinput module now (persists until reboot; boot-time load configured below)
sudo modprobe uinput 2>/dev/null && echo "      ✓ uinput module loaded" || true

# Make uinput load automatically on boot
if ! grep -qx uinput /etc/modules-load.d/*.conf 2>/dev/null; then
    echo uinput | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
    echo "      ✓ uinput added to boot modules"
fi

# Persistent udev rule: /dev/uinput owned by group 'input', mode 0660
UDEV_RULE='KERNEL=="uinput", MODE="0660", GROUP="input"'
if [[ ! -f /etc/udev/rules.d/99-uinput.rules ]]; then
    echo "$UDEV_RULE" | sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "      ✓ udev rule written"
else
    echo "      ✓ udev rule already in place"
fi

# Apply correct group to /dev/uinput for the current boot
sudo chgrp input /dev/uinput 2>/dev/null && sudo chmod 660 /dev/uinput 2>/dev/null && \
    echo "      ✓ /dev/uinput permissions applied" || true

# Add user to 'input' group (takes effect in next session)
if id -nG "$USER" | grep -qw input; then
    echo "      ✓ $USER is already in group 'input'"
else
    sudo usermod -aG input "$USER"
    echo "      ✓ $USER added to group 'input'"
fi

echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""

# Warn if group change has not taken effect yet
if ! id -nG | grep -qw input; then
    echo "  ⚠  The 'input' group change requires a new login session."
    echo ""
    echo "     To activate it NOW without logging out:"
    echo "       newgrp input"
    echo "     Or simply log out and back in."
    echo ""
fi

echo "  Launch the app:"
echo "    bash \"$SCRIPT_DIR/run.sh\""
echo ""
