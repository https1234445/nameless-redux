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
# Sample the whole poster rather than assuming a particular pixel is artwork.
# On headless Windows, text metrics and thumbnail placement can vary.
background = image.pixelColor(0, 0).rgba()
sampled_colors = {
    image.pixelColor(x, y).rgba()
    for y in range(40, image.height(), 35)
    for x in range(40, image.width(), 35)
}
assert background in sampled_colors
assert len(sampled_colors) >= 3, (
    "Atlas poster appears blank or lacks rendered concept content"
)
atlas.close()
app.quit()
print("REDUX atlas smoke: 20 concepts, selection and high-resolution poster OK")
