"""Offscreen functional checks for all four original REDUX showroom concepts."""
import io
import os
import sys
import tempfile
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from redux_showroom import PACKS, ReduxShowroom, ShowroomCanvas, original_shot_wav

app = QApplication.instance() or QApplication([])
assert set(PACKS) == {"SAKURA DREAM", "NEON NIGHT", "FROSTBITE", "CRIMSON"}
samples = set()

with tempfile.TemporaryDirectory() as directory:
    for name, spec in PACKS.items():
        canvas = ShowroomCanvas(pack=name)
        canvas.set_motion_enabled(False)
        assert not canvas._timer.isActive(), name
        image = canvas.snapshot()
        assert image.width() == 960 and image.height() == 540, name
        assert not image.isNull(), name
        assert image.save(str(Path(directory) / (name + ".png")), "PNG")
        samples.add(image.pixelColor(400, 30).rgb())
        # All four effect particle budgets are enforced by the same code path.
        created = canvas.fire_at(QPointF(605, 265))
        assert created == spec["particles"], name
        assert len(canvas.particles) == created, name
        for _ in range(40):
            canvas.step()
        assert not canvas.particles, name
        for _ in range(20):
            canvas.fire_at(QPointF(670, 240))
        assert len(canvas.particles) <= 64, name
        audio = original_shot_wav(name)
        with wave.open(io.BytesIO(audio), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 22050
            assert .20 <= wav.getnframes() / wav.getframerate() <= .25
        canvas.close()

assert len(samples) == 4, "Each Redux must have a distinct atmosphere"

dialog = ReduxShowroom(initial_pack="FROSTBITE", reduce_motion=True)
assert dialog.pack_select.count() == 4
assert dialog.canvas.pack == "FROSTBITE"
assert not dialog.canvas.motion_enabled
dialog.audio_check.setChecked(False)
for name in PACKS:
    dialog.pack_select.setCurrentText(name)
    assert dialog.canvas.pack == name
    dialog.canvas.fire_at(QPointF(550, 280))
    assert len(dialog.canvas.particles) == PACKS[name]["particles"]
dialog.close()
app.quit()
print("All four interactive Redux showroom concepts passed")
