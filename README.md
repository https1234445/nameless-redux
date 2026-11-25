# NAMELESS REDUX — ROB RUN Edition

NAMELESS is a desktop catalog of curated visual **concepts** for ROB RUN. The main screen is **Redux Collection**, with Sakura Dream, Neon Night, Frostbite, and Crimson.

## Premium showcase direction (3.11 DEV)

The Overview now opens with an original cinematic neon-city hero, an illustrated concept vehicle, large editorial headline and direct entry points into the interactive REDUX worlds and cosmetic garage. The artwork is drawn locally by Qt rather than fetched from external services or ROB RUN assets. It is static for low idle CPU/GPU overhead. The REDUX Collection now also uses cinematic cover art, editorial collection titles, compact category metadata and direct world/cosmetic actions. This is an evolving original design, not a pixel-identical reproduction of any reference image.

## REDUX Concept Atlas (3.12 DEV)

A full browseable gallery of **all 20 original cosmetic concepts**, organized by the four REDUX worlds and five cosmetic categories. Each concept opens its exact pack and category in Cosmetic Garage. The gallery can also export a **2400 × 2920 PNG presentation board** suitable for sharing the NAMELESS concept with collaborators or developers. All artwork is rendered locally with Qt, without external image downloads or access to ROB RUN game files. Atlas rendering and navigation have dedicated offscreen Windows CI coverage.

## Current features

- Browse four themed concepts and preview their color direction in Visual Lab.
- **LIVE REDUX SHOWROOM:** open a fully original interactive 16:9 scene for Sakura Dream, Neon Night, Frostbite or Crimson. Each scene has distinctive vector-drawn sky/environment, a concept weapon finish, animated ambient effects, and mouse-triggered impact particles. Try a synthesized original shot sound, toggle motion/audio, and export concept artwork as PNG. This runs only inside NAMELESS and never touches ROB RUN files.
- **COSMETIC GARAGE:** 20 original vector cosmetic concepts across four worlds and five slots (weapons, vehicles, outfits, masks, backpacks). Compose a mixed cosmetic look by selecting a different theme per slot; all five selections persist across app sessions. Inspect every item, export a PNG concept or a shareable NAMELESS-only JSON loadout, and import a saved loadout. Malformed stored loadouts are safely discarded. The JSON format explicitly identifies previews and never contains a game installation action.
- **ACTIVATE IN NAMELESS** applies a complete set of local preview settings with one click and remembers the selected look.
- **EXPORT LOOK** writes a portable `.json` preset describing the NAMELESS look (not game assets).
- Compare a real ROB RUN screenshot using before/after visual adjustments. The app attempts to load an official Steam screenshot or lets you select your own.
- Steam Connect discovers the installed game, shows a best-effort running status, and launches it through Steam.
- Existing Theme Lab, Sound Library, Crosshair Studio, Profiles, and settings remain available.

## REDUX pack vision and categories

A REDUX is a curated **whole-game appearance pack**, not just a color filter. The intended catalog spans:

- **World and atmosphere:** skies, environments, scenery, particles and ambient effects.
- **Weapons and projectiles:** weapon skins, muzzle/projectile visuals, themed effects.
- **Vehicles:** car skins, colors, decorations and cosmetic details (original NAMELESS concept preview available in Cosmetic Garage).
- **Characters:** player skins and character appearance.
- **Outfits:** costumes, clothing and wearable cosmetics.
- **Accessories:** bags, masks and other cosmetic items.
- **Audio:** sound effects and themed soundscapes.

Users should be able to browse complete themed collections **or individual categories**, inspect preview images and included components, and install a compatible pack with one action. A pack manifest should declare its supported game version, component categories, asset provenance, compatibility requirements, installation strategy and rollback details. Installation must never be offered until the relevant game resources and modification rights are verified.

**Sakura Dream** is one example, not the definition of a REDUX. The same structure should accommodate many visual styles and independent item packs.

## Performance-first REDUX design

The priority is **high and stable FPS**, not maximal visual complexity. Future game-compatible REDUX packs should provide a performance profile with bounded texture resolution and memory usage, efficient materials, restrained particle counts, and no unnecessary background processing. The NAMELESS UI animations must not run inside the game process.

An FPS increase **cannot be guaranteed**: changing cosmetics may have no effect or may reduce performance, depending on the engine, GPU, game settings and the asset. Claims of improved FPS require controlled before/after measurements on the same scene and hardware, including average FPS and 1% lows. Until supported modding and benchmarking exist, the gallery makes no performance improvement claims.

### Important limitations

**NAMELESS does not currently install game modifications.** Pink skies, sakura weapon textures, flower bullet particles, and replacement sounds are planned **game-content packs**, not implemented features. The current presets affect only NAMELESS previews. A real one-click installer requires legally distributable assets, a verified compatible game modification mechanism, safe backups, and restore/uninstall support. No files in ROB RUN are modified by these presets.

The catalog's colored art panels and the interactive showroom scenes are **original concept illustrations, not actual ROB RUN gameplay screenshots**. The showroom simulates weapon and impact cosmetics in its own Qt canvas and does not modify or load game assets. It deliberately limits each impact burst to 8–12 particles with a short lifetime, and stops animation while hidden. It does not establish or claim any ROB RUN FPS improvement.

## Windows build and release

1. Every push to `main` now **automatically** runs the Windows build, syntax check, and headless Qt UI smoke test. No manual workflow launch is needed. The result is an Actions artifact, **not** a published release.
2. Before the first public release, validate the latest green Actions build on Windows: navigate all nine pages, select/activate/export a look, open Visual Lab, and test Steam Connect. Automated UI smoke tests do not replace final real-desktop verification.
3. **Only after testing**, create a GitHub Release with a new higher `v*` tag. The tag triggers the workflow to publish the application ZIP, checksum, and launcher executable. The current development source is not a stable game-mod installer.
4. The existing `NAMELESS Launcher.exe` downloads the newest published release when run. Committing to `main` alone **does not** update installed launcher users.

Do not publish an untested development build as a stable release.

## Development

```bash
python -m pip install PySide6 numpy
python -m py_compile app/nameless_redux.py app/redux_showroom.py app/redux_armory.py launcher.py
python tests/validate_packs.py
QT_QPA_PLATFORM=offscreen python tests/smoke_ui.py
QT_QPA_PLATFORM=offscreen python tests/showroom_smoke.py
QT_QPA_PLATFORM=offscreen python tests/garage_smoke.py
```

Windows GitHub Actions runs the above checks automatically.
