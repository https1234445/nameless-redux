"""Release gate: the EXE must ship all approved visual assets."""
from pathlib import Path
from PySide6.QtGui import QImage
ROOT = Path(__file__).resolve().parents[1] / "app" / "assets"
NAMES = ("sakura_dream.jpg", "neon_night.jpg", "frostbite.jpg",
         "crimson.jpg", "rob_run_preview.jpg")
for name in NAMES:
    path = ROOT / name
    assert path.is_file(), f"Missing embedded visual: {path}"
    img = QImage(str(path))
    assert not img.isNull(), f"Corrupt embedded visual: {path}"
    assert img.width() >= 640 and img.height() >= 360, (
        f"Visual too small for REDUX gallery: {path} ({img.width()}x{img.height()})")
print("All five high-resolution NAMELESS visuals are present and valid.")
