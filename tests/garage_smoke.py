"""Offscreen validation of 20 original cosmetic concepts and mixed loadouts."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtWidgets import QApplication, QFileDialog
from redux_armory import (COSMETIC_TITLES, FORMAT, PACK_NAMES, SLOTS,
                          CosmeticCanvas, CosmeticGarage, build_loadout_payload,
                          validate_loadout_payload)

app = QApplication.instance() or QApplication([])
assert len(PACK_NAMES) == 4 and len(SLOTS) == 5

with tempfile.TemporaryDirectory() as temp:
    directory = Path(temp)
    for theme in PACK_NAMES:
        for slot in SLOTS:
            canvas = CosmeticCanvas(pack=theme, slot=slot)
            assert COSMETIC_TITLES[theme][slot]
            image = canvas.snapshot()
            assert image.width() == 1000 and image.height() == 620
            assert not image.isNull()
            target = directory / (theme.replace(" ", "_") + "_" + slot + ".png")
            assert image.save(str(target), "PNG")
            assert target.stat().st_size > 3500, (theme, slot)
            canvas.close()
    assert len(list(directory.glob("*.png"))) == 20

    # Mix independently instead of blindly applying one color palette.
    mixed = dict(zip(SLOTS, (
        "SAKURA DREAM", "NEON NIGHT", "FROSTBITE", "CRIMSON",
        "SAKURA DREAM")))
    payload = build_loadout_payload(mixed)
    assert payload["format"] == FORMAT
    assert payload["kind"] == "preview-only"
    assert payload["game_files_modified"] is False
    assert validate_loadout_payload(json.loads(json.dumps(payload))) == mixed

    for invalid in (
        {}, {"format": FORMAT, "kind": "preview-only",
             "game_files_modified": True, "slots": mixed},
        {"format": FORMAT, "kind": "preview-only",
         "game_files_modified": False, "slots": {"weapon": "SAKURA DREAM"}},
        {"format": FORMAT, "kind": "preview-only",
         "game_files_modified": False,
         "slots": {**mixed, "mask": "nonexistent-theme"}},
    ):
        try:
            validate_loadout_payload(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid loadout was accepted")

    garage = CosmeticGarage(initial_pack="NEON NIGHT")
    assert len(garage.slot_selects) == 5
    assert garage.category_select.count() == 5
    garage.apply_loadout(payload)
    assert garage.loadout_slots() == mixed
    for index, slot in enumerate(SLOTS):
        garage.category_select.setCurrentIndex(index)
        assert garage.canvas.slot == slot
        assert garage.canvas.pack == mixed[slot]
        assert garage.concept_name.text() == COSMETIC_TITLES[mixed[slot]][slot]

    original_dialog = QFileDialog.getSaveFileName
    try:
        path = directory / "mixed.json"
        QFileDialog.getSaveFileName = lambda *a, **kw: (str(path), "JSON (*.json)")
        garage.export_loadout()
        exported = json.loads(path.read_text(encoding="utf-8"))
        assert exported["slots"] == mixed
        assert exported["game_files_modified"] is False

        png = directory / "chosen-cosmetic.png"
        QFileDialog.getSaveFileName = lambda *a, **kw: (str(png), "PNG (*.png)")
        garage.export_png()
        assert png.is_file() and png.stat().st_size > 3500
    finally:
        QFileDialog.getSaveFileName = original_dialog
    garage.close()

app.quit()
print("All 20 cosmetic concepts, loadout mixes, safe exports and validation passed")
