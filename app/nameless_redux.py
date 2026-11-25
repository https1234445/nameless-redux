from ui_controls import ClickOnlyComboBox
from startup_brand import app_icon, startup_splash
import sys
import json
import hashlib
import zipfile
import os
import re
import subprocess
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QUrl, QPropertyAnimation, QEasingCurve, Property, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QLinearGradient, QRadialGradient, QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from redux_showroom import ReduxShowroom
from redux_armory import CosmeticGarage
from premium_hero import PremiumHero
from redux_atlas import CosmeticAtlas
from fps_lab import FPSLab
from ping_lab import PingLab
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QListWidget,
    QListWidgetItem, QSlider, QComboBox, QCheckBox, QFileDialog, QMessageBox,
    QLineEdit, QInputDialog, QProgressBar, QScrollArea, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QColorDialog
)

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    MULTIMEDIA_AVAILABLE = True
except Exception:
    MULTIMEDIA_AVAILABLE = False


# Read-only, heuristic inspection. Engine signatures are NOT mod support guarantees.
def inspect_game_layout(relative_paths):
    """Return evidence-based engine hints from relative file names only."""
    paths = [str(p).replace("\\", "/").lower() for p in relative_paths]
    names = {p.rsplit("/", 1)[-1] for p in paths}
    evidence = []
    hints = []
    if "globalgamemanagers" in names or any(p.endswith("_data/managed/assembly-csharp.dll") for p in paths):
        hints.append("Unity-like layout")
        evidence.extend(p for p in paths if p.endswith("globalgamemanagers") or p.endswith("_data/managed/assembly-csharp.dll"))
    if any(p.endswith("/content/paks/") or "/content/paks/" in p for p in paths) or any(p.endswith(".pak") for p in paths):
        hints.append("Unreal-like packaged assets (not definitive)")
        evidence.extend(p for p in paths if p.endswith(".pak"))
    if "godot.windows.opt.tools.64.exe" in names or any(p.endswith(".pck") for p in paths):
        hints.append("Godot-like package")
        evidence.extend(p for p in paths if p.endswith(".pck"))
    if any(p.endswith(".assets") for p in paths):
        hints.append("Unity asset files (not definitive)")
        evidence.extend(p for p in paths if p.endswith(".assets"))
    return {"engine_hints": list(dict.fromkeys(hints)),
            "evidence_paths": sorted(set(evidence))[:30],
            "compatibility_status": "unverified",
            "game_identity_verified": False,
            "safe_to_patch": False,
            "reason": "File names alone cannot establish ROB RUN identity, mod support or safe write targets."}




# Candidate discovery uses names and metadata only. Never parse unknown game configs.
CONFIG_SUFFIXES = {".ini", ".cfg", ".json", ".toml", ".yaml", ".yml", ".xml", ".properties"}
CONFIG_KEYWORDS = ("settings", "config", "graphics", "video", "render", "quality", "engine", "user")

def discover_config_candidates(root, max_files=20000, max_results=120):
    """Return a bounded, read-only inventory of plausible configuration files."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Choose an existing non-symlink directory")
    candidates = []
    inspected = 0
    errors = 0
    truncated = False
    def onerror(_):
        nonlocal errors
        errors += 1
    for current, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            inspected += 1
            if inspected > max_files:
                truncated = True
                break
            if path.suffix.lower() not in CONFIG_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            if not any(word in relative.lower() for word in CONFIG_KEYWORDS):
                continue
            try:
                info = path.stat()
            except OSError:
                errors += 1
                continue
            if len(candidates) < max_results:
                candidates.append({"path": relative, "size_bytes": info.st_size,
                                   "extension": path.suffix.lower(), "writable": False,
                                   "status": "candidate_only_unverified"})
            else:
                truncated = True
        if truncated:
            break
    return {"format": "nameless-config-discovery-v1", "folder": str(root.resolve()),
            "candidates": candidates, "files_inspected": min(inspected, max_files),
            "truncated": truncated, "read_errors": errors,
            "game_identity_verified": False, "config_support_verified": False,
            "files_modified": False}


# Pack staging deliberately operates outside the game directory.
def inspect_redux_pack(archive_path, max_files=250, max_bytes=256 * 1024**2):
    """Validate a portable ZIP pack and return a normalized manifest, without extraction."""
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > max_files + 1:
            raise ValueError("Too many archive entries (limit: 250 files).")
        names = set()
        total = 0
        for info in infos:
            name = info.filename
            parts = name.replace("\\", "/").split("/")
            if (not name or name.startswith(("/", "\\")) or "\\" in name
                    or any(part in ("", ".", "..") for part in parts if not (info.is_dir() and part == parts[-1]))
                    or ":" in name or name in names):
                raise ValueError("Unsafe or duplicate archive entry.")
            names.add(name)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symbolic links are not allowed.")
            if info.flag_bits & 0x1:
                raise ValueError("Encrypted ZIP entries are not supported.")
            total += info.file_size
            if total > max_bytes:
                raise ValueError("Pack exceeds 256 MiB unpacked size limit.")
        if "manifest.json" not in names:
            raise ValueError("Missing manifest.json")
        if archive.getinfo("manifest.json").file_size > 64 * 1024:
            raise ValueError("Manifest is too large.")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict) or manifest.get("format") != "nameless-redux-pack-v1":
            raise ValueError("Unsupported pack format.")
        title = manifest.get("name")
        if not isinstance(title, str) or not (1 <= len(title.strip()) <= 80):
            raise ValueError("Invalid pack name.")
        entries = manifest.get("files")
        if not isinstance(entries, list) or len(entries) > max_files:
            raise ValueError("Invalid file list.")
        expected = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid file entry.")
            relative, digest = entry.get("path"), entry.get("sha256")
            if (not isinstance(relative, str) or not relative.startswith("assets/")
                    or relative not in names or relative in expected or not isinstance(digest, str)
                    or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("Invalid asset path or SHA-256.")
            expected.add(relative)
        actual = {info.filename for info in infos if not info.is_dir()} - {"manifest.json"}
        if actual != expected:
            raise ValueError("Manifest does not match archived assets.")
        for entry in entries:
            with archive.open(entry["path"]) as stream:
                hasher = hashlib.sha256()
                while chunk := stream.read(1024 * 1024):
                    hasher.update(chunk)
                if hasher.hexdigest() != entry["sha256"]:
                    raise ValueError("Asset checksum mismatch: " + entry["path"])
        return manifest


def stage_redux_pack(archive_path, destination):
    """Extract a verified pack into a new empty staging folder, never the game."""
    manifest = inspect_redux_pack(archive_path)
    target = Path(destination).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("Choose an empty staging folder.")
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for entry in manifest["files"]:
                relative = entry["path"]
                output = target / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative) as source, output.open("xb") as dest:
                    while chunk := source.read(1024 * 1024):
                        dest.write(chunk)
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        import shutil
        shutil.rmtree(target, ignore_errors=True)
        raise
    return len(manifest["files"])

APP_NAME = "NAMELESS REDUX"
VERSION = "3.16.0-dev"
PRESETS = {
    "Ocean Deep": "#087f95",
    "Lagoon": "#12a6a0",
    "Arctic Blue": "#4aa9d8",
    "Midnight Teal": "#145b68",
    "Abyss": "#173b55",
    "Sea Glass": "#65bdb2",
    "Aurora": "#61a9fa", "Neon Reef": "#00e4cf", "Pearl": "#b4d7e5",
    "Storm": "#576b9b", "Coral": "#ee8e99", "Deep Violet": "#7962cc",
    "Ice Mint": "#9df7d7", "Sapphire": "#315bc0", "Sunset": "#f2a873",
    "Graphite": "#526477", "Glacier": "#70d7f6", "Emerald": "#1ab68e",
}
VISUAL_PACKS = {
    "Deep Ocean": {"palette": "Ocean Deep", "intensity": 82, "cool": True},
    "Tropical Lagoon": {"palette": "Lagoon", "intensity": 92, "cool": False},
    "Frozen Night": {"palette": "Arctic Blue", "intensity": 73, "cool": True},
    "Abyss Minimal": {"palette": "Abyss", "intensity": 45, "cool": True},
    "Sea Glass Soft": {"palette": "Sea Glass", "intensity": 58, "cool": False},
    "Aurora Drift": {"palette": "Aurora", "intensity": 78, "cool": True},
    "Neon Current": {"palette": "Neon Reef", "intensity": 96, "cool": True},
    "Pearl Haze": {"palette": "Pearl", "intensity": 42, "cool": True},
    "Storm Signal": {"palette": "Storm", "intensity": 75, "cool": True},
    "Coral Bloom": {"palette": "Coral", "intensity": 84, "cool": False},
    "Violet Depth": {"palette": "Deep Violet", "intensity": 81, "cool": True},
    "Mint Horizon": {"palette": "Ice Mint", "intensity": 63, "cool": False},
    "Sapphire Pulse": {"palette": "Sapphire", "intensity": 91, "cool": True},
    "Golden Tide": {"palette": "Sunset", "intensity": 72, "cool": False},
    "Graphite Zero": {"palette": "Graphite", "intensity": 32, "cool": True},
}
EFFECT_PRESETS = {
    "Neutral": {"brightness": 0, "contrast": 100, "saturation": 100, "warmth": 0},
    "Cinematic Deep": {"brightness": -12, "contrast": 138, "saturation": 84, "warmth": -18},
    "Vivid Ocean": {"brightness": 8, "contrast": 125, "saturation": 160, "warmth": -35},
    "Soft Film": {"brightness": 12, "contrast": 85, "saturation": 80, "warmth": 16},
    "Arctic Night": {"brightness": -8, "contrast": 132, "saturation": 106, "warmth": -70},
    "Golden Hour": {"brightness": 13, "contrast": 109, "saturation": 120, "warmth": 65},
    "Noir": {"brightness": -10, "contrast": 154, "saturation": 0, "warmth": 0},
    "Dreamscape": {"brightness": 18, "contrast": 76, "saturation": 138, "warmth": 10},
    "Cold Steel": {"brightness": -5, "contrast": 142, "saturation": 67, "warmth": -44},
    "Pastel Haze": {"brightness": 17, "contrast": 78, "saturation": 69, "warmth": 22},
}

CROSSHAIR_COLORS = {
    "Ocean Cyan": "#55e6e0",
    "White": "#f2fbff",
    "Mint": "#8cf5c5",
    "Amber": "#ffc66d",
    "Rose": "#ff8da1",
}


def create_backup_archive(source_dir, archive_path, selected_files, max_total_bytes=2 * 1024**3):
    """Archive explicitly selected regular files; never follow symlinks."""
    root = Path(source_dir).resolve(strict=True)
    destination = Path(archive_path).resolve()
    if destination.is_relative_to(root):
        raise ValueError("Save backups outside the game folder.")
    entries, total = [], 0
    for item in selected_files:
        path = Path(item)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Not a regular file: {path}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("Selected file is outside the game folder.")
        relative = resolved.relative_to(root).as_posix()
        if any(part in (".", "..") for part in Path(relative).parts):
            raise ValueError("Unsafe relative path")
        total += resolved.stat().st_size
        if total > max_total_bytes:
            raise ValueError("Backup exceeds 2 GiB safety limit.")
        entries.append((resolved, relative))
    if not entries:
        raise ValueError("Choose at least one file.")
    if len(set(relative for _, relative in entries)) != len(entries):
        raise ValueError("Duplicate files selected.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("Archive already exists. Choose a different filename.")
    manifest = {"format": "nameless-backup-v1", "created_utc": datetime.now(timezone.utc).isoformat(), "files": []}
    try:
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            for source, relative in entries:
                digest = hashlib.sha256()
                with source.open("rb") as stream, z.open("files/" + relative, "w") as output:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        output.write(chunk)
                manifest["files"].append({"path": relative, "size": source.stat().st_size, "sha256": digest.hexdigest()})
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return manifest


def extract_backup_archive(archive_path, destination_dir):
    """Verify hashes and extract into a new empty folder, never into the game."""
    destination = Path(destination_dir).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Restore destination must be empty.")
    with zipfile.ZipFile(archive_path, "r") as z:
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("format") != "nameless-backup-v1":
            raise ValueError("Unsupported backup format.")
        files = manifest.get("files")
        if not isinstance(files, list) or len(files) > 20000:
            raise ValueError("Invalid backup manifest.")
        planned = []
        for entry in files:
            relative = entry["path"]
            path = Path(relative)
            if (not relative or "\\" in relative or path.is_absolute() or
                    any(part in (".", "..") for part in relative.split("/"))):
                raise ValueError("Unsafe archive path.")
            target = (destination / path).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Archive path escapes destination.")
            name = "files/" + relative
            info = z.getinfo(name)
            if info.is_dir() or info.file_size != entry["size"] or info.file_size > 2 * 1024**3:
                raise ValueError("Invalid file size in backup.")
            planned.append((entry, name, target))
        if len({str(target) for _, _, target in planned}) != len(planned):
            raise ValueError("Duplicate paths in backup.")
        # Verify all file hashes before writing any output.
        for entry, name, _ in planned:
            digest = hashlib.sha256()
            with z.open(name) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != entry["sha256"]:
                raise ValueError("Backup integrity check failed.")
        destination.mkdir(parents=True, exist_ok=True)
        for _, name, target in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as source, target.open("xb") as output:
                import shutil
                shutil.copyfileobj(source, output, 1024 * 1024)
    return len(planned)



STEAM_APP_ID = "4262460"

def find_steam_game():
    """Read Steam library manifests only; never touch game data."""
    roots = []
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except (OSError, ValueError):
            pass
        for var in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            if os.environ.get(var):
                roots.append(Path(os.environ[var]) / "Steam")
    roots.append(Path.home() / ".steam" / "steam")
    for root in roots:
        steamapps = root / "steamapps"
        libraries = [steamapps]
        vdf = steamapps / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                text = vdf.read_text(encoding="utf-8-sig", errors="replace")
                for folder in re.findall(r'"path"\s*"([^"]+)"', text, re.I):
                    libraries.append(Path(folder.replace("\\\\", "\\")) / "steamapps")
            except OSError:
                pass
        for library in libraries:
            manifest = library / ("appmanifest_" + STEAM_APP_ID + ".acf")
            if not manifest.is_file():
                continue
            try:
                data = manifest.read_text(encoding="utf-8-sig", errors="replace")
                match = re.search(r'"installdir"\s*"([^"]+)"', data, re.I)
                if match:
                    location = library / "common" / match.group(1)
                    if location.is_dir():
                        return location
            except OSError:
                pass
    return None


class OceanSlider(QSlider):
    """Smooth click-to-seek slider; normal dragging remains responsive."""
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._seek_anim = QPropertyAnimation(self, b"value", self)
        self._seek_anim.setDuration(220)
        self._seek_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(27)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            # Clicking the groove eases to the requested position. Handle dragging
            # still uses the native QSlider implementation for immediate feedback.
            from PySide6.QtWidgets import QStyle, QStyleOptionSlider
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            if not handle.contains(event.position().toPoint()):
                groove = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
                span = max(1, groove.width() - handle.width())
                x = event.position().x() - groove.x() - handle.width() / 2
                fraction = max(0.0, min(1.0, x / span))
                if self.invertedAppearance():
                    fraction = 1.0 - fraction
                target = self.minimum() + round(fraction * (self.maximum() - self.minimum()))
                self._seek_anim.stop()
                self._seek_anim.setStartValue(self.value())
                self._seek_anim.setEndValue(target)
                self._seek_anim.start()
                event.accept()
                return
        self._seek_anim.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._seek_anim.stop()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        # Wheel scrolling should scroll the page, never change a setting.
        event.ignore()


class OceanToggle(QCheckBox):
    """Animated accessible checkbox with a custom ocean-style switch."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._position = 1.0 if self.isChecked() else 0.0
        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.toggled.connect(self._animate)
        self.setMinimumHeight(30)

    def _get_position(self):
        return self._position

    def _set_position(self, value):
        self._position = float(value)
        self.update()

    position = Property(float, _get_position, _set_position)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        track = QColor("#23505e")
        active = QColor("#42d8cb")
        t = self._position
        mix = QColor(*(round(a * (1-t) + b*t) for a,b in zip(track.getRgb()[:3], active.getRgb()[:3])))
        painter.setBrush(mix)
        painter.drawRoundedRect(1, 5, 42, 22, 11, 11)
        painter.setBrush(QColor("#f3ffff"))
        painter.drawEllipse(int(4 + 20*t), 8, 16, 16)
        painter.setPen(QColor("#d4eff2") if self.isEnabled() else QColor("#708d94"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(55, 0, max(0,self.width()-55), self.height(), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(max(165, hint.width()+42))
        hint.setHeight(max(32, hint.height()))
        return hint




class EffectsPreview(QWidget):
    """Cinematic vector landscape with fast, debounced pixel processing."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setMinimumWidth(350)
        self.base = self.make_scene()
        self.filtered = self.base.copy()
        self.real_screenshot = False
        self._pending = (0, 100, 100, 0)
        self.compare_percent = 50
        self.compare_enabled = True
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(35)
        self._render_timer.timeout.connect(self._render_effects)

    @staticmethod
    def make_scene():
        # A deliberately low-resolution source keeps processing responsive.
        # Qt performs the final smooth scaling in paintEvent.
        w, h = 640, 340
        image = QImage(w, h, QImage.Format_RGB32)
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing, True)
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor('#07152c'))
        sky.setColorAt(.40, QColor('#153f66'))
        sky.setColorAt(.73, QColor('#2d8192'))
        sky.setColorAt(1, QColor('#0a293b'))
        p.fillRect(0, 0, w, h, sky)
        # Atmospheric glow behind the skyline.
        from PySide6.QtGui import QRadialGradient, QPolygonF
        from PySide6.QtCore import QPointF, QRectF
        glow = QRadialGradient(QPointF(425, 128), 190)
        glow.setColorAt(0, QColor(165, 87, 211, 228))
        glow.setColorAt(.28, QColor(65, 113, 183, 90))
        glow.setColorAt(1, QColor(13, 31, 56, 0))
        p.fillRect(0, 0, w, h, glow)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#c5f2e9'))
        p.drawEllipse(QRectF(420, 70, 38, 38))
        # Back mountain layers.
        for points, color in [
            ([(0,220),(85,144),(158,194),(240,115),(320,192),(400,147),(520,205),(640,125),(640,340),(0,340)], '#163a59'),
            ([(0,255),(102,190),(180,238),(310,166),(402,244),(520,187),(640,240),(640,340),(0,340)], '#0c2c48')]:
            p.setBrush(QColor(color))
            p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in points]))
        # Water with reflected light streaks.
        water = QLinearGradient(0, 235, 0, 340)
        water.setColorAt(0, QColor('#1a6479'))
        water.setColorAt(1, QColor('#06192b'))
        p.fillRect(0, 240, w, 100, water)
        for i in range(36):
            y = 246 + i * 2.6
            width = 4 + (i * 31) % 95
            x = 440 - width / 2 + ((i * 13) % 25 - 12)
            alpha = max(12, 110 - i * 2)
            p.fillRect(QRectF(x, y, width, 1.2), QColor(116, 221, 223, alpha))
        # Futuristic cliffside outpost, lit windows and antenna.
        p.setBrush(QColor('#091e32'))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in [(70,260),(110,195),(200,195),(230,260)]]))
        p.fillRect(113, 155, 91, 94, QColor('#102a42'))
        p.fillRect(104, 149, 110, 9, QColor('#1c5065'))
        p.fillRect(148, 123, 10, 28, QColor('#12394f'))
        p.fillRect(152, 98, 2, 26, QColor('#72dfd9'))
        for x in (127,151,175):
            for y in (174,199):
                p.fillRect(x, y, 12, 8, QColor('#59d8d5'))
                p.fillRect(x+2, y+2, 8, 4, QColor('#b5fff0'))
        # Foreground silhouettes give the preview depth.
        p.setBrush(QColor('#061a2a'))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in [(0,300),(68,271),(145,300),(255,278),(330,320),(420,295),(510,322),(640,282),(640,340),(0,340)]]))
        p.setPen(QPen(QColor('#2f8894'), 2))
        p.drawLine(0, 282, 640, 282)
        p.end()
        return image

    def set_screenshot(self, image):
        if image.isNull():
            return False
        self.base = image.convertToFormat(QImage.Format_RGB32).scaled(
            960, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.real_screenshot = True
        self._render_timer.stop()
        self._render_effects()
        return True

    def apply_effects(self, brightness=0, contrast=100, saturation=100, warmth=0):
        self._pending = (brightness, contrast, saturation, warmth)
        self._render_timer.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.compare_enabled:
            self._move_comparison(event.position().x())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.compare_enabled:
            self._move_comparison(event.position().x())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def _move_comparison(self, x):
        bounds = self.rect().adjusted(8, 8, -8, -8)
        if self.base.isNull() or not bounds.width():
            return
        ratio = self.base.width() / self.base.height()
        width = min(bounds.width(), bounds.height() * ratio)
        left = bounds.center().x() - width / 2
        self.compare_percent = max(0, min(100, round((x-left)*100/width)))
        self.update()

    def flush_effects(self):
        if self._render_timer.isActive():
            self._render_timer.stop()
            self._render_effects()

    def _render_effects(self):
        brightness, contrast, saturation, warmth = self._pending
        if (brightness, contrast, saturation, warmth) == (0, 100, 100, 0):
            self.filtered = self.base
            self.update()
            return
        # NumPy operates on the QImage buffer in bulk, avoiding 200k Python
        # pixelColor/setPixelColor calls that froze the UI during dragging.
        try:
            import numpy as np
            src = self.base
            raw = np.frombuffer(src.constBits(), dtype=np.uint8).reshape(src.height(), src.bytesPerLine())
            rgb = raw[:, :src.width()*4].reshape(src.height(), src.width(), 4)[:, :, :3].astype(np.float32)
            # QImage RGB32 is stored as BGRA on little-endian Windows.
            b, g, r = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
            gray = .2126*r + .7152*g + .0722*b
            sat, c = saturation / 100.0, contrast / 100.0
            out = np.empty((src.height(), src.width(), 4), dtype=np.uint8)
            for idx, channel, tint in ((0,b,-.8),(1,g,.12),(2,r,.8)):
                adjusted = ((gray + (channel-gray)*sat - 127.5)*c + 127.5 + brightness*2.0 + warmth*tint)
                out[:,:,idx] = np.clip(adjusted, 0, 255).astype(np.uint8)
            out[:,:,3] = 255
            self.filtered = QImage(out.tobytes(), src.width(), src.height(), src.width()*4, QImage.Format_RGB32).copy()
        except ImportError:
            # Fallback without extra dependencies: precompute channel mappings
            # and transform a smaller image with bytearray operations.
            src = self.base.scaled(320, 170, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            data = bytearray(src.constBits())
            sat, c = saturation/100.0, contrast/100.0
            for i in range(0, len(data), 4):
                b, g, r = data[i], data[i+1], data[i+2]
                gray = .2126*r + .7152*g + .0722*b
                for idx, value, tint in ((0,b,-.8),(1,g,.12),(2,r,.8)):
                    v = ((gray + (value-gray)*sat - 127.5)*c + 127.5 + brightness*2 + warmth*tint)
                    data[i+idx] = max(0, min(255, round(v)))
            self.filtered = QImage(bytes(data), src.width(), src.height(), src.bytesPerLine(), QImage.Format_RGB32).copy()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor('#071923'))
        from PySide6.QtCore import QRectF
        bounds = self.rect().adjusted(8, 8, -8, -8)
        ratio = self.filtered.width() / self.filtered.height()
        width = min(bounds.width(), bounds.height() * ratio)
        height = width / ratio
        target = QRectF(bounds.center().x()-width/2, bounds.center().y()-height/2, width, height)
        p.drawImage(target, self.filtered)
        if self.compare_enabled:
            from PySide6.QtCore import QRectF
            split = target.left() + target.width() * self.compare_percent / 100.0
            p.save()
            p.setClipRect(QRectF(target.left(), target.top(), max(0, split-target.left()), target.height()))
            p.drawImage(target, self.base)
            p.restore()
            p.setPen(QPen(QColor('#e5ffff'), 2))
            p.drawLine(int(split), int(target.top()), int(split), int(target.bottom()))
            p.setPen(QColor('#f4ffff'))
            p.drawText(int(target.left()+12), int(target.top()+24), 'BEFORE')
            p.drawText(int(target.right()-64), int(target.top()+24), 'AFTER')
        p.end()

class CrosshairPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self.style_name = "Cross"
        self.color = CROSSHAIR_COLORS["Ocean Cyan"]
        self.size = 22
        self.gap = 6
        self.thickness = 2
        self.dot = False
        self.outline = True

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#071923"))
        # subtle preview grid
        p.setPen(QPen(QColor("#123542"), 1))
        for x in range(0, self.width(), 28):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 28):
            p.drawLine(0, y, self.width(), y)

        cx, cy = self.width() // 2, self.height() // 2
        color = QColor(self.color)
        pen = QPen(color, self.thickness, Qt.SolidLine, Qt.RoundCap)
        if self.outline:
            p.setPen(QPen(QColor("#001015"), self.thickness + 2, Qt.SolidLine, Qt.RoundCap))
            self._draw_shape(p, cx, cy)
        p.setPen(pen)
        self._draw_shape(p, cx, cy)
        p.end()

    def _draw_shape(self, p, cx, cy):
        s, g = self.size, self.gap
        if self.style_name == "Dot":
            p.setBrush(QBrush(QColor(self.color)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - max(2, self.thickness), cy - max(2, self.thickness),
                          max(4, self.thickness * 2), max(4, self.thickness * 2))
        elif self.style_name == "Circle":
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx - s // 2, cy - s // 2, s, s)
        else:
            p.drawLine(cx - s, cy, cx - g, cy)
            p.drawLine(cx + g, cy, cx + s, cy)
            if self.style_name == "Cross":
                p.drawLine(cx, cy - s, cx, cy - g)
                p.drawLine(cx, cy + g, cx, cy + s)
        if self.dot and self.style_name != "Dot":
            p.setBrush(QBrush(QColor(self.color)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - 2, cy - 2, 4, 4)




class AmbientSurface(QWidget):
    """Subtle animated ambient gradients. Paint only a few shapes at 20 fps."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self.gradient_start = QColor('#7959C8')
        self.gradient_end = QColor('#235F93')
        self._clock = QTimer(self)
        self._clock.setInterval(50)
        self._clock.timeout.connect(self._tick)
        self._clock.start()

    def _tick(self):
        if not self.isVisible() or self.isMinimized():
            return
        self._phase = (self._phase + 0.009) % 6.283185
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#101427'))
        w, h = max(1, self.width()), max(1, self.height())
        for cx, cy, radius, color in [
            (0.87 + 0.045 * math.sin(self._phase), 0.10 + 0.035 * math.cos(self._phase), 0.75, QColor(self.gradient_start.red(), self.gradient_start.green(), self.gradient_start.blue(), 57)),
            (0.12 + 0.035 * math.cos(self._phase * 0.7), 0.93 + 0.04 * math.sin(self._phase), 0.68, QColor(self.gradient_end.red(), self.gradient_end.green(), self.gradient_end.blue(), 44)),
        ]:
            r = max(w, h) * radius
            gradient = QRadialGradient(w * cx, h * cy, r)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(1.0, QColor(8, 19, 29, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(QPoint(int(w * cx), int(h * cy)), int(r), int(r))
        painter.end()


class ShimmerText(QLabel):
    """Animated gradient typography with crisp native text rendering."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._phase = 0.0
        self._clock = QTimer(self)
        self._clock.setInterval(42)
        self._clock.timeout.connect(self._tick)
        self._clock.start()

    def _tick(self):
        if self.isVisible():
            self._phase = (self._phase + .018) % 6.283185
            self.update()

    def paintEvent(self, event):
        import math
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        fm = self.fontMetrics()
        text = self.text()
        x = 0 if self.alignment() & Qt.AlignLeft else max(0, (self.width()-fm.horizontalAdvance(text))/2)
        y = (self.height()+fm.ascent()-fm.descent())/2
        path = QPainterPath()
        path.addText(x, y, self.font(), text)
        shimmer = (math.sin(self._phase)+1)/2
        gradient = QLinearGradient(0, 0, max(1,self.width()), 0)
        gradient.setColorAt(0, QColor("#89C8FF"))
        gradient.setColorAt(max(.01,min(.99, .25 + shimmer*.45)), QColor("#FFFFFF"))
        gradient.setColorAt(1, QColor("#F2A5F4"))
        p.setPen(Qt.NoPen)
        p.setBrush(gradient)
        p.drawPath(path)
        p.end()


class AuroraCard(QFrame):
    """A softly animated gradient outline, without a graphics effect on children."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._phase = 0.0
        self._clock = QTimer(self)
        self._clock.setInterval(65)
        self._clock.timeout.connect(self._tick)
        self._clock.start()

    def _tick(self):
        if self.isVisible():
            self._phase = (self._phase + .025) % 6.283185
            self.update()

    def paintEvent(self, event):
        import math
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0, QColor("#222544"))
        bg.setColorAt(.6, QColor("#171C36"))
        bg.setColorAt(1, QColor("#23213E"))
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 14, 14)
        t = (math.sin(self._phase)+1)/2
        outline = QLinearGradient(0, 0, self.width(), self.height())
        outline.setColorAt(0, QColor("#8B9DFB"))
        outline.setColorAt(max(.01,min(.99,.15+.65*t)), QColor("#F4BBFF"))
        outline.setColorAt(1, QColor("#5CE0F5"))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(outline), 2))
        p.drawRoundedRect(rect, 14, 14)
        p.end()


class GradientHero(QFrame):
    """A restrained animated gradient hero; children are normal Qt widgets."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0.0
        self.gradient_start = QColor('#7959C8')
        self.gradient_end = QColor('#235F93')
        self._clock = QTimer(self)
        self._clock.setInterval(65)
        self._clock.timeout.connect(self._tick)
        self._clock.start()

    def _tick(self):
        if self.isVisible():
            self._offset = (self._offset + 0.006) % 6.283185
            self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        middle = 0.48 + 0.11 * math.sin(self._offset)
        gradient.setColorAt(0.0, self.gradient_start)
        gradient.setColorAt(middle, QColor('#483B83'))
        gradient.setColorAt(1.0, self.gradient_end)
        painter.setBrush(gradient)
        border = QLinearGradient(0, 0, self.width(), self.height())
        border.setColorAt(0, QColor("#B6B4FF"))
        border.setColorAt(.5, QColor("#FFA8EE"))
        border.setColorAt(1, QColor("#76E4FF"))
        painter.setPen(QPen(QBrush(border), 2))
        painter.drawRoundedRect(rect, 13, 13)
        painter.end()

class GlowButton(QPushButton):
    """Smooth animated hover glow, including sidebar navigation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        glow = QGraphicsDropShadowEffect(self)
        glow.setColor(QColor(159, 128, 255, 175))
        glow.setBlurRadius(0)
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)
        self._glow = QPropertyAnimation(glow, b"blurRadius", self)
        self._glow.setDuration(190)
        self._glow.setEasingCurve(QEasingCurve.OutCubic)

    def _animate_glow(self, target):
        self._glow.stop()
        self._glow.setStartValue(self.graphicsEffect().blurRadius())
        self._glow.setEndValue(target)
        self._glow.start()

    def enterEvent(self, event):
        self._animate_glow(19)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_glow(0)
        super().leaveEvent(event)


class ReduxCover(QWidget):
    """Locally rendered theme artwork; concept illustration, not gameplay."""
    def __init__(self, name, accent, shadow, parent=None):
        super().__init__(parent)
        self.name, self.accent, self.shadow = name, QColor(accent), QColor(shadow)
        self.setMinimumHeight(200)
        self._phase = 0.0
        self._motion = QTimer(self)
        self._motion.setInterval(45)
        self._motion.timeout.connect(self._animate)
        self._motion.start()

    def _animate(self):
        if self.isVisible():
            self._phase = (self._phase + .035) % 6.283185
            self.update()

    def paintEvent(self, event):
        from PySide6.QtCore import QRectF
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # Optional realistic concept art from the NAMELESS art pack.
        # No fake screenshots: assets are labeled as generated concepts.
        art_names = {
            "SAKURA DREAM": "sakura_dream.jpg",
            "NEON NIGHT": "neon_night.jpg",
            "FROSTBITE": "frostbite.jpg",
            "CRIMSON": "crimson.jpg",
        }
        art_name = art_names.get(self.name)
        if art_name:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            exe_dir = (Path(sys.executable).resolve().parent if getattr(
                sys, "frozen", False) else Path(__file__).resolve().parent)
            for root in (base / "assets", exe_dir / "assets"):
                candidate = root / art_name
                if candidate.is_file():
                    picture = QImage(str(candidate))
                    if not picture.isNull():
                        scaled = picture.scaled(
                            w, h, Qt.KeepAspectRatioByExpanding,
                            Qt.SmoothTransformation)
                        p.drawImage((w - scaled.width()) // 2,
                                    (h - scaled.height()) // 2, scaled)
                        p.fillRect(0, h - 66, w, 66, QColor(8, 9, 22, 165))
                        p.setPen(QColor("#FFFFFF"))
                        p.setFont(QFont("Segoe UI", 18, QFont.Bold))
                        p.drawText(20, h - 24, self.name)
                        p.end()
                        return
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, self.shadow)
        bg.setColorAt(.55, self.accent.darker(180))
        bg.setColorAt(1, QColor("#090F20"))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0, 0, w, h), 16, 16)
        glow = QRadialGradient(w*.75, h*.35, h*.7)
        light = QColor(self.accent)
        light.setAlpha(180)
        glow.setColorAt(0, light)
        light.setAlpha(0)
        glow.setColorAt(1, light)
        p.setBrush(glow)
        p.drawEllipse(QRectF(w*.32, -h*.35, w*.9, h*1.4))
        # Atmospheric landscape with layered hills and graphic highlights.
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        for layer in range(3):
            shade = QColor(self.shadow).darker(125 + layer*38)
            p.setBrush(shade)
            pts = [QPointF(0, h)]
            for x in range(0, w+22, 18):
                y = h*(.58 + layer*.12) + math.sin(x/54 + layer*1.7)*14
                pts.append(QPointF(x, y))
            pts.append(QPointF(w, h))
            p.drawPolygon(QPolygonF(pts))
        if self.name == "SAKURA DREAM":
            sway = math.sin(self._phase) * 13
            p.setPen(QPen(QColor("#4B2943"), 9, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(int(w*.78), h, int(w*.77+sway), int(h*.22))
            for i in range(30):
                x = w*(.52 + .014*i) + sway*(.4 + i/45)
                y = h*(.13 + .17*math.sin(i*1.7))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#FFD2E9"))
                p.drawEllipse(QRectF(x, y, 15, 10))
            # Floating petals move across the entire scene, not just the tree.
            for i in range(22):
                x = (w*(i*.071) + self._phase*21*(1+i%3)) % max(1,w)
                y = (h*(i*.127) + self._phase*14*(1+i%2)) % max(1,h)
                p.setBrush(QColor("#FFC6E3"))
                p.drawEllipse(QRectF(x, y, 5+i%4, 3+i%3))
        elif self.name == "NEON NIGHT":
            p.setPen(QPen(QColor("#D8A7FF"), 3))
            for i in range(7):
                x = int(w*(.2+i*.11))
                shift = math.sin(self._phase*2+i)*9
                p.drawLine(x, int(h*.55+shift), int(w*.5+(x-w*.5)*1.7), h)
        elif self.name == "FROSTBITE":
            p.setPen(QPen(QColor("#D8F8FF"), 2))
            for i in range(14):
                x, y = int(w*(i+.5)/15 + math.sin(self._phase+i)*7), int((h*(.14+(i%4)*.12)+self._phase*15)%h)
                p.drawLine(x-5,y,x+5,y)
                p.drawLine(x,y-5,x,y+5)
        else:
            p.setPen(QPen(QColor("#FFB66D"), 2))
            for i in range(22):
                x = int(w*(i+.5)/23)
                y = int((h*(.25+.3*math.sin(i*2.1)**2)-self._phase*12)%h)
                p.drawLine(x,y,x+4,y-10)
        p.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 20, QFont.Bold)
        p.setFont(font)
        p.drawText(20, h-26, self.name)
        p.end()


class ReduxWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("NamelessStudio", "NamelessRedux")
        self.setWindowTitle(f"{APP_NAME}  •  {VERSION}")
        self.network = QNetworkAccessManager(self)
        self.steam_timer = QTimer(self)
        self.steam_timer.setInterval(6500)
        self.steam_timer.timeout.connect(self.refresh_steam_status)
        self._last_game_running = False
        self._fade_animation = None
        self.resize(1360, 850)
        self.setMinimumSize(1050, 680)
        self.audio_files = self.read_json_setting("audio/files", [])
        self.audio_files = [str(p) for p in self.audio_files if isinstance(p, str) and Path(p).is_file()]
        self.profiles = self.read_json_setting("profiles", {})
        self.custom_visual_packs = self.read_json_setting("visual/packs", {})
        self.theme_colors = self.read_json_setting("theme/colors", {"start": "#7959C8", "end": "#235F93"})
        self.player = None
        self.audio_output = None
        if MULTIMEDIA_AVAILABLE:
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(258)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 28, 18, 20)
        side.setSpacing(10)

        brand = ShimmerText("N A M E L E S S")
        brand.setObjectName("brand")
        side.addWidget(brand)
        sub = QLabel("R E D U X   /   ROB RUN EDITION")
        sub.setObjectName("subbrand")
        side.addWidget(sub)
        side.addSpacing(28)
        nav_label = QLabel("WORKSPACE")
        nav_label.setObjectName("navSection")
        side.addWidget(nav_label)
        side.addSpacing(8)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        self.pages = {}
        nav_items = [
            ("Redux Collection", "✿"),
            ("Overview", "◈"),
            ("Visuals Studio", "◉"),
            ("Theme Lab", "✦"),
            ("Sound Library", "♫"),
            ("Crosshair Studio", "⌖"),
            ("Profiles", "▤"),
            ("Game Center", "▣"),
            ("Settings", "⚙"),
        ]
        for name, glyph in nav_items:
            if name in ("Sound Library", "Game Center"):
                side.addSpacing(17)
                group = QLabel("TOOLS" if name == "Sound Library" else "SYSTEM")
                group.setObjectName("navSection")
                side.addWidget(group)
                side.addSpacing(6)
            btn = GlowButton(f"{glyph}    {name}")
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, n=name: self.navigate(n))
            side.addWidget(btn)
            if name == "Overview":
                self.first_nav = btn
            setattr(self, "nav_" + name.lower().replace(" ", "_"), btn)

        side.addStretch()
        version = QLabel(f"NAMELESS REDUX / {VERSION}\nROB RUN EDITION")
        version.setObjectName("version")
        side.addWidget(version)

        content = AmbientSurface()
        content.setObjectName("contentSurface")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 22, 34, 26)
        content_layout.setSpacing(20)
        header = QHBoxLayout()
        self.page_title = QLabel("Overview")
        self.page_title.setObjectName("pageTitle")
        header.addWidget(self.page_title)
        header.addStretch()
        self.top_game_status = QLabel("ROB RUN  /  CHECKING")
        self.top_game_status.setObjectName("status")
        header.addWidget(self.top_game_status)
        header.addSpacing(12)
        launch_button = GlowButton("▶  LAUNCH GAME")
        self.top_launch_button = launch_button
        launch_button.setObjectName("primaryAction")
        launch_button.clicked.connect(self.launch_steam_game)
        header.addWidget(launch_button)
        content_layout.addLayout(header)
        separator = QFrame()
        separator.setObjectName("headerRule")
        separator.setFixedHeight(1)
        content_layout.addWidget(separator)
        content_layout.addWidget(self.stack, 1)

        main.addWidget(sidebar)
        main.addWidget(content, 1)

        self.build_pages()
        self.build_collection()
        self.apply_theme_colors()
        self.apply_style()
        self.load_settings()
        self.restore_audio_list()
        self.navigate("Redux Collection")
        self.steam_timer.start()
        QTimer.singleShot(500, self.refresh_steam_status)
        QTimer.singleShot(900, self.load_initial_screenshot)

    def card(self, title, subtitle=None):
        frame = AuroraCard()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        if subtitle:
            desc = QLabel(subtitle)
            desc.setObjectName("muted")
            desc.setWordWrap(True)
            layout.addWidget(desc)
        return frame, layout

    def heading(self, title, subtitle):
        box = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("sectionTitle")
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        box.setSpacing(7)
        box.addWidget(t)
        box.addWidget(s)
        return box

    def build_pages(self):
        # Overview
        page = QWidget()
        l = QVBoxLayout(page)
        l.setSpacing(20)
        hero = PremiumHero()
        self.hero = hero
        hero.setObjectName("heroCard")
        hero.setMinimumHeight(302)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(38, 31, 34, 28)
        hl.setSpacing(10)
        tag = QLabel("N A M E L E S S   /   ROB RUN EDITION  •  CONCEPT SHOWCASE")
        tag.setObjectName("accent")
        hl.addWidget(tag)
        headline = QLabel("MAKE EVERY\nRUN YOURS.")
        headline.setObjectName("heroHeadline")
        hl.addWidget(headline)
        desc = QLabel(
            "FOUR ORIGINAL WORLDS  /  TWENTY COSMETIC CONCEPTS\n"
            "Build your signature look. Preview it safely inside NAMELESS."
        )
        desc.setObjectName("heroDescription")
        hl.addWidget(desc)
        hl.addStretch()
        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(10)
        open_visuals = QPushButton("EXPLORE VISUAL LAB   ↗")
        open_visuals.setObjectName("primaryAction")
        open_visuals.clicked.connect(lambda: self.navigate("Visuals Studio"))
        hero_actions.addWidget(open_visuals)
        showroom = QPushButton("EXPLORE REDUX WORLDS")
        showroom.clicked.connect(
            lambda checked=False: self.open_redux_showroom())
        hero_actions.addWidget(showroom)
        garage = QPushButton("BUILD YOUR LOOK")
        garage.clicked.connect(
            lambda checked=False: self.open_cosmetic_garage())
        hero_actions.addWidget(garage)
        hero_actions.addStretch()
        hl.addLayout(hero_actions)
        l.addWidget(hero)
        grid = QGridLayout()
        stats = [
            ("VISUAL PACKS", str(len(VISUAL_PACKS) + len(self.custom_visual_packs)), "Built-in and custom"),
            ("SAVED PROFILES", str(len(self.profiles)), "Your configurations"),
            ("AUDIO FILES", "0", "Local preview library"),
        ]
        self.stat_values = []
        for i, (title, value, hint) in enumerate(stats):
            c, cl = self.card(title, hint)
            val = QLabel(value)
            val.setObjectName("stat")
            c.setObjectName("statCard")
            cl.addWidget(val)
            grid.addWidget(c, 0, i)
            self.stat_values.append(val)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        l.addLayout(grid)
        quick, ql = self.card("QUICK ACCESS", "Jump into your workspace.")
        row = QHBoxLayout()
        for text, target in [("Visuals Studio", "Visuals Studio"),
                             ("Sound Library", "Sound Library"),
                             ("Crosshair Studio", "Crosshair Studio")]:
            b = QPushButton(text)
            b.clicked.connect(lambda checked=False, n=target: self.navigate(n))
            row.addWidget(b)
        ql.addLayout(row)
        overview_bottom = QHBoxLayout()
        overview_bottom.setSpacing(14)
        overview_bottom.addWidget(quick, 3)
        steam_shortcut, steam_shortcut_layout = self.card(
            "ROB RUN  /  STEAM", "Connect to your installed game safely.")
        steam_launch = QPushButton("OPEN GAME CENTER   ↗")
        steam_launch.clicked.connect(lambda: self.navigate("Game Center"))
        steam_shortcut_layout.addWidget(steam_launch)
        overview_bottom.addWidget(steam_shortcut, 2)
        l.addLayout(overview_bottom)
        note = QLabel("ORIGINAL CONCEPT ART   •   STANDALONE PREVIEWS   •   NO GAME-FILE MODIFICATIONS")
        note.setObjectName("muted")
        note.setWordWrap(True)
        l.addWidget(note)
        l.addStretch()
        self.add_page("Overview", page)

        # Visuals
        page = QWidget()
        l = QVBoxLayout(page)
        l.addLayout(self.heading("VISUAL LAB", "Live color controls and real ROB RUN screenshot comparisons."))
        c, cl = self.card("COLOR PRESET", "Choose a base palette.")
        self.palette_combo = ClickOnlyComboBox()
        self.palette_combo.setMinimumHeight(40)
        self.palette_combo.addItems(PRESETS.keys())
        cl.addWidget(self.palette_combo)
        self.intensity_label = QLabel("Intensity  •  65%")
        self.intensity_slider = OceanSlider(Qt.Horizontal)
        self.intensity_slider.setRange(0, 100)
        self.intensity_slider.setValue(65)
        self.intensity_slider.valueChanged.connect(lambda v: self.intensity_label.setText(f"Intensity  •  {v}%"))
        cl.addWidget(self.intensity_label)
        cl.addWidget(self.intensity_slider)
        self.cool_check = OceanToggle("Prefer cool blue tones")
        self.cool_check.setChecked(True)
        cl.addWidget(self.cool_check)
        self.visual_swatch = QFrame()
        self.visual_swatch.setMinimumHeight(105)
        self.visual_swatch.setObjectName("swatch")
        cl.addWidget(self.visual_swatch)
        self.palette_combo.currentTextChanged.connect(self.update_swatch)
        self.intensity_slider.valueChanged.connect(self.update_swatch)
        self.cool_check.stateChanged.connect(self.update_swatch)
        save = QPushButton("SAVE VISUAL SETTINGS")
        save.clicked.connect(self.save_visuals)
        cl.addWidget(save)
        l.addWidget(c)
        packs_card, packs_layout = self.card("VISUAL PACK LIBRARY", "Choose a ready-made look or save your own. Packs only change this application's visual preview.")
        self.pack_list = QListWidget()
        self.pack_list.setMinimumHeight(120)
        packs_layout.addWidget(self.pack_list)
        actions = QGridLayout()
        for index, (label, handler) in enumerate([
            ("APPLY PACK", self.apply_visual_pack),
            ("SAVE CURRENT AS PACK", self.create_visual_pack),
            ("DELETE CUSTOM PACK", self.delete_visual_pack),
            ("IMPORT PACK", self.import_visual_pack),
            ("EXPORT PACK", self.export_visual_pack),
        ]):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button, index // 2, index % 2)
        packs_layout.addLayout(actions)
        l.addWidget(packs_card)
        self.refresh_visual_packs()
        effects_card, effects_layout = self.card(
            "ROB RUN VISUAL LAB", "Real Steam screenshot • before/after grading • live cinematic controls. Preview only.")
        self.effects_preview = EffectsPreview()
        self.effects_preview.setToolTip(
            "Drag the comparison divider to inspect your visual adjustments.")
        self.effects_preview.setMinimumHeight(460)
        self.effects_preview.setObjectName("visualCanvas")
        effects_layout.addWidget(self.effects_preview)
        self.preview_source = QLabel("ROB RUN • automatic official Steam preview")
        self.preview_source.setObjectName("previewSource")
        self.preview_source.setWordWrap(True)
        effects_layout.addWidget(self.preview_source)
        compare_row = QHBoxLayout()
        self.compare_check = OceanToggle("Before / after comparison")
        self.compare_check.setChecked(True)
        self.compare_check.stateChanged.connect(self.toggle_compare)
        compare_row.addWidget(self.compare_check)
        effects_layout.addLayout(compare_row)
        self.compare_slider = self.add_slider(effects_layout, "BEFORE / AFTER SPLIT", 0, 100, 50)
        self.compare_slider.valueChanged.connect(self.update_compare)
        self.effect_preset = ClickOnlyComboBox()
        self.effect_preset.addItems(EFFECT_PRESETS.keys())
        effects_layout.addWidget(QLabel("CINEMATIC EFFECT PRESET"))
        effects_layout.addWidget(self.effect_preset)
        preset_btn = QPushButton("APPLY EFFECT PRESET")
        preset_btn.clicked.connect(self.apply_effect_preset)
        effects_layout.addWidget(preset_btn)
        self.effect_sliders = {}
        for key, label, low, high, initial in [
            ("brightness", "BRIGHTNESS", -50, 50, 0),
            ("contrast", "CONTRAST", 0, 200, 100),
            ("saturation", "SATURATION", 0, 200, 100),
            ("warmth", "TEMPERATURE", -100, 100, 0),
        ]:
            self.effect_sliders[key] = self.add_slider(effects_layout, label, low, high, initial)
        self.effects_timer = QTimer(self)
        self.effects_timer.setSingleShot(True)
        self.effects_timer.setInterval(25)
        self.effects_timer.timeout.connect(self.update_effects_preview)
        for slider in self.effect_sliders.values():
            slider.valueChanged.connect(self.update_effects_preview)
        effect_actions = QHBoxLayout()
        for title, handler in [
            ("SAVE EFFECTS", self.save_effects),
            ("RESET EFFECTS", self.reset_effects),
            ("EXPORT PREVIEW PNG", self.export_effects_preview),
        ]:
            btn = QPushButton(title)
            btn.clicked.connect(handler)
            effect_actions.addWidget(btn)
        effects_layout.addLayout(effect_actions)
        l.addWidget(effects_card)
        l.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("oceanScroll")
        scroll.setAutoFillBackground(False)
        scroll.viewport().setObjectName("oceanViewport")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        self.add_page("Visuals Studio", scroll)

        # Theme Lab: user-defined gradient and animation preferences.
        page = QWidget()
        l = QVBoxLayout(page)
        l.setSpacing(16)
        l.addLayout(self.heading("THEME LAB", "Build your own animated gradient. Settings remain local."))
        c, cl = self.card("GRADIENT DESIGNER", "Choose two colors for the ambient background and hero panel.")
        self.theme_preview = GradientHero()
        self.theme_preview.setMinimumHeight(125)
        cl.addWidget(self.theme_preview)
        color_row = QHBoxLayout()
        start_btn = QPushButton("START COLOR")
        start_btn.clicked.connect(lambda: self.pick_theme_color("start"))
        end_btn = QPushButton("END COLOR")
        end_btn.clicked.connect(lambda: self.pick_theme_color("end"))
        color_row.addWidget(start_btn)
        color_row.addWidget(end_btn)
        cl.addLayout(color_row)
        self.motion_check = OceanToggle("Enable ambient animations")
        self.motion_check.setChecked(True)
        self.motion_check.stateChanged.connect(self.update_motion)
        cl.addWidget(self.motion_check)
        self.motion_speed = self.add_slider(cl, "MOTION SPEED", 1, 5, 2)
        self.motion_speed.valueChanged.connect(self.update_motion)
        actions = QHBoxLayout()
        for title, handler in [("SAVE THEME", self.save_theme),
                               ("EXPORT THEME", self.export_theme),
                               ("IMPORT THEME", self.import_theme),
                               ("RESET THEME", self.reset_theme)]:
            btn = QPushButton(title)
            btn.clicked.connect(handler)
            actions.addWidget(btn)
        cl.addLayout(actions)
        l.addWidget(c)
        hint = QLabel("Motion settings also affect the main background. Disable animations for lower CPU use.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        l.addWidget(hint)
        l.addStretch()
        self.add_page("Theme Lab", page)

        # Sound
        page = QWidget()
        l = QVBoxLayout(page)
        l.addLayout(self.heading("SOUND LIBRARY", "Organize audio files and listen to them locally before using them in your own projects."))
        c, cl = self.card("LOCAL AUDIO COLLECTION", "Supported formats: WAV, MP3, OGG, FLAC.")
        row = QHBoxLayout()
        add = QPushButton("＋  ADD AUDIO")
        add.clicked.connect(self.add_audio)
        play = QPushButton("PLAY SELECTED")
        play.clicked.connect(self.play_audio)
        remove = QPushButton("REMOVE SELECTED")
        remove.clicked.connect(self.remove_audio)
        stop = QPushButton("STOP")
        stop.clicked.connect(self.stop_audio)
        row.addWidget(add)
        row.addWidget(play)
        row.addWidget(stop)
        row.addWidget(remove)
        cl.addLayout(row)
        self.audio_list = QListWidget()
        self.audio_list.setMinimumHeight(220)
        cl.addWidget(self.audio_list)
        self.audio_count_label = QLabel("0 audio files in this session")
        self.audio_count_label.setObjectName("muted")
        cl.addWidget(self.audio_count_label)
        if not MULTIMEDIA_AVAILABLE:
            hint = QLabel("Audio playback is unavailable in this Python environment. You can still organize files here.")
            hint.setObjectName("muted")
            cl.addWidget(hint)
        l.addWidget(c)
        l.addStretch()
        self.add_page("Sound Library", page)

        # Crosshair
        page = QWidget()
        l = QVBoxLayout(page)
        l.addLayout(self.heading("CROSSHAIR STUDIO", "Design a standalone visual preview. Changes stay inside this editor."))
        grid = QGridLayout()
        preview_card, pl = self.card("LIVE PREVIEW", "Preview area")
        self.cross_preview = CrosshairPreview()
        pl.addWidget(self.cross_preview)
        grid.addWidget(preview_card, 0, 0, 2, 1)
        controls, cl = self.card("DESIGN CONTROLS")
        self.cross_style = ClickOnlyComboBox()
        self.cross_style.addItems(["Classic", "Cross", "Dot", "Circle"])
        self.cross_color = ClickOnlyComboBox()
        self.cross_color.addItems(CROSSHAIR_COLORS.keys())
        cl.addWidget(QLabel("STYLE"))
        cl.addWidget(self.cross_style)
        cl.addWidget(QLabel("COLOR"))
        cl.addWidget(self.cross_color)
        self.cross_size = self.add_slider(cl, "SIZE", 8, 50, 22)
        self.cross_gap = self.add_slider(cl, "GAP", 0, 20, 6)
        self.cross_thickness = self.add_slider(cl, "THICKNESS", 1, 6, 2)
        self.cross_dot = OceanToggle("Center dot")
        self.cross_outline = OceanToggle("Dark outline")
        self.cross_outline.setChecked(True)
        cl.addWidget(self.cross_dot)
        cl.addWidget(self.cross_outline)
        export_png = QPushButton("EXPORT PNG")
        export_png.clicked.connect(self.export_crosshair_png)
        cl.addWidget(export_png)
        save = QPushButton("SAVE CROSSHAIR PRESET")
        save.clicked.connect(self.save_crosshair)
        cl.addWidget(save)
        grid.addWidget(controls, 0, 1)
        l.addLayout(grid)
        l.addStretch()
        for widget in [self.cross_style, self.cross_color]:
            widget.currentTextChanged.connect(self.update_crosshair)
        for slider in [self.cross_size, self.cross_gap, self.cross_thickness]:
            slider.valueChanged.connect(self.update_crosshair)
        self.cross_dot.stateChanged.connect(self.update_crosshair)
        self.cross_outline.stateChanged.connect(self.update_crosshair)
        self.add_page("Crosshair Studio", page)

        # Profiles
        page = QWidget()
        l = QVBoxLayout(page)
        l.addLayout(self.heading("PROFILE SYSTEM", "Save named combinations of your visual and crosshair settings."))
        c, cl = self.card("YOUR PROFILES", "Profiles are stored locally in this application.")
        row = QHBoxLayout()
        create = QPushButton("＋  SAVE CURRENT AS PROFILE")
        create.clicked.connect(self.create_profile)
        load = QPushButton("LOAD SELECTED")
        load.clicked.connect(self.load_profile)
        export_profiles = QPushButton("EXPORT JSON")
        export_profiles.clicked.connect(self.export_profiles)
        import_profiles = QPushButton("IMPORT JSON")
        import_profiles.clicked.connect(self.import_profiles)
        delete = QPushButton("DELETE")
        delete.clicked.connect(self.delete_profile)
        row.addWidget(create)
        row.addWidget(load)
        row.addWidget(delete)
        cl.addLayout(row)
        transfer_row = QHBoxLayout()
        transfer_row.addWidget(export_profiles)
        transfer_row.addWidget(import_profiles)
        cl.addLayout(transfer_row)
        self.profile_list = QListWidget()
        cl.addWidget(self.profile_list)
        l.addWidget(c)
        l.addStretch()
        self.add_page("Profiles", page)
        self.refresh_profiles()

        # Game Center — read-only inspection, never edits game files.
        page = QWidget()
        l = QVBoxLayout(page)
        l.setSpacing(14)
        l.addLayout(self.heading("GAME CENTER", "Steam Connect • ROB RUN / App ID 4262460 • safe read-only detection"))
        fps_card, fps_layout = self.card(
            "FPS LAB  /  PERFORMANCE STUDIO",
            "Read-only hardware check, three optimization guides and honest FPS comparisons.")
        fps_open = QPushButton("OPEN FPS LAB  /  HELP LOW-END PCs")
        fps_open.clicked.connect(self.open_fps_lab)
        fps_layout.addWidget(fps_open)
        l.addWidget(fps_card)
        ping_card, ping_layout = self.card(
            "PING LAB  /  NETWORK STABILITY",
            "Check public reference connections for delays and failures; "
            "not a ROB RUN server or UDP packet-loss test.")
        ping_open = QPushButton("OPEN PING LAB  /  CHECK CONNECTION")
        ping_open.clicked.connect(self.open_ping_lab)
        ping_layout.addWidget(ping_open)
        l.addWidget(ping_card)

        steam_card, steam_layout = self.card("STEAM CONNECT  /  LIVE", "Find the installed game and launch it through Steam. No injection or game file modification.")
        self.steam_status = QLabel("Checking Steam installation…")
        self.steam_status.setObjectName("accent")
        steam_layout.addWidget(self.steam_status)
        steam_buttons = QHBoxLayout()
        for title, handler in [
            ("FIND ROB RUN", self.refresh_steam_status),
            ("PLAY VIA STEAM", self.launch_steam_game),
        ]:
            btn = QPushButton(title)
            btn.clicked.connect(handler)
            steam_buttons.addWidget(btn)
        steam_layout.addLayout(steam_buttons)
        l.addWidget(steam_card)
        c, cl = self.card("GAME INSTALLATION", "Choose the game's root folder manually. This does not verify game compatibility.")
        path_row = QHBoxLayout()
        self.game_path_input = QLineEdit()
        self.game_path_input.setPlaceholderText("Select ROB RUN folder...")
        self.game_path_input.setReadOnly(True)
        path_row.addWidget(self.game_path_input, 1)
        browse = QPushButton("BROWSE")
        browse.clicked.connect(self.choose_game_folder)
        path_row.addWidget(browse)
        cl.addLayout(path_row)
        scan_row = QHBoxLayout()
        scan = QPushButton("SCAN FOLDER")
        scan.clicked.connect(self.scan_game_folder)
        export = QPushButton("EXPORT REPORT")
        export.clicked.connect(self.export_game_report)
        scan_row.addWidget(scan)
        scan_row.addWidget(export)
        cl.addLayout(scan_row)
        self.game_status = QLabel("No folder scanned yet.")
        self.game_status.setObjectName("muted")
        self.game_status.setWordWrap(True)
        cl.addWidget(self.game_status)
        l.addWidget(c)
        report_card, report_layout = self.card("SCAN RESULTS", "File types and total size. Symlinks are skipped; scanning is capped at 20,000 files.")
        self.game_report_view = QListWidget()
        self.game_report_view.setMinimumHeight(170)
        report_layout.addWidget(self.game_report_view)
        l.addWidget(report_card)
        l.addStretch()
        self.game_report = None
        compatibility_card, compatibility_layout = self.card(
            "COMPATIBILITY INSPECTOR",
            "Read-only engine clues based on file names. No game identity or mod support is assumed.")
        self.compatibility_label = QLabel("Run SCAN FOLDER to inspect engine clues.")
        self.compatibility_label.setObjectName("muted")
        self.compatibility_label.setWordWrap(True)
        compatibility_layout.addWidget(self.compatibility_label)
        self.compatibility_evidence = QListWidget()
        self.compatibility_evidence.setMinimumHeight(90)
        compatibility_layout.addWidget(self.compatibility_evidence)
        l.addWidget(compatibility_card)
        config_card, config_layout = self.card(
            "CONFIG DISCOVERY / v1.4",
            "Find likely settings files by name and extension. Read-only inventory; no config values are read or changed.")
        config_actions = QHBoxLayout()
        discover = QPushButton("FIND CONFIG CANDIDATES")
        discover.clicked.connect(self.find_game_configs)
        export_configs = QPushButton("EXPORT CONFIG REPORT")
        export_configs.clicked.connect(self.export_config_report)
        config_actions.addWidget(discover)
        config_actions.addWidget(export_configs)
        config_layout.addLayout(config_actions)
        self.config_status = QLabel("No config discovery performed yet.")
        self.config_status.setObjectName("muted")
        self.config_status.setWordWrap(True)
        config_layout.addWidget(self.config_status)
        self.config_list = QListWidget()
        self.config_list.setMinimumHeight(125)
        config_layout.addWidget(self.config_list)
        self.config_report = None
        l.addWidget(config_card)
        backup_card, backup_layout = self.card(
            "BACKUP MANAGER", "Create a ZIP backup of selected game files. Restore only to a separate empty folder; never overwrite the game.")
        backup_buttons = QHBoxLayout()
        create_backup = QPushButton("BACK UP SELECTED FILES")
        create_backup.clicked.connect(self.create_game_backup)
        restore_backup = QPushButton("EXTRACT BACKUP SAFELY")
        restore_backup.clicked.connect(self.restore_game_backup)
        backup_buttons.addWidget(create_backup)
        backup_buttons.addWidget(restore_backup)
        backup_layout.addLayout(backup_buttons)
        self.backup_status = QLabel("No backup operation performed.")
        self.backup_status.setObjectName("muted")
        self.backup_status.setWordWrap(True)
        backup_layout.addWidget(self.backup_status)
        l.addWidget(backup_card)
        pack_card, pack_layout = self.card(
            "REDUX PACK MANAGER", "Inspect ZIP packs, verify SHA-256 checksums and stage assets outside the game. Game files are never patched.")
        pack_buttons = QHBoxLayout()
        for label, callback in [("OPEN PACK", self.open_redux_pack), ("STAGE PACK", self.stage_selected_pack)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            pack_buttons.addWidget(button)
        pack_layout.addLayout(pack_buttons)
        self.redux_pack_path = None
        self.redux_pack_manifest = None
        self.redux_pack_status = QLabel("No pack selected. Expected ZIP format: nameless-redux-pack-v1.")
        self.redux_pack_status.setObjectName("muted")
        self.redux_pack_status.setWordWrap(True)
        pack_layout.addWidget(self.redux_pack_status)
        self.redux_pack_assets = QListWidget()
        self.redux_pack_assets.setMinimumHeight(110)
        pack_layout.addWidget(self.redux_pack_assets)
        l.addWidget(pack_card)
        scroll_game = QScrollArea()
        scroll_game.setWidgetResizable(True)
        scroll_game.setObjectName("oceanScroll")
        scroll_game.setAutoFillBackground(False)
        scroll_game.viewport().setObjectName("oceanViewport")
        scroll_game.viewport().setAutoFillBackground(False)
        scroll_game.setFrameShape(QFrame.NoFrame)
        scroll_game.setWidget(page)
        self.add_page("Game Center", scroll_game)

        # Settings
        page = QWidget()
        l = QVBoxLayout(page)
        l.addLayout(self.heading("SETTINGS", "Application information and local preferences."))
        c, cl = self.card("ABOUT NAMELESS REDUX", "A standalone creative workspace with local previews.")
        for line in [f"Version: {VERSION}", "Edition: Ocean Reborn 2.0", "Mode: Local preview",
                     "Game integration: Read-only inspector, backup + pack staging", "Settings storage: This PC", "Theme Lab: animated custom gradients"]:
            lab = QLabel(line)
            lab.setObjectName("muted")
            cl.addWidget(lab)
        reset = QPushButton("RESET APPLICATION PREFERENCES")
        reset.clicked.connect(self.reset_settings)
        cl.addWidget(reset)
        l.addWidget(c)
        l.addStretch()
        self.add_page("Settings", page)

    def load_initial_screenshot(self):
        """Restore the user's screenshot first, then bundled/cache/Steam sources."""
        from PySide6.QtCore import QStandardPaths
        # Invalidate any in-flight Steam replies before choosing a local image.
        self._preview_request_id = getattr(self, "_preview_request_id", 0) + 1
        saved = str(self.settings.value("preview/screenshot", "") or "")
        if saved and Path(saved).is_file():
            if self.effects_preview.set_screenshot(QImage(saved)):
                self.preview_source.setText("YOUR ROB RUN SCREENSHOT • " + Path(saved).name)
                return
        bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / "rob_run_preview.jpg"
        executable_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        candidates = (bundled, executable_dir / "rob_run_preview.jpg", executable_dir / "images.jpg")
        for candidate in candidates:
            if candidate.is_file() and self.effects_preview.set_screenshot(QImage(str(candidate))):
                self.preview_source.setText("ROB RUN • permanent reference image • preview only")
                return
        cache_root = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        self._official_preview_cache = Path(cache_root) / "rob_run_official_preview.png"
        if self._official_preview_cache.is_file():
            if self.effects_preview.set_screenshot(QImage(str(self._official_preview_cache))):
                self.preview_source.setText("ROB RUN • official Steam preview (cached)")
                return
        self.load_official_screenshot()

    def choose_preview_screenshot(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select a real ROB RUN screenshot", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if filename:
            image = QImage(filename)
            if self.effects_preview.set_screenshot(image):
                self._preview_request_id = getattr(self, "_preview_request_id", 0) + 1
                self.preview_source.setText("YOUR ROB RUN SCREENSHOT • " + Path(filename).name)
                # Persist a private local copy so moving/deleting Downloads won't
                # silently restore the unrelated vector placeholder.
                from PySide6.QtCore import QStandardPaths
                cache = Path(QStandardPaths.writableLocation(
                    QStandardPaths.AppLocalDataLocation)) / "user_rob_run_preview.png"
                try:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    if not image.save(str(cache), "PNG"):
                        raise OSError("Could not save screenshot")
                    self.settings.setValue("preview/screenshot", str(cache))
                except OSError:
                    self.settings.setValue("preview/screenshot", filename)
            else:
                QMessageBox.warning(self, "Image error", "Could not open the screenshot.")

    def load_official_screenshot(self):
        # Ignore stale requests if the user selects their own screenshot.
        self._preview_request_id = getattr(self, "_preview_request_id", 0) + 1
        request_id = self._preview_request_id
        url = QUrl("https://store.steampowered.com/api/appdetails?appids=4262460&l=english")
        reply = self.network.get(QNetworkRequest(url))
        reply.finished.connect(lambda r=reply, n=request_id: self._steam_metadata_ready(r, n))

    def _steam_metadata_ready(self, reply, request_id):
        try:
            if request_id != self._preview_request_id:
                return
            if reply.error():
                raise ValueError(reply.errorString())
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            shots = payload[STEAM_APP_ID]["data"]["screenshots"]
            if not shots:
                raise ValueError("No screenshots published")
            url = QUrl(shots[0]["path_full"])
            if url.scheme() != "https" or not (
                url.host() == "steamstatic.com" or url.host().endswith(".steamstatic.com")
            ):
                raise ValueError("Unexpected screenshot host")
            picture_reply = self.network.get(QNetworkRequest(url))
            picture_reply.finished.connect(lambda r=picture_reply, n=request_id: self._steam_image_ready(r, n))
        except (ValueError, KeyError, IndexError, TypeError, UnicodeError) as exc:
            self.preview_source.setText(
                "Official ROB RUN preview temporarily unavailable • " + str(exc))
        finally:
            reply.deleteLater()

    def _steam_image_ready(self, reply, request_id):
        try:
            if request_id != self._preview_request_id:
                return
            if reply.error():
                raise ValueError(reply.errorString())
            data = bytes(reply.readAll())
            if len(data) > 12 * 1024 * 1024:
                raise ValueError("Image too large")
            image = QImage.fromData(data)
            if not self.effects_preview.set_screenshot(image):
                raise ValueError("Invalid image")
            self.preview_source.setText(
                "ROB RUN • official Steam preview • visual comparison only")
            try:
                self._official_preview_cache.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(self._official_preview_cache), "PNG")
            except (OSError, AttributeError):
                pass
        except ValueError as exc:
            self.preview_source.setText("Screenshot unavailable: " + str(exc))
        finally:
            reply.deleteLater()

    def refresh_steam_status(self):
        folder = find_steam_game()
        if folder is None:
            self.steam_status.setText("● ROB RUN NOT FOUND IN STEAM LIBRARIES")
            self.top_game_status.setText("● ROB RUN  /  NOT FOUND")
            self._last_game_running = False
            self.top_launch_button.setProperty("gameRunning", False)
            self.top_launch_button.setText("▶  LAUNCH GAME")
            self.top_launch_button.setEnabled(True)
            self.top_launch_button.style().unpolish(self.top_launch_button)
            self.top_launch_button.style().polish(self.top_launch_button)
            return
        if not self.game_path_input.text():
            self.game_path_input.setText(str(folder))
        running = False
        if os.name == "nt":
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=3, creationflags=flags)
                # Steam's game process may use a different executable name.
                # Only match executable names found in the installed game root.
                import csv
                from io import StringIO
                candidates = {
                    p.name.casefold() for p in folder.glob("*.exe") if p.is_file()
                }
                running = any(
                    row and row[0].strip().casefold() in candidates
                    for row in csv.reader(StringIO(result.stdout))
                )
            except (OSError, subprocess.TimeoutExpired, UnicodeError, csv.Error):
                pass
        if running and not self._last_game_running:
            self.statusBar().showMessage(
                "ROB RUN detected • Your NAMELESS workspace is ready", 5000)
        self._last_game_running = running
        if self.top_launch_button.property("gameRunning") != running:
            self.top_launch_button.setProperty("gameRunning", running)
            self.top_launch_button.setText("●  GAME RUNNING" if running else "▶  LAUNCH GAME")
            self.top_launch_button.style().unpolish(self.top_launch_button)
            self.top_launch_button.style().polish(self.top_launch_button)
        # Do not launch a second instance when the game is already running.
        self.top_launch_button.setEnabled(not running)
        self.steam_status.setText(
            ("● ROB RUN RUNNING" if running else "● ROB RUN INSTALLED")
            + "  •  " + str(folder))
        self.top_game_status.setText("● ROB RUN  /  " + ("RUNNING" if running else "INSTALLED"))

    def launch_steam_game(self):
        import webbrowser
        webbrowser.open("steam://rungameid/" + STEAM_APP_ID)

    def choose_game_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose ROB RUN installation")
        if not folder:
            return
        resolved = str(Path(folder).resolve())
        self.game_path_input.setText(resolved)
        self.settings.setValue("game/folder", resolved)
        self.game_report = None
        self.config_report = None
        self.config_list.clear()
        self.config_status.setText("No config discovery performed yet.")
        self.game_report_view.clear()
        self.game_status.setText("Folder selected. Press SCAN FOLDER to inspect it.")
        self.compatibility_label.setText("Run SCAN FOLDER to inspect engine clues.")
        self.compatibility_evidence.clear()

    def scan_game_folder(self):
        folder = Path(self.game_path_input.text())
        if not folder.is_dir() or folder.is_symlink():
            QMessageBox.warning(self, "Invalid folder", "Select an existing, non-symlink folder first.")
            return
        counts = Counter()
        size = 0
        total = 0
        limited = False
        errors = 0
        sample_paths = []
        # Do not follow directory symlinks or read/modify file contents.
        import os
        def on_error(_):
            nonlocal errors
            errors += 1
        for root, dirs, files in os.walk(folder, followlinks=False, onerror=on_error):
            dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
            for filename in files:
                candidate = Path(root) / filename
                if candidate.is_symlink():
                    continue
                try:
                    info = candidate.stat()
                except OSError:
                    errors += 1
                    continue
                total += 1
                if len(sample_paths) < 20000:
                    sample_paths.append(candidate.relative_to(folder).as_posix())
                size += info.st_size
                counts[candidate.suffix.lower() or "[no extension]"] += 1
                if total >= 20000:
                    limited = True
                    break
            if limited:
                break
        compatibility = inspect_game_layout(sample_paths)
        self.game_report = {
            "format": "nameless-game-scan-v2",
            "compatibility": compatibility,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "folder": str(folder.resolve()),
            "file_count": total,
            "total_bytes": size,
            "extensions": dict(counts.most_common()),
            "limited": limited,
            "read_errors": errors,
            "compatibility_verified": False,
            "files_modified": False,
        }
        self.compatibility_evidence.clear()
        for path in compatibility["evidence_paths"]:
            self.compatibility_evidence.addItem(path)
        hints = ", ".join(compatibility["engine_hints"]) or "No recognizable engine signatures"
        self.compatibility_label.setText(
            f"Possible layout: {hints}. Compatibility: UNVERIFIED. Game files will not be modified.")
        self.game_report_view.clear()
        for ext, count in counts.most_common(40):
            self.game_report_view.addItem(f"{ext}    —    {count} files")
        suffix = " (scan limit reached)" if limited else ""
        self.game_status.setText(f"Scanned {total:,} files, {size / (1024**3):.2f} GiB{suffix}. Read errors: {errors}. Compatibility not verified.")

    def find_game_configs(self):
        folder = Path(self.game_path_input.text())
        try:
            report = discover_config_candidates(folder)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Discovery failed", str(exc))
            return
        self.config_report = report
        self.config_list.clear()
        for item in report["candidates"]:
            self.config_list.addItem(f'{item["path"]}  ({item["size_bytes"]:,} bytes)')
        suffix = " Results capped." if report["truncated"] else ""
        self.config_status.setText(
            f'{len(report["candidates"])} possible config files among '
            f'{report["files_inspected"]:,} inspected. Errors: {report["read_errors"]}.{suffix} '
            'These are unverified candidates, NOT confirmed game settings.')

    def export_config_report(self):
        if not self.config_report:
            QMessageBox.information(self, "No config report", "Run FIND CONFIG CANDIDATES first.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export read-only config inventory", "nameless_config_candidates.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps(self.config_report, indent=2, ensure_ascii=False), encoding="utf-8")
            self.statusBar().showMessage("Config inventory exported.", 3500)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def export_game_report(self):
        if self.game_report is None:
            QMessageBox.information(self, "No report", "Scan a folder first.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save scan report", "nameless_game_scan.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps(self.game_report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.statusBar().showMessage("Scan report exported.", 4000)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def create_game_backup(self):
        folder = Path(self.game_path_input.text())
        if not folder.is_dir() or folder.is_symlink():
            QMessageBox.warning(self, "No game folder", "Select a valid game folder first.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select files to back up", str(folder), "All files (*)")
        if not files:
            return
        archive, _ = QFileDialog.getSaveFileName(self, "Save backup outside game folder", "nameless_backup.zip", "ZIP (*.zip)")
        if not archive:
            return
        try:
            result = create_backup_archive(folder, archive, files)
            self.backup_status.setText(f"Backup created: {len(result['files'])} files → {archive}")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def restore_game_backup(self):
        archive, _ = QFileDialog.getOpenFileName(self, "Choose backup archive", "", "ZIP (*.zip)")
        if not archive:
            return
        destination = QFileDialog.getExistingDirectory(self, "Choose an EMPTY extraction folder (not the game)")
        if not destination:
            return
        try:
            folder = Path(self.game_path_input.text())
            target = Path(destination).resolve()
            if folder.is_dir() and (target == folder.resolve() or target.is_relative_to(folder.resolve())):
                raise ValueError("Cannot extract inside the selected game directory.")
            count = extract_backup_archive(archive, destination)
            self.backup_status.setText(f"Verified and extracted {count} files to {destination}. Game untouched.")
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Extraction failed", str(exc))

    def open_redux_pack(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Redux pack", "", "Redux packs (*.zip)")
        if not path:
            return
        self.redux_pack_path = None
        self.redux_pack_manifest = None
        self.redux_pack_assets.clear()
        try:
            manifest = inspect_redux_pack(path)
            self.redux_pack_path = path
            self.redux_pack_manifest = manifest
            for entry in manifest["files"]:
                self.redux_pack_assets.addItem(entry["path"])
            self.redux_pack_status.setText(
                f"VERIFIED: {manifest['name']} | {len(manifest['files'])} assets | staging only, no game integration")
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            self.redux_pack_status.setText("Pack rejected: " + str(exc))
            QMessageBox.warning(self, "Invalid Redux pack", str(exc))

    def stage_selected_pack(self):
        if not self.redux_pack_path:
            QMessageBox.information(self, "No pack", "Open a valid pack first.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose an EMPTY staging folder outside the game")
        if not folder:
            return
        try:
            target = Path(folder).resolve()
            game = Path(self.game_path_input.text())
            if game.is_dir():
                root = game.resolve()
                if target == root or target.is_relative_to(root):
                    raise ValueError("Staging inside the game folder is blocked.")
            count = stage_redux_pack(self.redux_pack_path, target)
            self.redux_pack_status.setText(f"Staged {count} verified assets to {target}. Game unchanged.")
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Staging failed", str(exc))

    def build_collection(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.addLayout(self.heading(
            "REDUX COLLECTION",
            "Four original worlds • 20 cosmetic concepts • mix-and-match garage • performance-first design."))
        performance_note = QLabel(
            "PERFORMANCE FIRST  /  Future game packs must offer FPS-friendly assets, "
            "reduced particle load, and tested compatibility. No FPS boost is claimed yet.")
        performance_note.setObjectName("muted")
        performance_note.setWordWrap(True)
        layout.addWidget(performance_note)
        showroom_intro = QHBoxLayout()
        showroom_button = GlowButton("OPEN INTERACTIVE REDUX SHOWROOM   ↗")
        showroom_button.setObjectName("primaryAction")
        showroom_button.clicked.connect(
            lambda checked=False: self.open_redux_showroom())
        showroom_intro.addWidget(showroom_button)
        garage_button = QPushButton("OPEN COSMETIC GARAGE  /  20 DESIGNS")
        garage_button.clicked.connect(
            lambda checked=False: self.open_cosmetic_garage())
        showroom_intro.addWidget(garage_button)
        atlas_button = QPushButton("THE REDUX ATLAS  /  ALL 20 CONCEPTS")
        atlas_button.clicked.connect(
            lambda checked=False: self.open_redux_atlas())
        showroom_intro.addWidget(atlas_button)
        showroom_intro.addStretch()
        layout.addLayout(showroom_intro)
        grid = QGridLayout()
        grid.setSpacing(14)
        packs = [
            ("SAKURA DREAM", "Pink skies / cherry blossoms / soft soundscape", "#E9A3BB", "#704357", "Coral"),
            ("NEON NIGHT", "Purple neon / electric trails / synth atmosphere", "#A57AF4", "#39255A", "Deep Violet"),
            ("FROSTBITE", "Icy blue / snow particles / crystalline atmosphere", "#A7E0F0", "#244C67", "Arctic Blue"),
            ("CRIMSON", "Red sky / ember particles / dramatic soundscape", "#E47E68", "#562A2E", "Sunset"),
        ]
        pack_features = {
            "SAKURA DREAM": ("01 / DREAMSCAPE", "PETAL BLOOM", "Pink dusk · Sakura blossoms · Soft acoustic concepts"),
            "NEON NIGHT": ("02 / AFTER DARK", "ELECTRIC CITY", "Violet skyline · Electric trails · Synth atmosphere"),
            "FROSTBITE": ("03 / WINTER SIGNAL", "ZERO DEGREE", "Frozen peaks · Crystalline particles · Cool tones"),
            "CRIMSON": ("04 / LAST LIGHT", "BURNING HORIZON", "Red sunset · Ember trails · Dramatic soundscape"),
        }
        for i, (name, detail, accent, shadow, palette) in enumerate(packs):
            card, inner = self.card(name)
            card.setObjectName("reduxCollectionCard")
            inner.setContentsMargins(16, 16, 16, 18)
            inner.setSpacing(10)
            art = ReduxCover(name, accent, shadow)
            art.setMinimumHeight(230)
            inner.insertWidget(0, art)
            number, tagline, mood = pack_features[name]
            edition = QLabel(number + "   /   ORIGINAL REDUX CONCEPT")
            edition.setObjectName("collectionEyebrow")
            inner.insertWidget(1, edition)
            headline = QLabel(tagline)
            headline.setObjectName("collectionHeadline")
            inner.insertWidget(2, headline)
            mood_label = QLabel(mood)
            mood_label.setObjectName("collectionMood")
            mood_label.setWordWrap(True)
            inner.addWidget(mood_label)
            collection_stats = QLabel("01 WORLD   /   05 COSMETIC CATEGORIES   /   LIVE PREVIEW")
            collection_stats.setObjectName("collectionEyebrow")
            inner.addWidget(collection_stats)

            actions = QHBoxLayout()
            actions.setSpacing(8)
            demo = QPushButton("EXPLORE WORLD   ↗")
            demo.setObjectName("primaryAction")
            demo.clicked.connect(
                lambda checked=False, n=name: self.open_redux_showroom(n))
            actions.addWidget(demo, 1)
            cosmetics = QPushButton("VIEW COSMETICS")
            cosmetics.clicked.connect(
                lambda checked=False, n=name: self.open_cosmetic_garage(n))
            actions.addWidget(cosmetics, 1)
            inner.addLayout(actions)

            activate = QPushButton("APPLY LOOK TO NAMELESS")
            activate.setToolTip("Only changes local NAMELESS previews; ROB RUN stays untouched.")
            activate.clicked.connect(
                lambda checked=False, p=palette, n=name: self.activate_collection_pack(p, n))
            inner.addWidget(activate)
            compatibility = QLabel(
                "CONCEPT ONLY   •   GAME INSTALL NOT AVAILABLE   •   NO GAME FILES CHANGED")
            compatibility.setObjectName("collectionDisclaimer")
            compatibility.setWordWrap(True)
            inner.addWidget(compatibility)
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)
        active = self.settings.value("collection/active", "")
        self.collection_active = QLabel(
            "ACTIVE NAMELESS LOOK  /  " + (active or "NONE SELECTED"))
        self.collection_active.setObjectName("accent")
        layout.addWidget(self.collection_active)
        disclaimer = QLabel(
            "These are design concepts, not downloadable ROB RUN modifications. "
            "Game installation requires verified supported assets and an approved method.")
        disclaimer.setObjectName("muted")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("oceanScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        self.add_page("Redux Collection", scroll)

    def open_redux_showroom(self, name="SAKURA DREAM"):
        """Open a self-contained concept viewer; never interact with game files."""
        dialog = ReduxShowroom(
            self, initial_pack=name,
            reduce_motion=not self.motion_check.isChecked())
        dialog.exec()

    def open_redux_atlas(self):
        """Open all twenty original concept artworks in a single gallery."""
        def open_selected(pack, slot):
            # Open the garage after the atlas closes, avoiding nested modal loops.
            QTimer.singleShot(0, lambda: self.open_cosmetic_garage(pack, slot))

        CosmeticAtlas(self, on_select=open_selected).exec()

    def open_ping_lab(self):
        """Open safe connection diagnostics; no network settings are changed."""
        PingLab(self).exec()

    def open_fps_lab(self):
        """Launch safe performance guidance without changing game or Windows settings."""
        FPSLab(self).exec()

    def open_cosmetic_garage(self, name="SAKURA DREAM", slot=None):
        """Open original cosmetic loadout studio; no ROB RUN asset modification."""
        dialog = CosmeticGarage(self, initial_pack=name, focused=True)
        if slot in ("weapon", "vehicle", "outfit", "mask", "backpack"):
            dialog.category_select.setCurrentIndex(("weapon", "vehicle", "outfit", "mask", "backpack").index(slot))
            dialog.slot_selects[slot].setCurrentText(name)
        dialog.exec()

    def preview_collection_pack(self, palette, name):
        self.palette_combo.setCurrentText(palette)
        self.navigate("Visuals Studio")
        self.statusBar().showMessage(
            name + " selected for preview only; game unchanged", 6000)

    def activate_collection_pack(self, palette, name):
        """One-click local look; never writes to ROB RUN installation."""
        self.palette_combo.setCurrentText(palette)
        self.intensity_slider.setValue(80)
        self.cool_check.setChecked(name == "FROSTBITE")
        effects = {
            "SAKURA DREAM": (12, 104, 115, 28),
            "NEON NIGHT": (-8, 128, 145, -12),
            "FROSTBITE": (6, 114, 82, -28),
            "CRIMSON": (-5, 125, 130, 35),
        }
        values = effects.get(name, (0, 100, 100, 0))
        for key, value in zip(
                ("brightness", "contrast", "saturation", "warmth"), values):
            self.effect_sliders[key].setValue(value)
            self.settings.setValue("effects/" + key, value)
        self.settings.setValue("visual/palette", palette)
        self.settings.setValue("visual/intensity", 80)
        self.settings.setValue("visual/cool", name == "FROSTBITE")
        self.settings.setValue("collection/active", name)
        self.settings.sync()
        self.collection_active.setText("ACTIVE NAMELESS LOOK  /  " + name)
        self.update_effects_preview()
        self.effects_preview.flush_effects()
        QMessageBox.information(
            self, "NAMELESS look activated",
            name + " is active in NAMELESS previews and saved locally.\n\n"
            "ROB RUN files, sky, weapons, bullets and sounds have NOT been modified.")

    def export_collection_pack(self, name, palette):
        """Export a portable NAMELESS-only preset with no game modifications."""
        effects = {
            "SAKURA DREAM": (12, 104, 115, 28),
            "NEON NIGHT": (-8, 128, 145, -12),
            "FROSTBITE": (6, 114, 82, -28),
            "CRIMSON": (-5, 125, 130, 35),
        }
        if name not in effects:
            return
        suggested = name.lower().replace(" ", "-") + ".nameless.json"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export NAMELESS look", suggested, "NAMELESS presets (*.json)")
        if not filename:
            return
        values = effects[name]
        payload = {
            "format": "nameless-redux-look-v1",
            "name": name,
            "game": "ROB RUN",
            "kind": "preview-only",
            "palette": palette,
            "intensity": 80,
            "cool": name == "FROSTBITE",
            "effects": dict(zip(
                ("brightness", "contrast", "saturation", "warmth"), values)),
            "game_files_modified": False,
        }
        try:
            Path(filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage("NAMELESS look exported: " + name, 5000)

    def add_page(self, name, page):
        self.pages[name] = page
        self.stack.addWidget(page)

    def add_slider(self, layout, label, minimum, maximum, value):
        lab = QLabel(f"{label}  •  {value}")
        lab.setObjectName("muted")
        slider = OceanSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(lambda v, x=lab, n=label: x.setText(f"{n}  •  {v}"))
        layout.addWidget(lab)
        layout.addWidget(slider)
        return slider

    def navigate(self, name):
        """Switch pages without an opacity effect on a scroll viewport.

        Qt graphics effects on QScrollArea can leave stale child-widget
        renderings until a hover or another repaint event occurs.
        """
        target = self.pages[name]
        if self.stack.currentWidget() is not target:
            previous = self.stack.currentWidget()
            if previous is not None and previous.graphicsEffect() is not None:
                previous.setGraphicsEffect(None)
            if target.graphicsEffect() is not None:
                target.setGraphicsEffect(None)
            self.stack.setCurrentWidget(target)
            target.updateGeometry()
            target.update()
            if isinstance(target, QScrollArea):
                # A newly opened page must begin at its top, with the thumb
                # at the corresponding topmost position.
                target.verticalScrollBar().setValue(0)
                target.horizontalScrollBar().setValue(0)
                target.viewport().update()
                if target.widget() is not None:
                    target.widget().update()
            self.stack.update()
        self.page_title.setText({
            "Overview": "Dashboard",
            "Visuals Studio": "Visual Lab",
            "Game Center": "Steam Connect",
        }.get(name, name))
        self.statusBar().showMessage("WORKSPACE  /  " + name.upper(), 1600)
        for key in ["redux_collection", "overview", "visuals_studio", "theme_lab", "sound_library", "crosshair_studio", "profiles", "game_center", "settings"]:
            btn = getattr(self, "nav_" + key)
            btn.setChecked(btn.text().endswith(name))
        if name == "Overview":
            self.update_stats()

    def update_stats(self):
        self.stat_values[0].setText(str(len(VISUAL_PACKS) + len(self.custom_visual_packs)))
        self.stat_values[1].setText(str(len(self.profiles)))
        self.stat_values[2].setText(str(len(self.audio_files)))

    def update_swatch(self, *args):
        name = self.palette_combo.currentText()
        color = QColor(PRESETS.get(name, "#087f95"))
        intensity = self.intensity_slider.value() / 100
        if self.cool_check.isChecked():
            color = QColor(int(color.red() * .75), int(color.green() * .9), min(255, int(color.blue() * 1.12)))
        color = QColor(int(7 + (color.red() - 7) * intensity),
                       int(25 + (color.green() - 25) * intensity),
                       int(35 + (color.blue() - 35) * intensity))
        self.visual_swatch.setStyleSheet(
            f"QFrame#swatch {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #071923, stop:1 {color.name()}); border: 1px solid #286071; border-radius: 12px; }}"
        )

    def update_compare(self, value=None):
        self.effects_preview.compare_percent = self.compare_slider.value()
        self.effects_preview.update()

    def toggle_compare(self, *args):
        self.effects_preview.compare_enabled = self.compare_check.isChecked()
        self.compare_slider.setEnabled(self.compare_check.isChecked())
        self.effects_preview.update()

    def apply_theme_colors(self):
        start = QColor(self.theme_colors.get("start", "#11707e"))
        end = QColor(self.theme_colors.get("end", "#0f5386"))
        if not start.isValid() or not end.isValid():
            return
        for w in (self.hero, self.theme_preview):
            w.gradient_start = start
            w.gradient_end = end
            w.update()
        self.centralWidget().findChild(AmbientSurface).gradient_start = start
        self.centralWidget().findChild(AmbientSurface).gradient_end = end
        self.centralWidget().findChild(AmbientSurface).update()

    def pick_theme_color(self, key):
        current = QColor(self.theme_colors.get(key, "#11707e"))
        chosen = QColorDialog.getColor(current, self, "Choose gradient color")
        if chosen.isValid():
            self.theme_colors[key] = chosen.name()
            self.apply_theme_colors()

    def update_motion(self, *args):
        enabled = self.motion_check.isChecked()
        speed = self.motion_speed.value()
        interval = {1: 120, 2: 65, 3: 45, 4: 32, 5: 24}[speed]
        ambient = self.centralWidget().findChild(AmbientSurface)
        for widget in (ambient, self.hero, self.theme_preview):
            clock = getattr(widget, "_clock", None)
            if clock is None:
                continue  # Static premium artwork does not need a repaint timer.
            clock.setInterval(interval)
            if enabled:
                clock.start()
            else:
                clock.stop()
        # Performance option applies to every animated UI element, not just
        # the hero. Inactive pages must not keep repainting in the background.
        for widget_type in (ShimmerText, AuroraCard, ReduxCover):
            for widget in self.findChildren(widget_type):
                clock = widget._motion if isinstance(widget, ReduxCover) else widget._clock
                if enabled:
                    clock.start()
                else:
                    clock.stop()
        self.settings.setValue("theme/motion", enabled)
        self.settings.setValue("theme/speed", speed)

    def save_theme(self):
        self.settings.setValue("theme/colors", json.dumps(self.theme_colors))
        self.settings.setValue("theme/motion", self.motion_check.isChecked())
        self.settings.setValue("theme/speed", self.motion_speed.value())
        self.statusBar().showMessage("Gradient theme saved.", 3000)

    def export_theme(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export theme", "nameless_theme.json", "JSON (*.json)")
        if not path:
            return
        data = {"format": "nameless-theme-v1", "colors": self.theme_colors,
                "motion": self.motion_check.isChecked(), "speed": self.motion_speed.value()}
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def import_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import theme", "", "JSON (*.json)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 64 * 1024:
                raise ValueError("Theme file exceeds 64 KiB.")
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != "nameless-theme-v1":
                raise ValueError("Unsupported theme format.")
            colors = data.get("colors")
            if not isinstance(colors, dict) or any(not isinstance(colors.get(k), str) or
                not __import__('re').fullmatch(r'#[0-9a-fA-F]{6}', colors[k]) for k in ("start", "end")):
                raise ValueError("Invalid theme colors.")
            speed = data.get("speed", 2)
            if type(speed) is not int or not 1 <= speed <= 5 or type(data.get("motion")) is not bool:
                raise ValueError("Invalid animation settings.")
            self.theme_colors = {k: colors[k] for k in ("start", "end")}
            self.motion_check.setChecked(data["motion"])
            self.motion_speed.setValue(speed)
            self.apply_theme_colors()
            self.save_theme()
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def reset_theme(self):
        self.theme_colors = {"start": "#11707e", "end": "#0f5386"}
        self.motion_check.setChecked(True)
        self.motion_speed.setValue(2)
        self.apply_theme_colors()
        self.save_theme()

    def apply_effect_preset(self):
        name = self.effect_preset.currentText()
        values = EFFECT_PRESETS.get(name)
        if values:
            for key, value in values.items():
                self.effect_sliders[key].setValue(value)
            self.effects_timer.stop()
            self.update_effects_preview()

    def update_effects_preview(self):
        values = {key: slider.value() for key, slider in self.effect_sliders.items()}
        self.effects_preview.apply_effects(**values)
        # Every adjustment updates the AFTER half while BEFORE stays original.
        self.effects_preview.flush_effects()

    def save_effects(self):
        for key, slider in self.effect_sliders.items():
            self.settings.setValue("effects/" + key, slider.value())
        self.statusBar().showMessage("Visual effects saved locally.", 3000)

    def reset_effects(self):
        for key, value in {"brightness": 0, "contrast": 100, "saturation": 100, "warmth": 0}.items():
            self.effect_sliders[key].setValue(value)
        self.effects_timer.stop()
        self.update_effects_preview()

    def export_effects_preview(self):
        self.effects_timer.stop()
        self.update_effects_preview()
        self.effects_preview.flush_effects()
        filename, _ = QFileDialog.getSaveFileName(self, "Export preview", "nameless_effects_preview.png", "PNG image (*.png)")
        if filename:
            if not filename.lower().endswith('.png'):
                filename += '.png'
            if self.effects_preview.filtered.save(filename, "PNG"):
                self.statusBar().showMessage("Preview image exported.", 3000)
            else:
                QMessageBox.warning(self, "Export failed", "Could not write the PNG file.")

    def save_visuals(self):
        self.settings.setValue("visual/palette", self.palette_combo.currentText())
        self.settings.setValue("visual/intensity", self.intensity_slider.value())
        self.settings.setValue("visual/cool", self.cool_check.isChecked())
        self.statusBar().showMessage("Visual settings saved locally.", 3000)

    def visual_pack_data(self):
        return {"palette": self.palette_combo.currentText(),
                "intensity": self.intensity_slider.value(),
                "cool": self.cool_check.isChecked()}

    @staticmethod
    def validate_visual_pack(data):
        if not isinstance(data, dict) or data.get("palette") not in PRESETS:
            raise ValueError("Unknown palette in visual pack.")
        intensity = data.get("intensity")
        if type(intensity) is not int or not 0 <= intensity <= 100:
            raise ValueError("Intensity must be between 0 and 100.")
        if type(data.get("cool")) is not bool:
            raise ValueError("Cool-tone option must be true or false.")
        return {"palette": data["palette"], "intensity": intensity, "cool": data["cool"]}

    def refresh_visual_packs(self):
        self.pack_list.clear()
        for name in VISUAL_PACKS:
            item = QListWidgetItem("★  " + name)
            item.setData(Qt.UserRole, ("builtin", name))
            self.pack_list.addItem(item)
        for name in sorted(self.custom_visual_packs):
            item = QListWidgetItem("◆  " + name)
            item.setData(Qt.UserRole, ("custom", name))
            self.pack_list.addItem(item)
        if hasattr(self, "stat_values"):
            self.update_stats()

    def selected_visual_pack(self):
        item = self.pack_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Visual packs", "Select a pack first.")
            return None
        kind, name = item.data(Qt.UserRole)
        return kind, name, (VISUAL_PACKS if kind == "builtin" else self.custom_visual_packs)[name]

    def apply_visual_pack(self):
        selected = self.selected_visual_pack()
        if not selected:
            return
        _, name, pack = selected
        self.palette_combo.setCurrentText(pack["palette"])
        self.intensity_slider.setValue(pack["intensity"])
        self.cool_check.setChecked(pack["cool"])
        self.update_swatch()
        self.save_visuals()
        self.statusBar().showMessage(f"Visual pack '{name}' applied to preview.", 4000)

    def persist_visual_packs(self):
        self.settings.setValue("visual/packs", json.dumps(self.custom_visual_packs, ensure_ascii=False))
        self.refresh_visual_packs()

    def create_visual_pack(self):
        name, ok = QInputDialog.getText(self, "Save visual pack", "Pack name:")
        name = name.strip()
        if not ok or not name:
            return
        if len(name) > 60 or name in VISUAL_PACKS:
            QMessageBox.warning(self, "Invalid name", "Use up to 60 characters and avoid built-in pack names.")
            return
        if name in self.custom_visual_packs and QMessageBox.question(self, "Overwrite pack", f"Replace '{name}'?") != QMessageBox.Yes:
            return
        self.custom_visual_packs[name] = self.visual_pack_data()
        self.persist_visual_packs()

    def delete_visual_pack(self):
        selected = self.selected_visual_pack()
        if not selected:
            return
        kind, name, _ = selected
        if kind == "builtin":
            QMessageBox.information(self, "Built-in pack", "Built-in packs cannot be deleted.")
            return
        if QMessageBox.question(self, "Delete pack", f"Delete '{name}'?") == QMessageBox.Yes:
            del self.custom_visual_packs[name]
            self.persist_visual_packs()

    def export_visual_pack(self):
        selected = self.selected_visual_pack()
        if not selected:
            return
        _, name, data = selected
        filename, _ = QFileDialog.getSaveFileName(self, "Export visual pack", "visual_pack.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps({"format": "nameless-visual-pack-v1", "name": name, "visual": data}, indent=2), encoding="utf-8")
            self.statusBar().showMessage("Visual pack exported.", 4000)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def import_visual_pack(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import visual pack", "", "JSON (*.json)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 100_000:
                raise ValueError("File is too large.")
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj, dict) or obj.get("format") != "nameless-visual-pack-v1":
                raise ValueError("Unsupported visual pack format.")
            name = obj.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 60 or name in VISUAL_PACKS:
                raise ValueError("Invalid or reserved pack name.")
            name = name.strip()
            pack = self.validate_visual_pack(obj.get("visual"))
            if name in self.custom_visual_packs and QMessageBox.question(self, "Overwrite pack", f"Replace '{name}'?") != QMessageBox.Yes:
                return
            self.custom_visual_packs[name] = pack
            self.persist_visual_packs()
            self.statusBar().showMessage("Visual pack imported.", 4000)
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def update_crosshair(self, *args):
        p = self.cross_preview
        p.style_name = self.cross_style.currentText()
        p.color = CROSSHAIR_COLORS[self.cross_color.currentText()]
        p.size = self.cross_size.value()
        p.gap = self.cross_gap.value()
        p.thickness = self.cross_thickness.value()
        p.dot = self.cross_dot.isChecked()
        p.outline = self.cross_outline.isChecked()
        p.update()

    def crosshair_data(self):
        return {
            "style": self.cross_style.currentText(),
            "color": self.cross_color.currentText(),
            "size": self.cross_size.value(),
            "gap": self.cross_gap.value(),
            "thickness": self.cross_thickness.value(),
            "dot": self.cross_dot.isChecked(),
            "outline": self.cross_outline.isChecked(),
        }

    def apply_crosshair_data(self, data):
        self.cross_style.setCurrentText(data.get("style", "Cross"))
        self.cross_color.setCurrentText(data.get("color", "Ocean Cyan"))
        self.cross_size.setValue(int(data.get("size", 22)))
        self.cross_gap.setValue(int(data.get("gap", 6)))
        self.cross_thickness.setValue(int(data.get("thickness", 2)))
        self.cross_dot.setChecked(bool(data.get("dot", False)))
        self.cross_outline.setChecked(bool(data.get("outline", True)))
        self.update_crosshair()

    def save_crosshair(self):
        self.settings.setValue("crosshair", json.dumps(self.crosshair_data(), ensure_ascii=False))
        self.statusBar().showMessage("Crosshair preset saved locally.", 3000)

    def add_audio(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add audio files", "", "Audio (*.wav *.mp3 *.ogg *.flac)")
        for path in files:
            if path not in self.audio_files:
                self.audio_files.append(path)
                self.audio_list.addItem(QListWidgetItem(Path(path).name))
        self.persist_audio_list()
        self.update_stats()

    def persist_audio_list(self):
        self.settings.setValue("audio/files", json.dumps(self.audio_files, ensure_ascii=False))
        self.audio_count_label.setText(f"{len(self.audio_files)} audio files in library")

    def restore_audio_list(self):
        self.audio_list.clear()
        for path in self.audio_files:
            self.audio_list.addItem(Path(path).name)
        self.persist_audio_list()

    def remove_audio(self):
        idx = self.audio_list.currentRow()
        if 0 <= idx < len(self.audio_files):
            self.stop_audio()
            self.audio_files.pop(idx)
            self.audio_list.takeItem(idx)
            self.persist_audio_list()
            self.update_stats()

    def export_crosshair_png(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export crosshair PNG", "nameless_crosshair.png", "PNG Image (*.png)")
        if not filename:
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QPoint
        canvas = QPixmap(256, 256)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        preview = self.cross_preview
        cx = cy = 128
        if preview.outline:
            painter.setPen(QPen(QColor("#001015"), preview.thickness + 2, Qt.SolidLine, Qt.RoundCap))
            preview._draw_shape(painter, cx, cy)
        painter.setPen(QPen(QColor(preview.color), preview.thickness, Qt.SolidLine, Qt.RoundCap))
        preview._draw_shape(painter, cx, cy)
        painter.end()
        if canvas.save(filename, "PNG"):
            self.statusBar().showMessage("Crosshair PNG exported.", 4000)
        else:
            QMessageBox.warning(self, "Export failed", "Could not save PNG file.")

    def export_profiles(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export profiles", "nameless_profiles.json", "JSON (*.json)")
        if not filename:
            return
        try:
            Path(filename).write_text(json.dumps({"format": "nameless-profiles-v1", "profiles": self.profiles}, indent=2, ensure_ascii=False), encoding="utf-8")
            self.statusBar().showMessage("Profiles exported.", 4000)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def import_profiles(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import profiles", "", "JSON (*.json)")
        if not filename:
            return
        try:
            if Path(filename).stat().st_size > 2_000_000:
                raise ValueError("File is too large.")
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != "nameless-profiles-v1":
                raise ValueError("Unsupported profile file format.")
            profiles = data.get("profiles")
            if not isinstance(profiles, dict) or len(profiles) > 500:
                raise ValueError("Invalid profile collection.")
            for name, profile in profiles.items():
                if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(profile, dict):
                    raise ValueError("Invalid profile entry.")
                if not isinstance(profile.get("visual"), dict) or not isinstance(profile.get("crosshair"), dict):
                    raise ValueError("Invalid profile settings.")
            collisions = set(profiles) & set(self.profiles)
            if collisions and QMessageBox.question(self, "Overwrite profiles?", f"Replace {len(collisions)} existing profile(s) with matching names?") != QMessageBox.Yes:
                return
            self.profiles.update(profiles)
            self.settings.setValue("profiles", json.dumps(self.profiles, ensure_ascii=False))
            self.refresh_profiles()
            self.update_stats()
            self.statusBar().showMessage(f"Imported {len(profiles)} profiles.", 4000)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def play_audio(self):
        if not MULTIMEDIA_AVAILABLE or not self.player:
            QMessageBox.information(self, "Playback unavailable", "Qt Multimedia is not available in this Python environment.")
            return
        idx = self.audio_list.currentRow()
        if idx < 0 or idx >= len(self.audio_files):
            return
        self.player.setSource(QUrl.fromLocalFile(self.audio_files[idx]))
        self.player.play()

    def stop_audio(self):
        if self.player:
            self.player.stop()

    def create_profile(self):
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        name = name.strip()
        if not ok or not name:
            return
        self.profiles[name] = {
            "visual": {
                "palette": self.palette_combo.currentText(),
                "intensity": self.intensity_slider.value(),
                "cool": self.cool_check.isChecked(),
            },
            "crosshair": self.crosshair_data(),
            "effects": {key: slider.value() for key, slider in self.effect_sliders.items()},
            "theme": dict(self.theme_colors),
        }
        self.settings.setValue("profiles", json.dumps(self.profiles, ensure_ascii=False))
        self.refresh_profiles()
        self.update_stats()
        self.statusBar().showMessage(f"Profile '{name}' saved.", 3000)

    def load_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        data = self.profiles.get(item.text(), {})
        visual = data.get("visual", {})
        self.palette_combo.setCurrentText(visual.get("palette", "Ocean Deep"))
        self.intensity_slider.setValue(int(visual.get("intensity", 65)))
        self.cool_check.setChecked(bool(visual.get("cool", True)))
        self.apply_crosshair_data(data.get("crosshair", {}))
        effects = data.get("effects", {})
        if isinstance(effects, dict):
            for key, slider in self.effect_sliders.items():
                try:
                    val = int(effects.get(key, slider.value()))
                    slider.setValue(max(slider.minimum(), min(slider.maximum(), val)))
                except (ValueError, TypeError):
                    pass
        theme = data.get("theme", {})
        if isinstance(theme, dict) and all(isinstance(theme.get(k), str) and
            __import__('re').fullmatch(r'#[0-9a-fA-F]{6}', theme[k]) for k in ("start", "end")):
            self.theme_colors = {k: theme[k] for k in ("start", "end")}
            self.apply_theme_colors()
        self.update_swatch()
        self.statusBar().showMessage(f"Profile '{item.text()}' loaded.", 3000)

    def delete_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        self.profiles.pop(item.text(), None)
        self.settings.setValue("profiles", json.dumps(self.profiles, ensure_ascii=False))
        self.refresh_profiles()
        self.update_stats()

    def refresh_profiles(self):
        if not hasattr(self, "profile_list"):
            return
        self.profile_list.clear()
        for name in sorted(self.profiles):
            self.profile_list.addItem(name)

    def read_json_setting(self, key, default):
        raw = self.settings.value(key, "")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                value = json.loads(raw)
                return value if isinstance(value, type(default)) else default
            except (json.JSONDecodeError, TypeError):
                return default
        return default

    def load_settings(self):
        self.game_path_input.setText(str(self.settings.value("game/folder", "")))
        self.motion_check.setChecked(self.settings.value("theme/motion", True, type=bool))
        try:
            speed = int(self.settings.value("theme/speed", 2))
        except (TypeError, ValueError):
            speed = 2
        self.motion_speed.setValue(max(1, min(5, speed)))
        self.update_motion()
        self.palette_combo.setCurrentText(self.settings.value("visual/palette", "Ocean Deep"))
        self.intensity_slider.setValue(int(self.settings.value("visual/intensity", 65)))
        self.cool_check.setChecked(self.settings.value("visual/cool", True, type=bool))
        cross = self.read_json_setting("crosshair", {})
        if isinstance(cross, dict):
            self.apply_crosshair_data(cross)
        self.update_swatch()
        self.update_crosshair()
        defaults = {"brightness": 0, "contrast": 100, "saturation": 100, "warmth": 0}
        for key, default in defaults.items():
            slider = self.effect_sliders[key]
            try:
                saved = int(self.settings.value("effects/" + key, default))
            except (ValueError, TypeError):
                saved = default
            slider.setValue(max(slider.minimum(), min(slider.maximum(), saved)))
        self.effects_timer.stop()
        self.update_effects_preview()

    def reset_settings(self):
        answer = QMessageBox.question(self, "Reset preferences", "Reset saved visual, crosshair and profile settings?")
        if answer == QMessageBox.Yes:
            self.settings.clear()
            self.reset_effects()
            self.game_path_input.clear()
            self.game_report_view.clear()
            self.game_report = None
            self.game_status.setText("No folder scanned yet.")
            self.compatibility_label.setText("Run SCAN FOLDER to inspect engine clues.")
            self.compatibility_evidence.clear()
            self.audio_files = []
            self.restore_audio_list()
            self.profiles = {}
            self.custom_visual_packs = {}
            self.reset_theme()
            self.refresh_visual_packs()
            self.refresh_profiles()
            self.palette_combo.setCurrentText("Ocean Deep")
            self.intensity_slider.setValue(65)
            self.cool_check.setChecked(True)
            self.apply_crosshair_data({})
            self.update_swatch()
            self.update_stats()
            self.collection_active.setText("ACTIVE NAMELESS LOOK  /  NONE SELECTED")
            # Reset must not retain a previously selected custom image.
            self._preview_request_id = getattr(self, "_preview_request_id", 0) + 1
            self.load_initial_screenshot()
            self.settings.sync()
            self.statusBar().showMessage("Preferences reset.", 3000)

    def apply_style(self):
        """ROB RUN-inspired editorial minimalism: graphite, bone, restrained signal orange."""
        self.setStyleSheet("""
            QMainWindow, QWidget, QWidget#root, QWidget#pageStack, QStackedWidget,
            QScrollArea, QScrollArea#oceanScroll, QWidget#oceanViewport,
            QScrollArea > QWidget > QWidget {
                background-color: #101427; color: #F4F5FF;
                font-family: 'Segoe UI'; font-size: 12px;
            }
            QWidget#contentSurface { background: transparent; }
            QFrame#sidebar {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1F2448,stop:.55 #201B45,stop:1 #10243B);
                border-right: 2px solid #7974D0;
            }
            QLabel { background: transparent; color: #F1F0EC; }
            QLabel#navSection {
                color: #77777D; font-size: 9px; font-weight: 700;
                letter-spacing: 2px; padding-left: 12px;
            }
            QFrame#headerRule {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6B9FFF,stop:.55 #D78DFF,stop:1 #60E3E9);
                border: none;
            }
            QWidget#visualCanvas {
                background-color: #101114; border: 1px solid #3B3B40;
                border-radius: 12px;
            }
            QPushButton#primaryAction {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #9E83FF,stop:.55 #E9A0EA,stop:1 #76D8F9);
                color: #141329; border: 1px solid #D8BAFF; font-weight: 900;
            }
            QPushButton#primaryAction:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #C3ADFF,stop:1 #A0ECFF);
                border-color: #FFFFFF;
            }
            QPushButton#primaryAction[gameRunning="true"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2DDC96,stop:1 #7BF4B0);
                color: #082E22; border: 2px solid #A9FFD5;
            }
            QPushButton#primaryAction[gameRunning="true"]:hover {
                background: #A2FFD2; border-color: #FFFFFF;
            }
            QLabel#status { color: #9CA9E9; font-size: 11px; font-weight: 800; }
            QLabel#brand { color: #FAF8F3; font-size: 19px; font-weight: 800; letter-spacing: 3px; }
            QLabel#subbrand { color: #B7A0FF; font-size: 9px; letter-spacing: 1px; }
            QLabel#version { color: #77777A; font-size: 10px; }
            QLabel#pageTitle { color: #F8F7F4; font-size: 29px; font-weight: 700; }

            QLabel#sectionTitle { color: #F4F2EF; font-size: 21px; font-weight: 700; }
            QLabel#cardTitle { color: #D6D2CD; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            QLabel#previewSource {
                color: #B5A69B; font-size: 11px; padding: 8px 2px;
            }
            QLabel#muted { color: #99999D; font-size: 12px; }
            QLabel#accent { color: #D8AFFF; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#stat { color: #F7F2FF; font-size: 36px; font-weight: 800; }
            QLabel#collectionEyebrow {
                color: #B7A5E7; font-size: 10px; font-weight: 800; letter-spacing: 1px;
            }
            QLabel#collectionHeadline {
                color: #FFFFFF; font-size: 24px; font-weight: 900; letter-spacing: 1px;
            }
            QLabel#collectionMood { color: #D5D3E8; font-size: 12px; }
            QLabel#collectionDisclaimer { color: #8C91AE; font-size: 10px; }

            QLabel#heroHeadline { color: #FFFFFF; font-size: 43px; font-weight: 900; letter-spacing: 1px; }
            QLabel#heroDescription { color: #E2DDF7; font-size: 12px; line-height: 1.4; }
            QFrame#card { background: transparent; border: 0px; }
            QFrame#statCard { background: #202542; border: 1px solid #777BC3; border-radius: 13px; }
            QFrame#statCard:hover { border-color: #E3B3FF; background: #292D50; }
            QFrame#heroCard { background: transparent; border: 0px; }
            QPushButton#nav {
                background: transparent; color: #C4C6E6; text-align: left;
                padding: 14px 15px; border: 0; border-radius: 10px;
                font-size: 12px; font-weight: 800;
            }
            QPushButton#nav:hover { background: #353A70; color: #FFFFFF; }
            QPushButton#nav:checked {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #564D9C,stop:1 #2C416D);
                color: #FFFFFF; border-left: 3px solid #C7A7FF; font-weight: 900;
            }
            QPushButton {
                background-color: #30385C; color: #FFFFFF;
                border: 1px solid #6371A5; border-radius: 10px;
                padding: 11px 16px; font-size: 12px; font-weight: 900;
            }
            QPushButton:hover { background-color: #5559A0; border-color: #BDA5FF; }
            QPushButton:pressed { background-color: #765DB3; }
            QPushButton:disabled { color: #77777A; background: #1D1E21; border-color: #303136; }
            QComboBox, QLineEdit, QListWidget {
                background-color: #111215; color: #F0EEEB;
                border: 1px solid #38393E; border-radius: 8px; padding: 10px;
                selection-background-color: #71472E;
            }
            QComboBox:hover, QLineEdit:focus, QListWidget:focus { border-color: #D99360; }
            QComboBox QAbstractItemView {
                background-color: #202125; color: #F4F2EF;
                selection-background-color: #65442F;
            }
            QSlider { background: transparent; }
            QSlider::groove:horizontal { height: 5px; background: #3A3B3E; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #D99565; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #F5D2B4; width: 16px; margin: -6px 0;
                border: 2px solid #C58254; border-radius: 8px;
            }
            QSlider::handle:horizontal:hover { background: #FFFFFF; }
            OceanToggle { color: #D6D2CD; background: transparent; font-size: 12px; }
            QProgressBar {
                background: #202125; border: 1px solid #44454A;
                border-radius: 5px; color: #F2EEE8; text-align: center;
            }
            QProgressBar::chunk { background: #D99565; border-radius: 4px; }
            QStatusBar { background-color: #111215; color: #D5A27F; }
            QScrollBar:vertical { background: #222743; width: 13px; margin: 0; border: 0; }
            QScrollBar::handle:vertical { background: #F5F7FF; border-radius: 6px; min-height: 48px; margin: 1px 2px; }
            QScrollBar::handle:vertical:hover { background: #FFFFFF; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QToolTip {
                background: #25262A; color: #FAF7F2;
                border: 1px solid #665042; padding: 6px;
            }
        """)
        from PySide6.QtGui import QPalette
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor('#0C0D0F'))
        palette.setColor(QPalette.Base, QColor('#111215'))
        palette.setColor(QPalette.AlternateBase, QColor('#202125'))
        palette.setColor(QPalette.WindowText, QColor('#F1F0EC'))
        palette.setColor(QPalette.Text, QColor('#F1F0EC'))
        self.setPalette(palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    splash = startup_splash()
    app.processEvents()
    window = ReduxWindow()
    window.setWindowIcon(app_icon())
    window.show()
    splash.finish(window)
    sys.exit(app.exec())
