"""
db.py — NateWake Sleep Journal
================================
All SQLite operations + versioned migration system.
No UI dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

import config
from models import Nuit

# ─────────────────────────────────────────────────────────────
#  Database path
# ─────────────────────────────────────────────────────────────

def _get_db_path() -> str:
    """Return the platform-appropriate database path."""
    # On Android, use the app's private data directory if available.
    try:
        from android.storage import app_storage_path  # type: ignore
        base = app_storage_path()
    except ImportError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "natewake.db")


DB_PATH: str = _get_db_path()


# ─────────────────────────────────────────────────────────────
#  Connection helper
# ─────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ─────────────────────────────────────────────────────────────
#  DDL — base schema (version 1)
# ─────────────────────────────────────────────────────────────

_DDL_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS migrations (
    version  INTEGER PRIMARY KEY,
    applique TEXT DEFAULT (datetime('now'))
);
"""

_DDL_V1 = """
CREATE TABLE IF NOT EXISTS nuits (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 TEXT NOT NULL UNIQUE,
    heure_coucher        TEXT NOT NULL,
    heure_reveil         TEXT NOT NULL,
    duree_totale_min     REAL NOT NULL,
    reveils_nocturnes    TEXT DEFAULT '[]',
    intervalles_min      TEXT DEFAULT '[]',
    cycles_estimes       INTEGER,
    duree_moy_cycle_min  REAL,
    qualite_reveil       INTEGER CHECK(qualite_reveil IN (0,1,2)),
    type_nuit            TEXT CHECK(type_nuit IN (
                             'normale','nocturne','récupération','sieste'
                         )),
    source               TEXT CHECK(source IN (
                             'manuel','sleep_as_android','sleep_cycle'
                         )) DEFAULT 'manuel',
    is_outlier           INTEGER DEFAULT 0,
    outlier_auto         INTEGER DEFAULT 0,
    outlier_manuel       INTEGER DEFAULT NULL,
    score_circadien      REAL DEFAULT NULL,
    note                 TEXT DEFAULT '',
    timestamp_creation   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    cle   TEXT PRIMARY KEY,
    valeur TEXT
);
"""


# ─────────────────────────────────────────────────────────────
#  Migration registry
# Each entry: (version_int, sql_string_or_callable)
# Callable signature: (conn: sqlite3.Connection) -> None
# ─────────────────────────────────────────────────────────────

def _migration_v1(conn: sqlite3.Connection) -> None:
    """Initial schema creation."""
    conn.executescript(_DDL_V1)
    # Seed app_version into config
    conn.execute(
        "INSERT OR IGNORE INTO config(cle, valeur) VALUES (?, ?)",
        ("app_version", config.APP_VERSION),
    )


MIGRATIONS: List[tuple] = [
    (1, _migration_v1),
    # Future migrations go here:
    # (2, _migration_v2),
]


# ─────────────────────────────────────────────────────────────
#  Public init
# ─────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Initialise the database and apply any pending migrations.
    Safe to call multiple times (idempotent).
    """
    conn = _connect()
    with conn:
        conn.executescript(_DDL_MIGRATIONS)
        applied = {row[0] for row in conn.execute("SELECT version FROM migrations")}
        for version, migrate in MIGRATIONS:
            if version not in applied:
                if callable(migrate):
                    migrate(conn)
                else:
                    conn.executescript(migrate)
                conn.execute(
                    "INSERT INTO migrations(version) VALUES (?)", (version,)
                )
    conn.close()


# ─────────────────────────────────────────────────────────────
#  CRUD — Nuits
# ─────────────────────────────────────────────────────────────

def _nuit_to_params(n: Nuit) -> dict:
    return {
        "date": n.date,
        "heure_coucher": n.heure_coucher,
        "heure_reveil": n.heure_reveil,
        "duree_totale_min": n.duree_totale_min,
        "reveils_nocturnes": json.dumps(n.reveils_nocturnes),
        "intervalles_min": json.dumps(n.intervalles_min),
        "cycles_estimes": n.cycles_estimes,
        "duree_moy_cycle_min": n.duree_moy_cycle_min,
        "qualite_reveil": n.qualite_reveil,
        "type_nuit": n.type_nuit,
        "source": n.source,
        "is_outlier": n.is_outlier,
        "outlier_auto": n.outlier_auto,
        "outlier_manuel": n.outlier_manuel,
        "score_circadien": n.score_circadien,
        "note": n.note,
    }


def insert_nuit(nuit: Nuit) -> int:
    """Insert a new night. Returns the new row id."""
    params = _nuit_to_params(nuit)
    sql = """
        INSERT INTO nuits (
            date, heure_coucher, heure_reveil, duree_totale_min,
            reveils_nocturnes, intervalles_min, cycles_estimes,
            duree_moy_cycle_min, qualite_reveil, type_nuit, source,
            is_outlier, outlier_auto, outlier_manuel, score_circadien, note
        ) VALUES (
            :date, :heure_coucher, :heure_reveil, :duree_totale_min,
            :reveils_nocturnes, :intervalles_min, :cycles_estimes,
            :duree_moy_cycle_min, :qualite_reveil, :type_nuit, :source,
            :is_outlier, :outlier_auto, :outlier_manuel, :score_circadien, :note
        )
    """
    conn = _connect()
    with conn:
        cur = conn.execute(sql, params)
        new_id = cur.lastrowid
    conn.close()
    return new_id


def update_nuit(nuit: Nuit) -> None:
    """Update an existing night by id."""
    if nuit.id is None:
        raise ValueError("Cannot update a Nuit without an id.")
    params = _nuit_to_params(nuit)
    params["id"] = nuit.id
    sql = """
        UPDATE nuits SET
            date=:date, heure_coucher=:heure_coucher, heure_reveil=:heure_reveil,
            duree_totale_min=:duree_totale_min, reveils_nocturnes=:reveils_nocturnes,
            intervalles_min=:intervalles_min, cycles_estimes=:cycles_estimes,
            duree_moy_cycle_min=:duree_moy_cycle_min, qualite_reveil=:qualite_reveil,
            type_nuit=:type_nuit, source=:source, is_outlier=:is_outlier,
            outlier_auto=:outlier_auto, outlier_manuel=:outlier_manuel,
            score_circadien=:score_circadien, note=:note
        WHERE id=:id
    """
    conn = _connect()
    with conn:
        conn.execute(sql, params)
    conn.close()


def delete_nuit(nuit_id: int) -> None:
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM nuits WHERE id=?", (nuit_id,))
    conn.close()


def get_nuit_by_date(date_iso: str) -> Optional[Nuit]:
    conn = _connect()
    row = conn.execute("SELECT * FROM nuits WHERE date=?", (date_iso,)).fetchone()
    conn.close()
    if row:
        return Nuit.from_row(dict(row))
    return None


def get_nuit_by_id(nuit_id: int) -> Optional[Nuit]:
    conn = _connect()
    row = conn.execute("SELECT * FROM nuits WHERE id=?", (nuit_id,)).fetchone()
    conn.close()
    if row:
        return Nuit.from_row(dict(row))
    return None


def get_nuits_page(
    page: int = 0,
    page_size: int = config.HISTORY_PAGE_SIZE,
    type_nuit: Optional[str] = None,
    source: Optional[str] = None,
    days: Optional[int] = None,
    outlier_only: bool = False,
) -> List[Nuit]:
    """
    Return a paginated, filtered list of nights (newest first).
    """
    conditions = []
    params: List[Any] = []

    if type_nuit:
        conditions.append("type_nuit = ?")
        params.append(type_nuit)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if days is not None:
        conditions.append("date >= date('now', ?)")
        params.append(f"-{days} days")
    if outlier_only:
        conditions.append("is_outlier = 1")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT * FROM nuits
        {where}
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """
    params += [page_size, page * page_size]

    conn = _connect()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [Nuit.from_row(dict(r)) for r in rows]


def get_all_nuits_df():
    """Return all nights as a pandas DataFrame (for analytics)."""
    import pandas as pd

    conn = _connect()
    df = pd.read_sql_query("SELECT * FROM nuits ORDER BY date ASC", conn)
    conn.close()

    # Parse JSON columns
    if not df.empty:
        df["reveils_nocturnes"] = df["reveils_nocturnes"].apply(
            lambda x: json.loads(x) if x else []
        )
        df["intervalles_min"] = df["intervalles_min"].apply(
            lambda x: json.loads(x) if x else []
        )
        # Resolve is_outlier using outlier_manuel override
        df["is_outlier"] = df.apply(
            lambda row: int(row["outlier_manuel"])
            if row["outlier_manuel"] is not None
            else int(row["outlier_auto"]),
            axis=1,
        )
    return df


def count_nuits(non_outlier_only: bool = False) -> int:
    conn = _connect()
    if non_outlier_only:
        n = conn.execute("SELECT COUNT(*) FROM nuits WHERE is_outlier=0").fetchone()[0]
    else:
        n = conn.execute("SELECT COUNT(*) FROM nuits").fetchone()[0]
    conn.close()
    return n


def update_outlier_scores(updates: List[tuple]) -> None:
    """
    Batch-update outlier_auto and score_circadien.
    updates = [(outlier_auto, score_circadien, id), ...]
    """
    conn = _connect()
    with conn:
        conn.executemany(
            "UPDATE nuits SET outlier_auto=?, score_circadien=? WHERE id=?", updates
        )
    conn.close()


def update_is_outlier_column() -> None:
    """
    Recompute the is_outlier column for all rows:
    is_outlier = outlier_manuel if outlier_manuel IS NOT NULL else outlier_auto
    """
    conn = _connect()
    with conn:
        conn.execute("""
            UPDATE nuits
            SET is_outlier = CASE
                WHEN outlier_manuel IS NOT NULL THEN outlier_manuel
                ELSE outlier_auto
            END
        """)
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Config key-value store
# ─────────────────────────────────────────────────────────────

def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = _connect()
    row = conn.execute("SELECT valeur FROM config WHERE cle=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_config(key: str, value: str) -> None:
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO config(cle, valeur) VALUES (?, ?)", (key, value)
        )
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Export helpers
# ─────────────────────────────────────────────────────────────

def export_all_csv(path: str) -> None:
    """Write all nights to a CSV file."""
    import csv
    conn = _connect()
    rows = conn.execute("SELECT * FROM nuits ORDER BY date ASC").fetchall()
    conn.close()
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])


def export_all_json(path: str) -> None:
    """Write all nights to a JSON file with metadata."""
    import datetime
    conn = _connect()
    rows = conn.execute("SELECT * FROM nuits ORDER BY date ASC").fetchall()
    conn.close()
    data = {
        "app_version": config.APP_VERSION,
        "export_timestamp": datetime.datetime.now().isoformat(),
        "nuits": [dict(r) for r in rows],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_db_copy(dest_path: str) -> None:
    """Copy the SQLite file to dest_path."""
    import shutil
    shutil.copy2(DB_PATH, dest_path)
