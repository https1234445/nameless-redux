"""Windows CI smoke test: instantiate all NAMELESS pages without a visible desktop."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from nameless_redux import ReduxWindow

app = QApplication([])
window = ReduxWindow()
assert window.stack.count() == 9, "All nine workspace pages must exist"
for name in ("Redux Collection", "Overview", "Visuals Studio", "Theme Lab", "Sound Library",
             "Crosshair Studio", "Profiles", "Game Center", "Settings"):
    window.navigate(name)
    assert window.stack.currentWidget() is window.pages[name], name
window.navigate("Overview")
assert window.page_title.text() == "Dashboard"
assert window.effects_preview.base.width() > 0
assert window.top_game_status is not None
# Verify every visual slider changes the filtered half of before/after.
window.navigate("Visuals Studio")
from PySide6.QtGui import QImage
source = QImage(120, 70, QImage.Format_RGB32)
source.fill(0xFF9B8050)
assert window.effects_preview.set_screenshot(source)
original = window.effects_preview.base.copy()
for key, value in (("brightness", 30), ("contrast", 145),
                   ("saturation", 0), ("warmth", 75)):
    window.reset_effects()
    window.effect_sliders[key].setValue(value)
    window.update_effects_preview()
    window.effects_preview.flush_effects()
    assert window.effects_preview.filtered != original, key
    assert window.effects_preview.base == original, "before must remain original"
window.effects_preview._move_comparison(window.effects_preview.width() * .75)
assert 0 <= window.effects_preview.compare_percent <= 100
assert window.pages["Redux Collection"].verticalScrollBar().value() == 0
window.steam_timer.stop()
window.close()
QTimer.singleShot(0, app.quit)
app.exec()
print("NAMELESS UI smoke test passed")
