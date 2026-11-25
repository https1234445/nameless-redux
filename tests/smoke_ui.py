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
assert window.stack.count() == 10, "All ten workspace pages must exist"
for name in ("World Reborn", "Redux Collection", "Overview", "Visuals Studio", "Theme Lab", "Sound Library",
             "Crosshair Studio", "Profiles", "Game Center", "Settings"):
    window.navigate(name)
    assert window.stack.currentWidget() is window.pages[name], name
window.navigate("World Reborn")
assert window.pages["World Reborn"].hero_title.text() == "SAKURA DREAM"
# Release gate: the collection must not contain the heavy Visual Lab.
world = window.pages["World Reborn"]
assert not hasattr(world, "split"), "Visual Lab must be separate from World Reborn"
assert len(world.angle_buttons) == 5
assert all(not button.icon().isNull() for button in world.angle_buttons), "Missing car thumbnails"
# All reference-style top tabs navigate to their real workspace pages.
for destination, tab in window.quick_tab_buttons.items():
    tab.click()
    assert window.stack.currentWidget() is window.pages[destination], destination
    assert tab.isChecked(), destination
window.navigate("World Reborn")
# Slider changes must be deferred, never synchronously force pixel processing.
window.navigate("Visuals Studio")
window.effect_sliders["brightness"].setValue(17)
assert window.effects_preview._render_timer.isActive(), "Slider must debounce processing"
window.effects_preview.flush_effects()
window.navigate("World Reborn")
for index, name in enumerate(("SAKURA DREAM", "NEON NIGHT", "FROSTBITE", "CRIMSON")):
    window.pages["World Reborn"].select_pack(index)
    assert window.pages["World Reborn"].hero_title.text() == name
# World Reborn's PREVIEW HERE must open the exact selected world.
world = window.pages["World Reborn"]
world.select_pack(2)
world.open_collection.emit("FROSTBITE")
assert window.gallery_pack == "FROSTBITE"
assert window.stack.currentWidget() is window.pages["Redux Collection"]
world.select_pack(0)
window.navigate("Overview")
assert window.page_title.text() == "Dashboard"
# Four collection cards retain distinct worlds and working preview actions.
from PySide6.QtWidgets import QLabel, QPushButton
collection = window.pages["Redux Collection"]
headlines = [w.text() for w in collection.findChildren(QLabel)
             if w.objectName() == "collectionHeadline"]
assert set(headlines) == {"PETAL BLOOM", "ELECTRIC CITY", "ZERO DEGREE", "BURNING HORIZON"}
assert len([b for b in collection.findChildren(QPushButton)
            if b.text() == "PREVIEW HERE"]) == 4
assert len([b for b in collection.findChildren(QPushButton)
            if b.text() == "VIEW COSMETICS"]) == 4
assert len([b for b in collection.findChildren(QPushButton)
            if b.text() == "APPLY LOOK TO NAMELESS"]) == 4

# All preview buttons must change the selected pack, not open a wrong default.
from PySide6.QtWidgets import QPushButton
preview_buttons = [b for b in collection.findChildren(QPushButton)
                   if b.text() == "PREVIEW HERE"]
assert len(preview_buttons) == 4
for button, pack in zip(preview_buttons, (
        "SAKURA DREAM", "NEON NIGHT", "FROSTBITE", "CRIMSON")):
    button.click()
    assert window.gallery_pack == pack, pack

# Cinematic right-side gallery switches all four REDUX packs and five categories.
from redux_armory import COSMETIC_TITLES, SLOTS
for pack in COSMETIC_TITLES:
    window.select_gallery_pack(pack)
    assert window.gallery_pack == pack
    for slot in SLOTS:
        window.select_gallery_slot(slot)
        assert window.gallery_canvas.pack == pack
        assert window.gallery_canvas.slot == slot
        assert window.gallery_title.text() == COSMETIC_TITLES[pack][slot]
window.select_gallery_pack("SAKURA DREAM")
window.select_gallery_slot("vehicle")

# Premium hero is static, legible and paintable without an animation timer.
from premium_hero import PremiumHero
assert isinstance(window.hero, PremiumHero)
assert window.hero.minimumHeight() >= 300
assert not hasattr(window.hero, "_clock")

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
    assert key.upper() in window.effect_feedback.text(), key
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
        assert window._preview_request_id == 5, "restoring a local image invalidates pending Steam replies"
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
# Each REDUX must explicitly communicate preview-only limitations.
from PySide6.QtWidgets import QPushButton
disclaimers = [label for label in collection.findChildren(QLabel)
               if label.objectName() == "collectionDisclaimer"]
assert len(disclaimers) == 4
assert all("GAME INSTALL NOT AVAILABLE" in label.text() and
           "NO GAME FILES CHANGED" in label.text() for label in disclaimers)
garage_buttons = [button for button in collection.findChildren(QPushButton)
                  if button.text() == "VIEW COSMETICS"]
assert len(garage_buttons) == 4, "Every Redux has its own Cosmetic Garage entry"
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
# Reset restores an honest empty Redux state and refreshes the preview source.
original_question = QMessageBox.question
original_load = window.load_initial_screenshot
calls = []
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
window.load_initial_screenshot = lambda: calls.append("reload")
try:
    window.reset_settings()
    assert window.collection_active.text().endswith("NONE SELECTED")
    assert window.settings.value("collection/active", "") == ""
    assert calls == ["reload"]
finally:
    QMessageBox.question = original_question
    window.load_initial_screenshot = original_load
# Produce a real Qt screenshot on Windows for release visual inspection.
window.navigate("World Reborn")
window.resize(1672, 941)
window.show()
app.processEvents()
capture_dir = Path("release-preview")
capture_dir.mkdir(exist_ok=True)
capture_path = capture_dir / "nemelis-world-reborn.png"
assert window.grab().save(str(capture_path)), "Failed to capture Windows interface"
assert capture_path.stat().st_size > 10000, "Windows interface screenshot is empty"
window.steam_timer.stop()
window.close()
QTimer.singleShot(0, app.quit)
app.exec()
print("NAMELESS UI smoke test passed")
