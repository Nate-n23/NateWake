"""
screens/export.py — NateWake
==============================
Export screen: SQLite copy, CSV, JSON.
"""

from __future__ import annotations

import datetime
import os

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar


def _snack(message: str) -> None:
    """KivyMD 1.2.0-compatible snackbar."""
    from kivymd.uix.label import MDLabel
    sb = Snackbar()
    sb.add_widget(MDLabel(text=message))
    sb.open()
from kivymd.uix.textfield import MDTextField

import config
import db


def _export_dir() -> str:
    """Return a writable export directory."""
    try:
        from android.storage import primary_external_storage_path  # type: ignore
        base = os.path.join(primary_external_storage_path(), "NateWake")
    except ImportError:
        base = os.path.join(os.path.dirname(os.path.abspath(db.DB_PATH)), "exports")
    os.makedirs(base, exist_ok=True)
    return base


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class ExportScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "export"
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="Export Data", elevation=2)
        root.add_widget(toolbar)

        scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(14),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        # Custom path (optional)
        content.add_widget(
            MDLabel(
                text="Export directory (leave blank for default)",
                size_hint_y=None,
                height=dp(22),
            )
        )
        self._tf_dir = MDTextField(
            hint_text="e.g. /sdcard/Download",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48),
        )
        content.add_widget(self._tf_dir)

        # Status label
        self._lbl_status = MDLabel(
            text="", size_hint_y=None, height=dp(28), theme_text_color="Hint"
        )
        content.add_widget(self._lbl_status)

        # Export buttons
        for label, desc, cb in [
            (
                "Export SQLite (.db)",
                "Full database copy — import into any SQLite browser.",
                self._export_sqlite,
            ),
            (
                "Export CSV",
                "All nights including outliers. Compatible with spreadsheets.",
                self._export_csv,
            ),
            (
                "Export JSON",
                "Full data with metadata (app_version, export_timestamp).",
                self._export_json,
            ),
        ]:
            card = MDCard(
                orientation="vertical",
                padding=dp(12),
                size_hint_y=None,
                height=dp(90),
                radius=[dp(10)],
                md_bg_color=(0.10, 0.13, 0.17, 1),
            )
            card.add_widget(
                MDLabel(text=label, font_style="Subtitle1", size_hint_y=None, height=dp(28), bold=True)
            )
            card.add_widget(
                MDLabel(text=desc, font_style="Caption", size_hint_y=None, height=dp(20),
                        theme_text_color="Hint")
            )
            card.add_widget(
                MDRaisedButton(
                    text=label,
                    size_hint_y=None,
                    height=dp(36),
                    on_release=cb,
                )
            )
            content.add_widget(card)

        content.add_widget(
            MDLabel(
                text=f"App version: {config.APP_VERSION}",
                font_style="Caption",
                size_hint_y=None,
                height=dp(22),
                theme_text_color="Hint",
            )
        )

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Export actions
    # ──────────────────────────────────────────

    def _get_dir(self) -> str:
        custom = self._tf_dir.text.strip()
        if custom:
            os.makedirs(custom, exist_ok=True)
            return custom
        return _export_dir()

    def _export_sqlite(self, *_):
        try:
            dest = os.path.join(self._get_dir(), f"natewake_{_ts()}.db")
            db.export_db_copy(dest)
            self._lbl_status.text = f"✓ Saved: {dest}"
            _snack(f"SQLite exported → {os.path.basename(dest)}")
        except Exception as e:
            self._lbl_status.text = f"⚠ Error: {e}"

    def _export_csv(self, *_):
        try:
            dest = os.path.join(self._get_dir(), f"natewake_{_ts()}.csv")
            db.export_all_csv(dest)
            self._lbl_status.text = f"✓ Saved: {dest}"
            _snack(f"CSV exported → {os.path.basename(dest)}")
        except Exception as e:
            self._lbl_status.text = f"⚠ Error: {e}"

    def _export_json(self, *_):
        try:
            dest = os.path.join(self._get_dir(), f"natewake_{_ts()}.json")
            db.export_all_json(dest)
            self._lbl_status.text = f"✓ Saved: {dest}"
            _snack(f"JSON exported → {os.path.basename(dest)}")
        except Exception as e:
            self._lbl_status.text = f"⚠ Error: {e}"
