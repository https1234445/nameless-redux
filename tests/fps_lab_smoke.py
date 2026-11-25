"""Offscreen FPS LAB validation: honest comparisons, guide and hardware."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtWidgets import QApplication
from fps_lab import FPSLab, PROFILES, hardware_snapshot, compare_fps

app = QApplication.instance() or QApplication([])
snapshot = hardware_snapshot()
assert "os" in snapshot and "logical_cpus" in snapshot
assert len(PROFILES) == 3
assert compare_fps(30, 45)["change_percent"] == 50.0
assert compare_fps(60, 45)["delta_fps"] == -15
for invalid in (0, -10, 1001, True, "30"):
    try:
        compare_fps(invalid, 40)
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted invalid FPS value: %r" % invalid)
dialog = FPSLab()
assert dialog.profile.count() == 3
assert dialog.comparison()["delta_fps"] == 0
dialog.profile.setCurrentIndex(1)
assert "medium" in dialog.guide.toPlainText().lower()
dialog.before.setValue(30)
dialog.after.setValue(40)
dialog.show_comparison()
assert "+10.0 FPS" in dialog.result.text()
dialog.close()
print("FPS LAB: diagnostics, guides, comparisons and offscreen dialog OK")
