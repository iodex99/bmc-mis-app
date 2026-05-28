"""Column-template engine.

A *layout signature* fingerprints a file's header row. The first time a layout
is seen the operator maps its columns; the mapping is stored and then reused
automatically for every future file with the same layout.
"""

from __future__ import annotations

import hashlib
import json

from ..database import transaction


def layout_signature(grid: list[list], header_row: int) -> str:
    """A stable fingerprint of the header row + column count."""
    headers = [str(c).strip().lower() for c in grid[header_row]] if grid else []
    raw = "|".join(headers) + f"#cols={len(headers)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def find_template(file_type: str, signature: str) -> dict | None:
    """Return a saved mapping ``{'header_row': int, 'columns': {field: idx}}``."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT column_map FROM column_templates "
            "WHERE file_type = ? AND layout_signature = ?",
            (file_type, signature),
        ).fetchone()
    return json.loads(row["column_map"]) if row else None


def save_template(file_type: str, signature: str, header_row: int,
                  columns: dict[str, int], *,
                  service_map: dict[int, str] | None = None,
                  tax_cols: list[int] | None = None,
                  name: str | None = None,
                  entity_id: int | None = None) -> None:
    """Persist (or overwrite) a column mapping for a layout."""
    body: dict = {"header_row": header_row, "columns": columns}
    if service_map:
        # JSON object keys must be strings.
        body["service_map"] = {str(k): v for k, v in service_map.items()}
    if tax_cols:
        body["tax_cols"] = list(tax_cols)
    payload = json.dumps(body)
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO column_templates "
            "(file_type, layout_signature, column_map, name, entity_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_type, signature, payload, name, entity_id),
        )
