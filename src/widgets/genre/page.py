import logging
import threading

from gi.repository import Adw, GLib, GObject, Gtk

from ...integrations import get_current_integration, models
from ..album import AlbumButton
from ..artist import ArtistButton
from ..song import SongSmallRow

logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/jeffser/Nocturne/genre/page.ui")
class GenrePage(Adw.NavigationPage):
    __gtype_name__ = "NocturneGenrePage"

    model = GObject.Property(type=models.Genre)

    clamp_el = Gtk.Template.Child()
    name_el = Gtk.Template.Child()
    artists_carousel = Gtk.Template.Child()
    album_carousel = Gtk.Template.Child()
    song_list_el = Gtk.Template.Child()

    def __init__(self, id: str):
        self.id = id
        integration = get_current_integration()
        super().__init__(model=integration.loaded_models.get(id))

        self._integration = integration
        self._started = False
        self._album_gen = 0
        self._artist_gen = 0
        self._song_gen = 0

    # Lifecycle
    def do_showing(self):
        if not self._started:
            self._started = True
            threading.Thread(target=self.update_album_list, daemon=True).start()
            threading.Thread(target=self.update_artist_list, daemon=True).start()
            threading.Thread(target=self.update_song_list, daemon=True).start()
        Adw.NavigationPage.do_showing(self)

    @Gtk.Template.Callback()
    def format_to_bool(self, obj, value) -> bool:
        return bool(value)

    # Helper to verify model
    def _verify(self, ids, verify_fn, is_current):
        for model_id in ids:
            if not is_current():
                return False
            if model_id in self._integration.loaded_models:
                continue
            try:
                verify_fn(model_id, use_threading=False, minimal=True)
            except Exception:
                logger.exception("verify failed for %s", model_id)
        return True

    # Album carousel
    def update_album_list(self):
        self._album_gen += 1
        gen = self._album_gen

        def is_current():
            return self._album_gen == gen

        try:
            genre_albums = self._integration.getAlbumList(
                list_type="byGenre", genre=self.id, size=-1
            )
        except Exception:
            logger.exception("getAlbumList failed for genre %s", self.id)
            return

        if not is_current():
            return

        if not genre_albums:
            GLib.idle_add(self._hide, self.album_carousel, is_current)
            return

        if not self._verify(genre_albums, self._integration.verifyAlbum, is_current):
            return

        def configure():
            if not is_current() or self.get_root() is None:
                return
            buttons = []
            for album_id in genre_albums:
                try:
                    button = AlbumButton(album_id)
                    button.year_el.set_visible(True)
                    button.artist_el.set_visible(True)
                    button.name_el.remove_css_class("title-3")
                    buttons.append(button)
                except Exception:
                    logger.exception("Failed to build AlbumButton for %s", album_id)
                    continue
            self.album_carousel.set_widgets(buttons)
            self.album_carousel.set_visible(True)

        GLib.idle_add(configure)

    # Artist carousel
    def update_artist_list(self):
        self._artist_gen += 1
        gen = self._artist_gen

        def is_current():
            return self._artist_gen == gen

        try:
            genre_artists = self._integration.getGenreArtists(
                genre_id=self.id, size=-1
            )
        except Exception:
            logger.exception("getGenreArtists failed for genre %s", self.id)
            return

        if not is_current():
            return

        if not genre_artists:
            GLib.idle_add(self._hide, self.artists_carousel, is_current)
            return

        if not self._verify(genre_artists, self._integration.verifyArtist, is_current):
            return

        def configure():
            if not is_current() or self.get_root() is None:
                return
            buttons = []
            for artist_id in genre_artists:
                try:
                    button = ArtistButton(artist_id)
                    button.album_count_el.set_visible(False)
                    buttons.append(button)
                except Exception:
                    logger.exception("Failed to build ArtistButton for %s", artist_id)
                    continue
            self.artists_carousel.set_widgets(buttons)
            self.artists_carousel.set_visible(True)

        GLib.idle_add(configure)

    # Song wrapbox
    def update_song_list(self):
        self._song_gen += 1
        gen = self._song_gen

        def is_current():
            return self._song_gen == gen

        try:
            genre_songs = self._integration.getGenreSongs(self.id)
        except Exception:
            logger.exception("getGenreSongs failed for genre %s", self.id)
            return

        if not is_current():
            return

        if not genre_songs:
            GLib.idle_add(self._hide, self.song_list_el, is_current)
            return

        if not self._verify(genre_songs, self._integration.verifySong, is_current):
            return

        songs_variant = GLib.Variant("as", genre_songs)
        origin_variant = GLib.Variant("s", self.id)

        def configure():
            if not is_current() or self.get_root() is None:
                return
            widgets = []
            for song_id in genre_songs:
                try:
                    row = SongSmallRow(song_id, show_album_name=True)
                    row.set_action_name(None)
                    row.set_action_target_value(GLib.Variant("a{sv}", {
                        "songId": GLib.Variant("s", row.id),
                        "songs": songs_variant,
                        "originId": origin_variant,
                    }))
                    row.set_action_name("app.play_song_from_list")
                    widgets.append(row)
                except Exception:
                    logger.exception("Failed to build SongSmallRow for %s", song_id)
                    continue
            self.song_list_el.list_el.remove_all()
            self.song_list_el.set_widgets(widgets)
            self.song_list_el.set_visible(True)

        GLib.idle_add(configure)


    def _hide(self, widget, is_current_fn):
        if not is_current_fn() or self.get_root() is None:
            return
        widget.set_visible(False)