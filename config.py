"""
config.py — NateWake Sleep Journal
===================================
Central configuration file. ALL business constants and tunable thresholds
are defined here. Never hard-code these values in screens or analytics.
"""

# ─────────────────────────────────────────────
#  Application metadata
# ─────────────────────────────────────────────
APP_NAME = "NateWake"
APP_VERSION = "0.1.0"
DB_SCHEMA_VERSION = 1  # Increment when a new migration is added

# ─────────────────────────────────────────────
#  Sleep cycle biology
# ─────────────────────────────────────────────
CYCLE_MIN_MIN: float = 70.0
"""Lower biological bound for a single sleep cycle (minutes)."""

CYCLE_MAX_MIN: float = 115.0
"""Upper biological bound for a single sleep cycle (minutes)."""

ENDORMISSEMENT_MIN: float = 15.0
"""Estimated sleep-onset latency subtracted before cycle division (minutes).
   This value is used only for cycle estimation and interval calculations,
   NOT for duree_totale_min."""

TARGET_CYCLE_MIN: float = 90.0
"""Reference cycle length used in the fallback estimator when no valid
   n satisfies [CYCLE_MIN_MIN, CYCLE_MAX_MIN]."""

MAX_CYCLES: int = 6
"""Maximum number of cycles considered in estimation / planner."""

# ─────────────────────────────────────────────
#  Outlier detection
# ─────────────────────────────────────────────
IQR_K_NORMAL: float = 1.5
"""IQR multiplier for moderate outlier fences (Tukey standard)."""

IQR_K_EXTREME: float = 3.0
"""IQR multiplier for extreme outlier fences."""

# ─────────────────────────────────────────────
#  Minimum data thresholds
# ─────────────────────────────────────────────
N_MIN_CYCLE_PERSO: int = 7
"""Minimum non-outlier nights required to use the personal cycle mean
   in the planner. Below this, 90 min is used with a warning."""

N_MIN_MODELE: int = 14
"""Minimum non-outlier nights with wake_quality filled before the
   Ridge regression model is trained."""

N_MIN_CIRCADIEN: int = 21
"""Minimum non-outlier nights with wake_quality filled before the
   circadian window analysis is performed."""

N_MIN_WINDOW_FILL: int = 5
"""Minimum nights inside a sliding window for the window to be
   considered statistically meaningful in circadian analysis."""

# ─────────────────────────────────────────────
#  Circadian window analysis
# ─────────────────────────────────────────────
CIRCADIAN_WINDOW_WIDTH_MIN: int = 60
"""Width of the sliding window used in circadian analysis (minutes)."""

CIRCADIAN_WINDOW_STEP_MIN: int = 15
"""Step size of the sliding window (minutes)."""

CIRCADIAN_WINDOW_PERCENTILE: float = 75.0
"""Percentile of wake quality above which a window is considered optimal."""

CIRCADIAN_WINDOW_GAP_MERGE_MIN: int = 15
"""Maximum gap between consecutive optimal windows before they are merged
   into a single contiguous range (minutes)."""

CIRCADIAN_SCORE_INNER: float = 1.0
"""Score assigned to nights whose bedtime falls inside the optimal window."""

CIRCADIAN_SCORE_DECAY_DENOMINATOR: float = 120.0
"""Distance from window centre at which the circadian score reaches the
   minimum. score = max(0.4, 1.0 - |distance| / DECAY_DEN)"""

CIRCADIAN_SCORE_FLOOR: float = 0.4
"""Minimum circadian score for nights outside the optimal window."""

# ─────────────────────────────────────────────
#  Predictive model (Ridge regression)
# ─────────────────────────────────────────────
RIDGE_ALPHA: float = 1.0
"""L2 regularisation strength for the Ridge regression model.
   Higher values → more regularisation → safer on small datasets."""

LOOCV_THRESHOLD: int = 50
"""Use Leave-One-Out CV when n < this value; otherwise use K-Fold."""

KFOLD_K: int = 5
"""Number of folds for K-Fold cross-validation when n >= LOOCV_THRESHOLD."""

COEF_SIGNIFICANCE_THRESHOLD: float = 0.05
"""Minimum absolute coefficient value (after de-normalisation) required
   for a Ridge coefficient to produce an interpretation sentence."""

# ─────────────────────────────────────────────
#  Planner
# ─────────────────────────────────────────────
PLANNER_MARGE_MIN: float = 10.0
"""±margin around the theoretical wake time in the planner (minutes)."""

# ─────────────────────────────────────────────
#  History pagination
# ─────────────────────────────────────────────
HISTORY_PAGE_SIZE: int = 30
"""Number of history entries loaded per page (lazy loading)."""

# ─────────────────────────────────────────────
#  UI / display
# ─────────────────────────────────────────────
CI_95_LABEL: str = "IC 95%"
"""Label used when displaying 95% confidence intervals in the UI."""
