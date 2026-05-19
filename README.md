# 🖱️ Mouse Axis Remapper

**Fix a physically rotated mouse sensor — in software, at the kernel level — no firmware, no hardware mods, no driver restarts.**

If your mouse was assembled with its sensor rotated 90°, 180°, or 270° relative to the case (moving the mouse up makes the cursor go right, etc.), this app corrects it permanently and transparently, even on Wayland.

---

## Screenshots

> *Catppuccin Mocha dark theme GUI — pick your device, choose the rotation, click Start.*

![Mouse Axis Remapper GUI](https://raw.githubusercontent.com/TheHackitect/mouse-axis-remapper/main/assets/screenshot.png)

---

## How It Works

Most "mouse remappers" hook into the display server (X11 `xinput`, Wayland compositor settings, etc.) and only work in one environment. This app works differently:

```
Physical mouse motion
       │
       ▼
 /dev/input/eventN   ◄─── evdev grabs the device exclusively
       │                  (raw kernel events — no display server involved)
       ▼
  Axis transform      ◄─── rotation math applied (90°/180°/270° + optional flip)
       │
       ▼
 /dev/uinput          ◄─── a virtual mouse is injected back into the kernel
       │
       ▼
  libinput / Xorg     ◄─── sees only the already-corrected virtual device
       │
       ▼
  Your desktop cursor moves correctly ✓
```

Because interception happens **before** any display server sees the device, it works identically on:
- **Wayland** (GNOME, KDE Plasma, Sway, Hyprland, …)
- **Xorg** / X11
- **Headless / TTY** environments

---

## Features

| Feature | Detail |
|---|---|
| **Rotation presets** | 0° · 90° CW · 90° CCW · 180° |
| **Independent axis flip** | Flip X and/or Y independently on top of any rotation |
| **Persistent config** | Settings saved to `~/.config/mouse-remapper/config.json` |
| **Auto-start on login** | One-click XDG autostart `.desktop` entry creation |
| **Multi-device support** | Detects all relative-axis input devices; re-scannable at runtime |
| **Zero display-server dependency** | Works on Wayland, Xorg, and headless |
| **Permission self-healing** | Detects missing `input` group at launch; re-execs under `sg input` automatically |
| **One-click permission fix** | "Fix Permissions" button runs `setup.sh` logic without needing a terminal |
| **Standalone binary** | Single-file 71 MB ELF executable — no Python install required |

---

## Quick Start (Standalone Binary)

### 1. Download the latest release

Go to the [Releases page](https://github.com/TheHackitect/mouse-axis-remapper/releases) and download `mouse-axis-remapper`.

### 2. Run setup (once)

```bash
chmod +x mouse-axis-remapper
sudo ./mouse-axis-remapper --setup   # not needed if you use install.sh
```

Or use the full installer:

```bash
curl -fsSL https://raw.githubusercontent.com/TheHackitect/mouse-axis-remapper/main/setup.sh | bash
```

### 3. Install system-wide (optional)

```bash
bash install.sh
```

This places the binary in `/usr/local/bin`, adds a `.desktop` entry to your app launcher, and installs the icon — so it appears in GNOME Activities, KDE Application Launcher, etc.

### 4. Launch

```bash
mouse-axis-remapper
```

Or search for **Mouse Axis Remapper** in your app menu.

---

## Building from Source

### Requirements

- Linux (kernel ≥ 4.0 for uinput)
- Python 3.9 – 3.12 (PyQt6 has no Python 3.13+ binary wheels yet)
- [`pyenv`](https://github.com/pyenv/pyenv) recommended (auto-used if available)

### Setup

```bash
git clone https://github.com/TheHackitect/mouse-axis-remapper.git
cd mouse-axis-remapper
bash setup.sh
```

`setup.sh` does the following automatically:

1. Finds or installs a compatible Python (prefers pyenv 3.12.x)
2. Creates a local virtualenv (`venv/`)
3. Installs `PyQt6` and `evdev` (using pre-built wheels — no build tools needed)
4. Installs system dependency `libxcb-cursor0` (required by Qt 6.5+ on Ubuntu/Debian)
5. Loads the `uinput` kernel module and makes it persistent across reboots
6. Writes a udev rule so `/dev/uinput` is writable by the `input` group
7. Adds your user to the `input` group (takes effect at next login, or immediately via auto-reexec)

### Run

```bash
bash run.sh
# or
venv/bin/python3 main.py
```

### Build standalone binary

```bash
venv/bin/pip install pyinstaller
venv/bin/pyinstaller --onefile --name mouse-axis-remapper \
  --collect-all evdev \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  main.py
```

Output: `dist/mouse-axis-remapper` (single self-contained ELF binary, ~71 MB)

---

## Installation

```bash
bash install.sh
```

| Path | Contents |
|---|---|
| `/usr/local/bin/mouse-axis-remapper` | Executable binary |
| `/usr/share/applications/mouse-axis-remapper.desktop` | App menu entry |
| `/usr/share/icons/hicolor/scalable/apps/mouse-axis-remapper.svg` | App icon |
| `/usr/local/share/mouse-axis-remapper/uninstall.sh` | Uninstaller |

### Uninstall

```bash
sudo bash /usr/local/share/mouse-axis-remapper/uninstall.sh
```

---

## Axis Transformation Reference

The UI offers four rotation presets. Here's what each one fixes:

| Preset | Raw sensor behaviour | After remapping |
|---|---|---|
| **No rotation** | Normal mouse | Normal |
| **90° Clockwise** | Physical UP → cursor RIGHT | Physical UP → cursor UP ✓ |
| **90° Counter-Clockwise** | Physical UP → cursor LEFT | Physical UP → cursor UP ✓ |
| **180° Flip** | Physical UP → cursor DOWN | Physical UP → cursor UP ✓ |

You can additionally tick **Flip X** or **Flip Y** to mirror either axis, independently of the rotation — useful for mice with both a rotated sensor and a mirrored housing.

### Math

```python
rot=90  CW:   (dx, dy) → ( dy, -dx)
rot=270 CCW:  (dx, dy) → (-dy,  dx)
rot=180:      (dx, dy) → (-dx, -dy)
rot=0:        (dx, dy) → ( dx,  dy)   # identity
```

Verification for a 90° CW sensor (physical UP reports +dx):
```
Physical UP   →  reports (dx=+1, dy=0)  →  transformed (0, -1)  =  cursor UP   ✓
Physical DOWN →  reports (dx=-1, dy=0)  →  transformed (0, +1)  =  cursor DOWN ✓
Physical LEFT →  reports (dx=0, dy=+1)  →  transformed (+1, 0)  =  cursor RIGHT ✓
```

---

## Troubleshooting

### "No mouse devices detected" / "Permission denied"

Your user needs to be in the `input` group. The app detects this at startup and re-execs automatically after `setup.sh`. If it still fails:

```bash
sudo usermod -aG input $USER
# Then either log out and back in, or:
newgrp input
```

### "Cannot write to /dev/uinput"

The `uinput` kernel module must be loaded and the udev rule must be in place. Click the **⚙ Fix Permissions** button in the app, or run:

```bash
sudo modprobe uinput
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### App won't start — "xcb platform plugin not found"

```bash
sudo apt-get install libxcb-cursor0
```

### Mouse stops working after I close the app

That's by design — the app holds an **exclusive grab** on the device while running so raw events go through the remapper only. When you stop remapping, the original device is ungrabbed and returns to normal immediately.

### It works on Xorg but not Wayland (or vice versa)

It should work on both — the interception happens below the display server layer. If you see issues, ensure the virtual device created by uinput is recognised (`evdev ls` / `libinput list-devices`). File an issue with your compositor name and version.

---

## System Requirements

| Component | Minimum |
|---|---|
| OS | Linux (any distribution) |
| Kernel | 4.0+ (uinput support) |
| Python (source build only) | 3.9 – 3.12 |
| Display server | Any (Wayland, Xorg, none) |
| Packages | `libxcb-cursor0` (Ubuntu/Debian), `uinput` kernel module |

> **Windows / macOS:** Not supported. This tool relies on Linux-specific kernel interfaces (`evdev` and `uinput`). See [Platform Notes](#platform-notes) below.

---

## Platform Notes

### Why Linux only?

This tool is built on two Linux kernel interfaces that have no direct equivalents on other platforms:

- **`evdev`** (`/dev/input/event*`) — the kernel's raw input event interface  
- **`uinput`** (`/dev/uinput`) — allows userspace to create virtual input devices that the rest of the kernel treats as real hardware

These are Linux-specific. There is no portable equivalent.

### Windows

Windows does not expose raw HID mouse events through a grab-and-reinject interface like evdev/uinput. The closest equivalents would be:

- **Win32 Raw Input API** + a kernel-mode filter driver (requires code signing)
- **Interception driver** (open-source, but requires disabling driver signature enforcement)
- **AutoHotkey v2** with `A_Cursor` hooks (limited — works at application level, not kernel level)

A Windows port would need to be rebuilt almost entirely from scratch using a different technology stack.

### macOS

macOS uses IOHIDFamily for low-level input. A port would require Objective-C/Swift and Apple's `IOHIDManager` API. The Python library `pyobjc-framework-IOKit` can access it, but mouse remapping at the kernel level on macOS is significantly more restricted since macOS Catalina (system integrity protection, driver notarisation).

---

## Project Structure

```
mouse-axis-remapper/
├── main.py           # Full PyQt6 application (device picker + remapping worker)
├── setup.sh          # One-time system setup (permissions, udev, venv)
├── run.sh            # Development launcher (activates venv + input group)
├── install.sh        # System installer (binary → /usr/local/bin + .desktop)
├── requirements.txt  # Python dependencies (PyQt6, evdev)
├── .python-version   # pyenv version pin (3.12.3)
└── .gitignore
```

---

## Contributing

Pull requests are welcome. Please:
- Keep changes scoped — this is an intentionally small, focused tool
- Test on both Wayland and Xorg if possible
- Follow the existing code style (type hints, Google-style docstrings)

### Filing a bug report

Include:
- Linux distribution and version (`lsb_release -a`)
- Kernel version (`uname -r`)
- Desktop environment and display server (`echo $XDG_SESSION_TYPE`)
- Mouse device ID (`lsusb | grep -i mouse`)
- Full error output from the terminal

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [python-evdev](https://python-evdev.readthedocs.io/) — the Python binding for Linux evdev
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — Qt6 bindings for Python
- [Catppuccin](https://github.com/catppuccin/catppuccin) — the Mocha colour palette used in the UI
- The Linux kernel `uinput` documentation and community
