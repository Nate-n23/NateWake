"""
screens/historique.py — NateWake
==================================
Scrollable history screen with filters, swipe-to-delete, and detail/edit view.
"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.selectioncontrol import MDSwitch

import config
import db
from models import Nuit, QUALITE_LABELS


def _snack(message: str) -> None:
    """Show a KivyMD 1.2.0-compatible snackbar."""
    snackbar = Snackbar()
    snackbar.add_widget(MDLabel(text=message))
    snackbar.open()


def fmt_dur(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h{m:02d}"


SOURCE_ICON = {
    "manuel": "pencil",
    "sleep_as_android": "android",
    "sleep_cycle": "moon-waxing-crescent",
}

QUALITE_ICON = {0: "emoticon-sad-outline", 1: "emoticon-neutral-outline", 2: "emoticon-happy-outline"}


class NightCard(MDCard):
    """One history list item."""

    def __init__(self, nuit: Nuit, on_tap, on_delete, **kwargs):
        super().__init__(**kwargs)
        self.nuit = nuit
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(72)
        self.padding = dp(8)
        self.spacing = dp(8)
        self.radius = [dp(8)]
        # Outlier dimming
        alpha = 0.45 if nuit.effective_is_outlier else 1.0
        self.md_bg_color = (0.12, 0.14, 0.18, alpha)

        # Left: date + metrics
        left = BoxLayout(orientation="vertical", size_hint_x=0.75)
        date_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24))

        date_row.add_widget(
            MDLabel(
                text=nuit.date,
                font_style="Subtitle1",
                size_hint_x=0.6,
                bold=True,
            )
        )
        if nuit.effective_is_outlier:
            date_row.add_widget(
                MDLabel(
                    text="[color=ff6b6b]● OUTLIER[/color]",
                    markup=True,
                    size_hint_x=0.4,
                    font_style="Caption",
                )
            )
        else:
            date_row.add_widget(MDLabel(size_hint_x=0.4))

        left.add_widget(date_row)

        detail = (
            f"{nuit.type_nuit}  ·  {fmt_dur(nuit.duree_totale_min)}"
            f"  ·  {nuit.cycles_estimes or '?'} cycles"
            f"  ·  {nuit.qualite_label}"
        )
        left.add_widget(
            MDLabel(
                text=detail,
                font_style="Caption",
                size_hint_y=None,
                height=dp(20),
            )
        )
        src = nuit.source.replace("_", " ")
        left.add_widget(
            MDLabel(
                text=f"via {src}",
                font_style="Overline",
                size_hint_y=None,
                height=dp(16),
            )
        )
        self.add_widget(left)

        # Right: actions
        right = BoxLayout(orientation="vertical", size_hint_x=0.12, spacing=dp(2))
        right.add_widget(
            MDIconButton(icon="pencil-outline", on_release=lambda _: on_tap(nuit))
        )
        right.add_widget(
            MDIconButton(icon="delete-outline", on_release=lambda _: on_delete(nuit))
        )
        self.add_widget(right)


class HistoriqueScreen(MDScreen):
    """History list screen with pagination and filters."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "historique"
        self._page = 0
        self._filter_type: str | None = None
        self._filter_source: str | None = None
        self._filter_days: int | None = None
        self._outlier_only = False
        self._all_loaded = False
        self._type_menu = None
        self._source_menu = None
        self._period_menu = None
        self._build_ui()

    # ──────────────────────────────────────────
    #  UI
    # ──────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        from kivymd.uix.toolbar import MDTopAppBar
        toolbar = MDTopAppBar(title="History", elevation=2)
        root.add_widget(toolbar)

        # Filter bar
        filter_bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            padding=dp(6),
            spacing=dp(6),
        )

        for label, cb in [
            ("Type", self._open_type_menu),
            ("Source", self._open_source_menu),
            ("Period", self._open_period_menu),
        ]:
            btn = MDFlatButton(text=label, on_release=cb, size_hint_x=0.28)
            setattr(self, f"_btn_{label.lower()}", btn)
            filter_bar.add_widget(btn)

        reset_btn = MDIconButton(
            icon="filter-remove-outline",
            on_release=self._reset_filters,
        )
        filter_bar.add_widget(reset_btn)
        root.add_widget(filter_bar)

        # Outlier toggle
        out_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            padding=[dp(10), 0],
        )
        self._outlier_label = MDLabel(text="All nights", size_hint_x=0.8)
        out_row.add_widget(self._outlier_label)
        self._outlier_switch = MDSwitch()
        self._outlier_switch.bind(active=self._on_outlier_toggle)
        out_row.add_widget(self._outlier_switch)
        root.add_widget(out_row)

        # List
        self._scroll = ScrollView()
        self._list_box = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            padding=dp(8),
            size_hint_y=None,
        )
        self._list_box.bind(minimum_height=self._list_box.setter("height"))
        self._scroll.add_widget(self._list_box)
        self._scroll.bind(scroll_y=self._on_scroll)
        root.add_widget(self._scroll)

        # Load more button
        self._btn_more = MDFlatButton(
            text="Load more",
            size_hint_y=None,
            height=dp(40),
            on_release=self._load_more,
        )
        root.add_widget(self._btn_more)

        self.add_widget(root)

    # ──────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────

    def on_pre_enter(self, *_):
        self.reload()

    def reload(self):
        self._page = 0
        self._all_loaded = False
        self._list_box.clear_widgets()
        self._load_page()

    def _load_page(self):
        nuits = db.get_nuits_page(
            page=self._page,
            page_size=config.HISTORY_PAGE_SIZE,
            type_nuit=self._filter_type,
            source=self._filter_source,
            days=self._filter_days,
            outlier_only=self._outlier_only,
        )
        if len(nuits) < config.HISTORY_PAGE_SIZE:
            self._all_loaded = True
            self._btn_more.disabled = True
        else:
            self._btn_more.disabled = False

        if not nuits and self._page == 0:
            self._list_box.add_widget(
                MDLabel(
                    text="No entries yet. Log your first night!",
                    halign="center",
                    size_hint_y=None,
                    height=dp(60),
                )
            )
            return

        for n in nuits:
            card = NightCard(
                nuit=n,
                on_tap=self._open_detail,
                on_delete=self._confirm_delete,
            )
            self._list_box.add_widget(card)

    def _load_more(self, *_):
        if not self._all_loaded:
            self._page += 1
            self._load_page()

    def _on_scroll(self, scroll, value):
        if value < 0.05 and not self._all_loaded:
            self._load_more()

    # ──────────────────────────────────────────
    #  Filters
    # ──────────────────────────────────────────

    def _open_type_menu(self, btn):
        items = [
            {
                "text": t or "All types",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=t: self._set_filter_type(x),
            }
            for t in [None, "normale", "nocturne", "récupération", "sieste"]
        ]
        self._type_menu = MDDropdownMenu(caller=btn, items=items, width_mult=4)
        self._type_menu.open()

    def _set_filter_type(self, t):
        self._filter_type = t
        self._btn_type.text = t or "Type"
        if self._type_menu:
            self._type_menu.dismiss()
        self.reload()

    def _open_source_menu(self, btn):
        items = [
            {
                "text": s or "All sources",
                "viewclass": "OneLineListItem",
                "on_release": lambda x=s: self._set_filter_source(x),
            }
            for s in [None, "manuel", "sleep_as_android", "sleep_cycle"]
        ]
        self._source_menu = MDDropdownMenu(caller=btn, items=items, width_mult=4)
        self._source_menu.open()

    def _set_filter_source(self, s):
        self._filter_source = s
        self._btn_source.text = s or "Source"
        if self._source_menu:
            self._source_menu.dismiss()
        self.reload()

    def _open_period_menu(self, btn):
        options = [(None, "All time"), (7, "7 days"), (30, "30 days")]
        items = [
            {
                "text": label,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=days: self._set_filter_days(x),
            }
            for days, label in options
        ]
        self._period_menu = MDDropdownMenu(caller=btn, items=items, width_mult=4)
        self._period_menu.open()

    def _set_filter_days(self, days):
        self._filter_days = days
        self._btn_period.text = f"{days}d" if days else "Period"
        if self._period_menu:
            self._period_menu.dismiss()
        self.reload()

    def _on_outlier_toggle(self, switch, value):
        self._outlier_only = bool(value)
        self._outlier_label.text = "Outliers only" if self._outlier_only else "All nights"
        self.reload()

    def _reset_filters(self, *_):
        self._filter_type = None
        self._filter_source = None
        self._filter_days = None
        self._outlier_only = False
        self._outlier_switch.active = False  # triggers _on_outlier_toggle
        self._btn_type.text = "Type"
        self._btn_source.text = "Source"
        self._btn_period.text = "Period"
        self.reload()

    # ──────────────────────────────────────────
    #  Detail / edit
    # ──────────────────────────────────────────

    def _open_detail(self, nuit: Nuit):
        wakes_str = ", ".join(nuit.reveils_nocturnes) or "None"
        intervals_str = " — ".join(f"{i}min" for i in nuit.intervalles_min) or "—"

        content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        content.bind(minimum_height=content.setter("height"))

        rows = [
            ("Date", nuit.date),
            ("Bedtime", nuit.heure_coucher),
            ("Wake time", nuit.heure_reveil),
            ("Duration", fmt_dur(nuit.duree_totale_min)),
            ("Cycles", str(nuit.cycles_estimes or "?")),
            ("Avg cycle", f"{nuit.duree_moy_cycle_min:.1f} min" if nuit.duree_moy_cycle_min else "—"),
            ("Wake quality", nuit.qualite_label),
            ("Nocturnal wakes", wakes_str),
            ("Intervals", intervals_str),
            ("Night type", nuit.type_nuit),
            ("Source", nuit.source),
            ("Outlier", "Yes" if nuit.effective_is_outlier else "No"),
            ("Note", nuit.note or "—"),
        ]
        for k, v in rows:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))
            row.add_widget(MDLabel(text=f"[b]{k}[/b]", markup=True, size_hint_x=0.4))
            row.add_widget(MDLabel(text=v, size_hint_x=0.6))
            content.add_widget(row)

        # Outlier manual override
        override_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(36)
        )
        override_row.add_widget(MDLabel(text="Mark as outlier", size_hint_x=0.7))
        sw = MDSwitch()
        sw.active = bool(nuit.effective_is_outlier)
        override_row.add_widget(sw)
        content.add_widget(override_row)

        scroll = ScrollView(size_hint=(1, None), size=(dp(300), dp(400)))
        scroll.add_widget(content)

        dialog = MDDialog(
            title=f"Night — {nuit.date}",
            type="custom",
            content_cls=scroll,
            buttons=[
                MDFlatButton(
                    text="Close",
                    on_release=lambda _: dialog.dismiss(),
                ),
                MDFlatButton(
                    text="Edit",
                    on_release=lambda _: self._go_edit(dialog, nuit),
                ),
                MDRaisedButton(
                    text="Save outlier",
                    on_release=lambda _: self._save_outlier(dialog, nuit, sw.active),
                ),
            ],
        )
        dialog.open()

    def _save_outlier(self, dialog, nuit: Nuit, is_outlier: bool):
        nuit.outlier_manuel = 1 if is_outlier else 0
        nuit.is_outlier = nuit.outlier_manuel
        db.update_nuit(nuit)
        db.update_is_outlier_column()
        dialog.dismiss()
        _snack("Outlier flag updated ✓")
        self.reload()

    def _go_edit(self, dialog, nuit: Nuit):
        dialog.dismiss()
        saisie = self.manager.get_screen("saisie")
        saisie.load_for_edit(nuit)
        self.manager.current = "saisie"

    # ──────────────────────────────────────────
    #  Delete
    # ──────────────────────────────────────────

    def _confirm_delete(self, nuit: Nuit):
        dialog = MDDialog(
            title="Delete entry",
            text=f"Delete sleep entry for {nuit.date}? This cannot be undone.",
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda _: dialog.dismiss()),
                MDRaisedButton(
                    text="Delete",
                    md_bg_color=(0.7, 0.15, 0.15, 1),
                    on_release=lambda _: self._do_delete(dialog, nuit),
                ),
            ],
        )
        dialog.open()

    def _do_delete(self, dialog, nuit: Nuit):
        dialog.dismiss()
        db.delete_nuit(nuit.id)
        _snack("Entry deleted")
        self.reload()
