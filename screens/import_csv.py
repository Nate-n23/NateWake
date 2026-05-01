"""
screens/import_csv.py — NateWake
===================================
CSV import screen: Sleep as Android and Sleep Cycle.
Shows preview, handles duplicates.
"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
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

import db
from importers import (
    ImportResult,
    parse_sleep_as_android,
    parse_sleep_cycle,
    resolve_duplicates,
)
from models import Nuit


class ImportCSVScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "import_csv"
        self._pending_result: ImportResult | None = None
        self._pending_source: str = ""
        self._build_ui()

    # ──────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="Import CSV", elevation=2)
        root.add_widget(toolbar)

        scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(14),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        # ── File path field ──
        content.add_widget(
            MDLabel(text="CSV file path", size_hint_y=None, height=dp(22))
        )
        self._tf_path = MDTextField(
            hint_text="/sdcard/Download/sleep_export.csv",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48),
        )
        content.add_widget(self._tf_path)

        # ── Source buttons ──
        btn_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(10)
        )
        btn_saa = MDRaisedButton(
            text="Sleep as Android",
            size_hint_x=0.5,
            on_release=lambda _: self._load_file("sleep_as_android"),
        )
        btn_sc = MDRaisedButton(
            text="Sleep Cycle",
            size_hint_x=0.5,
            on_release=lambda _: self._load_file("sleep_cycle"),
        )
        btn_row.add_widget(btn_saa)
        btn_row.add_widget(btn_sc)
        content.add_widget(btn_row)

        # ── Status / errors ──
        self._lbl_status = MDLabel(
            text="", size_hint_y=None, height=dp(30), theme_text_color="Hint"
        )
        content.add_widget(self._lbl_status)

        # ── Preview table ──
        content.add_widget(
            MDLabel(text="Preview (first 5 rows)", size_hint_y=None, height=dp(22), bold=True)
        )
        self._preview_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4)
        )
        self._preview_box.bind(minimum_height=self._preview_box.setter("height"))
        content.add_widget(self._preview_box)

        # ── Error list ──
        self._error_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2)
        )
        self._error_box.bind(minimum_height=self._error_box.setter("height"))
        content.add_widget(self._error_box)

        # ── Confirm import button ──
        self._btn_import = MDRaisedButton(
            text="Import all entries",
            size_hint_y=None,
            height=dp(52),
            md_bg_color=(0.18, 0.55, 0.34, 1),
            disabled=True,
            on_release=self._confirm_import,
        )
        content.add_widget(self._btn_import)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Load / parse
    # ──────────────────────────────────────────

    def _load_file(self, source: str):
        path = self._tf_path.text.strip()
        if not path:
            self._lbl_status.text = "⚠ Please enter the file path."
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except FileNotFoundError:
            self._lbl_status.text = f"⚠ File not found: {path}"
            return
        except Exception as e:
            self._lbl_status.text = f"⚠ Read error: {e}"
            return

        if source == "sleep_as_android":
            result = parse_sleep_as_android(content)
        else:
            result = parse_sleep_cycle(content)

        self._pending_result = result
        self._pending_source = source
        self._render_preview(result)

    def _render_preview(self, result: ImportResult):
        self._preview_box.clear_widgets()
        self._error_box.clear_widgets()

        self._lbl_status.text = (
            f"Found {len(result.nuits)} entries  ·  {len(result.errors)} errors"
        )

        if result.preview_rows:
            # Header
            h = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(22))
            for col in result.preview_rows[0].keys():
                h.add_widget(
                    MDLabel(text=col, bold=True, font_style="Caption",
                            size_hint_x=1 / len(result.preview_rows[0]))
                )
            self._preview_box.add_widget(h)

            for row in result.preview_rows:
                r = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(22))
                for v in row.values():
                    r.add_widget(
                        MDLabel(text=str(v), font_style="Caption",
                                size_hint_x=1 / len(row))
                    )
                self._preview_box.add_widget(r)

        for err in result.errors[:10]:
            self._error_box.add_widget(
                MDLabel(
                    text=f"[color=ff6b6b]{err}[/color]",
                    markup=True,
                    font_style="Caption",
                    size_hint_y=None,
                    height=dp(20),
                )
            )

        self._btn_import.disabled = len(result.nuits) == 0

    # ──────────────────────────────────────────
    #  Import with duplicate handling
    # ──────────────────────────────────────────

    def _confirm_import(self, *_):
        if not self._pending_result:
            return

        # Find existing dates
        all_df = db.get_all_nuits_df()
        existing_dates = set(all_df["date"].tolist()) if not all_df.empty else set()

        nuits = self._pending_result.nuits
        duplicates = [n for n in nuits if n.date in existing_dates]

        if not duplicates:
            self._do_import(nuits, [], [])
            return

        dialog = MDDialog(
            title=f"{len(duplicates)} duplicate date(s) found",
            text="Some entries already exist in your journal. What should we do?",
            buttons=[
                MDFlatButton(
                    text="Cancel",
                    on_release=lambda _: dialog.dismiss(),
                ),
                MDFlatButton(
                    text="Skip duplicates",
                    on_release=lambda _: self._resolve_and_import(
                        dialog, existing_dates, "ignore"
                    ),
                ),
                MDRaisedButton(
                    text="Replace duplicates",
                    on_release=lambda _: self._resolve_and_import(
                        dialog, existing_dates, "replace"
                    ),
                ),
            ],
        )
        dialog.open()

    def _resolve_and_import(self, dialog, existing_dates: set, strategy: str):
        dialog.dismiss()
        nuits = self._pending_result.nuits
        to_insert, to_replace, skipped = resolve_duplicates(nuits, existing_dates, strategy)
        self._do_import(to_insert, to_replace, skipped)

    def _do_import(
        self,
        to_insert: list,
        to_replace: list,
        skipped: list,
    ):
        inserted = 0
        replaced = 0
        errors = []

        for nuit in to_insert:
            try:
                db.insert_nuit(nuit)
                inserted += 1
            except Exception as e:
                errors.append(str(e))

        for nuit in to_replace:
            try:
                existing = db.get_nuit_by_date(nuit.date)
                if existing:
                    nuit.id = existing.id
                    db.update_nuit(nuit)
                    replaced += 1
            except Exception as e:
                errors.append(str(e))

        msg = f"✓ {inserted} inserted, {replaced} replaced, {len(skipped)} skipped."
        if errors:
            msg += f" {len(errors)} errors."
        _snack(msg)

        self._btn_import.disabled = True
        self._pending_result = None
        self._lbl_status.text = msg

        # Trigger analytics refresh
        try:
            import analytics
            df = db.get_all_nuits_df()
            result = analytics.run_full_analytics(df)
            if "df_refreshed" in result:
                df_r = result["df_refreshed"]
                updates = [
                    (int(row["outlier_auto"]), row.get("score_circadien"), int(row["id"]))
                    for _, row in df_r.iterrows()
                ]
                db.update_outlier_scores(updates)
                db.update_is_outlier_column()
        except Exception as e:
            print(f"[analytics] post-import error: {e}")
