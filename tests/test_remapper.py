"""
Unit and integration tests for Mouse Axis Remapper
"""

import os
import sys
import time
import ctypes
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import main


class TestTransformationMath(unittest.TestCase):
    def test_rotations(self):
        # rot=0 (Identity)
        self.assertEqual(main.transform(10, 20, 0, False, False), (10, 20))
        self.assertEqual(main.transform(-5, 8, 0, False, False), (-5, 8))

        # rot=90 CW: (x, y) -> (y, -x)
        # Moving physical UP (dx=10, dy=0) -> cursor UP (nx=0, ny=-10)
        self.assertEqual(main.transform(10, 0, 90, False, False), (0, -10))
        # Moving physical DOWN (dx=-10, dy=0) -> cursor DOWN (nx=0, ny=10)
        self.assertEqual(main.transform(-10, 0, 90, False, False), (0, 10))
        # Moving physical RIGHT (dx=0, dy=10) -> cursor RIGHT (nx=10, ny=0)
        self.assertEqual(main.transform(0, 10, 90, False, False), (10, 0))
        # Moving physical LEFT (dx=0, dy=-10) -> cursor LEFT (nx=-10, ny=0)
        self.assertEqual(main.transform(0, -10, 90, False, False), (-10, 0))

        # rot=270 CCW: (x, y) -> (-y, x)
        self.assertEqual(main.transform(10, 0, 270, False, False), (0, 10))
        self.assertEqual(main.transform(0, 10, 270, False, False), (-10, 0))

        # rot=180: (x, y) -> (-x, -y)
        self.assertEqual(main.transform(10, 20, 180, False, False), (-10, -20))

    def test_flips(self):
        # Flip X
        self.assertEqual(main.transform(10, 20, 0, True, False), (-10, 20))
        # Flip Y
        self.assertEqual(main.transform(10, 20, 0, False, True), (10, -20))
        # Both flips
        self.assertEqual(main.transform(10, 20, 0, True, True), (-10, -20))


class TestWindowsCtypes(unittest.TestCase):
    def test_win32_structures(self):
        if main.PLATFORM != "win32":
            self.skipTest("Windows-only test")

        # Win32 x64 struct sizes & alignments
        self.assertEqual(ctypes.sizeof(main._INPUT), 40)
        self.assertEqual(ctypes.sizeof(main._MSLLHOOKSTRUCT), 32)
        self.assertEqual(ctypes.sizeof(main._MOUSEINPUT), 32)
        self.assertEqual(ctypes.sizeof(main._POINT), 8)

    def test_desktop_attached(self):
        if main.PLATFORM != "win32":
            self.skipTest("Windows-only test")

        # Ensure GetCursorPos succeeds
        ctypes.set_last_error(0)
        cur = main._POINT()
        res = main._user32.GetCursorPos(ctypes.byref(cur))
        self.assertTrue(res)
        self.assertEqual(ctypes.get_last_error(), 0)


class TestRemapWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_worker_lifecycle(self):
        if main.PLATFORM != "win32":
            self.skipTest("Windows-only test")

        statuses = []
        worker = main.RemapWorker("__win_system__", 90, False, False)
        worker.status.connect(lambda msg, err: statuses.append((msg, err)))
        worker.start()

        # Let worker start and process messages
        for _ in range(10):
            self.app.processEvents()
            time.sleep(0.03)

        self.assertTrue(worker.isRunning())
        self.assertTrue(any("Active" in s[0] for s in statuses))

        # Stop worker
        worker.stop()
        worker.wait(2000)

        for _ in range(5):
            self.app.processEvents()
            time.sleep(0.03)

        self.assertFalse(worker.isRunning())
        self.assertTrue(any("Stopped" in s[0] for s in statuses))

    def test_gui_controls(self):
        win = main.App()
        win.show()

        for _ in range(5):
            self.app.processEvents()
            time.sleep(0.02)

        self.assertTrue(win._sb.isEnabled())
        self.assertFalse(win._qb.isEnabled())

        # Start remapping
        win._sb.click()
        for _ in range(10):
            self.app.processEvents()
            time.sleep(0.02)

        self.assertFalse(win._sb.isEnabled())
        self.assertTrue(win._qb.isEnabled())
        self.assertIn("Active", win._msg.text())

        # Stop remapping
        win._qb.click()
        for _ in range(10):
            self.app.processEvents()
            time.sleep(0.02)

        self.assertTrue(win._sb.isEnabled())
        self.assertFalse(win._qb.isEnabled())

        win.close()


if __name__ == "__main__":
    unittest.main()
