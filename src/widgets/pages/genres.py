# genres.py

import threading

from gi.repository import Adw, Gio, GLib, Gtk

from ...integrations import get_current_integration
from ..genre import GenreButton, GenreRow


@Gtk.Template(resource_path='/com/jeffser/Nocturne/pages/genres.ui')
class GenresPage(Adw.NavigationPage):
    __gtype_name__ = 'NocturneGenresPage'

    toggle_group_el = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    list_el = Gtk.Template.Child()
    wrapbox_el = Gtk.Template.Child()
    end_stack = Gtk.Template.Child()
    scrolledwindow = Gtk.Template.Child()
    offset = 0
    searching = False
    skipped_genres = 0
    lazy_reload = False
    all_genres = []

    def __init__(self):
        super().__init__()
        self.settings = Gio.Settings(schema_id="com.jeffser.Nocturne")
        self.settings.bind(
            "default-view-mode-artists", #TODO change to genres view mode
            self.toggle_group_el,
            "active-name",
            Gio.SettingsBindFlags.DEFAULT
        )
        self.scrolledwindow.get_vadjustment().connect('notify::upper', lambda va, ud: GLib.timeout_add(1000, self.check_scrollbar, va))

    def check_scrollbar(self, adjustment):
        if adjustment.get_upper() <= adjustment.get_page_size():
            threading.Thread(target=self.search, daemon=True).start()

    def load(self):
        if len(list(self.list_el)) + len(list(self.wrapbox_el)) == 0:
            GLib.idle_add(self.on_search, self.search_entry)

    def reload(self):
        self.lazy_reload = False
        GLib.idle_add(self.reset)
        self.load()

    def do_showing(self):
        if self.lazy_reload:
            self.reload()

    def reset(self):
        self.offset = 0
        self.list_el.remove_all()
        for el in list(self.wrapbox_el):
            self.wrapbox_el.remove(el)

    def search(self):
        if self.searching:
            return
        self.searching = True
        self.skipped_genres = 0
        # Dont pull genres on every search event. They dont change alot
        if not self.all_genres:
            integration = get_current_integration()
            self.all_genres = integration.getGenres()

        query = None
        while query != self.search_entry.get_text(): # In case query changes whilst calling integration
            query = self.search_entry.get_text()
            search_results = [g for g in self.all_genres if query in g]
        for genre_id in search_results:
            should_skip = False
            results_list = [row for row in list(self.list_el) if row.id == genre_id]
            if len(results_list) > 0:
                GLib.idle_add(results_list[0].set_visible, not should_skip)
            elif not should_skip:
                row = GenreRow(genre_id)
                GLib.idle_add(self.list_el.append, row)

            results_wrapbox = [button for button in list(self.wrapbox_el) if button.id == genre_id]
            if len(results_wrapbox) > 0:
                GLib.idle_add(results_wrapbox[0].set_visible, not should_skip)
            elif not should_skip:
                button = GenreButton(genre_id)
                GLib.idle_add(self.wrapbox_el.append, button)

        GLib.idle_add(self.end_stack.set_visible_child_name, 'end')
        self.searching = False
        GLib.idle_add(self.update_visibility)

    @Gtk.Template.Callback()
    def on_search(self, search_entry):
        self.offset = 0
        self.searching = False
        for widget in list(self.list_el) + list(self.wrapbox_el):
            widget.set_visible(False)
        self.end_stack.set_visible_child_name('loading')
        threading.Thread(target=self.search, daemon=True).start()

    @Gtk.Template.Callback()
    def scroll_edge_reached(self, scrolledwindow, pos):
        if pos == Gtk.PositionType.BOTTOM and self.end_stack.get_visible_child_name() == 'loading':
            threading.Thread(target=self.search, daemon=True).start()

    def update_visibility(self):
        for row in list(self.list_el) + list(self.wrapbox_el):
            if row.get_visible():
                self.main_stack.set_visible_child_name('content')
                return
        self.main_stack.set_visible_child_name('no-content')
