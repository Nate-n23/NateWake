"""
main.py — NateWake Sleep Journal
===================================
Kivy / KivyMD entry point.
Sets up the dark theme, bottom navigation, screen manager, and DB init.
"""

from __future__ import annotations

# Kivy config must be set before any kivy imports
import os
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager

import db
from screens.saisie import SaisieScreen
from screens.historique import HistoriqueScreen
from screens.statistiques import StatistiquesScreen
from screens.planificateur import PlanificateurScreen
from screens.import_csv import ImportCSVScreen
from screens.export import ExportScreen


# ─────────────────────────────────────────────────────────────
#  KV string — bottom navigation shell
# ─────────────────────────────────────────────────────────────

KV = """
MDBoxLayout:
    orientation: "vertical"

    MDScreenManager:
        id: screen_manager

    MDBottomNavigation:
        id: bottom_nav
        panel_color: 0.08, 0.09, 0.12, 1
        text_color_active: 0.3, 0.85, 0.55, 1
        text_color_normal: 0.55, 0.55, 0.6, 1
        selected_color_background: 0.12, 0.18, 0.14, 1

        MDBottomNavigationItem:
            name: "tab_saisie"
            text: "Log"
            icon: "moon-waning-crescent"
            on_tab_press: app.go_to("saisie")

        MDBottomNavigationItem:
            name: "tab_historique"
            text: "History"
            icon: "calendar-month-outline"
            on_tab_press: app.go_to("historique")

        MDBottomNavigationItem:
            name: "tab_stats"
            text: "Stats"
            icon: "chart-line"
            on_tab_press: app.go_to("statistiques")

        MDBottomNavigationItem:
            name: "tab_planner"
            text: "Planner"
            icon: "alarm"
            on_tab_press: app.go_to("planificateur")

        MDBottomNavigationItem:
            name: "tab_import"
            text: "Import"
            icon: "file-import-outline"
            on_tab_press: app.go_to("import_csv")

        MDBottomNavigationItem:
            name: "tab_export"
            text: "Export"
            icon: "database-export-outline"
            on_tab_press: app.go_to("export")
"""


# ─────────────────────────────────────────────────────────────
#  App
# ─────────────────────────────────────────────────────────────

class NateWakeApp(MDApp):
    """Root application class."""

    def build(self):
        # ── Theme ──
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.primary_hue = "400"
        self.theme_cls.accent_palette = "Cyan"

        # ── Database ──
        db.init_db()

        # ── Root widget from KV ──
        root = Builder.load_string(KV)
        self._sm: MDScreenManager = root.ids.screen_manager

        # Register screens
        screens = [
            SaisieScreen(),
            HistoriqueScreen(),
            StatistiquesScreen(),
            PlanificateurScreen(),
            ImportCSVScreen(),
            ExportScreen(),
        ]
        for screen in screens:
            self._sm.add_widget(screen)

        self._sm.current = "saisie"
        return root

    def go_to(self, screen_name: str):
        """Switch the active screen."""
        self._sm.current = screen_name

    def on_start(self):
        """Called after build(). Good place for deferred analytics warm-up."""
        from kivy.clock import Clock
        Clock.schedule_once(self._warm_up_analytics, 1.5)

    def _warm_up_analytics(self, dt):
        """Load and cache the model on first launch if data is available."""
        try:
            import analytics
            df = db.get_all_nuits_df()
            if df.empty:
                return
            df_refreshed = analytics.refresh_outliers(df)
            cached = analytics.load_model()
            if cached is None:
                analytics.train_model(df_refreshed)
        except Exception as e:
            print(f"[warm-up] analytics error: {e}")


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    NateWakeApp().run()
