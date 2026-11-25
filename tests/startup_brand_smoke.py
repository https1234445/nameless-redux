"""Startup branding works without network or Windows shell interactions."""
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PySide6.QtWidgets import QApplication
from startup_brand import brand_pixmap, app_icon, startup_splash

app = QApplication.instance() or QApplication([])
pix = brand_pixmap()
assert pix.width() == 720 and pix.height() == 390
assert not pix.isNull()
assert not app_icon().isNull()
splash = startup_splash()
app.processEvents()
assert splash.isVisible()
splash.close()
app.quit()
print("NAMELESS startup splash and icon OK")
