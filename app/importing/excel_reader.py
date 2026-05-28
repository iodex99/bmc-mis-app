"""Read uploaded .xlsx files into plain Python row grids.

Kept deliberately format-agnostic — the parsers and the column-template engine
decide what the rows mean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl


def sheet_names(path: str | Path) -> list[str]:
    """List worksheet names in a workbook."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def read_grid(path: str | Path, sheet: str | None = None) -> list[list[Any]]:
    """Return a worksheet as a list of equal-length rows of cell values."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    width = max((len(r) for r in rows), default=0)
    for r in rows:
        r.extend([None] * (width - len(r)))
    return rows


def guess_header_row(grid: list[list[Any]], must_contain: tuple[str, ...] = ()) -> int:
    """Best-guess the index of the header row.

    Picks the row with the most non-empty text cells; if *must_contain* keywords
    are given, prefers a row containing one of them.
    """
    best_idx, best_score = 0, -1
    for i, row in enumerate(grid[:40]):
        texts = [str(c).strip().lower() for c in row if c not in (None, "")]
        if not texts:
            continue
        score = sum(1 for c in row if isinstance(c, str) and c.strip())
        if must_contain and any(k in t for t in texts for k in must_contain):
            score += 100
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx
