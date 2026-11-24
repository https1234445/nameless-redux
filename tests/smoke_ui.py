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
# A custom screenshot survives startup and is not replaced by a pending Steam response.
import tempfile
with tempfile.TemporaryDirectory() as preview_dir:
    preview_file = str(Path(preview_dir) / "rob_run_test.png")
    assert source.save(preview_file)
    previous = window.settings.value("preview/screenshot", "")
    try:
        window.settings.setValue("preview/screenshot", preview_file)
        window._preview_request_id = 4
        window.load_initial_screenshot()
        assert "rob_run_test.png" in window.preview_source.text()
        assert window.effects_preview.real_screenshot
        assert window._preview_request_id == 4
    finally:
        if previous:
            window.settings.setValue("preview/screenshot", previous)
        else:
            window.settings.remove("preview/screenshot")
window.effects_preview._move_comparison(window.effects_preview.width() * .75)
assert 0 <= window.effects_preview.compare_percent <= 100
assert window.pages["Redux Collection"].verticalScrollBar().value() == 0
collection_scroll = window.pages["Redux Collection"]
collection_scroll.verticalScrollBar().setValue(collection_scroll.verticalScrollBar().maximum())
window.navigate("Overview")
window.navigate("Redux Collection")
assert collection_scroll.verticalScrollBar().value() == 0, "page must reopen at top"
# Every animated component obeys the performance / motion setting.
from nameless_redux import ShimmerText, AuroraCard, ReduxCover
window.motion_check.setChecked(False)
for widget_type in (ShimmerText, AuroraCard, ReduxCover):
    for widget in window.findChildren(widget_type):
        timer = widget._motion if isinstance(widget, ReduxCover) else widget._clock
        assert not timer.isActive(), widget_type.__name__
window.motion_check.setChecked(True)
for widget_type in (ShimmerText, AuroraCard, ReduxCover):
    for widget in window.findChildren(widget_type):
        timer = widget._motion if isinstance(widget, ReduxCover) else widget._clock
        assert timer.isActive(), widget_type.__name__
# Sakura's game install must remain visibly disabled until mod support is verified.
from PySide6.QtWidgets import QPushButton
install_buttons = [b for b in window.findChildren(QPushButton)
                   if b.text().startswith("INSTALL INTO ROB RUN")]
assert len(install_buttons) == 1
assert not install_buttons[0].isEnabled()
# A collection selection changes local preview only, without a game patch.
from PySide6.QtWidgets import QMessageBox
original_info = QMessageBox.information
QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok
try:
    window.activate_collection_pack("Coral", "SAKURA DREAM")
    assert window.settings.value("collection/active") == "SAKURA DREAM"
    assert window.effect_sliders["brightness"].value() == 12
    assert window.collection_active.text().endswith("SAKURA DREAM")
    assert window.effects_preview.filtered != window.effects_preview.base
    # Export is a safe local manifest; it must not contain a game install path.
    import json
    import tempfile
    from PySide6.QtWidgets import QFileDialog
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "sakura.json")
        original_dialog = QFileDialog.getSaveFileName
        QFileDialog.getSaveFileName = lambda *args, **kwargs: (path, "NAMELESS presets (*.json)")
        try:
            window.export_collection_pack("SAKURA DREAM", "Coral")
        finally:
            QFileDialog.getSaveFileName = original_dialog
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["format"] == "nameless-redux-look-v1"
        assert data["kind"] == "preview-only"
        assert data["game_files_modified"] is False
        assert data["effects"]["brightness"] == 12
        assert "install_path" not in data
finally:
    QMessageBox.information = original_info
window.steam_timer.stop()
window.close()
QTimer.singleShot(0, app.quit)
app.exec()
print("NAMELESS UI smoke test passed")
