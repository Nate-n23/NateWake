"""
screens/planificateur.py — NateWake
======================================
Wake planner: enter a planned bedtime, get a table of ideal
wake windows for 1–6 cycles using your personal cycle mean.
"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

import analytics
import config
import db


def fmt_dur(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h}h{m:02d}"


class PlanificateurScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "planificateur"
        self._build_ui()

    # ──────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="Wake Planner", elevation=2)
        root.add_widget(toolbar)

        scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        # Planned bedtime
        content.add_widget(
            MDLabel(text="Planned bedtime (HH:MM)", size_hint_y=None, height=dp(24))
        )
        self._tf_coucher = MDTextField(
            hint_text="e.g. 23:00",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48),
        )
        content.add_widget(self._tf_coucher)

        self._btn_calc = MDRaisedButton(
            text="Calculate wake windows",
            size_hint_y=None,
            height=dp(48),
            md_bg_color=(0.18, 0.45, 0.7, 1),
            on_release=self._calculate,
        )
        content.add_widget(self._btn_calc)

        # Warning / info label
        self._lbl_info = MDLabel(
            text="",
            size_hint_y=None,
            height=dp(32),
            theme_text_color="Hint",
        )
        content.add_widget(self._lbl_info)

        # Cycle info
        self._lbl_cycle = MDLabel(
            text="",
            size_hint_y=None,
            height=dp(28),
            font_style="Subtitle2",
        )
        content.add_widget(self._lbl_cycle)

        # Table header
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24))
        for col in ["Cycles", "Duration", "Wake window", "Circ. window?"]:
            header.add_widget(
                MDLabel(text=col, bold=True, size_hint_x=0.25, font_style="Caption")
            )
        content.add_widget(header)

        # Table rows container
        self._table_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4)
        )
        self._table_box.bind(minimum_height=self._table_box.setter("height"))
        content.add_widget(self._table_box)

        # Circadian note
        self._lbl_circ = MDLabel(
            text="",
            size_hint_y=None,
            height=dp(32),
            theme_text_color="Hint",
            font_style="Caption",
        )
        content.add_widget(self._lbl_circ)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Calculation
    # ──────────────────────────────────────────

    def _calculate(self, *_):
        import re

        coucher = self._tf_coucher.text.strip()
        if not re.match(r"^\d{1,2}:\d{2}$", coucher):
            self._lbl_info.text = "⚠ Enter a valid bedtime in HH:MM format."
            return

        self._lbl_info.text = ""
        self._table_box.clear_widgets()

        # Get personal cycle mean
        df = db.get_all_nuits_df()
        cycle_moy = None
        fenetre = None

        if not df.empty:
            df = analytics.refresh_outliers(df)
            stats = analytics.stats_descriptives(df)
            if stats and stats.n >= config.N_MIN_CYCLE_PERSO:
                cycle_moy = stats.cycle_moy

            fenetre = analytics.fenetre_circadienne_optimale(df)

        plans, approx = analytics.planifie_reveil(coucher, cycle_moy, fenetre=fenetre)

        if approx:
            self._lbl_info.text = (
                f"⚠ Personal cycle unavailable (need {config.N_MIN_CYCLE_PERSO}+ non-outlier nights). "
                f"Using 90 min default."
            )
        if cycle_moy:
            self._lbl_cycle.text = f"Your avg cycle: {cycle_moy:.0f} min"
        else:
            self._lbl_cycle.text = "Avg cycle: 90 min (default)"

        if fenetre:
            self._lbl_circ.text = (
                f"Your optimal bedtime window: {fenetre.label}  ·  "
                f"'✓' = your bedtime falls within it."
            )
        else:
            self._lbl_circ.text = (
                f"Circadian window not yet available ({config.N_MIN_CIRCADIEN} nights needed)."
            )

        for p in plans:
            row = MDCard(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(44),
                padding=dp(6),
                radius=[dp(6)],
                md_bg_color=(0.10, 0.13, 0.18, 1),
            )

            # Color code highlights
            bg = (0.10, 0.13, 0.18, 1)
            if p.cycles in [4, 5] and cycle_moy:
                bg = (0.08, 0.18, 0.12, 1)  # green tint for "good" cycle counts
            row.md_bg_color = bg

            row.add_widget(
                MDLabel(text=str(p.cycles), size_hint_x=0.25, font_style="Subtitle1", bold=True)
            )
            row.add_widget(MDLabel(text=fmt_dur(p.duree_min), size_hint_x=0.25))
            row.add_widget(
                MDLabel(
                    text=f"{p.fenetre_min}–{p.fenetre_max}",
                    size_hint_x=0.3,
                )
            )

            # Circadian window indicator
            if p.dans_fenetre_circadienne is True:
                circ_text = "[color=00e676]✓[/color]"
            elif p.dans_fenetre_circadienne is False:
                circ_text = "[color=ff5252]✗[/color]"
            else:
                circ_text = "—"
            row.add_widget(
                MDLabel(text=circ_text, markup=True, size_hint_x=0.15, halign="center")
            )

            self._table_box.add_widget(row)

        self._table_box.height = len(plans) * dp(48)
