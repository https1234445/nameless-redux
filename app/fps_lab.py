from ui_controls import ClickOnlyComboBox
"""FPS LAB: read-only hardware diagnostics and honest, user-entered FPS comparisons.

No registry changes, process injection, game-file edits, or invented FPS gains.
"""
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QTextEdit, QFileDialog, QMessageBox, QFrame)


def hardware_snapshot():
    """Best-effort diagnostics; never require admin privileges."""
    info = {
        "os": platform.platform(),
        "processor": platform.processor() or "Not reported",
        "logical_cpus": os.cpu_count(),
        "ram_gib": None,
        "gpu": "Not detected (check Windows Device Manager)",
    }
    if os.name == "nt":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            state = MEMORYSTATUSEX()
            state.dwLength = ctypes.sizeof(state)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
                info["ram_gib"] = round(state.ullTotalPhys / (1024 ** 3), 1)
        except (AttributeError, OSError, ValueError):
            pass
    else:
        try:
            info["ram_gib"] = round(
                os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") /
                (1024 ** 3), 1)
        except (AttributeError, ValueError, OSError):
            pass
    return info


PROFILES = {
    "LOW-END / STABILITY": (
        "Start with the lowest in-game graphics preset and 720p resolution.",
        "Disable or lower shadows, reflections, anti-aliasing and post-processing if ROB RUN exposes these options.",
        "Try an in-game FPS cap that your machine can sustain; stable frame pacing matters more than a peak FPS.",
        "Close unnecessary background apps manually and keep the laptop plugged in.",
    ),
    "BALANCED / CLARITY": (
        "Start with the medium in-game preset and native resolution.",
        "Lower shadows and reflections before sacrificing texture clarity.",
        "Compare the same scene and resolution before and after each change.",
    ),
    "COMPETITIVE / LATENCY": (
        "Prefer a consistent frame rate and monitor refresh-rate settings you understand.",
        "Use the game's own supported latency, display and fullscreen options where available.",
        "Change one option at a time; record both average FPS and frame-time stability.",
    ),
}


def compare_fps(before, after):
    """Only calculate measured/user-reported values, never predicted gains."""
    if not isinstance(before, (int, float)) or isinstance(before, bool):
        raise ValueError("FPS must be numeric")
    if not isinstance(after, (int, float)) or isinstance(after, bool):
        raise ValueError("FPS must be numeric")
    if not 1 <= before <= 1000 or not 1 <= after <= 1000:
        raise ValueError("FPS values must be between 1 and 1000")
    return {"before_fps": before, "after_fps": after,
            "delta_fps": round(after - before, 2),
            "change_percent": round((after - before) / before * 100, 2)}


class FPSLab(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NAMELESS REDUX / FPS LAB")
        self.resize(850, 740)
        self.setMinimumSize(650, 580)
        self.setStyleSheet("""
            QDialog { background: #101326; color: #F5F2FF; }
            QLabel { color: #F5F2FF; }
            QLabel#labTitle { font-size: 26px; font-weight: 900; color: #CDB5FF; }
            QLabel#labNote { color: #AEB8D3; }
            QFrame { background: #1B203A; border: 1px solid #42486C; border-radius: 12px; }
            QPushButton, QComboBox, QSpinBox { background: #302B52; color: #F8F4FF;
                border: 1px solid #69618E; border-radius: 7px; padding: 8px; }
            QPushButton:hover { background: #493C78; }
            QTextEdit { background: #151A30; color: #F2EEFF; border: 1px solid #45496A;
                border-radius: 8px; padding: 10px; }
        """)
        root = QVBoxLayout(self)
        root.setSpacing(13)
        title = QLabel("FPS LAB  /  PERFORMANCE STUDIO")
        title.setObjectName("labTitle")
        root.addWidget(title)
        note = QLabel("Read-only diagnostics. Recommendations are not guaranteed FPS boosts.")
        note.setObjectName("labNote")
        root.addWidget(note)
        self.snapshot = hardware_snapshot()
        self.hardware = QLabel()
        self.hardware.setWordWrap(True)
        root.addWidget(self.hardware)
        self.refresh_hardware()
        refresh = QPushButton("REFRESH HARDWARE INFO")
        refresh.clicked.connect(self.refresh_hardware)
        root.addWidget(refresh)
        root.addWidget(QLabel("OPTIMIZATION GUIDE"))
        self.profile = ClickOnlyComboBox()
        self.profile.addItems(PROFILES)
        self.profile.currentTextChanged.connect(self.refresh_guide)
        root.addWidget(self.profile)
        self.guide = QTextEdit()
        self.guide.setReadOnly(True)
        root.addWidget(self.guide, 1)
        self.refresh_guide()
        root.addWidget(QLabel("YOUR MEASURED FPS  /  SAME SCENE AND SETTINGS EXCEPT TESTED CHANGE"))
        inputs = QHBoxLayout()
        self.before = QSpinBox()
        self.before.setRange(1, 1000)
        self.before.setValue(30)
        self.before.setPrefix("BEFORE  ")
        self.after = QSpinBox()
        self.after.setRange(1, 1000)
        self.after.setValue(30)
        self.after.setPrefix("AFTER  ")
        inputs.addWidget(self.before)
        inputs.addWidget(self.after)
        root.addLayout(inputs)
        self.result = QLabel("Enter FPS readings and select COMPARE.")
        root.addWidget(self.result)
        buttons = QHBoxLayout()
        compare = QPushButton("COMPARE FPS")
        compare.clicked.connect(self.show_comparison)
        buttons.addWidget(compare)
        export = QPushButton("EXPORT REPORT JSON")
        export.clicked.connect(self.export_report)
        buttons.addWidget(export)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)
        footer = QLabel("FPS readings are entered by you, not captured by NAMELESS. ROB RUN files remain untouched.")
        footer.setWordWrap(True)
        footer.setObjectName("labNote")
        root.addWidget(footer)

    def refresh_hardware(self):
        self.snapshot = hardware_snapshot()
        d = self.snapshot
        ram = str(d["ram_gib"]) + " GiB" if d["ram_gib"] is not None else "Unavailable"
        self.hardware.setText(
            "SYSTEM  /  " + d["os"] + "\nCPU  /  " + d["processor"] +
            "\nLOGICAL THREADS  /  " + str(d["logical_cpus"]) +
            "\nRAM  /  " + ram + "\nGPU  /  " + d["gpu"])

    def refresh_guide(self, *_):
        self.guide.setPlainText("\n\n".join(
            "%02d  %s" % (i, line)
            for i, line in enumerate(PROFILES[self.profile.currentText()], 1)))

    def comparison(self):
        return compare_fps(self.before.value(), self.after.value())

    def show_comparison(self):
        d = self.comparison()
        self.result.setText(
            "USER-REPORTED RESULT  /  %+.1f FPS  (%+.1f%%)" %
            (d["delta_fps"], d["change_percent"]))

    def export_report(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save FPS LAB report", "nameless-fps-lab.json", "JSON (*.json)")
        if not filename:
            return
        data = {
            "format": "nameless-fps-lab-v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source": "user-entered-fps",
            "automated_benchmark": False,
            "profile": self.profile.currentText(),
            "hardware": self.snapshot,
            "comparison": self.comparison(),
            "game_files_modified": False,
        }
        try:
            Path(filename).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.result.setText("Report saved. FPS numbers were user-entered.")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
