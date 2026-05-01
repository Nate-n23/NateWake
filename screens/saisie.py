"""
screens/saisie.py — NateWake
==============================
Entry screen: manual sleep data input with real-time recalculation.
"""

from __future__ import annotations

import datetime

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.pickers import MDTimePicker
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.textfield import MDTextField

import analytics
import db
from models import Nuit, TYPE_NUIT_CHOICES, QUALITE_LABELS


def ouvrir_time_picker(champ_cible, callback_apres) -> None:
    picker = MDTimePicker()
    picker.set_time(datetime.datetime.now().time())

    def on_save(instance, time):
        heure = f"{time.hour:02d}:{time.minute:02d}"
        champ_cible.text = heure
        callback_apres(heure)
        picker.unbind(on_save=on_save)  # évite les bindings cumulatifs

    picker.bind(on_save=on_save)
    picker.open()


def _snack(message: str) -> None:
    """Show a KivyMD 1.2.0-compatible snackbar."""
    snackbar = Snackbar()
    snackbar.add_widget(MDLabel(text=message))
    snackbar.open()


# ─── tiny helper to format minutes as XhYY ───
def fmt_dur(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h{m:02d}"


class NocturneWakeRow(BoxLayout):
    """A single nocturnal-wake time row with a TimePicker button and delete button."""

    def __init__(self, on_delete, on_change, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(52)
        self.spacing = dp(4)
        self._on_delete = on_delete
        self._on_change = on_change
        self._value: str = ""

        self._btn = MDRaisedButton(
            text="Tap to set time",
            size_hint_x=0.82,
            md_bg_color=(0.15, 0.18, 0.24, 1),
            on_release=self._open_picker,
        )
        self.add_widget(self._btn)

        del_btn = MDIconButton(
            icon="close-circle-outline",
            on_release=lambda _: self._on_delete(self),
        )
        self.add_widget(del_btn)

    def _open_picker(self, *_):
        ouvrir_time_picker(self._btn, self._on_pick)

    def _on_pick(self, heure: str):
        self._value = heure
        self._on_change()

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str):
        self._value = v
        self._btn.text = v if v else "Tap to set time"


class QualiteToggle(BoxLayout):
    """Three-button toggle for wake quality."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(52)
        self.spacing = dp(6)
        self._selected: int | None = None
        self._buttons = []

        labels = {0: "😴 Groggy", 1: "😐 Correct", 2: "😊 Rested"}
        colors = {
            0: (0.6, 0.2, 0.2, 1),
            1: (0.6, 0.55, 0.1, 1),
            2: (0.1, 0.55, 0.25, 1),
        }
        self._normal_color = (0.15, 0.15, 0.18, 1)

        for k, label in labels.items():
            btn = MDRaisedButton(
                text=label,
                size_hint_x=1 / 3,
                md_bg_color=self._normal_color,
                font_size="13sp",
            )
            btn._qualite_key = k
            btn._active_color = colors[k]
            btn.bind(on_release=self._on_press)
            self._buttons.append(btn)
            self.add_widget(btn)

    def _on_press(self, btn):
        key = btn._qualite_key
        if self._selected == key:
            self._selected = None
            btn.md_bg_color = self._normal_color
        else:
            self._selected = key
            for b in self._buttons:
                b.md_bg_color = (
                    b._active_color if b._qualite_key == key else self._normal_color
                )

    @property
    def value(self) -> int | None:
        return self._selected

    def set_value(self, v: int | None):
        self._selected = v
        for b in self._buttons:
            b.md_bg_color = (
                b._active_color if b._qualite_key == v else self._normal_color
            )


class SaisieScreen(MDScreen):
    """Main entry screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "saisie"
        self._wake_rows: list[NocturneWakeRow] = []
        self._edit_nuit_id: int | None = None  # set when editing existing entry
        self._type_menu: MDDropdownMenu | None = None
        self._selected_type = "normale"
        self._build_ui()

    # ──────────────────────────────────────────
    #  UI construction
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        # Toolbar
        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="NateWake — Log Sleep", elevation=2)
        root.add_widget(toolbar)

        scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        # ── Date display ──
        today = datetime.date.today().isoformat()
        self._date_label = MDLabel(
            text=f"Date: {today}",
            font_style="H6",
            size_hint_y=None,
            height=dp(36),
        )
        content.add_widget(self._date_label)

        # ── Bedtime ──
        content.add_widget(MDLabel(text="Bedtime", size_hint_y=None, height=dp(20)))
        self._btn_coucher = MDRaisedButton(
            text="Tap to set bedtime",
            size_hint_y=None,
            height=dp(48),
            md_bg_color=(0.15, 0.18, 0.24, 1),
            on_release=lambda _: ouvrir_time_picker(self._btn_coucher, self._set_coucher),
        )
        self._coucher_value: str = ""
        content.add_widget(self._btn_coucher)

        # ── Wake time ──
        content.add_widget(MDLabel(text="Wake time", size_hint_y=None, height=dp(20)))
        self._btn_reveil = MDRaisedButton(
            text="Tap to set wake time",
            size_hint_y=None,
            height=dp(48),
            md_bg_color=(0.15, 0.18, 0.24, 1),
            on_release=lambda _: ouvrir_time_picker(self._btn_reveil, self._set_reveil),
        )
        self._reveil_value: str = ""
        content.add_widget(self._btn_reveil)

        # ── Nocturnal wakes ──
        content.add_widget(MDLabel(text="Nocturnal wake-ups", size_hint_y=None, height=dp(20)))
        self._nocturnes_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(4)
        )
        self._nocturnes_box.bind(minimum_height=self._nocturnes_box.setter("height"))
        content.add_widget(self._nocturnes_box)

        btn_add_wake = MDFlatButton(
            text="+ Add nocturnal wake",
            size_hint_y=None,
            height=dp(40),
            on_release=lambda _: self._add_wake_row(),
        )
        content.add_widget(btn_add_wake)

        # ── Wake quality ──
        content.add_widget(MDLabel(text="Wake quality", size_hint_y=None, height=dp(20)))
        self._qualite_toggle = QualiteToggle()
        self._qualite_toggle.bind(size=lambda *_: None)  # force height update
        content.add_widget(self._qualite_toggle)

        # ── Night type dropdown ──
        content.add_widget(MDLabel(text="Night type", size_hint_y=None, height=dp(20)))
        self._btn_type = MDRaisedButton(
            text="normale",
            size_hint_y=None,
            height=dp(44),
            on_release=self._open_type_menu,
        )
        content.add_widget(self._btn_type)

        # ── Note ──
        content.add_widget(MDLabel(text="Note (optional)", size_hint_y=None, height=dp(20)))
        self._tf_note = MDTextField(
            hint_text="Free text…",
            mode="rectangle",
            multiline=True,
            size_hint_y=None,
            height=dp(80),
        )
        content.add_widget(self._tf_note)

        # ── Real-time results card ──
        self._results_card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(140),
            radius=[dp(10)],
            md_bg_color=(0.1, 0.12, 0.16, 1),
        )
        self._lbl_duration = MDLabel(text="Total duration: —", size_hint_y=None, height=dp(24))
        self._lbl_cycles = MDLabel(text="Estimated cycles: —", size_hint_y=None, height=dp(24))
        self._lbl_cycle_dur = MDLabel(text="Avg cycle: —", size_hint_y=None, height=dp(24))
        self._lbl_intervals = MDLabel(text="Intervals: —", size_hint_y=None, height=dp(24))
        for lbl in [self._lbl_duration, self._lbl_cycles, self._lbl_cycle_dur, self._lbl_intervals]:
            self._results_card.add_widget(lbl)
        content.add_widget(self._results_card)

        # ── Save button ──
        self._btn_save = MDRaisedButton(
            text="Save",
            size_hint_y=None,
            height=dp(52),
            disabled=True,
            md_bg_color=(0.18, 0.55, 0.34, 1),
            on_release=self._save,
        )
        content.add_widget(self._btn_save)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Type dropdown
    # ──────────────────────────────────────────

    def _open_type_menu(self, btn):
        items = [
            {
                "text": t,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=t: self._select_type(x),
            }
            for t in TYPE_NUIT_CHOICES
        ]
        self._type_menu = MDDropdownMenu(
            caller=self._btn_type, items=items, width_mult=4
        )
        self._type_menu.open()

    def _select_type(self, t: str):
        self._selected_type = t
        self._btn_type.text = t
        if self._type_menu:
            self._type_menu.dismiss()

    # ──────────────────────────────────────────
    #  Nocturnal wakes
    # ──────────────────────────────────────────

    # ──────────────────────────────────────────
    #  TimePicker callbacks
    # ──────────────────────────────────────────

    def _set_coucher(self, heure: str):
        self._coucher_value = heure
        self._recalculate()

    def _set_reveil(self, heure: str):
        self._reveil_value = heure
        self._recalculate()

    # ──────────────────────────────────────────
    #  Nocturnal wakes
    # ──────────────────────────────────────────

    def _add_wake_row(self, value: str = ""):
        row = NocturneWakeRow(
            on_delete=self._remove_wake_row,
            on_change=self._recalculate,
        )
        if value:
            row.value = value
        self._wake_rows.append(row)
        self._nocturnes_box.add_widget(row)
        self._nocturnes_box.height = len(self._wake_rows) * dp(56)

    def _remove_wake_row(self, row: NocturneWakeRow):
        self._wake_rows.remove(row)
        self._nocturnes_box.remove_widget(row)
        self._nocturnes_box.height = len(self._wake_rows) * dp(56)
        self._recalculate()

    # ──────────────────────────────────────────
    #  Real-time recalculation
    # ──────────────────────────────────────────

    def _recalculate(self, *_):
        if not self._coucher_value or not self._reveil_value:
            return

        coucher = self._coucher_value
        reveil = self._reveil_value

        valid = self._valid_hhmm(coucher) and self._valid_hhmm(reveil)
        self._btn_save.disabled = not valid

        if not valid:
            return

        try:
            duree = analytics.calcule_duree_totale(coucher, reveil)
            n_cycles, cycle_dur = analytics.estime_cycles(duree)
            wakes = [r.value for r in self._wake_rows if self._valid_hhmm(r.value)]
            intervalles = analytics.calcule_intervalles(coucher, wakes, reveil)

            self._lbl_duration.text = f"Total duration: {fmt_dur(duree)}"
            self._lbl_cycles.text = f"Estimated cycles: {n_cycles}"
            self._lbl_cycle_dur.text = f"Avg cycle: {fmt_dur(cycle_dur)}"
            int_str = " — ".join(f"{i}min" for i in intervalles) if intervalles else "—"
            self._lbl_intervals.text = f"Intervals: {int_str}"
        except Exception:
            pass

    @staticmethod
    def _valid_hhmm(s: str) -> bool:
        import re
        return bool(re.match(r"^\d{1,2}:\d{2}$", s))

    # ──────────────────────────────────────────
    #  Save
    # ──────────────────────────────────────────

    def _save(self, *_):
        coucher = self._coucher_value
        reveil = self._reveil_value
        wakes = [r.value for r in self._wake_rows if self._valid_hhmm(r.value)]
        today = datetime.date.today().isoformat()

        duree = analytics.calcule_duree_totale(coucher, reveil)
        n_cycles, cycle_dur = analytics.estime_cycles(duree)
        intervalles = analytics.calcule_intervalles(coucher, wakes, reveil)

        nuit = Nuit(
            date=today,
            heure_coucher=coucher,
            heure_reveil=reveil,
            duree_totale_min=duree,
            reveils_nocturnes=wakes,
            intervalles_min=intervalles,
            cycles_estimes=n_cycles,
            duree_moy_cycle_min=cycle_dur,
            qualite_reveil=self._qualite_toggle.value,
            type_nuit=self._selected_type,
            source="manuel",
            note=self._tf_note.text.strip(),
        )

        existing = db.get_nuit_by_date(today)

        if self._edit_nuit_id is not None:
            nuit.id = self._edit_nuit_id
            db.update_nuit(nuit)
            _snack("Entry updated ✓")
        elif existing is not None:
            self._confirm_update(existing, nuit)
            return
        else:
            new_id = db.insert_nuit(nuit)
            nuit.id = new_id
            _snack("Sleep logged ✓")

        self._trigger_analytics()
        self._reset_form()

    def _confirm_update(self, existing: Nuit, new_nuit: Nuit):
        dialog = MDDialog(
            title="Entry already exists",
            text=f"A sleep entry for {existing.date} already exists. Replace it?",
            buttons=[
                MDFlatButton(
                    text="Cancel",
                    on_release=lambda _: dialog.dismiss(),
                ),
                MDRaisedButton(
                    text="Replace",
                    on_release=lambda _: self._do_replace(dialog, existing, new_nuit),
                ),
            ],
        )
        dialog.open()

    def _do_replace(self, dialog, existing: Nuit, new_nuit: Nuit):
        dialog.dismiss()
        new_nuit.id = existing.id
        db.update_nuit(new_nuit)
        _snack("Entry replaced ✓")
        self._trigger_analytics()
        self._reset_form()

    def _trigger_analytics(self):
        """Run analytics pipeline in background after save."""
        try:
            df = db.get_all_nuits_df()
            result = analytics.run_full_analytics(df)
            # Persist outlier updates
            if "df_refreshed" in result:
                df_r = result["df_refreshed"]
                updates = [
                    (int(row["outlier_auto"]), row.get("score_circadien"), int(row["id"]))
                    for _, row in df_r.iterrows()
                ]
                db.update_outlier_scores(updates)
                db.update_is_outlier_column()
        except Exception as e:
            print(f"[analytics] post-save error: {e}")

    def _reset_form(self):
        self._coucher_value = ""
        self._reveil_value = ""
        self._btn_coucher.text = "Tap to set bedtime"
        self._btn_reveil.text = "Tap to set wake time"
        self._tf_note.text = ""
        self._qualite_toggle.set_value(None)
        self._selected_type = "normale"
        self._btn_type.text = "normale"
        for row in list(self._wake_rows):
            self._nocturnes_box.remove_widget(row)
        self._wake_rows.clear()
        self._nocturnes_box.height = 0
        self._edit_nuit_id = None
        self._lbl_duration.text = "Total duration: —"
        self._lbl_cycles.text = "Estimated cycles: —"
        self._lbl_cycle_dur.text = "Avg cycle: —"
        self._lbl_intervals.text = "Intervals: —"
        self._btn_save.disabled = True
        today = datetime.date.today().isoformat()
        self._date_label.text = f"Date: {today}"

    def load_for_edit(self, nuit: Nuit):
        """Pre-populate the form to edit an existing entry."""
        self._reset_form()
        self._edit_nuit_id = nuit.id
        self._date_label.text = f"Date: {nuit.date} (editing)"
        self._coucher_value = nuit.heure_coucher
        self._btn_coucher.text = nuit.heure_coucher
        self._reveil_value = nuit.heure_reveil
        self._btn_reveil.text = nuit.heure_reveil
        self._tf_note.text = nuit.note
        self._qualite_toggle.set_value(nuit.qualite_reveil)
        self._selected_type = nuit.type_nuit
        self._btn_type.text = nuit.type_nuit
        for t in nuit.reveils_nocturnes:
            self._add_wake_row(t)
        self._recalculate()
