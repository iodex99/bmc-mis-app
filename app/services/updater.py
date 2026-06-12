"""In-app updater — checks GitHub Releases, downloads and applies new builds.

The user's data (under ``%LOCALAPPDATA%\\BMC MIS``) is never touched. Only the
contents of the install folder are replaced.

Secrets
-------
:mod:`app._secrets` (gitignored) holds ``GITHUB_TOKEN`` and ``GITHUB_REPO``.
The module imports them with a fallback so source/dev runs simply have updates
disabled. The file is created at build time from environment variables.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from .. import __version__
from ..database import transaction

try:
    from .._secrets import GITHUB_TOKEN, GITHUB_REPO  # type: ignore[attr-defined]
except ImportError:                                    # source/dev runs
    GITHUB_TOKEN = ""
    GITHUB_REPO = ""

UPDATES_ENABLED = bool(GITHUB_TOKEN and GITHUB_REPO)
_API = "https://api.github.com"
_TIMEOUT_CHECK = 15
_TIMEOUT_DOWNLOAD = 300

AUTO_CHECK_KEY = "auto_check_updates"


@dataclass
class UpdateInfo:
    """Details of an available release."""
    version: str
    notes: str
    asset_url: str
    asset_name: str


# --- version helpers ---------------------------------------------------------

def current_version() -> str:
    return __version__


def _parse(tag: str) -> tuple[int, ...]:
    parts = tag.lstrip("vV").split("-", 1)[0].split(".")
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            break
    return tuple(out) or (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


# --- preferences -------------------------------------------------------------

def auto_check_enabled() -> bool:
    """Whether the app should silently look for updates at launch."""
    if not UPDATES_ENABLED:
        return False
    with transaction() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (AUTO_CHECK_KEY,)).fetchone()
    return (row["value"] != "0") if row else True


def set_auto_check(enabled: bool) -> None:
    with transaction() as conn:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (AUTO_CHECK_KEY, "1" if enabled else "0"))


# --- check -------------------------------------------------------------------

def _headers(accept: str = "application/vnd.github+json") -> dict:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bmc-mis-updater",
    }


def check_latest() -> UpdateInfo | None:
    """Hit the GitHub Releases API; return UpdateInfo if newer, else None.

    Lists releases (rather than relying on ``/releases/latest``) so the check
    works even when no release is flagged as "latest" on GitHub.
    """
    if not UPDATES_ENABLED:
        return None
    url = f"{_API}/repos/{GITHUB_REPO}/releases?per_page=30"
    r = requests.get(url, headers=_headers(), timeout=_TIMEOUT_CHECK)
    r.raise_for_status()

    best = None
    best_ver: tuple[int, ...] = ()
    for rel in (r.json() or []):
        if rel.get("draft") or rel.get("prerelease"):
            continue
        tag = (rel.get("tag_name") or "").lstrip("v")
        if not tag:
            continue
        ver = _parse(tag)
        if ver > best_ver:
            best_ver, best = ver, rel
    if best is None:
        return None
    tag = (best.get("tag_name") or "").lstrip("v")
    if not _is_newer(tag, current_version()):
        return None
    asset = next((a for a in best.get("assets", [])
                  if a["name"].lower().endswith(".zip")), None)
    if not asset:
        return None
    return UpdateInfo(
        version=tag,
        notes=best.get("body", "") or "",
        asset_url=asset["url"],
        asset_name=asset["name"],
    )


# --- install -----------------------------------------------------------------

def _install_dir() -> Path:
    """Folder housing the running executable (PyInstaller one-folder build)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    raise RuntimeError("Updates can only be applied to an installed build.")


def download_update(info: UpdateInfo, progress=None) -> Path:
    """Download the release zip; return the path to the extracted folder."""
    tmp = Path(tempfile.mkdtemp(prefix="bmc_mis_update_"))
    zip_path = tmp / info.asset_name
    with requests.get(info.asset_url,
                      headers=_headers("application/octet-stream"),
                      timeout=_TIMEOUT_DOWNLOAD, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(64 * 1024):
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total)
    new_dir = tmp / "new"
    new_dir.mkdir()
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(new_dir)
    # If the zip contained the "BMC MIS" folder rather than its contents,
    # collapse one level so robocopy mirrors the right thing.
    children = list(new_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        new_dir = children[0]
    return new_dir


def build_helper_script(new_dir: Path, install_dir: Path, pid: int) -> str:
    """Compose the update-helper batch script (separate for testability).

    Design constraints learned in the field:

    * **Every external tool is fully qualified** to
      ``%SystemRoot%\\System32`` — a bare ``find`` resolves through
      PATH, and on any machine with Git-for-Windows / MSYS installed
      GNU ``find`` shadows the Windows one, silently breaking the PID
      wait. Same precaution for tasklist / ping / robocopy.
    * **Sleep with ``ping``, never ``timeout``** — ``timeout /t`` exits
      immediately ("Input redirection is not supported") when stdin is
      redirected, which it always is for our hidden helper. ``ping -n
      N 127.0.0.1`` sleeps N−1 seconds and needs no console input.
    * **The PID wait is BOUNDED** (~120 s). If the app somehow never
      exits (or the PID gets recycled), the helper logs it and moves
      on — robocopy's own /R retries cover a briefly-locked exe. The
      old unbounded loop could spin forever, which the operator saw
      as a stuck console they had to Ctrl+C.
    * **Purge is restricted to the app's own ``_internal`` payload.**
      The user's database lives in ``%LOCALAPPDATA%\\BMC MIS`` and is
      never touched at all — but pre-v0.3.71 the single ``/MIR`` over
      the whole install folder would also have DELETED any stray file
      the operator kept next to the exe (a saved MIS workbook, a
      Tally export, notes…). Now only ``_internal`` is mirrored with
      purge (it holds nothing but our own build output); the install
      ROOT is copied with ``/E`` — overwrite ours, never delete
      theirs.
    * Every phase appends to ``update.log`` in the install folder so
      failures are debuggable after the fact.
    """
    log_file = install_dir / "update.log"
    exe_path = install_dir / "BMC MIS.exe"
    sys32 = r"%SystemRoot%\System32"
    rcopy = f'"{sys32}\\robocopy.exe"'
    if (new_dir / "_internal").is_dir():
        # PyInstaller 6 one-folder layout: exe at root + _internal payload.
        copy_cmds = [
            f'>> "{log_file}" echo Mirroring _internal (with purge)...',
            f'{rcopy} "{new_dir}\\_internal" "{install_dir}\\_internal" '
            f'/MIR /R:5 /W:2 >> "{log_file}" 2>&1',
            f'>> "{log_file}" echo _internal mirror returned %ERRORLEVEL%',
            f'>> "{log_file}" echo Copying root files (no purge)...',
            f'{rcopy} "{new_dir}" "{install_dir}" /E /R:5 /W:2 '
            f'/XD "{new_dir}\\_internal" /XF "{log_file.name}" '
            f'>> "{log_file}" 2>&1',
            f'>> "{log_file}" echo Root copy returned %ERRORLEVEL%',
        ]
    else:
        # Unexpected build layout — copy everything, purge NOTHING.
        copy_cmds = [
            f'>> "{log_file}" echo No _internal in build; full copy, no purge',
            f'{rcopy} "{new_dir}" "{install_dir}" /E /R:5 /W:2 '
            f'/XF "{log_file.name}" >> "{log_file}" 2>&1',
            f'>> "{log_file}" echo Full copy returned %ERRORLEVEL%',
        ]
    lines = [
        '@echo off',
        f'> "{log_file}" echo === BMC MIS update helper ===',
        f'>> "{log_file}" echo Started at %DATE% %TIME%',
        f'>> "{log_file}" echo Waiting for PID {pid} to exit...',
        'set /a tries=0',
        ':wait',
        f'"{sys32}\\tasklist.exe" /FI "PID eq {pid}" 2>NUL '
        f'| "{sys32}\\find.exe" "{pid}" >NUL',
        'if errorlevel 1 goto exited',
        'set /a tries+=1',
        f'if %tries% GEQ 120 (>> "{log_file}" '
        'echo Gave up waiting for the old process & goto exited)',
        f'"{sys32}\\ping.exe" -n 2 127.0.0.1 >NUL',
        'goto wait',
        ':exited',
        f'>> "{log_file}" echo App gone after %tries% tick(s); '
        'pausing 2s for handle release',
        f'"{sys32}\\ping.exe" -n 3 127.0.0.1 >NUL',
        *copy_cmds,
        f'>> "{log_file}" echo Relaunching "{exe_path}"',
        f'start "" "{exe_path}"',
        f'>> "{log_file}" echo Done at %DATE% %TIME%',
        # NOTE: we deliberately do NOT rmdir the temp folder here. Doing so
        # while the bat itself is still executing from another folder used to
        # hang on some Windows configurations. Windows cleans its temp on
        # disk-cleanup / reboot; the few stray folders are harmless.
    ]
    return "\r\n".join(lines) + "\r\n"


def apply_update(new_dir: Path) -> None:
    """Write the helper script, launch it hidden, then exit this process.

    The helper waits for the current process to exit (by PID, not by image
    name — more reliable), mirrors the freshly-downloaded files over the
    install folder, relaunches the app and cleans up. A log is written to
    the install folder so post-mortem debugging is possible.
    """
    import time

    install_dir = _install_dir()
    tmp_parent = new_dir.parent
    bat = tmp_parent / "apply_update.bat"
    bat.write_text(build_helper_script(new_dir, install_dir, os.getpid()),
                   encoding="ascii")

    # CREATE_NO_WINDOW gives cmd a real but INVISIBLE console that all of
    # its child commands (tasklist / find / ping / robocopy) inherit.
    #
    # Crucially, DETACHED_PROCESS must NOT be combined with it (pre-v0.3.70
    # bug): a detached cmd has no console at all, so every console-subsystem
    # child allocated its own VISIBLE window — those were the stray
    # `find "<pid>"` and robocopy terminals the operator saw on every
    # update, with the wait loop wedged until they pressed Ctrl+C.
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
        cwd=str(tmp_parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)
    os._exit(0)
