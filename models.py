"""
models.py — NateWake Sleep Journal
====================================
Pure Python dataclasses for all domain entities.
No Kivy / UI dependencies here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────
#  Wake-quality enum helper
# ─────────────────────────────────────────────────────────────

QUALITE_LABELS = {0: "Groggy", 1: "Correct", 2: "Rested"}
QUALITE_COLORS = {0: (0.8, 0.3, 0.3, 1), 1: (0.9, 0.75, 0.2, 1), 2: (0.3, 0.8, 0.4, 1)}

TYPE_NUIT_CHOICES = ["normale", "nocturne", "récupération", "sieste"]
SOURCE_CHOICES = ["manuel", "sleep_as_android", "sleep_cycle"]


# ─────────────────────────────────────────────────────────────
#  Night entity
# ─────────────────────────────────────────────────────────────

@dataclass
class Nuit:
    """Represents one night (or nap) entry in the sleep journal."""

    date: str                              # ISO format: YYYY-MM-DD
    heure_coucher: str                     # HH:MM 24h
    heure_reveil: str                      # HH:MM 24h
    duree_totale_min: float                # calculated
    reveils_nocturnes: List[str] = field(default_factory=list)   # ["HH:MM", ...]
    intervalles_min: List[int] = field(default_factory=list)     # [int, ...] calculated
    cycles_estimes: Optional[int] = None
    duree_moy_cycle_min: Optional[float] = None
    qualite_reveil: Optional[int] = None   # 0 | 1 | 2
    type_nuit: str = "normale"
    source: str = "manuel"
    is_outlier: int = 0
    outlier_auto: int = 0
    outlier_manuel: Optional[int] = None
    score_circadien: Optional[float] = None
    note: str = ""
    timestamp_creation: str = ""
    id: Optional[int] = None

    # ─── serialisation helpers ───

    @classmethod
    def from_row(cls, row: dict) -> "Nuit":
        """Build a Nuit from a sqlite3.Row dict."""
        reveils = json.loads(row.get("reveils_nocturnes") or "[]")
        intervalles = json.loads(row.get("intervalles_min") or "[]")
        return cls(
            id=row["id"],
            date=row["date"],
            heure_coucher=row["heure_coucher"],
            heure_reveil=row["heure_reveil"],
            duree_totale_min=row["duree_totale_min"],
            reveils_nocturnes=reveils,
            intervalles_min=intervalles,
            cycles_estimes=row.get("cycles_estimes"),
            duree_moy_cycle_min=row.get("duree_moy_cycle_min"),
            qualite_reveil=row.get("qualite_reveil"),
            type_nuit=row.get("type_nuit") or "normale",
            source=row.get("source") or "manuel",
            is_outlier=row.get("is_outlier") or 0,
            outlier_auto=row.get("outlier_auto") or 0,
            outlier_manuel=row.get("outlier_manuel"),
            score_circadien=row.get("score_circadien"),
            note=row.get("note") or "",
            timestamp_creation=row.get("timestamp_creation") or "",
        )

    def to_dict(self) -> dict:
        """Serialise to plain dict (for JSON export)."""
        return {
            "id": self.id,
            "date": self.date,
            "heure_coucher": self.heure_coucher,
            "heure_reveil": self.heure_reveil,
            "duree_totale_min": self.duree_totale_min,
            "reveils_nocturnes": self.reveils_nocturnes,
            "intervalles_min": self.intervalles_min,
            "cycles_estimes": self.cycles_estimes,
            "duree_moy_cycle_min": self.duree_moy_cycle_min,
            "qualite_reveil": self.qualite_reveil,
            "type_nuit": self.type_nuit,
            "source": self.source,
            "is_outlier": self.is_outlier,
            "outlier_auto": self.outlier_auto,
            "outlier_manuel": self.outlier_manuel,
            "score_circadien": self.score_circadien,
            "note": self.note,
            "timestamp_creation": self.timestamp_creation,
        }

    # ─── display helpers ───

    @property
    def duree_label(self) -> str:
        """Format duration as XhYY."""
        h = int(self.duree_totale_min // 60)
        m = int(self.duree_totale_min % 60)
        return f"{h}h{m:02d}"

    @property
    def qualite_label(self) -> str:
        if self.qualite_reveil is None:
            return "—"
        return QUALITE_LABELS.get(self.qualite_reveil, "—")

    @property
    def effective_is_outlier(self) -> int:
        """Resolved outlier flag: manual override takes precedence."""
        if self.outlier_manuel is not None:
            return self.outlier_manuel
        return self.outlier_auto


# ─────────────────────────────────────────────────────────────
#  Analytics result containers
# ─────────────────────────────────────────────────────────────

@dataclass
class StatsDescriptives:
    n: int
    duree_moy: float
    duree_std: float
    duree_median: float
    duree_ic95: Optional[tuple]
    cycle_moy: float
    cycle_std: float
    cycle_ic95: Optional[tuple]
    cycles_par_nuit_moy: float
    qualite_moy: Optional[float]


@dataclass
class FenetreCircadienne:
    debut: int        # minutes since midnight
    fin: int
    qualite_moy: float
    n: int
    ic95: Optional[tuple]
    label: str        # e.g. "23h15 – 00h45"


@dataclass
class PlanReveil:
    cycles: int
    duree_min: int
    heure_theorique: str   # HH:MM
    fenetre_min: str       # HH:MM
    fenetre_max: str       # HH:MM
    dans_fenetre_circadienne: Optional[bool] = None


@dataclass
class ModelMetrics:
    r2_cv: float
    rmse_cv: float
    method: str          # "LOOCV" or "KFold-K"
    n_samples: int
    trained_at: str      # ISO datetime
    interpretations: List[str] = field(default_factory=list)
