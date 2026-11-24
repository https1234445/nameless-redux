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
assert window.stack.count() == 8, "All eight workspace pages must exist"
for name in ("Overview", "Visuals Studio", "Theme Lab", "Sound Library",
             "Crosshair Studio", "Profiles", "Game Center", "Settings"):
    window.navigate(name)
    assert window.stack.currentWidget() is window.pages[name], name
window.navigate("Overview")
assert window.page_title.text() == "Dashboard"
assert window.effects_preview.base.width() > 0
assert window.top_game_status is not None
window.steam_timer.stop()
window.close()
QTimer.singleShot(0, app.quit)
app.exec()
print("NAMELESS UI smoke test passed")
