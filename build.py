"""Build the Windows executable with PyInstaller.

Usage:  python build.py

If the ``BMC_MIS_GH_TOKEN`` and ``BMC_MIS_GH_REPO`` environment variables are
set, the in-app updater is wired up by writing ``app/_secrets.py`` from those
values before PyInstaller runs. CI (``.github/workflows/release.yml``) sets
them from repo secrets. Builds without the env vars still work — the updater
just stays disabled.

Produces a one-folder application under ``dist/BMC MIS/`` containing
``BMC MIS.exe``.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECRETS_PATH = ROOT / "app" / "_secrets.py"


def _write_secrets() -> bool:
    token = os.environ.get("BMC_MIS_GH_TOKEN", "").strip()
    repo = os.environ.get("BMC_MIS_GH_REPO", "").strip()
    if not (token and repo):
        print("Note: BMC_MIS_GH_TOKEN / BMC_MIS_GH_REPO not set — "
              "auto-updater will be disabled in this build.")
        return False
    SECRETS_PATH.write_text(
        '"""Auto-updater credentials — written at build time, gitignored."""\n'
        f'GITHUB_TOKEN = "{token}"\n'
        f'GITHUB_REPO = "{repo}"\n',
        encoding="utf-8",
    )
    print(f"Wrote {SECRETS_PATH} (repo: {repo}).")
    return True


def main() -> int:
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed.  Run:  pip install pyinstaller")
        return 1

    _write_secrets()

    for folder in ("build", "dist"):
        target = ROOT / folder
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    args = [
        "run.py",
        "--name", "BMC MIS",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--noupx",
    ]
    # Bundle read-only assets (the vendored Chart.js the HTML dashboard
    # inlines, plus the icon). Resolved at runtime via config.resource_path
    # (sys._MEIPASS). PyInstaller wants SRC<os.pathsep>DEST.
    assets = ROOT / "app" / "assets"
    if assets.exists():
        args += ["--add-data", f"{assets}{os.pathsep}app/assets"]
    icon = assets / "icon.ico"
    if icon.exists():
        args += ["--icon", str(icon)]

    import PyInstaller.__main__ as pyi
    pyi.run(args)

    exe = ROOT / "dist" / "BMC MIS" / "BMC MIS.exe"
    if exe.exists():
        print(f"\nBuild complete:  {exe}")
        return 0
    print("\nBuild finished but the executable was not found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
