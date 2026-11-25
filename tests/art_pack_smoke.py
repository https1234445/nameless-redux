"""Validate safe art ZIP imports and exact theme paths without game access."""
import io
import os
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from art_pack import ART_NAMES, art_candidates, import_art_pack

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as temp:
    os.environ["XDG_DATA_HOME"] = temp
    image = QImage(120, 80, QImage.Format_RGB32)
    image.fill(QColor("#B28BC3"))
    image_path = Path(temp) / "test.jpg"
    assert image.save(str(image_path), "JPG")
    archive = Path(temp) / "pack.zip"
    with ZipFile(archive, "w") as z:
        for name in ART_NAMES:
            z.write(image_path, "assets/" + name)
    assert import_art_pack(str(archive)) == 5
    for name in ART_NAMES:
        assert any(path.is_file() for path in art_candidates(name))
    bad = Path(temp) / "bad.zip"
    with ZipFile(bad, "w") as z:
        z.writestr("../danger.jpg", b"unsafe")
    try:
        import_art_pack(str(bad))
    except ValueError:
        pass
    else:
        raise AssertionError("Missing themes must be rejected")
print("REDUX art pack import OK")
