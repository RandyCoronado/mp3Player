import io
import json
import os
import platform
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

# Prevent a noisy Tk warning on macOS.
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

import pygame

try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None


class Running:
    def __init__(self, root=None):
        self.root = root

        # Audio settings chosen to work well on both Windows and macOS.
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=1024)
        pygame.init()
        pygame.font.init()
        try:
            pygame.mixer.init()
            self.audio_ready = True
        except pygame.error as exc:
            self.audio_ready = False
            self.startup_audio_error = str(exc)

        self.screen = pygame.display.set_mode((980, 640))
        pygame.display.set_caption("MP3 Player")
        self.clock = pygame.time.Clock()
        self.running = True

        # Colors
        self.bg_color = (14, 18, 28)
        self.panel_color = (24, 30, 45)
        self.card_color = (32, 40, 58)
        self.accent_color = (84, 155, 255)
        self.soft_accent = (120, 188, 255)
        self.text_color = (242, 246, 255)
        self.subtext_color = (182, 190, 210)
        self.success_color = (84, 204, 138)
        self.warning_color = (255, 186, 73)
        self.error_color = (255, 105, 105)
        self.border_color = (58, 69, 96)
        self.scroll_track_color = (19, 24, 37)
        self.scroll_thumb_color = (150, 156, 168)

        # Fonts: try common system fonts on Windows/macOS, then let pygame fall back.
        font_name = self.pick_system_font()
        self.title_font = pygame.font.SysFont(font_name, 34, bold=True)
        self.header_font = pygame.font.SysFont(font_name, 24, bold=True)
        self.body_font = pygame.font.SysFont(font_name, 20)
        self.small_font = pygame.font.SysFont(font_name, 16)
        self.button_font = pygame.font.SysFont(font_name, 22, bold=True)

        # Shared state
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.queue_commands = queue.Queue()
        self.playback_commands = queue.Queue()
        self.metadata_commands = queue.Queue()
        self.album_art_commands = queue.Queue()
        self.ui_updates = queue.Queue()

        # Player state
        self.current_path = None
        self.current_song = "No song loaded"
        self.current_artist = "Choose Load or Queue"
        self.current_time = "00:00"
        self.total_time = "00:00"
        self.song_length = 0
        self.position = 0
        self.status = "idle"  # idle, playing, paused, error
        self.message = "Load plays a file. Queue adds files to Up Next."
        if not getattr(self, "audio_ready", True):
            self.message = f"Audio unavailable: {getattr(self, 'startup_audio_error', 'mixer failed')}"
        self.art_message = ""
        self.album_art_surface = None
        self.playback_start_offset = 0
        self.waiting_for_next_song = False

        # Visible queue: list[dict]
        self.queue_items = []

        # Queue UI
        self.queue_scroll_index = 0
        self.visible_queue_count = 4
        self.queue_card_rect = pygame.Rect(650, 112, 300, 360)
        self.queue_list_rect = pygame.Rect(675, 205, 210, 245)
        self.scrollbar_rect = pygame.Rect(895, 190, 30, 206)
        self.scroll_up_rect = pygame.Rect(895, 145, 30, 36)
        self.scroll_down_rect = pygame.Rect(895, 414, 30, 36)
        self.queue_item_height = 58
        self.queue_item_gap = 14

        # Buttons
        self.buttons = {
            "load": pygame.Rect(60, 510, 140, 72),
            "play": pygame.Rect(220, 510, 140, 72),
            "pause": pygame.Rect(380, 510, 140, 72),
            "queue": pygame.Rect(540, 510, 140, 72),
            "next": pygame.Rect(700, 510, 140, 72),
        }

        self.queue_thread = threading.Thread(target=self.queue_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.metadata_thread = threading.Thread(target=self.metadata_worker, daemon=True)
        self.album_art_thread = threading.Thread(target=self.album_art_worker, daemon=True)
        self.timer_thread = threading.Thread(target=self.timer_worker, daemon=True)

        self.queue_thread.start()
        self.playback_thread.start()
        self.metadata_thread.start()
        self.album_art_thread.start()
        self.timer_thread.start()

        while self.running:
            self.handle_events()
            self.process_ui_updates()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(60)

        self.shutdown()
        pygame.quit()

    def pick_system_font(self):
        # Segoe UI is standard on Windows; Helvetica/Arial are standard on macOS.
        candidates = ["segoeui", "segoe ui", "helvetica", "arial", "dejavusans"]
        available = {name.lower() for name in pygame.font.get_fonts()}
        for candidate in candidates:
            if candidate.replace(" ", "") in available or candidate in available:
                return candidate
        return None

    def normalize_path(self, path):
        return str(Path(path).expanduser()) if path else ""

    def choose_files(self, multiple=False):
        # Tk is only used for the native file picker. Keep it hidden and on top so
        # the picker behaves correctly on both Windows and macOS.
        owns_root = self.root is None
        root = self.root or tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        root.update_idletasks()

        filetypes = [
            ("Audio files", "*.mp3 *.wav *.ogg"),
            ("MP3 files", "*.mp3"),
            ("WAV files", "*.wav"),
            ("OGG files", "*.ogg"),
            ("All files", "*.*"),
        ]
        try:
            if multiple:
                paths = filedialog.askopenfilenames(parent=root, title="Queue songs", filetypes=filetypes)
                result = [self.normalize_path(path) for path in paths]
            else:
                path = filedialog.askopenfilename(parent=root, title="Load song", filetypes=filetypes)
                result = [self.normalize_path(path)] if path else []
        finally:
            if owns_root:
                root.destroy()
        return result

    def format_time(self, seconds):
        seconds = max(0, int(seconds or 0))
        return f"{seconds // 60:02}:{seconds % 60:02}"

    def display_name(self, path):
        return Path(path).stem

    def read_metadata(self, path):
        title = self.display_name(path)
        artist = "Unknown Artist"
        length = 0
        art_bytes = None

        if MutagenFile is None:
            return {"path": path, "title": title, "artist": artist, "length": length, "art": None}

        try:
            audio = MutagenFile(path)
            if audio is None:
                return {"path": path, "title": title, "artist": artist, "length": length, "art": None}

            if getattr(audio, "info", None) and getattr(audio.info, "length", None):
                length = int(audio.info.length)

            tags = getattr(audio, "tags", None)
            if tags:
                raw_title = tags.get("TIT2") or tags.get("title")
                raw_artist = tags.get("TPE1") or tags.get("artist")
                if raw_title:
                    title = str(raw_title[0] if isinstance(raw_title, list) else raw_title)
                if raw_artist:
                    artist = str(raw_artist[0] if isinstance(raw_artist, list) else raw_artist)

                # ID3 embedded art usually lives in APIC frames.
                for key in tags.keys():
                    if str(key).startswith("APIC"):
                        art_bytes = tags[key].data
                        break

                # MP4/M4A cover art fallback.
                if art_bytes is None and "covr" in tags:
                    covers = tags.get("covr")
                    if covers:
                        art_bytes = bytes(covers[0])
        except Exception:
            pass

        return {"path": path, "title": title, "artist": artist, "length": length, "art": art_bytes}

    def art_surface_from_bytes(self, art_bytes):
        if not art_bytes:
            return None
        try:
            surface = pygame.image.load(io.BytesIO(art_bytes)).convert_alpha()
            return pygame.transform.smoothscale(surface, (220, 220))
        except Exception:
            return None

    def is_generic_artist(self, artist):
        return not artist or str(artist).strip().lower() in {
            "unknown artist",
            "reading tags...",
            "choose load or queue",
            "queue is empty",
        }

    def search_itunes_metadata(self, title, artist):
        query_parts = [title or ""]
        if artist and not self.is_generic_artist(artist):
            query_parts.append(artist)
        term = quote_plus(" ".join(part for part in query_parts if part).strip())
        if not term:
            return None

        url = f"https://itunes.apple.com/search?term={term}&entity=song&limit=1"
        request = Request(url, headers={"User-Agent": "PygameMP3Player/1.0"})

        try:
            with urlopen(request, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            if not results:
                return None

            result = results[0]
            metadata = {
                "title": result.get("trackName") or title,
                "artist": result.get("artistName") or artist,
                "length": int(result.get("trackTimeMillis", 0) / 1000) if result.get("trackTimeMillis") else 0,
                "art": None,
            }

            artwork_url = result.get("artworkUrl100")
            if artwork_url:
                artwork_url = artwork_url.replace("100x100bb", "600x600bb")
                art_request = Request(artwork_url, headers={"User-Agent": "PygameMP3Player/1.0"})
                with urlopen(art_request, timeout=6) as art_response:
                    metadata["art"] = art_response.read()
            return metadata
        except Exception:
            return None

    def request_itunes_metadata(self, path, title, artist, target="current"):
        self.album_art_commands.put({
            "path": path,
            "title": title,
            "artist": artist,
            "target": target,
        })

    def process_ui_updates(self):
        while True:
            try:
                update = self.ui_updates.get_nowait()
            except queue.Empty:
                break

            if update.get("type") == "itunes_metadata":
                itunes = update.get("metadata") or {}
                target = update.get("target", "current")

                if target == "queue":
                    with self.lock:
                        for item in self.queue_items:
                            if item["path"] == update.get("path"):
                                if itunes.get("title") and item.get("title") == self.display_name(item["path"]):
                                    item["title"] = itunes["title"]
                                if itunes.get("artist") and self.is_generic_artist(item.get("artist")):
                                    item["artist"] = itunes["artist"]
                                if not item.get("length") and itunes.get("length"):
                                    item["length"] = itunes["length"]
                                break
                    continue

                with self.lock:
                    still_current = update.get("path") == self.current_path
                if not still_current:
                    continue

                surface = self.art_surface_from_bytes(itunes.get("art"))
                with self.lock:
                    if self.is_generic_artist(self.current_artist) and itunes.get("artist"):
                        self.current_artist = itunes["artist"]
                    if itunes.get("title") and self.current_song == self.display_name(self.current_path):
                        self.current_song = itunes["title"]
                    if not self.song_length and itunes.get("length"):
                        self.song_length = itunes["length"]
                        self.total_time = self.format_time(self.song_length)
                    if surface:
                        self.album_art_surface = surface
                        self.art_message = "Album art loaded from iTunes."
                    else:
                        if not self.album_art_surface:
                            self.art_message = "No iTunes artwork found."
                        if itunes.get("artist"):
                            self.message = "Artist loaded from iTunes."

    def max_scroll_index(self):
        with self.lock:
            return max(0, len(self.queue_items) - self.visible_queue_count)

    def scroll_queue(self, direction):
        self.queue_scroll_index = max(0, min(self.queue_scroll_index + direction, self.max_scroll_index()))

    def scroll_to_bottom(self):
        self.queue_scroll_index = self.max_scroll_index()

    def play_path(self, path):
        path = self.normalize_path(path)
        if not getattr(self, "audio_ready", True):
            with self.lock:
                self.status = "error"
                self.message = "Audio device is not available."
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            meta = self.read_metadata(path)
            art_surface = self.art_surface_from_bytes(meta.get("art"))
            with self.lock:
                self.current_path = path
                self.current_song = meta["title"]
                self.current_artist = meta["artist"]
                self.song_length = meta["length"]
                self.total_time = self.format_time(meta["length"])
                self.position = 0
                self.playback_start_offset = 0
                self.waiting_for_next_song = False
                self.current_time = "00:00"
                self.album_art_surface = art_surface
                self.art_message = "Using embedded album art." if art_surface else "Searching iTunes for album art..."
                self.status = "playing"
                self.message = f"Playing: {self.current_song}"
            # Ask iTunes for missing artwork and/or a better artist name.
            if (not art_surface) or self.is_generic_artist(meta["artist"]):
                self.request_itunes_metadata(path, meta["title"], meta["artist"], target="current")
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.message = f"Could not play file: {exc}"

    def play_next_from_queue(self):
        with self.lock:
            if not self.queue_items:
                if getattr(self, "audio_ready", True):
                    pygame.mixer.music.stop()
                self.current_path = None
                self.current_song = "No song loaded"
                self.current_artist = "Queue is empty"
                self.song_length = 0
                self.position = 0
                self.playback_start_offset = 0
                self.waiting_for_next_song = False
                self.current_time = "00:00"
                self.total_time = "00:00"
                self.album_art_surface = None
                self.status = "idle"
                self.message = "Queue is empty."
                return
            item = self.queue_items.pop(0)
            self.queue_scroll_index = min(self.queue_scroll_index, self.max_scroll_index())
        self.play_path(item["path"])

    # THREAD 1: queue control
    def queue_worker(self):
        while not self.stop_event.is_set():
            try:
                command, payload = self.queue_commands.get(timeout=0.1)
            except queue.Empty:
                continue

            if command == "quit":
                break
            if command == "load_path":
                if payload:
                    self.playback_commands.put(("load_and_play", payload))
            elif command == "add_paths":
                paths = [p for p in payload if p]
                with self.lock:
                    for path in paths:
                        self.queue_items.append({
                            "path": path,
                            "title": self.display_name(path),
                            "artist": "Reading tags...",
                            "length": 0,
                        })
                        self.metadata_commands.put(("queue", path))
                    self.message = f"Queued {len(paths)} song(s)."
            elif command == "next":
                self.play_next_from_queue()

    # THREAD 2: playback logic
    def playback_worker(self):
        while not self.stop_event.is_set():
            try:
                command, payload = self.playback_commands.get(timeout=0.1)
            except queue.Empty:
                continue

            if command == "quit":
                break

            if command == "load_and_play":
                self.play_path(payload)

            elif command == "play":
                with self.lock:
                    has_song = self.current_path is not None
                    status = self.status

                if has_song and status == "paused":
                    if getattr(self, "audio_ready", True):
                        pygame.mixer.music.unpause()
                    with self.lock:
                        self.status = "playing"
                        self.waiting_for_next_song = False
                        self.message = "Resumed."

                elif has_song and status != "playing":
                    with self.lock:
                        start_at = self.position
                    if getattr(self, "audio_ready", True):
                        try:
                            pygame.mixer.music.play(start=start_at)
                        except (TypeError, pygame.error):
                            # Some pygame/audio backends do not support start=.
                            pygame.mixer.music.play()
                            start_at = 0
                    with self.lock:
                        self.playback_start_offset = start_at
                        self.status = "playing"
                        self.waiting_for_next_song = False

                elif not has_song:
                    self.play_next_from_queue()

                else:
                    with self.lock:
                        self.message = "Already playing."

            elif command == "pause":
                if getattr(self, "audio_ready", True):
                    pygame.mixer.music.pause()
                with self.lock:
                    if self.status == "playing":
                        self.status = "paused"
                        self.message = "Paused."

            elif command == "resume":
                if getattr(self, "audio_ready", True):
                    pygame.mixer.music.unpause()
                with self.lock:
                    if self.status == "paused":
                        self.status = "playing"
                        self.waiting_for_next_song = False
                        self.message = "Resumed."

            elif command == "next":
                self.queue_commands.put(("next", None))

    # THREAD 3: metadata / album art fetcher
    def metadata_worker(self):
        while not self.stop_event.is_set():
            try:
                command, path = self.metadata_commands.get(timeout=0.1)
            except queue.Empty:
                continue
            if command == "quit":
                break
            if command == "queue":
                meta = self.read_metadata(path)
                with self.lock:
                    for item in self.queue_items:
                        if item["path"] == path:
                            item.update({"title": meta["title"], "artist": meta["artist"], "length": meta["length"]})
                            break
                if self.is_generic_artist(meta.get("artist")) or not meta.get("length"):
                    self.request_itunes_metadata(path, meta["title"], meta["artist"], target="queue")

    # THREAD 4: iTunes album art fetcher
    def album_art_worker(self):
        while not self.stop_event.is_set():
            try:
                job = self.album_art_commands.get(timeout=0.1)
            except queue.Empty:
                continue
            if job == "quit":
                break

            metadata = self.search_itunes_metadata(job.get("title"), job.get("artist"))
            self.ui_updates.put({
                "type": "itunes_metadata",
                "path": job.get("path"),
                "target": job.get("target", "current"),
                "metadata": metadata,
            })

    # THREAD 5: timer / song end detection
    def timer_worker(self):
        while not self.stop_event.is_set():
            time.sleep(0.25)
            with self.lock:
                status = self.status
                length = self.song_length
                start_offset = self.playback_start_offset
                already_advancing = self.waiting_for_next_song

            if status != "playing":
                continue

            mixer_seconds = pygame.mixer.music.get_pos() / 1000.0 if getattr(self, "audio_ready", True) else -1
            if mixer_seconds >= 0:
                new_position = int(start_offset + mixer_seconds)
                if length:
                    new_position = min(new_position, length)
                with self.lock:
                    self.position = new_position
                    self.current_time = self.format_time(self.position)

            with self.lock:
                position = self.position
                already_advancing = self.waiting_for_next_song

            song_finished_by_time = bool(length and position >= length)
            song_finished_by_mixer = (
                getattr(self, "audio_ready", True)
                and (position > 0 or mixer_seconds > 1)
                and not pygame.mixer.music.get_busy()
            )
            if (song_finished_by_time or song_finished_by_mixer) and not already_advancing:
                with self.lock:
                    self.waiting_for_next_song = True
                self.queue_commands.put(("next", None))

    def shutdown(self):
        self.running = False
        self.stop_event.set()
        self.queue_commands.put(("quit", None))
        self.playback_commands.put(("quit", None))
        self.metadata_commands.put(("quit", None))
        self.album_art_commands.put("quit")
        if getattr(self, "audio_ready", True):
            pygame.mixer.music.stop()
        self.queue_thread.join(timeout=1)
        self.playback_thread.join(timeout=1)
        self.metadata_thread.join(timeout=1)
        self.album_art_thread.join(timeout=1)
        self.timer_thread.join(timeout=1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos

                if event.button == 1:
                    if self.buttons["load"].collidepoint(mouse_pos):
                        paths = self.choose_files(multiple=False)
                        if paths:
                            self.queue_commands.put(("load_path", paths[0]))

                    elif self.buttons["play"].collidepoint(mouse_pos):
                        self.playback_commands.put(("play", None))

                    elif self.buttons["pause"].collidepoint(mouse_pos):
                        with self.lock:
                            paused = self.status == "paused"
                        self.playback_commands.put(("resume" if paused else "pause", None))

                    elif self.buttons["queue"].collidepoint(mouse_pos):
                        paths = self.choose_files(multiple=True)
                        if paths:
                            self.queue_commands.put(("add_paths", paths))
                            self.scroll_to_bottom()

                    elif self.buttons["next"].collidepoint(mouse_pos):
                        self.queue_commands.put(("next", None))

                    elif self.scroll_up_rect.collidepoint(mouse_pos):
                        self.scroll_queue(-1)
                    elif self.scroll_down_rect.collidepoint(mouse_pos):
                        self.scroll_queue(1)

                if event.button == 4 and self.queue_card_rect.collidepoint(mouse_pos):
                    self.scroll_queue(-1)
                elif event.button == 5 and self.queue_card_rect.collidepoint(mouse_pos):
                    self.scroll_queue(1)

    def draw_ui(self):
        self.screen.fill(self.bg_color)

        with self.lock:
            current_song = self.current_song
            current_artist = self.current_artist
            current_time = self.current_time
            total_time = self.total_time
            status = self.status
            position = self.position
            song_length = self.song_length
            queue_items = [item.copy() for item in self.queue_items]
            message = self.message
            album_art_surface = self.album_art_surface

        pygame.draw.rect(self.screen, self.panel_color, (30, 24, 920, 70), border_radius=24)
        self.draw_text("MP3 Player", self.title_font, self.text_color, 55, 42)
        self.draw_text(message, self.small_font, self.subtext_color, 710, 52, max_width=220)

        pygame.draw.rect(self.screen, self.panel_color, (30, 112, 590, 360), border_radius=28)

        art_rect = pygame.Rect(58, 145, 220, 220)
        pygame.draw.rect(self.screen, self.card_color, art_rect, border_radius=28)
        if album_art_surface:
            self.screen.blit(album_art_surface, art_rect)
        else:
            pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 52, width=8)
            pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 10)

        with self.lock:
            art_message = self.art_message
        caption = art_message or ("No Album Art" if not album_art_surface else "")
        if caption:
            caption_surface = self.small_font.render(str(caption), True, self.subtext_color)
            caption_rect = caption_surface.get_rect(center=(art_rect.centerx, 390))
            if caption_rect.width > 205:
                self.draw_text(caption, self.small_font, self.subtext_color, art_rect.x + 8, 382, max_width=205)
            else:
                self.screen.blit(caption_surface, caption_rect)

        self.draw_text(current_song, self.header_font, self.text_color, 310, 165, max_width=280)
        self.draw_text(current_artist, self.body_font, self.subtext_color, 310, 205, max_width=280)

        self.draw_text(current_time, self.body_font, self.text_color, 310, 275)
        self.draw_text(total_time, self.body_font, self.text_color, 535, 275)
        pygame.draw.rect(self.screen, self.card_color, (310, 310, 250, 14), border_radius=10)

        progress_width = int(250 * (position / max(1, song_length))) if song_length else 0
        pygame.draw.rect(self.screen, self.accent_color, (310, 310, min(250, progress_width), 14), border_radius=10)

        state_text = {"playing": "Playing", "paused": "Paused", "error": "Error"}.get(status, "Idle")
        state_color = {"playing": self.success_color, "paused": self.warning_color, "error": self.error_color}.get(status, self.subtext_color)
        pygame.draw.rect(self.screen, self.card_color, (310, 350, 170, 42), border_radius=18)
        self.draw_text(state_text, self.small_font, state_color, 346, 362)

        pygame.draw.rect(self.screen, self.panel_color, self.queue_card_rect, border_radius=28)
        self.draw_text("Up Next", self.header_font, self.text_color, 680, 145)
        self.draw_scroll_controls(len(queue_items))
        self.draw_queue_list(queue_items)

        pygame.draw.rect(self.screen, self.panel_color, (30, 490, 920, 120), border_radius=28)
        self.draw_buttons(status)

    def draw_queue_list(self, queue_items):
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self.queue_list_rect)

        visible_items = queue_items[self.queue_scroll_index:self.queue_scroll_index + self.visible_queue_count]
        item_y = self.queue_list_rect.y

        for item in visible_items:
            item_rect = pygame.Rect(self.queue_list_rect.x, item_y, self.queue_list_rect.width, self.queue_item_height)
            pygame.draw.rect(self.screen, self.card_color, item_rect, border_radius=18)
            self.draw_text(item.get("title", "Unknown"), self.body_font, self.text_color, item_rect.x + 16, item_rect.y + 10, max_width=170)
            artist = item.get("artist", "")
            length = self.format_time(item.get("length", 0)) if item.get("length", 0) else "--:--"
            self.draw_text(f"{artist} - {length}", self.small_font, self.subtext_color, item_rect.x + 16, item_rect.y + 34, max_width=175)
            item_y += self.queue_item_height + self.queue_item_gap

        if not queue_items:
            empty_rect = pygame.Rect(self.queue_list_rect.x, self.queue_list_rect.y, self.queue_list_rect.width, self.queue_item_height)
            pygame.draw.rect(self.screen, self.card_color, empty_rect, border_radius=18)
            self.draw_text("No queued songs", self.body_font, self.subtext_color, empty_rect.x + 16, empty_rect.y + 17)

        self.screen.set_clip(old_clip)

    def draw_scroll_controls(self, total_count):
        mouse_pos = pygame.mouse.get_pos()
        up_fill = self.soft_accent if self.scroll_up_rect.collidepoint(mouse_pos) else self.card_color
        down_fill = self.soft_accent if self.scroll_down_rect.collidepoint(mouse_pos) else self.card_color

        pygame.draw.rect(self.screen, up_fill, self.scroll_up_rect, border_radius=12)
        pygame.draw.rect(self.screen, down_fill, self.scroll_down_rect, border_radius=12)
        pygame.draw.polygon(self.screen, self.text_color, [(self.scroll_up_rect.centerx, self.scroll_up_rect.y + 10), (self.scroll_up_rect.x + 8, self.scroll_up_rect.bottom - 10), (self.scroll_up_rect.right - 8, self.scroll_up_rect.bottom - 10)])
        pygame.draw.polygon(self.screen, self.text_color, [(self.scroll_down_rect.centerx, self.scroll_down_rect.bottom - 10), (self.scroll_down_rect.x + 8, self.scroll_down_rect.y + 10), (self.scroll_down_rect.right - 8, self.scroll_down_rect.y + 10)])

        pygame.draw.rect(self.screen, self.scroll_track_color, self.scrollbar_rect, border_radius=16)
        total_items = max(1, total_count)
        visible_items = min(self.visible_queue_count, total_items)
        thumb_height = max(42, int(self.scrollbar_rect.height * (visible_items / total_items)))
        track_range = self.scrollbar_rect.height - thumb_height
        max_scroll = max(0, total_count - self.visible_queue_count)
        thumb_y = self.scrollbar_rect.y if max_scroll == 0 else self.scrollbar_rect.y + int(track_range * (self.queue_scroll_index / max_scroll))
        thumb_rect = pygame.Rect(self.scrollbar_rect.x + 5, thumb_y, self.scrollbar_rect.width - 10, thumb_height)
        pygame.draw.rect(self.screen, self.scroll_thumb_color, thumb_rect, border_radius=14)

    def draw_buttons(self, status):
        labels = {
            "load": "Load",
            "play": "Play",
            "pause": "Resume" if status == "paused" else "Pause",
            "queue": "Queue",
            "next": "Next",
        }
        mouse_pos = pygame.mouse.get_pos()
        for key, rect in self.buttons.items():
            fill = self.soft_accent if rect.collidepoint(mouse_pos) else self.accent_color
            pygame.draw.rect(self.screen, fill, rect, border_radius=22)
            pygame.draw.rect(self.screen, self.border_color, rect, width=2, border_radius=22)
            text_surface = self.button_font.render(labels[key], True, self.text_color)
            text_rect = text_surface.get_rect(center=rect.center)
            self.screen.blit(text_surface, text_rect)

    def draw_text(self, text, font, color, x, y, max_width=None):
        text = str(text)
        if max_width is not None:
            while text and font.size(text + "...")[0] > max_width:
                text = text[:-1]
            if font.size(str(text))[0] > max_width or len(text) < len(str(text)):
                text = text + "..."
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))


if __name__ == "__main__":
    # Required by multiprocessing/frozen app launchers on Windows, harmless elsewhere.
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:
        pass

    try:
        Running(None)
    except KeyboardInterrupt:
        sys.exit(0)
