"""
importers.py — NateWake Sleep Journal
=======================================
CSV parsers for Sleep as Android and Sleep Cycle exports.
No UI / Kivy dependencies.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from analytics import calcule_duree_totale, calcule_intervalles, estime_cycles
from models import Nuit


# ─────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────


def _rating_to_qualite(rating_raw) -> Optional[int]:
    """Map a 0-1 float rating to 0|1|2. Returns None if missing."""
    try:
        v = float(str(rating_raw).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
    if v <= 0.33:
        return 0
    elif v <= 0.66:
        return 1
    else:
        return 2


def _normalize_time(raw: str) -> Optional[str]:
    """
    Try to extract HH:MM from various date-time strings.
    Returns 'HH:MM' or None.
    """
    raw = str(raw).strip()
    # Try common patterns: 'YYYY-MM-DD HH:MM', 'HH:MM', 'HH:MM:SS'
    patterns = [
        r"\d{4}-\d{2}-\d{2}\s+(\d{2}):(\d{2})",  # datetime with space
        r"\d{2}\.\d{2}\.\d{4}\s+(\d{2}):(\d{2})",  # DD.MM.YYYY HH:MM
        r"^(\d{1,2}):(\d{2})(?::\d{2})?$",          # HH:MM[:SS]
    ]
    for p in patterns:
        m = re.search(p, raw)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            return f"{h:02d}:{mi:02d}"
    return None


def _extract_date(raw: str) -> Optional[str]:
    """Extract ISO date YYYY-MM-DD from various formats."""
    raw = str(raw).strip()
    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD.MM.YYYY
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _build_nuit_from_parsed(
    date_iso: str,
    heure_coucher: str,
    heure_reveil: str,
    qualite: Optional[int],
    note: str,
    source: str,
) -> Nuit:
    duree = calcule_duree_totale(heure_coucher, heure_reveil)
    n_cycles, cycle_dur = estime_cycles(duree)
    intervalles = calcule_intervalles(heure_coucher, [], heure_reveil)
    return Nuit(
        date=date_iso,
        heure_coucher=heure_coucher,
        heure_reveil=heure_reveil,
        duree_totale_min=duree,
        reveils_nocturnes=[],
        intervalles_min=intervalles,
        cycles_estimes=n_cycles,
        duree_moy_cycle_min=cycle_dur,
        qualite_reveil=qualite,
        type_nuit="normale",
        source=source,
        is_outlier=0,
        outlier_auto=0,
        outlier_manuel=None,
        score_circadien=None,
        note=note,
    )


# ─────────────────────────────────────────────────────────────
#  Result container
# ─────────────────────────────────────────────────────────────


@dataclass
class ImportResult:
    nuits: List[Nuit] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    preview_rows: List[dict] = field(default_factory=list)  # first N rows as dicts


# ─────────────────────────────────────────────────────────────
#  Sleep as Android parser
# ─────────────────────────────────────────────────────────────


def parse_sleep_as_android(file_content: str, preview_n: int = 5) -> ImportResult:
    """
    Parse a Sleep as Android CSV export.

    Expected columns (may vary by export version):
        From      — bedtime (datetime string)
        To        — wake time (datetime string)
        Hours     — ignored (recalculated)
        Rating    — 0.0–1.0 float

    Returns ImportResult with parsed Nuit objects.
    """
    result = ImportResult()

    try:
        reader = csv.DictReader(io.StringIO(file_content))
    except Exception as e:
        result.errors.append(f"CSV parsing error: {e}")
        return result

    # Normalise column names (strip spaces, lowercase)
    raw_rows = list(reader)
    if not raw_rows:
        result.errors.append("File appears to be empty.")
        return result

    # Sniff actual column names
    fieldnames = list(raw_rows[0].keys())
    col_map = {c.strip().lower(): c for c in fieldnames}

    from_col = col_map.get("from") or col_map.get("bedtime")
    to_col = col_map.get("to") or col_map.get("wake")
    rating_col = col_map.get("rating") or col_map.get("quality")

    if not from_col or not to_col:
        result.errors.append(
            "Could not find 'From'/'To' columns. "
            f"Found columns: {', '.join(fieldnames)}"
        )
        return result

    for i, row in enumerate(raw_rows):
        try:
            raw_from = row.get(from_col, "").strip()
            raw_to = row.get(to_col, "").strip()

            if not raw_from or not raw_to:
                continue

            date_iso = _extract_date(raw_from)
            heure_coucher = _normalize_time(raw_from)
            heure_reveil = _normalize_time(raw_to)

            if not date_iso or not heure_coucher or not heure_reveil:
                result.errors.append(f"Row {i + 2}: cannot parse date/times from '{raw_from}' / '{raw_to}'")
                continue

            rating_raw = row.get(rating_col, "") if rating_col else ""
            qualite = _rating_to_qualite(rating_raw)

            nuit = _build_nuit_from_parsed(
                date_iso, heure_coucher, heure_reveil,
                qualite, "", "sleep_as_android"
            )
            result.nuits.append(nuit)

            if i < preview_n:
                result.preview_rows.append({
                    "date": date_iso,
                    "coucher": heure_coucher,
                    "réveil": heure_reveil,
                    "qualité": qualite,
                    "durée": nuit.duree_label,
                })

        except Exception as e:
            result.errors.append(f"Row {i + 2}: {e}")

    return result


# ─────────────────────────────────────────────────────────────
#  Sleep Cycle parser
# ─────────────────────────────────────────────────────────────


def parse_sleep_cycle(file_content: str, preview_n: int = 5) -> ImportResult:
    """
    Parse a Sleep Cycle CSV export.

    Expected columns:
        Start          — bedtime
        End            — wake time
        Sleep quality  — percentage (0–100) or 0.0–1.0
        Notes          — free text note

    Returns ImportResult with parsed Nuit objects.
    """
    result = ImportResult()

    try:
        reader = csv.DictReader(io.StringIO(file_content), delimiter=";")
        raw_rows = list(reader)
        if not raw_rows:
            # Retry with comma delimiter
            reader = csv.DictReader(io.StringIO(file_content))
            raw_rows = list(reader)
    except Exception as e:
        result.errors.append(f"CSV parsing error: {e}")
        return result

    if not raw_rows:
        result.errors.append("File appears to be empty.")
        return result

    fieldnames = list(raw_rows[0].keys())
    col_map = {c.strip().lower(): c for c in fieldnames}

    start_col = col_map.get("start") or col_map.get("start time")
    end_col = col_map.get("end") or col_map.get("end time")
    quality_col = col_map.get("sleep quality") or col_map.get("quality")
    notes_col = col_map.get("notes") or col_map.get("note")

    if not start_col or not end_col:
        result.errors.append(
            "Could not find 'Start'/'End' columns. "
            f"Found columns: {', '.join(fieldnames)}"
        )
        return result

    for i, row in enumerate(raw_rows):
        try:
            raw_start = row.get(start_col, "").strip()
            raw_end = row.get(end_col, "").strip()

            if not raw_start or not raw_end:
                continue

            date_iso = _extract_date(raw_start)
            heure_coucher = _normalize_time(raw_start)
            heure_reveil = _normalize_time(raw_end)

            if not date_iso or not heure_coucher or not heure_reveil:
                result.errors.append(f"Row {i + 2}: cannot parse date/times")
                continue

            # Sleep quality may be expressed as % (0–100)
            raw_q = row.get(quality_col, "") if quality_col else ""
            raw_q_cleaned = str(raw_q).replace("%", "").strip()
            try:
                q_float = float(raw_q_cleaned.replace(",", "."))
                if q_float > 1.0:
                    q_float /= 100.0
                qualite = _rating_to_qualite(q_float)
            except (ValueError, TypeError):
                qualite = None

            note = row.get(notes_col, "").strip() if notes_col else ""

            nuit = _build_nuit_from_parsed(
                date_iso, heure_coucher, heure_reveil,
                qualite, note, "sleep_cycle"
            )
            result.nuits.append(nuit)

            if i < preview_n:
                result.preview_rows.append({
                    "date": date_iso,
                    "coucher": heure_coucher,
                    "réveil": heure_reveil,
                    "qualité": qualite,
                    "durée": nuit.duree_label,
                    "note": note[:30] + "…" if len(note) > 30 else note,
                })

        except Exception as e:
            result.errors.append(f"Row {i + 2}: {e}")

    return result


# ─────────────────────────────────────────────────────────────
#  Duplicate resolution helper
# ─────────────────────────────────────────────────────────────


def resolve_duplicates(
    nuits_new: List[Nuit],
    existing_dates: set,
    strategy: str = "ignore",
) -> Tuple[List[Nuit], List[Nuit], List[Nuit]]:
    """
    Split nuits_new into three lists:
        to_insert  — dates not in existing_dates
        to_replace — dates in existing_dates and strategy='replace'
        skipped    — dates in existing_dates and strategy='ignore'

    strategy: 'replace' | 'ignore' | 'cancel'
    If strategy='cancel', returns ([], [], all_new).
    """
    if strategy == "cancel":
        return [], [], nuits_new

    to_insert: List[Nuit] = []
    to_replace: List[Nuit] = []
    skipped: List[Nuit] = []

    for n in nuits_new:
        if n.date in existing_dates:
            if strategy == "replace":
                to_replace.append(n)
            else:
                skipped.append(n)
        else:
            to_insert.append(n)

    return to_insert, to_replace, skipped
