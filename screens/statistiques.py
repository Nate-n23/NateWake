"""
screens/statistiques.py — NateWake
=====================================
Statistics & conclusions screen: descriptive stats, predictive model,
outlier summary, and circadian rhythm discovery.
"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

import analytics
import config
import db
from models import StatsDescriptives


def fmt_dur(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h{m:02d}"


def fmt_ic(ic) -> str:
    if ic is None:
        return "n/a"
    lo, hi = ic
    return f"[{fmt_dur(lo)}, {fmt_dur(hi)}]"


class StatCard(MDCard):
    """A labelled metric card."""

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(12)
        self.spacing = dp(4)
        self.size_hint_y = None
        self.height = dp(90)
        self.radius = [dp(10)]
        self.md_bg_color = (0.10, 0.12, 0.17, 1)

        self._title = MDLabel(
            text=title,
            font_style="Caption",
            size_hint_y=None,
            height=dp(18),
            theme_text_color="Secondary",
        )
        self._value = MDLabel(
            text="—",
            font_style="H6",
            size_hint_y=None,
            height=dp(32),
            bold=True,
        )
        self._sub = MDLabel(
            text="",
            font_style="Caption",
            size_hint_y=None,
            height=dp(18),
            theme_text_color="Hint",
        )
        for w in [self._title, self._value, self._sub]:
            self.add_widget(w)

    def update(self, value: str, sub: str = ""):
        self._value.text = value
        self._sub.text = sub


class SectionHeader(MDLabel):
    def __init__(self, text: str, **kwargs):
        super().__init__(
            text=text,
            font_style="H6",
            size_hint_y=None,
            height=dp(36),
            bold=True,
            **kwargs,
        )


class StatistiquesScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "statistiques"
        self._build_ui()

    # ──────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="Statistics", elevation=2)
        root.add_widget(toolbar)

        scroll = ScrollView()
        self._content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
            size_hint_y=None,
        )
        self._content.bind(minimum_height=self._content.setter("height"))
        scroll.add_widget(self._content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        self._content.clear_widgets()
        df = db.get_all_nuits_df()

        if df.empty:
            self._content.add_widget(
                MDLabel(
                    text="No sleep data yet. Log your first night on the home screen.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(80),
                )
            )
            return

        df = analytics.refresh_outliers(df)
        stats = analytics.stats_descriptives(df)
        tendance = analytics.tendance_7j(df)
        _, iqr_lower, iqr_upper = analytics.detecte_outliers_iqr(df["duree_totale_min"])
        n_outlier_auto = int(df["outlier_auto"].sum())
        n_outlier_man = int(df[df["outlier_manuel"].notna()]["outlier_manuel"].fillna(0).sum())
        fenetre = analytics.fenetre_circadienne_optimale(df)

        # ─── Section A: Descriptive stats ───
        self._content.add_widget(SectionHeader("A — Sleep metrics"))
        self._render_section_a(stats, tendance)

        # ─── Section B: Personal wake windows ───
        self._content.add_widget(SectionHeader("B — Personal wake windows"))
        self._render_section_b(stats)

        # ─── Section C: Predictive model ───
        self._content.add_widget(SectionHeader("C — Predictive model"))
        self._render_section_c(df)

        # ─── Section D: Outliers ───
        self._content.add_widget(SectionHeader("D — Outliers"))
        self._render_section_d(df, n_outlier_auto, n_outlier_man, iqr_lower, iqr_upper)

        # ─── Section E: Circadian rhythm ───
        self._content.add_widget(SectionHeader("E — Personal circadian rhythm"))
        self._render_section_e(df, fenetre)

    # ──────────────────────────────────────────
    #  Section A
    # ──────────────────────────────────────────

    def _render_section_a(self, stats: StatsDescriptives | None, tendance):
        if stats is None:
            self._content.add_widget(
                MDLabel(
                    text="Not enough data yet.",
                    size_hint_y=None,
                    height=dp(30),
                )
            )
            return

        grid = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(100), spacing=dp(8)
        )

        # Duration card
        dur_sub = f"IC95: {fmt_ic(stats.duree_ic95)}" if stats.duree_ic95 else ""
        c1 = StatCard(title="Avg duration")
        c1.update(fmt_dur(stats.duree_moy), dur_sub)
        grid.add_widget(c1)

        # Cycle card
        cyc_sub = (
            f"IC95: [{stats.cycle_ic95[0]:.0f}, {stats.cycle_ic95[1]:.0f}] min"
            if stats.cycle_ic95 else ""
        )
        c2 = StatCard(title="Avg cycle")
        c2.update(f"{stats.cycle_moy:.0f} min", cyc_sub)
        grid.add_widget(c2)

        self._content.add_widget(grid)

        grid2 = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(100), spacing=dp(8)
        )
        c3 = StatCard(title="Cycles / night")
        c3.update(f"{stats.cycles_par_nuit_moy:.1f}", f"from {stats.n} nights")
        grid2.add_widget(c3)

        c4 = StatCard(title="Avg wake quality")
        qual_val = f"{stats.qualite_moy:.2f}/2" if stats.qualite_moy is not None else "—"
        c4.update(qual_val)
        grid2.add_widget(c4)
        self._content.add_widget(grid2)

        # Trend
        if tendance:
            arrow = {"up": "↑", "down": "↓", "stable": "→"}[tendance["direction"]]
            color = {"up": "00cc55", "down": "ff5555", "stable": "aaaaaa"}[tendance["direction"]]
            self._content.add_widget(
                MDLabel(
                    text=f"[b]7-day trend:[/b] [color={color}]{arrow} {tendance['delta']:+.0f} min[/color]",
                    markup=True,
                    size_hint_y=None,
                    height=dp(28),
                )
            )

    # ──────────────────────────────────────────
    #  Section B
    # ──────────────────────────────────────────

    def _render_section_b(self, stats: StatsDescriptives | None):
        from analytics import planifie_reveil

        cycle_moy = stats.cycle_moy if stats and stats.n >= config.N_MIN_CYCLE_PERSO else None
        plans, approx = planifie_reveil("00:00", cycle_moy)

        if approx:
            self._content.add_widget(
                MDLabel(
                    text=f"⚠ Using default 90 min cycle (need {config.N_MIN_CYCLE_PERSO} nights for personalised data).",
                    size_hint_y=None,
                    height=dp(32),
                    theme_text_color="Error",
                )
            )

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24))
        for col in ["Cycles", "Duration", "Window"]:
            header.add_widget(MDLabel(text=col, bold=True, size_hint_x=1 / 3))
        self._content.add_widget(header)

        for p in plans:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))
            row.add_widget(MDLabel(text=str(p.cycles), size_hint_x=1 / 3))
            row.add_widget(MDLabel(text=fmt_dur(p.duree_min), size_hint_x=1 / 3))
            row.add_widget(
                MDLabel(text=f"{p.fenetre_min} – {p.fenetre_max}", size_hint_x=1 / 3)
            )
            self._content.add_widget(row)

    # ──────────────────────────────────────────
    #  Section C
    # ──────────────────────────────────────────

    def _render_section_c(self, df):
        df_clean = df[(df["is_outlier"] == 0) & df["qualite_reveil"].notna()]
        n = len(df_clean)

        if n < config.N_MIN_MODELE:
            remaining = config.N_MIN_MODELE - n
            self._content.add_widget(
                MDLabel(
                    text=f"Model not available yet — {remaining} more night(s) with quality logged needed (minimum {config.N_MIN_MODELE}).",
                    size_hint_y=None,
                    height=dp(40),
                    theme_text_color="Hint",
                )
            )
            return

        # Try to load a cached model or retrain
        import analytics
        cached = analytics.load_model()
        if cached is None:
            metrics = analytics.train_model(df)
        else:
            # Reuse cached; compute metrics
            metrics = analytics.train_model(df)

        if metrics is None:
            self._content.add_widget(
                MDLabel(text="Model training failed.", size_hint_y=None, height=dp(30))
            )
            return

        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(160 + len(metrics.interpretations) * 28),
            radius=[dp(10)],
            md_bg_color=(0.10, 0.14, 0.20, 1),
        )
        card.add_widget(
            MDLabel(
                text=f"Reliability: R² = {metrics.r2_cv:.3f}  ·  RMSE = {metrics.rmse_cv:.3f}",
                font_style="Subtitle1",
                size_hint_y=None,
                height=dp(28),
                bold=True,
            )
        )
        card.add_widget(
            MDLabel(
                text=f"Method: {metrics.method}  ·  n = {metrics.n_samples}",
                font_style="Caption",
                size_hint_y=None,
                height=dp(20),
            )
        )
        card.add_widget(
            MDLabel(
                text=f"Last trained: {metrics.trained_at}",
                font_style="Caption",
                size_hint_y=None,
                height=dp(20),
                theme_text_color="Hint",
            )
        )
        if metrics.interpretations:
            card.add_widget(
                MDLabel(
                    text="Key findings:",
                    font_style="Subtitle2",
                    size_hint_y=None,
                    height=dp(24),
                )
            )
            for line in metrics.interpretations:
                card.add_widget(
                    MDLabel(
                        text=line,
                        font_style="Caption",
                        size_hint_y=None,
                        height=dp(22),
                    )
                )
        self._content.add_widget(card)

    # ──────────────────────────────────────────
    #  Section D
    # ──────────────────────────────────────────

    def _render_section_d(self, df, n_auto, n_man, iqr_lower, iqr_upper):
        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(110),
            radius=[dp(10)],
            md_bg_color=(0.14, 0.10, 0.10, 1),
        )
        card.add_widget(
            MDLabel(
                text=f"Auto-detected: {n_auto}  ·  Manual overrides: {n_man}",
                size_hint_y=None,
                height=dp(28),
            )
        )
        card.add_widget(
            MDLabel(
                text=f"IQR lower fence: {iqr_lower:.0f} min ({fmt_dur(iqr_lower)})",
                font_style="Caption",
                size_hint_y=None,
                height=dp(22),
            )
        )
        card.add_widget(
            MDLabel(
                text=f"IQR upper fence: {iqr_upper:.0f} min ({fmt_dur(iqr_upper)})",
                font_style="Caption",
                size_hint_y=None,
                height=dp(22),
            )
        )
        view_btn = MDFlatButton(
            text="View outliers in history →",
            size_hint_y=None,
            height=dp(36),
            on_release=self._go_to_outliers,
        )
        card.add_widget(view_btn)
        self._content.add_widget(card)

    def _go_to_outliers(self, *_):
        hist = self.manager.get_screen("historique")
        hist._outlier_only = True
        hist._outlier_switch.active = True
        hist.reload()
        self.manager.current = "historique"

    # ──────────────────────────────────────────
    #  Section E
    # ──────────────────────────────────────────

    def _render_section_e(self, df, fenetre):
        df_clean = df[(df["is_outlier"] == 0) & df["qualite_reveil"].notna()]
        n = len(df_clean)

        if n < config.N_MIN_CIRCADIEN:
            remaining = config.N_MIN_CIRCADIEN - n
            self._content.add_widget(
                MDLabel(
                    text=f"Insufficient data — {remaining} more night(s) needed before circadian analysis ({config.N_MIN_CIRCADIEN} required).",
                    size_hint_y=None,
                    height=dp(40),
                    theme_text_color="Hint",
                )
            )
            return

        if fenetre is None:
            self._content.add_widget(
                MDLabel(
                    text="No consistent optimal window found yet. Keep logging!",
                    size_hint_y=None,
                    height=dp(36),
                )
            )
            return

        ic_str = (
            f"[{fenetre.ic95[0]:.2f}, {fenetre.ic95[1]:.2f}]" if fenetre.ic95 else "n/a"
        )

        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(140),
            radius=[dp(10)],
            md_bg_color=(0.08, 0.14, 0.18, 1),
        )
        card.add_widget(
            MDLabel(
                text=f"Optimal bedtime window: {fenetre.label}",
                font_style="H6",
                size_hint_y=None,
                height=dp(32),
                bold=True,
            )
        )
        card.add_widget(
            MDLabel(
                text=f"Based on {fenetre.n} nights  ·  avg quality {fenetre.qualite_moy:.2f}/2  ·  IC95 {ic_str}",
                font_style="Caption",
                size_hint_y=None,
                height=dp(22),
            )
        )

        # Compare last 7 nights to window
        recent = df_clean.tail(7).copy()
        recent["coucher_min"] = recent["heure_coucher"].apply(
            lambda t: sum(int(x) * m for x, m in zip(t.split(":"), [60, 1]))
        )
        recent["coucher_adj"] = recent["coucher_min"].apply(
            lambda m: m - 1440 if m > 720 else m
        )
        n_in = int(
            ((recent["coucher_adj"] >= fenetre.debut) & (recent["coucher_adj"] <= fenetre.fin)).sum()
        )
        card.add_widget(
            MDLabel(
                text=f"Last 7 nights: {n_in}/7 within the optimal window",
                size_hint_y=None,
                height=dp(24),
                font_style="Subtitle2",
            )
        )
        self._content.add_widget(card)
