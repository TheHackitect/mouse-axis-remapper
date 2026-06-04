# 🖱️ Mouse Axis Remapper

**Fix a physically rotated mouse sensor — in software, no firmware needed.**

If your mouse was assembled with its sensor rotated 90°, 180°, or 270° inside the case (moving the mouse up makes the cursor go right, etc.) this app corrects it permanently and transparently.

| Platform | Method | Works with |
|---|---|---|
| **Linux** | evdev grab → uinput inject (kernel-level) | Wayland, Xorg, all DEs |
| **Windows** | WH_MOUSE_LL hook → SendInput (system-wide) | All Windows applications |

---

## How It Works

### Linux

```
Physical mouse motion
       │
       ▼
 /dev/input/eventN   ◄─── evdev grabs the device exclusively
       │                  (raw kernel events — below any display server)
       ▼
  Axis transform      ◄─── rotation math applied
       │
       ▼
 /dev/uinput          ◄─── virtual mouse injected back into the kernel
       │
       ▼
  libinput / Xorg     ◄─── sees only the corrected virtual device ✓
```

The grab happens **below** libinput and every display server, so it works identically on Wayland, Xorg, Sway, Hyprland, KDE, GNOME, or a bare TTY.

### Windows

```
Physical mouse motion
       │
       ▼
  WH_MOUSE_LL hook    ◄─── installed system-wide (no driver needed)
       │                   real WM_MOUSEMOVE events suppressed here
       ▼
  Axis transform      ◄─── same rotation/flip math
       │
       ▼
  SendInput()         ◄─── re-injects corrected relative move
       │                   (LLMHF_INJECTED flag prevents hook re-entry)
       ▼
  All applications    ◄─── see only the corrected movement ✓
```

No kernel driver. No Interception driver. No elevated privileges required. Pure Win32 API via `ctypes`.

---

## Features

| Feature | Detail |
|---|---|
| **Rotation presets** | 0° · 90° CW · 90° CCW · 180° |
| **Independent axis flip** | Flip X and/or Y on top of any rotation |
| **Persistent config** | Saved to `~/.config/mouse-remapper/config.json` |
| **Auto-start on login** | Linux: XDG `.desktop` · Windows: Startup folder `.bat` |
| **Multi-device (Linux)** | Pick any evdev device; re-scannable at runtime |
| **All-mice (Windows)** | System hook intercepts all connected mice |
| **Permission self-healing** | Detects missing `input` group at launch, re-execs via `sg input` |
| **One-click permission fix** | Button runs udev/group fix (Linux only) |
| **Standalone binary** | Single-file ELF (Linux) or `.exe` (Windows) — no Python install needed |
| **Dark Catppuccin Mocha UI** | Clean PyQt6 desktop app |

---

## Supported Platforms

| OS | Version | Status |
|---|---|---|
| **Linux** (any distro) | Kernel ≥ 4.0 | ✅ Fully supported |
| **Windows** | 10 / 11 | ✅ Fully supported |
| macOS | — | ❌ Not supported (see [notes](#macos)) |

---

## Quick Start — Download Binary

Go to the [Releases page](https://github.com/TheHackitect/mouse-axis-remapper/releases) and download the binary for your platform.

### Linux

```bash
chmod +x mouse-axis-remapper
bash setup.sh          # first-time only: permissions, udev, venv
mouse-axis-remapper    # or use: bash run.sh
```

Or install system-wide (adds to app menu):
```bash
bash install.sh
```

### Windows

1. Download `mouse-axis-remapper.exe` from Releases
2. Double-click to run — no installation required
3. (Optional) Check **"Start automatically on login"** in the app

---

## Build from Source

### Requirements

| Platform | Python | Extra |
|---|---|---|
| Linux | 3.9 – 3.12 | `evdev`, `libxcb-cursor0`, `uinput` module |
| Windows | 3.9 – 3.12 | Nothing — only `PyQt6` (ctypes is built in) |

> PyQt6 has no pre-built wheels for Python 3.13+. Use 3.12.x for best compatibility.
> [`pyenv`](https://github.com/pyenv/pyenv) is auto-detected on Linux.

### Linux

```bash
git clone https://github.com/TheHackitect/mouse-axis-remapper.git
cd mouse-axis-remapper
bash setup.sh
bash run.sh
```

`setup.sh` automatically:
1. Finds or installs Python 3.9–3.12 (prefers pyenv 3.12.x)
2. Creates `venv/`, installs `PyQt6` + `evdev`
3. Installs `libxcb-cursor0` (required by Qt 6.5+ on Ubuntu/Debian)
4. Loads `uinput` kernel module + makes it persistent
5. Writes udev rule (`/etc/udev/rules.d/99-uinput.rules`)
6. Adds user to `input` group (auto-reexec handles active session)

### Windows

```bat
git clone https://github.com/TheHackitect/mouse-axis-remapper.git
cd mouse-axis-remapper
setup.bat
run.bat
```

### Build standalone binary

**Linux:**
```bash
venv/bin/pip install pyinstaller
venv/bin/pyinstaller --onefile --name mouse-axis-remapper \
  --collect-all evdev \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  main.py
# Output: dist/mouse-axis-remapper  (~71 MB single ELF)
```

**Windows (run in cmd/PowerShell):**
```bat
venv\Scripts\pip install pyinstaller
venv\Scripts\pyinstaller --onefile --windowed ^
  --name mouse-axis-remapper ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  main.py
:: Output: dist\mouse-axis-remapper.exe
```

---

## Installation (Linux)

```bash
bash install.sh
```

| Installed path | Contents |
|---|---|
| `/usr/local/bin/mouse-axis-remapper` | Executable binary |
| `/usr/share/applications/mouse-axis-remapper.desktop` | App menu entry |
| `/usr/share/icons/hicolor/scalable/apps/mouse-axis-remapper.svg` | App icon |
| `/usr/local/share/mouse-axis-remapper/uninstall.sh` | Uninstaller |

**Uninstall:**
```bash
sudo bash /usr/local/share/mouse-axis-remapper/uninstall.sh
```

**Windows:** The `.exe` is portable. No installation needed. Drop it anywhere and run.

---

## Axis Transformation Reference

| Preset | Raw sensor behaviour | After remapping |
|---|---|---|
| **No rotation** | Normal | Normal |
| **90° Clockwise** | Physical UP → cursor RIGHT | Physical UP → cursor UP ✓ |
| **90° Counter-Clockwise** | Physical UP → cursor LEFT | Physical UP → cursor UP ✓ |
| **180° Flip** | Physical UP → cursor DOWN | Physical UP → cursor UP ✓ |

Tick **Flip X** or **Flip Y** to mirror an axis independently of rotation.

### Math

```
rot=90  CW:   (dx, dy) → ( dy, -dx)
rot=270 CCW:  (dx, dy) → (-dy,  dx)
rot=180:      (dx, dy) → (-dx, -dy)
rot=0:        (dx, dy) → ( dx,  dy)   identity
```

---

## Troubleshooting

### Linux — "No mouse devices detected" / "Permission denied"

Your user must be in the `input` group. The app auto-fixes this at launch via `sg input` re-exec after `setup.sh`. If it still fails:

```bash
sudo usermod -aG input $USER
newgrp input     # activate immediately, or log out and back in
```

### Linux — "Cannot write to /dev/uinput"

```bash
sudo modprobe uinput
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' \
    | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Or just click **⚙ Fix Permissions** in the app.

### Linux — Qt error: "xcb platform plugin not found"

```bash
sudo apt-get install libxcb-cursor0
```

### Windows — "Failed to install mouse hook"

Rare. Try running the app as Administrator (right-click → Run as administrator). WH_MOUSE_LL hooks normally don't need elevation, but some security software can block them.

### Windows — Mouse movement is jumpy or lags

The Windows hook fires for every raw mouse event. If other software is also intercepting mouse events (gaming overlays, accessibility tools), there may be timing conflicts. Close other input-intercepting apps and retry.

### Both platforms — Mouse stops working after app closes

This is by design. On Linux the device grab is released immediately when the worker stops, returning the physical mouse to normal. On Windows the hook is unregistered. Either way, closing the app restores normal mouse behaviour instantly.

---

## System Requirements

| | Linux | Windows |
|---|---|---|
| OS version | Any distro, kernel ≥ 4.0 | Windows 10 / 11 |
| Python (source) | 3.9 – 3.12 | 3.9 – 3.12 |
| Extra packages | `libxcb-cursor0`, `evdev` | None |
| Privileges | `input` group membership | Standard user (no admin) |
| Display server | Wayland, Xorg, or none | N/A |

---

## macOS

macOS uses `IOHIDManager` for low-level input. Remapping mouse axes at system level requires Objective-C/Swift and explicit user approval via Accessibility permissions (since macOS Catalina). A macOS port would need to be built with `pyobjc-framework-IOKit` and is not planned at this time.

---

## Project Structure

```
mouse-axis-remapper/
├── main.py           # Full PyQt6 app — cross-platform (Linux + Windows)
├── setup.sh          # Linux: one-time setup (venv, udev, permissions)
├── setup.bat         # Windows: one-time setup (venv, PyQt6)
├── run.sh            # Linux: development launcher
├── run.bat           # Windows: development launcher
├── install.sh        # Linux: install binary system-wide
├── requirements.txt  # PyQt6 (all), evdev (Linux only)
├── .python-version   # pyenv pin: 3.12.3
└── .gitignore
```

---

## Contributing

Pull requests welcome. Please:
- Test on both Linux (Wayland + Xorg) and Windows if possible
- Keep changes focused — this is intentionally a small, single-purpose tool
- Follow existing code style (type hints, descriptive variable names)

**Bug reports** — include:
- OS + version (`uname -a` / `winver`)
- Python version
- Desktop environment / display server (Linux)
- Mouse USB ID (`lsusb` / Device Manager)
- Full terminal output

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [python-evdev](https://python-evdev.readthedocs.io/) — Linux evdev Python bindings
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — Qt6 Python bindings
- [Catppuccin Mocha](https://github.com/catppuccin/catppuccin) — colour palette used in the UI
- Windows `WH_MOUSE_LL` + `SendInput` Win32 API documentation


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
