# NAMELESS REDUX — Ocean Edition

## First-time setup

1. Upload all files and folders from this starter package to the **root** of `https1234445/nameless-redux`, preserving `.github/workflows/windows-release.yml` and `app/nameless_redux.py`.
2. Open **Actions → Windows release → Run workflow** to test a Windows build. A successful run produces downloadable artifacts, but does not publish a Release.
3. To publish the first version, create a GitHub Release with tag `v1.5.1` (GitHub will create the tag). The workflow triggered by the tag builds the Windows app and uploads the release assets automatically. If the Release is created before the workflow completes, wait for the workflow to upload the assets.
4. Download `NAMELESS Launcher.exe` from the Release **once**. Keep it in a convenient folder. Future app versions are fetched from GitHub Releases when launched.

### How updates work

Publish a new GitHub Release with a higher tag (`v1.5.2`, etc.) after updating `app/nameless_redux.py`. The launcher downloads the latest release ZIP, checks its SHA256, extracts the application into `%LOCALAPPDATA%\NAMELESS REDUX\versions\<tag>` and starts it. Previous versions remain for offline fallback.

**Limitations:** the initial Windows `.exe` must be built by GitHub Actions; local syntax checks are not Windows GUI runtime tests. The launcher trusts release assets in this repository, so secure your GitHub account with 2FA. This application does not modify ROB RUN itself.
