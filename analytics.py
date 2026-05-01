"""
analytics.py — NateWake Sleep Journal
=======================================
Pure analytics module. Entirely decoupled from UI.
All functions are stateless: they take DataFrames / values and return
plain Python structures (dataclasses, dicts, lists).
No Kivy imports.
"""

from __future__ import annotations

import datetime
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

import config
from models import (
    FenetreCircadienne,
    ModelMetrics,
    Nuit,
    PlanReveil,
    StatsDescriptives,
)

# ─────────────────────────────────────────────────────────────
#  §5.1 — Total sleep duration
# ─────────────────────────────────────────────────────────────


def calcule_duree_totale(heure_coucher: str, heure_reveil: str) -> float:
    """
    Returns total sleep duration in minutes.
    Handles midnight crossing: if wake_time <= bed_time, add 24h.
    """
    hc_h, hc_m = map(int, heure_coucher.split(":"))
    hr_h, hr_m = map(int, heure_reveil.split(":"))
    coucher_min = hc_h * 60 + hc_m
    reveil_min = hr_h * 60 + hr_m
    if reveil_min <= coucher_min:
        reveil_min += 1440  # +24h
    return float(reveil_min - coucher_min)


# ─────────────────────────────────────────────────────────────
#  §5.2 — Cycle estimation
# ─────────────────────────────────────────────────────────────


def estime_cycles(
    duree_totale_min: float,
    endormissement: float = config.ENDORMISSEMENT_MIN,
) -> Tuple[int, float]:
    """
    Returns (n_cycles, avg_cycle_duration_min).
    Among all n in [1..6] whose cycle length falls in [CYCLE_MIN, CYCLE_MAX],
    picks the one whose cycle duration is closest to TARGET_CYCLE_MIN (90 min).
    Fallback when no valid n exists: same closest-to-90 criterion over all n.
    """
    duree_effective = duree_totale_min - endormissement
    if duree_effective <= 0:
        return (1, max(duree_effective, 0.0))

    valides = [
        n for n in range(1, config.MAX_CYCLES + 1)
        if config.CYCLE_MIN_MIN <= duree_effective / n <= config.CYCLE_MAX_MIN
    ]
    candidates = valides if valides else range(1, config.MAX_CYCLES + 1)
    best_n = min(candidates, key=lambda n: abs(duree_effective / n - config.TARGET_CYCLE_MIN))
    return (best_n, round(duree_effective / best_n, 2))


# ─────────────────────────────────────────────────────────────
#  §5.3 — Nocturnal interval calculation
# ─────────────────────────────────────────────────────────────


def calcule_intervalles(
    heure_coucher: str,
    reveils_nocturnes: List[str],
    heure_reveil: str,
    endormissement: float = config.ENDORMISSEMENT_MIN,
) -> List[int]:
    """
    Returns list of segment durations (minutes) between each consecutive
    wake event, starting after sleep onset latency.
    Handles midnight crossing for each point.
    """

    def to_min(t: str) -> int:
        h, m = map(int, t.split(":"))
        return h * 60 + m

    coucher_m = to_min(heure_coucher)
    base = coucher_m + int(endormissement)
    points = [base]

    for r in reveils_nocturnes:
        rm = to_min(r)
        if rm < base:
            rm += 1440
        points.append(rm)

    rm_final = to_min(heure_reveil)
    if rm_final <= coucher_m:
        rm_final += 1440
    points.append(rm_final)

    return [round(points[i + 1] - points[i]) for i in range(len(points) - 1)]


# ─────────────────────────────────────────────────────────────
#  §6.1 — Descriptive statistics
# ─────────────────────────────────────────────────────────────


def _ci95(values: np.ndarray) -> Optional[Tuple[float, float]]:
    """95% confidence interval on the mean. Uses t if n<30, normal if n>=30."""
    n = len(values)
    if n < 2:
        return None
    mean = float(np.mean(values))
    sem = float(stats.sem(values))
    if n < 30:
        return stats.t.interval(0.95, df=n - 1, loc=mean, scale=sem)
    else:
        return stats.norm.interval(0.95, loc=mean, scale=sem)


def stats_descriptives(df: pd.DataFrame) -> Optional[StatsDescriptives]:
    """
    Computes descriptive stats on non-outlier nights.
    Input df must have: duree_totale_min, duree_moy_cycle_min, cycles_estimes,
                        qualite_reveil.
    Returns None if df is empty or lacks required columns.
    """
    if df.empty or "is_outlier" not in df.columns:
        return None
    df_clean = df[df["is_outlier"] == 0].copy()
    n = len(df_clean)
    if n == 0:
        return None

    duree = df_clean["duree_totale_min"].dropna().values.astype(float)
    cycles_dur = df_clean["duree_moy_cycle_min"].dropna().values.astype(float)
    cycles_n = df_clean["cycles_estimes"].dropna().values.astype(float)
    qualite = df_clean["qualite_reveil"].dropna().values.astype(float)

    return StatsDescriptives(
        n=n,
        duree_moy=float(np.mean(duree)) if len(duree) > 0 else 0.0,
        duree_std=float(np.std(duree, ddof=1)) if len(duree) > 1 else 0.0,
        duree_median=float(np.median(duree)) if len(duree) > 0 else 0.0,
        duree_ic95=_ci95(duree),
        cycle_moy=float(np.mean(cycles_dur)) if len(cycles_dur) > 0 else config.TARGET_CYCLE_MIN,
        cycle_std=float(np.std(cycles_dur, ddof=1)) if len(cycles_dur) > 1 else 0.0,
        cycle_ic95=_ci95(cycles_dur),
        cycles_par_nuit_moy=float(np.mean(cycles_n)) if len(cycles_n) > 0 else 0.0,
        qualite_moy=float(np.mean(qualite)) if len(qualite) > 0 else None,
    )


def tendance_7j(df: pd.DataFrame) -> Optional[Dict]:
    """
    Compare mean duration over last 7 nights vs previous 7 nights.
    Returns {'delta': float, 'direction': 'up'|'down'|'stable'} or None.
    """
    df_clean = df[df["is_outlier"] == 0].copy().sort_values("date")
    if len(df_clean) < 14:
        return None
    last7 = df_clean.tail(7)["duree_totale_min"].mean()
    prev7 = df_clean.iloc[-14:-7]["duree_totale_min"].mean()
    delta = last7 - prev7
    if abs(delta) < 5:
        direction = "stable"
    elif delta > 0:
        direction = "up"
    else:
        direction = "down"
    return {"delta": round(delta, 1), "direction": direction}


# ─────────────────────────────────────────────────────────────
#  §6.2 — IQR Outlier detection
# ─────────────────────────────────────────────────────────────


def detecte_outliers_iqr(
    series: pd.Series,
    k: float = config.IQR_K_NORMAL,
) -> Tuple[pd.Series, float, float]:
    """
    Returns (bool_mask_is_outlier, lower_fence, upper_fence).
    True in mask = outlier.
    Uses Tukey IQR fences: Q1 - k*IQR and Q3 + k*IQR.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    mask = (series < lower) | (series > upper)
    return mask, float(lower), float(upper)


def refresh_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-compute outlier_auto for all rows based on duree_totale_min.
    Returns df with updated outlier_auto and is_outlier columns.
    """
    if df.empty:
        return df
    mask, lower, upper = detecte_outliers_iqr(df["duree_totale_min"])
    df = df.copy()
    df["outlier_auto"] = mask.astype(int)
    df["is_outlier"] = df.apply(
        lambda row: int(row["outlier_manuel"])
        if row["outlier_manuel"] is not None and not pd.isna(row["outlier_manuel"])
        else int(row["outlier_auto"]),
        axis=1,
    )
    df.attrs["iqr_lower"] = lower
    df.attrs["iqr_upper"] = upper
    return df


# ─────────────────────────────────────────────────────────────
#  §6.3 — Predictive model (Ridge regression)
# ─────────────────────────────────────────────────────────────

_MODEL_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_ridge.joblib")


def _prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Build feature matrix X and target y from the dataframe."""
    from sklearn.preprocessing import label_binarize

    df = df.copy()
    # Circadian-adjusted bedtime
    df["heure_coucher_min"] = df["heure_coucher"].apply(
        lambda t: sum(int(x) * m for x, m in zip(t.split(":"), [60, 1]))
    )
    df["coucher_adj"] = df["heure_coucher_min"].apply(
        lambda m: m - 1440 if m > 720 else m
    )

    base_features = ["duree_totale_min", "coucher_adj", "cycles_estimes"]
    df_feat = df[base_features].copy()

    # One-hot encode type_nuit (drop first to avoid dummy trap)
    dummies = pd.get_dummies(df["type_nuit"], prefix="type", drop_first=True)
    df_feat = pd.concat([df_feat, dummies], axis=1)

    # Optional: score_circadien
    if "score_circadien" in df.columns and df["score_circadien"].notna().sum() > 0:
        df_feat["score_circadien"] = df["score_circadien"].fillna(0.6)

    y = df["qualite_reveil"]
    return df_feat, y


def train_model(df: pd.DataFrame) -> Optional[ModelMetrics]:
    """
    Train Ridge regression model if conditions are met.
    Saves model to disk, returns ModelMetrics or None.
    """
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_squared_error
    from sklearn.model_selection import KFold, LeaveOneOut, cross_val_predict
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    import joblib

    df_clean = df[(df["is_outlier"] == 0) & df["qualite_reveil"].notna()].copy()
    n = len(df_clean)

    if n < config.N_MIN_MODELE:
        return None

    X, y = _prepare_features(df_clean)
    X = X.fillna(0)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=config.RIDGE_ALPHA)),
    ])

    if n < config.LOOCV_THRESHOLD:
        cv = LeaveOneOut()
        method = "LOOCV"
    else:
        cv = KFold(n_splits=config.KFOLD_K, shuffle=True, random_state=42)
        method = f"KFold-{config.KFOLD_K}"

    y_pred = cross_val_predict(pipeline, X, y, cv=cv)
    ss_res = np.sum((y.values - y_pred) ** 2)
    ss_tot = np.sum((y.values - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
    rmse = math.sqrt(float(np.mean((y.values - y_pred) ** 2)))

    # Fit final model on all data
    pipeline.fit(X, y)
    joblib.dump({"pipeline": pipeline, "feature_names": list(X.columns)}, _MODEL_PATH)

    trained_at = datetime.datetime.now().isoformat(timespec="seconds")
    interpretations = interprete_coefficients(pipeline, list(X.columns))

    return ModelMetrics(
        r2_cv=round(r2, 3),
        rmse_cv=round(rmse, 3),
        method=method,
        n_samples=n,
        trained_at=trained_at,
        interpretations=interpretations,
    )


def load_model():
    """Load saved pipeline from disk. Returns dict or None."""
    import joblib
    if os.path.exists(_MODEL_PATH):
        try:
            return joblib.load(_MODEL_PATH)
        except Exception:
            return None
    return None


def interprete_coefficients(pipeline, feature_names: List[str]) -> List[str]:
    """
    Extract Ridge coefficients after de-normalisation and generate
    natural language interpretation sentences for significant ones.
    """
    try:
        scaler = pipeline.named_steps["scaler"]
        ridge = pipeline.named_steps["ridge"]
        coefs_raw = ridge.coef_
        # De-normalise: coef_raw / scale_ gives the effective coefficient
        scales = scaler.scale_
        coefs = {name: coefs_raw[i] / scales[i]
                 for i, name in enumerate(feature_names)}
    except Exception:
        return []

    sentences = []
    threshold = config.COEF_SIGNIFICANCE_THRESHOLD

    labels = {
        "duree_totale_min": ("Longer total sleep", "Shorter total sleep"),
        "coucher_adj": ("Later bedtime", "Earlier bedtime"),
        "cycles_estimes": ("More cycles", "Fewer cycles"),
        "score_circadien": ("Sleeping in your optimal window", "Sleeping outside your optimal window"),
    }

    for name, val in coefs.items():
        if abs(val) < threshold:
            continue
        direction = val > 0
        if name in labels:
            pos_label, neg_label = labels[name]
            subject = pos_label if direction else neg_label
            effect = "better" if direction else "worse"
            sentences.append(f"→ {subject} is associated with {effect} wake quality.")
        elif name.startswith("type_"):
            type_name = name.replace("type_", "")
            effect = "better" if direction else "worse"
            sentences.append(
                f"→ Night type '{type_name}' is associated with {effect} wake quality."
            )

    return sentences


# ─────────────────────────────────────────────────────────────
#  §6.4 — Circadian rhythm discovery
# ─────────────────────────────────────────────────────────────


def _hhmm_to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _coucher_adj(coucher_min: int) -> int:
    """Circadian-adjusted bedtime: late/early times stay continuous."""
    return coucher_min - 1440 if coucher_min > 720 else coucher_min


def _min_to_hhmm(minutes: int) -> str:
    minutes = minutes % 1440
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}h{m:02d}"


def fenetre_circadienne_optimale(df: pd.DataFrame) -> Optional[FenetreCircadienne]:
    """
    Discover optimal bedtime window from personal data.
    Returns FenetreCircadienne or None if insufficient data.
    """
    df_clean = df[(df["is_outlier"] == 0) & df["qualite_reveil"].notna()].copy()
    n = len(df_clean)

    if n < config.N_MIN_CIRCADIEN:
        return None

    df_clean["coucher_min"] = df_clean["heure_coucher"].apply(_hhmm_to_min)
    df_clean["coucher_adj"] = df_clean["coucher_min"].apply(_coucher_adj)

    adj_values = df_clean["coucher_adj"].values
    adj_min = int(np.min(adj_values))
    adj_max = int(np.max(adj_values))

    W = config.CIRCADIAN_WINDOW_WIDTH_MIN
    step = config.CIRCADIAN_WINDOW_STEP_MIN
    pct75 = float(np.percentile(df_clean["qualite_reveil"].dropna(), config.CIRCADIAN_WINDOW_PERCENTILE))

    good_windows: List[Tuple[int, int, float, int]] = []  # (start, end, mean_q, n)

    start = adj_min
    while start + W <= adj_max + W:
        end = start + W
        mask = (df_clean["coucher_adj"] >= start) & (df_clean["coucher_adj"] < end)
        subset = df_clean[mask]
        if len(subset) >= config.N_MIN_WINDOW_FILL:
            mean_q = float(subset["qualite_reveil"].mean())
            if mean_q >= pct75:
                good_windows.append((start, end, mean_q, len(subset)))
        start += step

    if not good_windows:
        return None

    # Merge contiguous windows
    good_windows.sort(key=lambda x: x[0])
    merged = []
    cur_start, cur_end, cur_q_sum, cur_n = good_windows[0]
    cur_q_sum *= cur_n

    for ws, we, wq, wn in good_windows[1:]:
        if ws <= cur_end + config.CIRCADIAN_WINDOW_GAP_MERGE_MIN:
            cur_end = max(cur_end, we)
            cur_q_sum += wq * wn
            cur_n += wn
        else:
            merged.append((cur_start, cur_end, cur_q_sum / cur_n, cur_n))
            cur_start, cur_end, cur_q_sum, cur_n = ws, we, wq * wn, wn

    merged.append((cur_start, cur_end, cur_q_sum / cur_n, cur_n))

    # Pick widest range
    best = max(merged, key=lambda x: x[1] - x[0])
    debut, fin, qualite_moy, n_win = best

    # IC95 on the nights in the window
    mask_win = (df_clean["coucher_adj"] >= debut) & (df_clean["coucher_adj"] < fin)
    qualites_in = df_clean[mask_win]["qualite_reveil"].dropna().values.astype(float)
    ic = _ci95(qualites_in) if len(qualites_in) >= 2 else None

    label = f"{_min_to_hhmm(debut)} – {_min_to_hhmm(fin)}"

    return FenetreCircadienne(
        debut=debut,
        fin=fin,
        qualite_moy=round(qualite_moy, 2),
        n=n_win,
        ic95=ic,
        label=label,
    )


def calcule_score_circadien(
    coucher_min: int,
    fenetre: FenetreCircadienne,
) -> float:
    """
    Compute the circadian score for a given bedtime given a known window.
    score = 1.0 if inside, else max(0.4, 1 - |dist| / 120)
    """
    adj = _coucher_adj(coucher_min)
    centre = (fenetre.debut + fenetre.fin) / 2
    if fenetre.debut <= adj <= fenetre.fin:
        return config.CIRCADIAN_SCORE_INNER
    dist = abs(adj - centre)
    return max(
        config.CIRCADIAN_SCORE_FLOOR,
        config.CIRCADIAN_SCORE_INNER - dist / config.CIRCADIAN_SCORE_DECAY_DENOMINATOR,
    )


def refresh_scores_circadiens(df: pd.DataFrame, fenetre: FenetreCircadienne) -> List[Tuple]:
    """
    Compute score_circadien for all rows. Returns list of (score, id) tuples.
    """
    results = []
    for _, row in df.iterrows():
        coucher_min = _hhmm_to_min(row["heure_coucher"])
        score = calcule_score_circadien(coucher_min, fenetre)
        results.append((score, int(row["id"])))
    return results


# ─────────────────────────────────────────────────────────────
#  §6.5 — Wake planner
# ─────────────────────────────────────────────────────────────


def planifie_reveil(
    heure_coucher: str,
    cycle_moy: Optional[float],
    endormissement: float = config.ENDORMISSEMENT_MIN,
    marge: float = config.PLANNER_MARGE_MIN,
    fenetre: Optional[FenetreCircadienne] = None,
) -> Tuple[List[PlanReveil], bool]:
    """
    Returns (list_of_PlanReveil, approximation_used).
    approximation_used = True when cycle_moy was None (90 min used).
    """
    approx = cycle_moy is None
    effective_cycle = cycle_moy if cycle_moy is not None else config.TARGET_CYCLE_MIN

    coucher_m = _hhmm_to_min(heure_coucher)
    coucher_adj = _coucher_adj(coucher_m)

    results = []
    for n in range(1, config.MAX_CYCLES + 1):
        duree_th = endormissement + n * effective_cycle
        reveil_m = coucher_m + int(duree_th)
        reveil_min_m = reveil_m - int(marge)
        reveil_max_m = reveil_m + int(marge)

        # Check if bedtime is in the circadian window
        dans_fenetre = None
        if fenetre is not None:
            dans_fenetre = fenetre.debut <= coucher_adj <= fenetre.fin

        results.append(
            PlanReveil(
                cycles=n,
                duree_min=int(duree_th),
                heure_theorique=_min_to_hhmm(reveil_m).replace("h", ":"),
                fenetre_min=_min_to_hhmm(reveil_min_m).replace("h", ":"),
                fenetre_max=_min_to_hhmm(reveil_max_m).replace("h", ":"),
                dans_fenetre_circadienne=dans_fenetre,
            )
        )

    return results, approx


# ─────────────────────────────────────────────────────────────
#  Orchestrator — called after each new entry
# ─────────────────────────────────────────────────────────────


def run_full_analytics(df: pd.DataFrame) -> Dict:
    """
    Run the complete analytics pipeline on the full dataset.
    Returns a dict with all results for the UI to display.
    """
    result: Dict = {}

    if df.empty:
        return result

    # Refresh outliers
    df = refresh_outliers(df)
    result["df_refreshed"] = df

    # Descriptive stats
    result["stats"] = stats_descriptives(df)
    result["tendance"] = tendance_7j(df)

    # IQR fences
    if not df.empty:
        _, lower, upper = detecte_outliers_iqr(df["duree_totale_min"])
        result["iqr_lower"] = lower
        result["iqr_upper"] = upper

    # Outlier counts
    df_clean = df[df["is_outlier"] == 0]
    result["n_outlier_auto"] = int(df["outlier_auto"].sum())
    result["n_outlier_manuel"] = int(
        df[df["outlier_manuel"].notna()]["outlier_manuel"].sum()
    )

    # Circadian
    fenetre = fenetre_circadienne_optimale(df)
    result["fenetre"] = fenetre

    if fenetre is not None:
        # Update scores
        score_updates = refresh_scores_circadiens(df, fenetre)
        result["score_updates"] = score_updates

    # Predictive model
    model_metrics = train_model(df)
    result["model"] = model_metrics

    return result
