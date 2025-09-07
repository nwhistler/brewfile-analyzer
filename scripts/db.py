#!/usr/bin/env python3
"""
DuckDB persistence layer for Brewfile Analyzer

- Provides a tools table as the source of truth
- Exports JSON/CSV snapshots for the web UI
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

try:
    import duckdb  # type: ignore
except Exception:
    duckdb = None  # Graceful fallback if package not installed


def is_available() -> bool:
    return duckdb is not None


def get_db_path(config) -> Path:
    data_dir = Path(config.output_root) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tools.duckdb"


def ensure_db(config):
    """Return a DuckDB connection with schema ensured, or None if unavailable."""
    if not is_available():
        return None
    db_path = get_db_path(config)
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tools (
            name TEXT PRIMARY KEY,
            type TEXT,
            description TEXT,
            example TEXT,
            mas_id TEXT,
            user_edited BOOLEAN DEFAULT FALSE,
            last_edited TIMESTAMP
        )
        """
    )
    return con


def fetch_tool(con, name: str) -> Optional[Dict[str, Any]]:
    row = con.execute(
        "SELECT name, type, description, example, mas_id, user_edited, last_edited FROM tools WHERE name = ?",
        [name],
    ).fetchone()
    if not row:
        return None
    keys = ["name", "type", "description", "example", "mas_id", "user_edited", "last_edited"]
    return dict(zip(keys, row))


def upsert_tool_merged(con, new_tool: Dict[str, Any]) -> None:
    """
    Insert/update tool while preserving user edits if present.
    new_tool keys: name, type, description, example, mas_id (optional)
    """
    name = new_tool.get("name")
    assert name, "tool name required"

    existing = fetch_tool(con, name)

    if existing and existing.get("user_edited"):
        # Preserve user edits
        description = existing.get("description") or new_tool.get("description", "")
        example = existing.get("example") or new_tool.get("example", "")
        # Keep last_edited as-is for preserved values
        con.execute(
            """
            UPDATE tools
            SET type = ?, description = ?, example = ?, mas_id = COALESCE(?, mas_id)
            WHERE name = ?
            """,
            [new_tool.get("type", existing.get("type")), description, example, new_tool.get("mas_id"), name],
        )
    elif existing:
        # Overwrite with new generated data
        con.execute(
            """
            UPDATE tools
            SET type = ?, description = ?, example = ?, mas_id = ?
            WHERE name = ?
            """,
            [
                new_tool.get("type"),
                new_tool.get("description", ""),
                new_tool.get("example", ""),
                new_tool.get("mas_id"),
                name,
            ],
        )
    else:
        # Insert new
        con.execute(
            """
            INSERT INTO tools(name, type, description, example, mas_id, user_edited, last_edited)
            VALUES (?, ?, ?, ?, ?, FALSE, NULL)
            """,
            [
                name,
                new_tool.get("type"),
                new_tool.get("description", ""),
                new_tool.get("example", ""),
                new_tool.get("mas_id"),
            ],
        )


def update_tool_fields(con, name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update tool fields (description/example). Marks user_edited and timestamp."""
    existing = fetch_tool(con, name)
    if not existing:
        raise KeyError(f"Tool '{name}' not found")

    description = updates.get("description", existing.get("description"))
    example = updates.get("example", existing.get("example"))

    con.execute(
        """
        UPDATE tools
        SET description = ?, example = ?, user_edited = TRUE, last_edited = CURRENT_TIMESTAMP
        WHERE name = ?
        """,
        [description, example, name],
    )

    return fetch_tool(con, name) or {}


def list_tools(con) -> List[Dict[str, Any]]:
    rows = con.execute(
        """
        SELECT
            name,
            description,
            example,
            type,
            mas_id,
            user_edited,
            CAST(last_edited AS VARCHAR) AS last_edited
        FROM tools
        ORDER BY lower(name)
        """
    ).fetchall()
    keys = ["name", "description", "example", "type", "mas_id", "user_edited", "last_edited"]
    return [dict(zip(keys, r)) for r in rows]


def export_snapshot(con, config) -> None:
    """Write JSON snapshot from DB for the web UI. (CSV disabled)"""
    tools = list_tools(con)

    # JSON only (no CSV)
    config.json_file.write_text(json.dumps(tools, indent=2), encoding="utf-8")

