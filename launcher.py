"""NAMELESS REDUX: GitHub Releases update launcher (stdlib only)."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from tkinter import Tk, Label, Button, StringVar, messagebox

API = 'https://api.github.com/repos/https1234445/nameless-redux/releases/latest'
ZIP_NAME = 'nameless-redux-app.zip'
HASH_NAME = ZIP_NAME + '.sha256'
EXE = 'NAMELESS REDUX.exe'
ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'NAMELESS REDUX'
VERSIONS = ROOT / 'versions'
HEADERS = {'User-Agent': 'NAMELESS-Launcher/1.0', 'Accept': 'application/vnd.github+json'}

def fetch(url, limit=128*1024):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Metadata too large')
    return data

def download(url, target):
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as resp, open(target, 'wb') as f:
        while chunk := resp.read(1024 * 1024):
            total += len(chunk)
            if total > 500 * 1024 * 1024:
                raise ValueError('Update exceeds size limit')
            digest.update(chunk)
            f.write(chunk)
    return digest.hexdigest()

def local_versions():
    if not VERSIONS.exists():
        return []
    return sorted((p for p in VERSIONS.iterdir() if (p / EXE).is_file()), key=lambda p: p.stat().st_mtime, reverse=True)

def install(release, status):
    tag = release['tag_name']
    if not tag or len(tag) > 60 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in tag):
        raise ValueError('Unsafe release tag')
    assets = {a['name']: a['browser_download_url'] for a in release['assets']}
    if ZIP_NAME not in assets or HASH_NAME not in assets:
        raise ValueError('Release missing ZIP or checksum')
    dest = VERSIONS / tag
    if (dest / EXE).is_file():
        return dest / EXE
    VERSIONS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='redux-', dir=ROOT) as temp:
        temp = Path(temp)
        expected = fetch(assets[HASH_NAME]).decode('ascii').split()[0].lower()
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Invalid checksum')
        status('Downloading ' + tag + '…')
        archive_path = temp / ZIP_NAME
        actual = download(assets[ZIP_NAME], archive_path)
        if actual != expected:
            raise ValueError('SHA256 mismatch: update rejected')
        status('Installing verified update…')
        stage = temp / 'app'
        stage.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != EXE or members[0].file_size > 500*1024*1024:
                raise ValueError('Unexpected ZIP structure')
            with archive.open(members[0]) as src, open(stage / EXE, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        if dest.exists():
            shutil.rmtree(dest)
        stage.rename(dest)
    return dest / EXE

def main():
    root = Tk()
    root.title('NAMELESS REDUX · Launcher')
    root.geometry('470x255')
    root.configure(bg='#071923')
    root.resizable(False, False)
    status_text = StringVar(value='Ready to check for updates')
    Label(root, text='NAMELESS REDUX', font=('Segoe UI', 22, 'bold'), bg='#071923', fg='#7cf9e6').pack(pady=(25, 6))
    Label(root, text='OCEAN EDITION · UPDATE CENTER', font=('Segoe UI', 10), bg='#071923', fg='#8db7c3').pack()
    Label(root, textvariable=status_text, font=('Segoe UI', 10), bg='#071923', fg='#d7f4f4', wraplength=430).pack(pady=23)
    def status(value):
        root.after(0, lambda: status_text.set(value))
    def worker():
        try:
            status('Checking GitHub Releases…')
            release = json.loads(fetch(API).decode('utf-8'))
            app = install(release, status)
            root.after(0, lambda: (subprocess.Popen([str(app)], cwd=str(app.parent)), root.destroy()))
        except Exception as error:
            installed = local_versions()
            if installed:
                app = installed[0] / EXE
                status('Offline or update unavailable — starting installed version')
                root.after(0, lambda: (subprocess.Popen([str(app)], cwd=str(app.parent)), root.destroy()))
            else:
                msg = 'No published release yet' if isinstance(error, urllib.error.HTTPError) and error.code == 404 else str(error)
                status('Cannot launch: ' + msg)
                root.after(0, lambda: (messagebox.showerror('NAMELESS REDUX', msg), button.config(state='normal')))
    def check():
        button.config(state='disabled')
        threading.Thread(target=worker, daemon=True).start()
    button = Button(root, text='CHECK & LAUNCH', command=check, font=('Segoe UI', 11, 'bold'), bg='#1a6870', fg='white', relief='flat', padx=25, pady=10)
    button.pack()
    root.mainloop()

if __name__ == '__main__':
    main()
