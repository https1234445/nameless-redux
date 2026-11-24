# NAMELESS REDUX — ROB RUN Edition

NAMELESS is a desktop catalog of curated visual **concepts** for ROB RUN. The main screen is **Redux Collection**, with Sakura Dream, Neon Night, Frostbite, and Crimson.

## Current features

- Browse four themed concepts and preview their color direction in Visual Lab.
- **ACTIVATE IN NAMELESS** applies a complete set of local preview settings with one click and remembers the selected look.
- **EXPORT LOOK** writes a portable `.json` preset describing the NAMELESS look (not game assets).
- Compare a real ROB RUN screenshot using before/after visual adjustments. The app attempts to load an official Steam screenshot or lets you select your own.
- Steam Connect discovers the installed game, shows a best-effort running status, and launches it through Steam.
- Existing Theme Lab, Sound Library, Crosshair Studio, Profiles, and settings remain available.

### Important limitations

**NAMELESS does not currently install game modifications.** Pink skies, sakura weapon textures, flower bullet particles, and replacement sounds are planned **game-content packs**, not implemented features. The current presets affect only NAMELESS previews. A real one-click installer requires legally distributable assets, a verified compatible game modification mechanism, safe backups, and restore/uninstall support. No files in ROB RUN are modified by these presets.

The catalog's colored art panels are concept visuals, **not actual gameplay screenshots**.

## Windows build and release

1. Go to **Actions → Windows release → Run workflow** to build a test artifact without publishing a release. The workflow now runs a syntax check and headless Qt UI smoke test before building.
2. Download the resulting workflow artifact and test `NAMELESS REDUX.exe` on Windows: navigate all nine pages, select/activate/export a look, open Visual Lab, and test Steam Connect.
3. **Only after testing**, create a GitHub Release with a new higher `v*` tag. The tag triggers the workflow to publish the application ZIP, checksum, and launcher executable.
4. The existing `NAMELESS Launcher.exe` downloads the newest published release when run. Committing to `main` alone **does not** update installed launcher users.

Do not publish an untested development build as a stable release.

## Development

```bash
python -m pip install PySide6 numpy
python -m py_compile app/nameless_redux.py launcher.py
QT_QPA_PLATFORM=offscreen python tests/smoke_ui.py
```

Windows GitHub Actions runs the above checks automatically.
