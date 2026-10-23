# page.py

import io
import threading

from colorthief import ColorThief
from gi.repository import Adw, Gdk, GLib, GObject, Gtk, Pango

from ...integrations import get_current_integration, models
from ..album import AlbumButton
from ..artist import ArtistButton
from ..song import SongSmallRow


@Gtk.Template(resource_path="/com/jeffser/Nocturne/genre/page.ui")
class GenrePage(Adw.NavigationPage):
    __gtype_name__ = "NocturneGenrePage"

    model = GObject.Property(type=models.Genre)

    clamp_el = Gtk.Template.Child()
    name_el = Gtk.Template.Child()
    artists_wrapbox = Gtk.Template.Child()
    album_wrapbox = Gtk.Template.Child()
    song_list_el = Gtk.Template.Child()

    def __init__(self, id: str):
        self.id = id
        integration = get_current_integration()
        super().__init__(model=integration.loaded_models.get(self.id))

        threading.Thread(target=self.update_album_list, daemon=True).start()
        threading.Thread(target=self.update_artist_list, daemon=True).start()
        threading.Thread(target=self.update_top_songs, daemon=True).start()


    @Gtk.Template.Callback()
    def format_to_bool(self, obj, value) -> bool:
        return bool(value)

    def update_album_list(self):
        # Generation token so overlapping calls can't interleave their queued idle mutations.
        generation = getattr(self, '_album_list_generation', 0) + 1
        self._album_list_generation = generation
        def is_current():
            return getattr(self, '_album_list_generation', None) == generation
        def configure():
            GLib.idle_add(lambda: is_current() and self.album_wrapbox.list_el.remove_all())
            albums_buttons = []
            for album_id in genre_albums:
                button = AlbumButton(album_id)
                button.year_el.set_visible(True)
                button.artist_el.set_visible(True)
                button.set_halign(Gtk.Align.CENTER)
                button.name_el.remove_css_class('title-3')
                albums_buttons.append(button)
            self.album_wrapbox.set_widgets(albums_buttons)

        integration = get_current_integration()
        genre_albums = integration.getAlbumList(list_type="byGenre",genre=self.id, size=-1)
        if genre_albums:
            GLib.idle_add(configure)
        else:
            GLib.idle_add(self.album_wrapbox.set_visible(False))

    def update_artist_list(self):
        def configure():
            artist_buttons = []
            for artist_id in genre_artists:
                button = ArtistButton(artist_id)
                button.album_count_el.set_visible(False)
                #
                # button.set_halign(Gtk.Align.CENTER)
                artist_buttons.append(button)
            self.artists_wrapbox.set_widgets(artist_buttons)

        integration = get_current_integration()
        genre_artists = integration.getGenreArtists(genre_id=self.id, size=-1)
        if genre_artists:
            GLib.idle_add(configure)
        else:
            GLib.idle_add(self.artists_wrapbox.set_visible(False))

    def update_top_songs(self):

        def configure():
            widgets = [SongSmallRow(song_id, show_album_name=True) for song_id in genre_songs]
            for row in widgets:
                row.set_action_name(None)
                row.set_action_target_value(GLib.Variant('a{sv}', {
                    'songId': GLib.Variant('s', row.id),
                    'songs': GLib.Variant('as', genre_songs),
                    'originId': GLib.Variant('s', self.id)
                }))
                row.set_action_name('app.play_song_from_list')
            self.song_list_el.set_widgets(widgets)

        integration = get_current_integration()
        genre_songs = integration.getGenreSongs(self.id)
        if genre_songs:
            GLib.idle_add(configure)
        else:
            GLib.idle_add(self.song_list_el.set_visible(False))


    def update_background(self, raw_bytes: bytes):
        def run():
            img_io = io.BytesIO(raw_bytes)
            color = ColorThief(img_io).get_color(quality=10)
            css = f"""
            clamp {{
                transition: background .2s;
                background: linear-gradient(180deg, color-mix(in srgb, rgb({",".join([str(c) for c in color])}) 50%, transparent), transparent 30%);
                background-size: 100% 1000px;
                background-repeat: no-repeat;
            }}
            """
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode())
            GLib.idle_add(
                self.clamp_el.get_style_context().add_provider,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        if raw_bytes:
            threading.Thread(target=run, daemon=True).start()

