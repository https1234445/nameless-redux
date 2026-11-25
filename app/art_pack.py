"""Safely import user-selected concept images without touching ROB RUN files."""
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage

ART_NAMES = ('sakura_dream.jpg', 'neon_night.jpg', 'frostbite.jpg',
             'crimson.jpg', 'rob_run_preview.jpg')


def art_directory():
    return Path(QStandardPaths.writableLocation(
        QStandardPaths.AppLocalDataLocation)) / 'concept_art'


def art_candidates(filename):
    import sys
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    exe_dir = (Path(sys.executable).resolve().parent if getattr(
        sys, 'frozen', False) else Path(__file__).resolve().parent)
    return (art_directory() / filename, base / 'assets' / filename,
            exe_dir / 'assets' / filename)


def import_art_pack(archive):
    """Accept only known JPEG files; validate image data before committing."""
    target = art_directory()
    staged = {}
    try:
        with ZipFile(archive) as z:
            for filename in ART_NAMES:
                name = 'assets/' + filename
                if name not in z.namelist():
                    continue
                info = z.getinfo(name)
                if info.file_size > 8 * 1024 * 1024:
                    raise ValueError('Image exceeds 8 MiB: ' + filename)
                data = z.read(info)
                if len(data) > 8 * 1024 * 1024:
                    raise ValueError('Image exceeds 8 MiB: ' + filename)
                image = QImage.fromData(data)
                if image.isNull() or image.width() * image.height() > 24000000:
                    raise ValueError('Invalid image: ' + filename)
                staged[filename] = data
    except (BadZipFile, OSError) as exc:
        raise ValueError('Invalid or unreadable art pack') from exc
    if len(staged) < 4 or any(n not in staged for n in ART_NAMES[:4]):
        raise ValueError('The art pack must contain all four REDUX themes')
    target.mkdir(parents=True, exist_ok=True)
    for filename, data in staged.items():
        temporary = target / (filename + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(target / filename)
    return len(staged)
