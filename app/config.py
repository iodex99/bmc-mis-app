"""Application-wide configuration: paths, constants, and shared vocabulary.

The data directory holds the SQLite database and generated reports. It defaults
to a ``data`` folder beside the project so the app is easy to run during
development; on an installed copy set the ``BMC_MIS_DATA`` environment variable
(the installer points it at ``%LOCALAPPDATA%\\BMC MIS``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Bilimoria Mehta & Co. — MIS Generator"
APP_SHORT = "BMC MIS"
ORG_NAME = "Bilimoria Mehta & Co."

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    """Where the database and exports live.

    Priority: the ``BMC_MIS_DATA`` env var → ``%LOCALAPPDATA%\\BMC MIS`` when
    running as a packaged .exe → a ``data`` folder beside the source (dev).
    """
    override = os.environ.get("BMC_MIS_DATA")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):  # packaged with PyInstaller
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "BMC MIS"
    return PROJECT_ROOT / "data"


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "mis.db"
EXPORT_DIR = DATA_DIR / "exports"


def resource_path(*parts: str) -> Path:
    """Absolute path to a bundled read-only asset (dev or frozen).

    Data files added via the PyInstaller spec land under ``sys._MEIPASS``
    in a packaged build; in development they sit beside the source tree.
    Used e.g. for the vendored Chart.js inlined into the HTML dashboard.
    """
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base.joinpath(*parts)

# --- Shared vocabulary -------------------------------------------------------

# Kinds of files the operator uploads.
FILE_TYPE_SALES = "sales"
FILE_TYPE_PURCHASE = "purchase"
FILE_TYPE_TIMESHEET = "timesheet"
FILE_TYPE_SALARY = "salary"
FILE_TYPE_REIMBURSEMENT = "reimbursement"
FILE_TYPES = (FILE_TYPE_SALES, FILE_TYPE_PURCHASE, FILE_TYPE_TIMESHEET,
               FILE_TYPE_SALARY, FILE_TYPE_REIMBURSEMENT)

# Cost-centre kinds.
CC_PARTNER = "partner"   # a senior partner cost centre
CC_OFFICE = "office"     # firm overhead bucket

# Voucher kinds.
VCH_SALES = "sales"
VCH_EXPENSE = "expense"


def ensure_dirs() -> None:
    """Create the data and export directories if they do not yet exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
