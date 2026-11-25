"""Headless coverage for the 20-item atlas and printable concept poster."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtWidgets import QApplication
from redux_armory import PACK_NAMES, SLOTS
from redux_atlas import CosmeticAtlas, render_atlas

app = QApplication.instance() or QApplication(sys.argv)
selected = []
atlas = CosmeticAtlas(on_select=lambda pack, slot: selected.append((pack, slot)))
assert len(atlas.concept_buttons) == len(PACK_NAMES) * len(SLOTS) == 20
for pack in PACK_NAMES:
    for slot in SLOTS:
        assert (pack, slot) in atlas.concept_buttons
atlas.choose("CRIMSON", "mask")
assert selected == [("CRIMSON", "mask")]
image = render_atlas()
assert image.width() == 2400 and image.height() == 2920
assert not image.isNull()
assert image.pixelColor(900, 700) != image.pixelColor(0, 0)
atlas.close()
app.quit()
print("REDUX atlas smoke: 20 concepts, selection and high-resolution poster OK")
