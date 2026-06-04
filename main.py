#!/usr/bin/env python3
"""
Mouse Axis Remapper
===================
Intercepts raw mouse motion and re-injects it with corrected axes.

Linux  : evdev → uinput (kernel-level, works on Wayland + Xorg)
Windows: WH_MOUSE_LL hook → SendInput (system-wide, all mice)

No firmware access required.  Select the rotation that matches your
sensor orientation and click Start.
"""

import sys
import os

PLATFORM = sys.platform  # 'linux', 'win32', 'darwin'

# ── Linux only: auto re-exec with 'input' group before any Qt import ──────────
if PLATFORM == "linux":
    def _ensure_input_group() -> None:
        import grp, shlex
        try:
            gid = grp.getgrnam("input").gr_gid
        except KeyError:
            return
        # On modern Linux (Ubuntu 26+), sg sets egid/gid but does NOT add the
        # group to the supplemental list returned by os.getgroups(), so we must
        # also check the effective/primary GID to avoid an infinite re-exec loop.
        already_active = (
            gid in os.getgroups()
            or os.getegid() == gid
            or os.getgid() == gid
        )
        if not already_active:
            cmd = " ".join(shlex.quote(a) for a in [sys.executable] + sys.argv)
            os.execvp("sg", ["sg", "input", "-c", cmd])
    _ensure_input_group()
# ─────────────────────────────────────────────────────────────────────────────

import json
import select
import subprocess
import threading
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QCheckBox,
    QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# ── Linux: evdev / uinput ─────────────────────────────────────────────────────
HAS_EVDEV = False
if PLATFORM == "linux":
    try:
        import evdev
        from evdev import InputDevice, UInput, ecodes
        HAS_EVDEV = True
    except ImportError:
        pass

# ── Windows: ctypes low-level hook + SendInput ────────────────────────────────
if PLATFORM == "win32":
    import ctypes
    import ctypes.wintypes as _wt

    _user32   = ctypes.WinDLL("user32",   use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WH_MOUSE_LL      = 14
    WM_MOUSEMOVE     = 0x0200
    WM_QUIT          = 0x0012
    LLMHF_INJECTED   = 0x00000001
    MOUSEEVENTF_MOVE = 0x0001
    INPUT_MOUSE      = 0
    PM_REMOVE        = 0x0001

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt",          _POINT),
            ("mouseData",   _wt.DWORD),
            ("flags",       _wt.DWORD),
            ("time",        _wt.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx",          ctypes.c_long),
            ("dy",          ctypes.c_long),
            ("mouseData",   ctypes.c_ulong),
            ("dwFlags",     ctypes.c_ulong),
            ("time",        ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("_u",)
        _fields_ = [("type", ctypes.c_ulong), ("_u", _INPUT_UNION)]

    _HOOKPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_int, _wt.WPARAM, _wt.LPARAM
    )

    _user32.SetWindowsHookExW.restype  = ctypes.c_void_p
    _user32.CallNextHookEx.restype     = ctypes.c_long
    _user32.GetCursorPos.argtypes      = [ctypes.POINTER(_POINT)]
    _user32.PostThreadMessageW.argtypes = [_wt.DWORD, _wt.UINT, _wt.WPARAM, _wt.LPARAM]
    _kernel32.GetCurrentThreadId.restype = _wt.DWORD

# ── Paths & constants ─────────────────────────────────────────────────────────

CONFIG_PATH  = Path.home() / ".config" / "mouse-remapper" / "config.json"
SCRIPT_PATH  = Path(__file__).resolve()
VENV_PYTHON  = SCRIPT_PATH.parent / "venv" / "bin" / "python3"

if PLATFORM == "win32":
    _STARTUP = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    )
    AUTOSTART = _STARTUP / "mouse-axis-remapper.bat"
else:
    AUTOSTART = Path.home() / ".config" / "autostart" / "mouse-remapper.desktop"

DEFAULTS: dict = {
    "device_path": "",
    "rotation": 90,
    "flip_x": False,
    "flip_y": False,
}

# Label, rotation-degrees pairs shown in the UI
ROTATIONS: list[tuple[str, int]] = [
    ('No rotation — normal',                                          0),
    ('90° Clockwise       ← fix "up moves right / down moves left"', 90),
    ('90° Counter-Clockwise ← fix "up moves left / down moves right"', 270),
    ('180° flip           ← fix "up moves down" (fully inverted)',    180),
]

# ── Config I/O ────────────────────────────────────────────────────────────────

def load_cfg() -> dict:
    try:
        return {**DEFAULTS, **json.loads(CONFIG_PATH.read_text())}
    except Exception:
        return dict(DEFAULTS)


def save_cfg(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ── Axis transformation math ──────────────────────────────────────────────────

def transform(dx: int, dy: int, rot: int, fx: bool, fy: bool) -> tuple[int, int]:
    """
    Rotate then optionally flip relative mouse deltas.

    rot=90  CW:  (x,y) → ( y, -x)   fixes "physical up = cursor right"
    rot=270 CCW: (x,y) → (-y,  x)   fixes "physical up = cursor left"
    rot=180:     (x,y) → (-x, -y)   fixes "physical up = cursor down"
    rot=0:       identity (pass-through)

    Verification for your mouse (sensor rotated 90° CW, rot=90):
      Physical UP   → reports (+dx, 0) → transformed (0, -dx) = cursor UP   ✓
      Physical DOWN → reports (-dx, 0) → transformed (0, +dx) = cursor DOWN ✓
    """
    if rot == 90:
        x, y = dy, -dx
    elif rot == 180:
        x, y = -dx, -dy
    elif rot == 270:
        x, y = -dy, dx
    else:
        x, y = dx, dy
    return (-x if fx else x), (-y if fy else y)


# ── Device discovery ──────────────────────────────────────────────────────────

# Sentinel returned by find_mice() when all devices are unreadable
_PERM_ERROR = "__permission_error__"


def find_mice() -> list[tuple[str, str]]:
    """
    Return [(path, name)] for every device that reports relative X+Y axes.
    On Windows returns a single synthetic entry for the system-wide hook.
    Returns [(_PERM_ERROR, ...)] on Linux if all readable paths fail with PermissionError.
    """
    if PLATFORM == "win32":
        return [("__win_system__", "System Mouse  [Windows — all mice]")]
    if not HAS_EVDEV:
        return []
    result: list[tuple[str, str]] = []
    perm_denied = 0
    paths = list(evdev.list_devices())
    for path in paths:
        try:
            d = InputDevice(path)
            rel = d.capabilities().get(ecodes.EV_REL, [])
            if ecodes.REL_X in rel and ecodes.REL_Y in rel:
                result.append((path, d.name))
            d.close()
        except PermissionError:
            perm_denied += 1
        except Exception:
            pass
    # If we got nothing but had permission errors, tell the caller why
    if not result and perm_denied > 0:
        return [(_PERM_ERROR, f"Permission denied on {perm_denied} device(s)")]
    return result


# ── Remapping worker — Windows (WH_MOUSE_LL → SendInput) ─────────────────────

if PLATFORM == "win32":
    class RemapWorker(QThread):
        """
        Installs a system-wide low-level mouse hook (WH_MOUSE_LL).
        Real WM_MOUSEMOVE events are suppressed; a transformed relative move
        is re-injected via SendInput.  Injected events carry LLMHF_INJECTED
        so the hook ignores them, preventing infinite loops.
        """
        status = pyqtSignal(str, bool)   # (message, is_error)

        def __init__(self, path: str, rot: int, fx: bool, fy: bool) -> None:
            super().__init__()
            self.path  = path
            self.rot   = rot
            self.fx    = fx
            self.fy    = fy
            self._quit = threading.Event()
            self._tid  = 0

        def stop(self) -> None:
            self._quit.set()
            if self._tid:
                _user32.PostThreadMessageW(
                    _wt.DWORD(self._tid), WM_QUIT, 0, 0
                )

        def run(self) -> None:
            self._tid = int(_kernel32.GetCurrentThreadId())

            # Prime the message queue so PostThreadMessageW works immediately
            msg = _wt.MSG()
            _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE)

            hook_ref: list = [None]   # mutable so the closure can read it

            @_HOOKPROC
            def _hook(nCode, wParam, lParam):
                if nCode >= 0 and wParam == WM_MOUSEMOVE:
                    info = ctypes.cast(
                        lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)
                    ).contents
                    # Skip events we injected ourselves
                    if not (info.flags & LLMHF_INJECTED):
                        cur = _POINT()
                        _user32.GetCursorPos(ctypes.byref(cur))
                        dx = info.pt.x - cur.x
                        dy = info.pt.y - cur.y
                        if dx or dy:
                            nx, ny = transform(dx, dy, self.rot, self.fx, self.fy)
                            mi = _MOUSEINPUT()
                            mi.dx     = nx
                            mi.dy     = ny
                            mi.dwFlags = MOUSEEVENTF_MOVE
                            inp = _INPUT()
                            inp.type = INPUT_MOUSE
                            inp.mi   = mi
                            _user32.SendInput(
                                1, ctypes.byref(inp), ctypes.sizeof(_INPUT)
                            )
                        return 1  # suppress original event
                return _user32.CallNextHookEx(hook_ref[0], nCode, wParam, lParam)

            self._hook_proc = _hook   # prevent GC while hook is active
            hook_ref[0] = _user32.SetWindowsHookExW(WH_MOUSE_LL, _hook, None, 0)

            if hook_ref[0] is None:
                err = ctypes.get_last_error()
                self.status.emit(
                    f"Failed to install mouse hook (error {err}).\n\n"
                    "Try running the app as Administrator.", True
                )
                return

            self.status.emit("Active — remapping all mice (Windows hook)", False)

            # Message loop — required for WH_MOUSE_LL to fire
            while not self._quit.is_set():
                if _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        break
                    _user32.TranslateMessage(ctypes.byref(msg))
                    _user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.001)   # 1 ms idle — minimal CPU use

            _user32.UnhookWindowsHookEx(hook_ref[0])
            self.status.emit("Stopped", False)

# ── Remapping worker — Linux (evdev → uinput) ─────────────────────────────────

class _LinuxRemapWorker(QThread):
    """
    Grabs the source device exclusively so raw events are invisible to
    the rest of the OS.  Applies the transformation and re-injects via
    a uinput virtual device.  Button clicks and scroll-wheel events are
    forwarded unchanged.
    """
    status = pyqtSignal(str, bool)   # (message, is_error)

    def __init__(self, path: str, rot: int, fx: bool, fy: bool) -> None:
        super().__init__()
        self.path = path
        self.rot  = rot
        self.fx   = fx
        self.fy   = fy
        self._quit = threading.Event()

    def stop(self) -> None:
        self._quit.set()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:
            self.status.emit(f"Fatal error: {exc}", True)

    def _loop(self) -> None:
        if not HAS_EVDEV:
            self.status.emit("evdev not installed.\nRun:  pip install evdev", True)
            return

        # ── Open source device ────────────────────────────────────────────────
        try:
            src = InputDevice(self.path)
        except PermissionError:
            self.status.emit(
                "Permission denied reading the input device.\n\n"
                "Fix (run setup.sh, or in a terminal):\n"
                "  sudo usermod -aG input $USER\n"
                "Then log out and back in.",
                True,
            )
            return
        except OSError as exc:
            self.status.emit(f"Cannot open device: {exc}", True)
            return

        # ── Create virtual output device ──────────────────────────────────────
        try:
            caps = {k: v for k, v in src.capabilities().items()
                    if k != ecodes.EV_SYN}
            virt = UInput(
                caps,
                name="MouseRemapper Virtual Mouse",
                vendor=0x1BCF, product=0x08A0, version=0x1,
            )
        except PermissionError:
            src.close()
            self.status.emit(
                "Cannot write to /dev/uinput — permission denied.\n\n"
                "Fix:  click 'Fix Permissions' below or run setup.sh.",
                True,
            )
            return
        except Exception as exc:
            src.close()
            self.status.emit(f"Cannot create virtual device: {exc}", True)
            return

        # ── Exclusive grab ────────────────────────────────────────────────────
        try:
            src.grab()
        except OSError as exc:
            virt.close()
            src.close()
            self.status.emit(f"Cannot grab device: {exc}", True)
            return

        self.status.emit(f"Active — remapping: {src.name}", False)

        # ── Main event loop ───────────────────────────────────────────────────
        px = py = 0   # accumulated deltas between SYN frames
        try:
            while not self._quit.is_set():
                # Poll with a short timeout so we can react to stop() quickly
                ready, _, _ = select.select([src.fd], [], [], 0.1)
                if not ready:
                    continue
                for ev in src.read():
                    if self._quit.is_set():
                        break
                    t, c, v = ev.type, ev.code, ev.value

                    if t == ecodes.EV_REL:
                        if c == ecodes.REL_X:
                            px += v
                        elif c == ecodes.REL_Y:
                            py += v
                        else:
                            # Scroll wheel and other relative axes — pass through
                            virt.write(t, c, v)

                    elif t == ecodes.EV_SYN:
                        # Flush one transformed motion frame
                        if px or py:
                            nx, ny = transform(px, py, self.rot, self.fx, self.fy)
                            if nx:
                                virt.write(ecodes.EV_REL, ecodes.REL_X, nx)
                            if ny:
                                virt.write(ecodes.EV_REL, ecodes.REL_Y, ny)
                            px = py = 0
                        virt.syn()

                    else:
                        # Buttons and any other event types — pass through unchanged
                        virt.write(t, c, v)

        except OSError as exc:
            if not self._quit.is_set():
                self.status.emit(f"Device error: {exc}", True)

        finally:
            try:
                src.ungrab()
            except Exception:
                pass
            src.close()
            virt.close()

        if not self._quit.is_set():
            self.status.emit("Stopped unexpectedly — device disconnected?", True)
        else:
            self.status.emit("Stopped", False)


# ── Worker alias — pick the right class for the current platform ──────────────
if PLATFORM != "win32":
    RemapWorker = _LinuxRemapWorker


# ── Autostart helper (platform-aware) ─────────────────────────────────────────

def set_autostart(enabled: bool) -> None:
    if PLATFORM == "win32":
        if enabled:
            # .bat in Windows Startup folder
            exe = str(Path(sys.executable).parent / "mouse-axis-remapper.exe")
            if not Path(exe).exists():
                exe = sys.executable
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART.write_text(f'@echo off\nstart "" "{exe}"\n', encoding="utf-8")
        else:
            AUTOSTART.unlink(missing_ok=True)
    else:
        if enabled:
            py = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Mouse Axis Remapper\n"
                f"Exec={py} {SCRIPT_PATH}\n"
                "Hidden=false\n"
                "NoDisplay=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
        else:
            AUTOSTART.unlink(missing_ok=True)


# ── Qt stylesheet (Catppuccin Mocha palette) ──────────────────────────────────

QSS = """
QWidget            { background: #1e1e2e; color: #cdd6f4; font-size: 13px; }
QMainWindow        { background: #1e1e2e; }
QGroupBox          { border: 1px solid #313244; border-radius: 6px;
                     margin-top: 6px; padding: 10px 8px 8px 8px;
                     color: #a6adc8; font-size: 11px; }
QGroupBox::title   { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QComboBox          { background: #313244; border: 1px solid #45475a;
                     border-radius: 4px; padding: 5px 8px; color: #cdd6f4; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #313244; border: 1px solid #45475a;
    color: #cdd6f4; selection-background-color: #45475a; }
QCheckBox          { spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px; border: 1px solid #585b70;
    border-radius: 3px; background: #313244; }
QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }
QPushButton        { border: none; border-radius: 5px; padding: 7px 18px;
                     font-weight: bold; color: #1e1e2e; }
QPushButton:disabled { background: #45475a !important; color: #6c7086 !important; }
#startBtn          { background: #a6e3a1; }
#startBtn:hover    { background: #94d68f; }
#stopBtn           { background: #f38ba8; }
#stopBtn:hover     { background: #ed6c8a; }
#permBtn           { background: #fab387; font-size: 12px; }
#permBtn:hover     { background: #f39965; }
#refreshBtn        { background: #45475a; color: #cdd6f4; font-size: 12px; }
#refreshBtn:hover  { background: #585b70; }
"""


# ── Main window ───────────────────────────────────────────────────────────────

class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = load_cfg()
        self._worker: "RemapWorker | None" = None
        self._build()
        self._fill_devices()
        self._restore()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setWindowTitle("Mouse Axis Remapper")
        self.setMinimumWidth(560)
        self.setMaximumWidth(700)
        self.setStyleSheet(QSS)

        root = QWidget()
        self.setCentralWidget(root)
        vb = QVBoxLayout(root)
        vb.setSpacing(10)
        vb.setContentsMargins(16, 16, 16, 16)

        # ── Device selection ──────────────────────────────────────────────────
        dg = QGroupBox("Input Device")
        dh = QHBoxLayout(dg)
        self._dev = QComboBox()
        self._dev.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rb = QPushButton("↺")
        rb.setObjectName("refreshBtn")
        rb.setFixedSize(36, 30)
        rb.setToolTip("Refresh device list")
        rb.clicked.connect(self._fill_devices)
        dh.addWidget(self._dev)
        dh.addWidget(rb)
        vb.addWidget(dg)

        # ── Transformation ────────────────────────────────────────────────────
        tg = QGroupBox("Axis Transformation")
        tv = QVBoxLayout(tg)
        self._rot = QComboBox()
        for lbl, _ in ROTATIONS:
            self._rot.addItem(lbl)
        tv.addWidget(self._rot)
        fh = QHBoxLayout()
        self._fx = QCheckBox("Flip X  (mirror left ↔ right)")
        self._fy = QCheckBox("Flip Y  (mirror up ↕ down)")
        fh.addWidget(self._fx)
        fh.addWidget(self._fy)
        tv.addLayout(fh)
        vb.addWidget(tg)

        # ── Status ────────────────────────────────────────────────────────────
        sg = QGroupBox("Status")
        sh = QHBoxLayout(sg)
        self._dot = QLabel("●")
        self._dot.setFixedWidth(22)
        self._dot.setFont(QFont("monospace", 16))
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg = QLabel("Idle")
        self._msg.setWordWrap(True)
        sh.addWidget(self._dot)
        sh.addWidget(self._msg, 1)
        vb.addWidget(sg)

        # ── Start / Stop ──────────────────────────────────────────────────────
        bh = QHBoxLayout()
        self._sb = QPushButton("▶  Start Remapping")
        self._sb.setObjectName("startBtn")
        self._sb.setFixedHeight(42)
        self._sb.clicked.connect(self._start)
        self._qb = QPushButton("■  Stop")
        self._qb.setObjectName("stopBtn")
        self._qb.setFixedHeight(42)
        self._qb.setEnabled(False)
        self._qb.clicked.connect(self._stop)
        bh.addWidget(self._sb)
        bh.addWidget(self._qb)
        vb.addLayout(bh)

        # ── Permissions helper (Linux only) ───────────────────────────────────
        if PLATFORM != "win32":
            pb = QPushButton("⚙  Fix Permissions  (requires sudo — run once after install)")
            pb.setObjectName("permBtn")
            pb.setFixedHeight(32)
            pb.clicked.connect(self._fix_perms)
            vb.addWidget(pb)

        # ── Autostart ─────────────────────────────────────────────────────────
        self._auto = QCheckBox("Start automatically on login")
        self._auto.toggled.connect(set_autostart)
        vb.addWidget(self._auto)

        # ── Info ──────────────────────────────────────────────────────────────
        if PLATFORM == "win32":
            info_text = (
                "ℹ  Remapping via a system-wide low-level mouse hook (WH_MOUSE_LL + SendInput). "
                "All connected mice are remapped. Works across all Windows applications."
            )
        else:
            info_text = (
                "ℹ  Remapping runs at kernel level via evdev/uinput — "
                "fully compatible with Wayland and Xorg.  "
                "The original device is captured exclusively; "
                "the virtual device is what the OS sees."
            )
        hint = QLabel(info_text)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        vb.addWidget(hint)

        self._set_dot("inactive")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_dot(self, state: str) -> None:
        colours = {
            "inactive": "#6c7086",
            "active":   "#a6e3a1",
            "error":    "#f38ba8",
        }
        self._dot.setStyleSheet(f"color: {colours.get(state, '#6c7086')};")

    def _fill_devices(self) -> None:
        """Populate the device combo, preserving the current selection."""
        prev = self._dev.currentData()
        self._dev.clear()
        devices = find_mice()
        if devices and devices[0][0] == _PERM_ERROR:
            self._dev.addItem(
                "⚠  Permission denied — run setup.sh or: newgrp input", ""
            )
            self._dev.setStyleSheet(
                self._dev.styleSheet() + " QComboBox { color: #f38ba8; }"
            )
        elif devices:
            self._dev.setStyleSheet("")  # reset any error colour
            for path, name in devices:
                self._dev.addItem(f"{name}  [{path}]", path)
        else:
            self._dev.addItem("No mouse devices detected", "")
        for i in range(self._dev.count()):
            if self._dev.itemData(i) == prev:
                self._dev.setCurrentIndex(i)
                break

    def _restore(self) -> None:
        """Load saved settings into the UI controls."""
        cfg = self._cfg
        for i in range(self._dev.count()):
            if self._dev.itemData(i) == cfg.get("device_path", ""):
                self._dev.setCurrentIndex(i)
                break
        for i, (_, v) in enumerate(ROTATIONS):
            if v == cfg.get("rotation", 90):
                self._rot.setCurrentIndex(i)
                break
        self._fx.setChecked(cfg.get("flip_x", False))
        self._fy.setChecked(cfg.get("flip_y", False))
        self._auto.setChecked(AUTOSTART.exists())

    def _snapshot(self) -> dict:
        return {
            "device_path": self._dev.currentData() or "",
            "rotation":    ROTATIONS[self._rot.currentIndex()][1],
            "flip_x":      self._fx.isChecked(),
            "flip_y":      self._fy.isChecked(),
        }

    def _lock(self, locked: bool) -> None:
        """Disable/enable controls while remapping is active."""
        self._sb.setEnabled(not locked)
        self._qb.setEnabled(locked)
        self._dev.setEnabled(not locked)
        self._rot.setEnabled(not locked)
        self._fx.setEnabled(not locked)
        self._fy.setEnabled(not locked)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start(self) -> None:
        snap = self._snapshot()
        if not snap["device_path"]:
            QMessageBox.warning(self, "No Device", "Please select a mouse device first.")
            return
        save_cfg(snap)
        self._cfg = snap
        self._worker = RemapWorker(
            snap["device_path"], snap["rotation"], snap["flip_x"], snap["flip_y"]
        )
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        self._lock(True)
        self._msg.setText("Starting…")
        self._set_dot("active")

    def _stop(self) -> None:
        if self._worker:
            self._worker.stop()

    def _on_status(self, txt: str, err: bool) -> None:
        self._msg.setText(txt)
        self._set_dot("error" if err else "active")

    def _on_done(self) -> None:
        self._worker = None
        self._lock(False)
        self._set_dot("inactive")
        if "Active" not in self._msg.text():
            self._msg.setText("Stopped")

    def _fix_perms(self) -> None:
        """Open a terminal and run the one-time permission fix commands."""
        cmd = (
            'sudo usermod -aG input "$USER" && '
            'echo \'KERNEL=="uinput", MODE="0660", GROUP="input"\' '
            '| sudo tee /etc/udev/rules.d/99-uinput.rules && '
            'sudo udevadm control --reload-rules && '
            'sudo udevadm trigger && '
            'echo "" && '
            'echo "✓ Done.  Log out and back in to apply group membership."'
        )
        pause = '; read -p "Press Enter to close this window..."'
        launched = False
        for term, flag in [
            ("gnome-terminal", "--"),
            ("xfce4-terminal", "-x"),
            ("konsole", "-e"),
            ("xterm", "-e"),
            ("x-terminal-emulator", "-e"),
        ]:
            if subprocess.run(["which", term], capture_output=True).returncode == 0:
                subprocess.Popen([term, flag, "bash", "-c", cmd + pause])
                launched = True
                break
        if not launched:
            QMessageBox.information(
                self,
                "Fix Permissions",
                "Run these commands in a terminal, then log out and back in:\n\n"
                "  sudo usermod -aG input $USER\n\n"
                "  echo 'KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"' \\\n"
                "      | sudo tee /etc/udev/rules.d/99-uinput.rules\n\n"
                "  sudo udevadm control --reload-rules && sudo udevadm trigger",
            )

    def closeEvent(self, event) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        save_cfg(self._snapshot())
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MouseAxisRemapper")
    app.setQuitOnLastWindowClosed(True)

    if PLATFORM == "linux" and not HAS_EVDEV:
        QMessageBox.critical(
            None,
            "Missing Dependency",
            "The 'evdev' library is required on Linux.\n\n"
            "Install it:\n"
            "  pip install evdev\n\n"
            "or run:  bash setup.sh",
        )
        sys.exit(1)

    win = App()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
