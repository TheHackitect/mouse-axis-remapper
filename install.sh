#!/usr/bin/env bash
# Mouse Axis Remapper — System Installer
# Installs the pre-built binary, desktop entry, and icon system-wide.
# Run after building with:  bash setup.sh  (or grab a release binary from GitHub)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="$SCRIPT_DIR/dist/mouse-axis-remapper"

# ── Check binary exists ───────────────────────────────────────────────────────
if [[ ! -f "$BINARY" ]]; then
    echo "ERROR: Built binary not found at $BINARY"
    echo "Build it first:  bash setup.sh"
    exit 1
fi

echo "========================================"
echo "  Mouse Axis Remapper — Install"
echo "========================================"
echo ""

# ── Install binary ────────────────────────────────────────────────────────────
echo "[1/4] Installing binary to /usr/local/bin ..."
sudo install -m 755 "$BINARY" /usr/local/bin/mouse-axis-remapper
echo "      ✓ /usr/local/bin/mouse-axis-remapper"
echo ""

# ── Install icon ──────────────────────────────────────────────────────────────
echo "[2/4] Installing icon ..."
sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
sudo tee /usr/share/icons/hicolor/scalable/apps/mouse-axis-remapper.svg > /dev/null << 'SVGEOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <!-- Mouse body -->
  <rect x="16" y="20" width="32" height="38" rx="16" ry="16"
        fill="#313244" stroke="#89b4fa" stroke-width="2.5"/>
  <!-- Left/right button divider -->
  <line x1="32" y1="20" x2="32" y2="40"
        stroke="#89b4fa" stroke-width="1.5" opacity="0.6"/>
  <!-- Scroll wheel -->
  <rect x="28" y="26" width="8" height="10" rx="4"
        fill="#a6adc8"/>
  <!-- Rotation arrows (clockwise) -->
  <path d="M 32 8 A 14 14 0 0 1 46 16" fill="none"
        stroke="#a6e3a1" stroke-width="3" stroke-linecap="round"/>
  <polygon points="46,10 46,18 52,14" fill="#a6e3a1"/>
  <path d="M 32 8 A 14 14 0 0 0 18 16" fill="none"
        stroke="#f38ba8" stroke-width="3" stroke-linecap="round"/>
  <polygon points="18,10 18,18 12,14" fill="#f38ba8"/>
</svg>
SVGEOF
sudo gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
echo "      ✓ /usr/share/icons/hicolor/scalable/apps/mouse-axis-remapper.svg"
echo ""

# ── Install .desktop entry ────────────────────────────────────────────────────
echo "[3/4] Installing desktop entry ..."
sudo tee /usr/share/applications/mouse-axis-remapper.desktop > /dev/null << 'DESKEOF'
[Desktop Entry]
Version=1.1
Type=Application
Name=Mouse Axis Remapper
GenericName=Mouse Calibration Tool
Comment=Fix hardware mouse axis rotation without firmware access
Exec=mouse-axis-remapper
Icon=mouse-axis-remapper
Terminal=false
Categories=Utility;HardwareSettings;Settings;
Keywords=mouse;input;remap;calibrate;rotation;axis;
StartupNotify=true
DESKEOF
sudo update-desktop-database 2>/dev/null || true
echo "      ✓ /usr/share/applications/mouse-axis-remapper.desktop"
echo ""

# ── Save uninstall script ─────────────────────────────────────────────────────
echo "[4/4] Saving uninstall script ..."
sudo mkdir -p /usr/local/share/mouse-axis-remapper
sudo tee /usr/local/share/mouse-axis-remapper/uninstall.sh > /dev/null << 'UNEOF'
#!/usr/bin/env bash
set -e
echo "Removing Mouse Axis Remapper..."
sudo rm -f /usr/local/bin/mouse-axis-remapper
sudo rm -f /usr/share/applications/mouse-axis-remapper.desktop
sudo rm -f /usr/share/icons/hicolor/scalable/apps/mouse-axis-remapper.svg
sudo rm -rf /usr/local/share/mouse-axis-remapper
sudo gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
sudo update-desktop-database 2>/dev/null || true
echo "✓ Uninstalled."
UNEOF
sudo chmod +x /usr/local/share/mouse-axis-remapper/uninstall.sh
echo "      ✓ Uninstall: sudo bash /usr/local/share/mouse-axis-remapper/uninstall.sh"
echo ""

echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "  Launch from app menu: Mouse Axis Remapper"
echo "  Or from terminal:     mouse-axis-remapper"
echo ""
