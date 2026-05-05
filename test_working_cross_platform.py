import pygame
import threading
import queue
import time
import os
import requests
import sys
import platform

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None
    filedialog = None

from io import BytesIO
from PIL import Image


class Running:
    def __init__(self, root=None):
        self.root = root

        pygame.init()
        pygame.font.init()
        pygame.mixer.init()

        self.screen = pygame.display.set_mode((980, 640))
        pygame.display.set_caption("MP3 Player")
        self.clock = pygame.time.Clock()
        self.running = True

        # Colors
        self.bg_color = (18, 18, 18)
        self.sidebar_color = (0, 0, 0)
        self.panel_color = (24, 24, 24)
        self.card_color = (32, 32, 32)
        self.card_hover_color = (41, 41, 41)
        self.accent_color = (30, 215, 96)
        self.soft_accent = (73, 232, 128)
        self.text_color = (255, 255, 255)
        self.subtext_color = (179, 179, 179)
        self.success_color = (30, 215, 96)
        self.warning_color = (245, 155, 35)
        self.border_color = (44, 44, 44)
        self.scroll_track_color = (44, 44, 44)
        self.scroll_thumb_color = (179, 179, 179)
        self.bottom_bar_color = (24, 24, 24)

        # Fonts
        self.title_font = pygame.font.SysFont("helvetica neue", 30, bold=True)
        self.header_font = pygame.font.SysFont("helvetica neue", 26, bold=True)
        self.body_font = pygame.font.SysFont("helvetica neue", 20)
        self.small_font = pygame.font.SysFont("helvetica neue", 15)
        self.button_font = pygame.font.SysFont("helvetica neue", 18, bold=True)

        # Threads
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        self.queue_commands = queue.Queue()
        self.playback_commands = queue.Queue()
        self.album_art_commands = queue.Queue()

        # Player state
        self.current_song = "No song loaded"
        self.current_artist = "Choose an MP3 file"
        self.current_path = None
        self.current_time = "00:00"
        self.total_time = "--:--"
        self.song_length = 1
        self.position = 0
        self.status = "idle"
        self.playback_start_offset = 0
        self.is_seeking = False
        self.seek_preview_position = 0

        self.album_art_surface = None

        # Queue stores file paths
        self.song_queue = []

        # Queue UI
        self.queue_scroll_index = 0
        self.visible_queue_count = 4
        self.sidebar_rect = pygame.Rect(0, 0, 220, 640)
        self.main_panel_rect = pygame.Rect(236, 20, 724, 492)
        self.queue_card_rect = pygame.Rect(676, 84, 250, 332)
        self.queue_list_rect = pygame.Rect(696, 154, 190, 224)
        self.scrollbar_rect = pygame.Rect(892, 154, 12, 224)
        self.scroll_up_rect = pygame.Rect(892, 126, 12, 18)
        self.scroll_down_rect = pygame.Rect(892, 388, 12, 18)
        self.queue_item_height = 50
        self.queue_item_gap = 10

        # Buttons
        self.buttons = {
            "load": pygame.Rect(318, 557, 118, 42),
            "play": pygame.Rect(450, 548, 52, 52),
            "pause": pygame.Rect(516, 557, 118, 42),
            "queue": pygame.Rect(648, 557, 118, 42),
            "next": pygame.Rect(780, 557, 118, 42),
        }
        self.progress_bar_rect = pygame.Rect(438, 610, 268, 6)

        self.queue_thread = threading.Thread(target=self.queue_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.timer_thread = threading.Thread(target=self.timer_worker, daemon=True)
        self.album_art_thread = threading.Thread(target=self.album_art_worker, daemon=True)

        self.queue_thread.start()
        self.playback_thread.start()
        self.timer_thread.start()
        self.album_art_thread.start()

        while self.running:
            self.handle_events()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(60)

        self.shutdown()
        pygame.quit()

    def choose_mp3_file(self):
        """Open a native file picker on Windows and macOS.

        The previous version used macOS-only AppleScript through `osascript`.
        Windows does not include `osascript`, which causes:
            [WinError 2] The system cannot find the file specified

        Tkinter is included with most Python installers on both Windows and macOS,
        so this keeps the same code path for both platforms.
        """
        if tk is None or filedialog is None:
            print("File picker error: tkinter is not available in this Python install.")
            return None

        picker_root = None
        try:
            picker_root = tk.Tk()
            picker_root.withdraw()

            # Make the dialog appear in front of the Pygame window where supported.
            try:
                picker_root.attributes("-topmost", True)
                picker_root.update()
            except Exception:
                pass

            path = filedialog.askopenfilename(
                parent=picker_root,
                title="Choose an audio file",
                filetypes=(
                    ("Audio files", ("*.mp3", "*.wav", "*.ogg")),
                    ("MP3 files", ("*.mp3",)),
                    ("All files", ("*.*",)),
                ),
            )

            if not path:
                return None

            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isfile(path):
                print("File picker error: selected path is not a file:", path)
                return None

            return os.path.normpath(path)

        except Exception as e:
            print("File picker error:", e)
            return None
        finally:
            if picker_root is not None:
                try:
                    picker_root.destroy()
                except Exception:
                    pass

    def song_name_from_path(self, path):
        return os.path.splitext(os.path.basename(path))[0]

    def format_time(self, seconds):
        seconds = max(0, int(seconds))
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    def max_scroll_index(self):
        with self.lock:
            return max(0, len(self.song_queue) - self.visible_queue_count)

    def scroll_queue(self, direction):
        self.queue_scroll_index = max(
            0,
            min(self.queue_scroll_index + direction, self.max_scroll_index())
        )

    def scroll_to_bottom(self):
        self.queue_scroll_index = self.max_scroll_index()

    def estimate_song_length(self, path):
        try:
            sound = pygame.mixer.Sound(path)
            return max(1, int(sound.get_length()))
        except Exception:
            return 1

    def position_from_progress_x(self, mouse_x):
        relative_x = mouse_x - self.progress_bar_rect.x
        relative_x = max(0, min(relative_x, self.progress_bar_rect.width))
        ratio = relative_x / self.progress_bar_rect.width if self.progress_bar_rect.width else 0
        return int(ratio * max(1, self.song_length))

    def seek_to_position(self, target_seconds):
        with self.lock:
            if not self.current_path:
                return
            target_seconds = max(0, min(int(target_seconds), max(0, self.song_length)))
            path = self.current_path
            status = self.status

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(start=target_seconds)
            if status == "paused":
                pygame.mixer.music.pause()
        except Exception as e:
            print("Seek error:", e)
            return

        with self.lock:
            self.position = target_seconds
            self.current_time = self.format_time(target_seconds)
            self.playback_start_offset = target_seconds
            self.is_seeking = False
            self.seek_preview_position = target_seconds

    def load_song(self, path, autoplay=False):
        song_name = self.song_name_from_path(path)

        try:
            pygame.mixer.music.load(path)
        except Exception as e:
            print("Could not load song:", e)
            return

        with self.lock:
            self.current_path = path
            self.current_song = song_name
            self.current_artist = "Local file"
            self.position = 0
            self.current_time = "00:00"
            self.song_length = self.estimate_song_length(path)
            self.total_time = self.format_time(self.song_length)
            self.status = "playing" if autoplay else "paused"
            self.album_art_surface = None
            self.playback_start_offset = 0
            self.is_seeking = False
            self.seek_preview_position = 0

        self.album_art_commands.put(song_name)

        if autoplay:
            pygame.mixer.music.play()

    def load_next_song(self):
        with self.lock:
            if not self.song_queue:
                self.current_song = "No song loaded"
                self.current_artist = "Choose an MP3 file"
                self.current_path = None
                self.position = 0
                self.current_time = "00:00"
                self.total_time = "--:--"
                self.status = "idle"
                self.album_art_surface = None
                self.playback_start_offset = 0
                self.is_seeking = False
                self.seek_preview_position = 0
                pygame.mixer.music.stop()
                return

            next_path = self.song_queue.pop(0)

        self.load_song(next_path, autoplay=True)

    # --------------------------
    # THREAD 1: queue control
    # --------------------------
    def queue_worker(self):
        while not self.stop_event.is_set():
            try:
                command, data = self.queue_commands.get(timeout=0.1)

                if command == "load":
                    self.load_song(data, autoplay=True)

                elif command == "queue":
                    with self.lock:
                        self.song_queue.append(data)

                elif command == "next":
                    self.load_next_song()

                elif command == "quit":
                    break

            except queue.Empty:
                pass

    # --------------------------
    # THREAD 2: playback logic
    # --------------------------
    def playback_worker(self):
        while not self.stop_event.is_set():
            try:
                command = self.playback_commands.get(timeout=0.1)

                if command == "play":
                    with self.lock:
                        has_song = self.current_path is not None
                        status = self.status

                    if has_song:
                        if status == "paused":
                            pygame.mixer.music.unpause()
                        else:
                            with self.lock:
                                start_at = self.position
                            pygame.mixer.music.play(start=start_at)

                        with self.lock:
                            self.status = "playing"
                            if status != "paused":
                                self.playback_start_offset = self.position
                    else:
                        self.load_next_song()

                elif command == "pause":
                    pygame.mixer.music.pause()
                    with self.lock:
                        if self.current_path:
                            self.status = "paused"

                elif command == "resume":
                    pygame.mixer.music.unpause()
                    with self.lock:
                        if self.current_path:
                            self.status = "playing"

                elif command == "quit":
                    break

            except queue.Empty:
                pass

    # --------------------------
    # THREAD 3: timer updates
    # --------------------------
    def timer_worker(self):
        while not self.stop_event.is_set():
            time.sleep(1)

            with self.lock:
                status = self.status
                has_song = self.current_path is not None

            if status == "playing" and has_song:
                pos_ms = pygame.mixer.music.get_pos()

                if pos_ms >= 0:
                    with self.lock:
                        start_offset = self.playback_start_offset
                    pos_seconds = int(start_offset + (pos_ms / 1000))
                    clamped_seconds = min(pos_seconds, self.song_length)
                    with self.lock:
                        self.position = clamped_seconds
                        self.current_time = self.format_time(clamped_seconds)

                if not pygame.mixer.music.get_busy():
                    self.load_next_song()

    # --------------------------
    # THREAD 4: album art fetching
    # --------------------------
    def album_art_worker(self):
        while not self.stop_event.is_set():
            try:
                song_query = self.album_art_commands.get(timeout=0.1)

                if song_query == "quit":
                    break

                response = requests.get(
                    "https://itunes.apple.com/search",
                    params={
                        "term": song_query,
                        "media": "music",
                        "entity": "song",
                        "limit": 1
                    },
                    timeout=5
                )

                data = response.json()

                if data.get("resultCount", 0) > 0:
                    result = data["results"][0]
                    artwork_url = result["artworkUrl100"].replace("100x100", "600x600")

                    img_data = requests.get(artwork_url, timeout=5).content
                    img = Image.open(BytesIO(img_data)).convert("RGB")
                    img = img.resize((220, 220))

                    surface = pygame.image.fromstring(img.tobytes(), img.size, img.mode)

                    with self.lock:
                        self.album_art_surface = surface
                else:
                    with self.lock:
                        self.album_art_surface = None

            except queue.Empty:
                pass
            except Exception as e:
                print("Album art error:", e)
                with self.lock:
                    self.album_art_surface = None

    def shutdown(self):
        self.running = False
        self.stop_event.set()

        self.queue_commands.put(("quit", None))
        self.playback_commands.put("quit")
        self.album_art_commands.put("quit")

        self.queue_thread.join(timeout=1)
        self.playback_thread.join(timeout=1)
        self.timer_thread.join(timeout=1)
        self.album_art_thread.join(timeout=1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos

                if event.button == 1:
                    if self.progress_bar_rect.collidepoint(mouse_pos):
                        with self.lock:
                            if self.current_path:
                                self.is_seeking = True
                                self.seek_preview_position = self.position_from_progress_x(mouse_pos[0])
                                self.position = self.seek_preview_position
                                self.current_time = self.format_time(self.seek_preview_position)
                        continue

                    if self.buttons["load"].collidepoint(mouse_pos):
                        path = self.choose_mp3_file()
                        if path:
                            self.queue_commands.put(("load", path))

                    elif self.buttons["play"].collidepoint(mouse_pos):
                        self.playback_commands.put("play")

                    elif self.buttons["pause"].collidepoint(mouse_pos):
                        with self.lock:
                            paused = self.status == "paused"

                        if paused:
                            self.playback_commands.put("resume")
                        else:
                            self.playback_commands.put("pause")

                    elif self.buttons["queue"].collidepoint(mouse_pos):
                        path = self.choose_mp3_file()
                        if path:
                            self.queue_commands.put(("queue", path))
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

            elif event.type == pygame.MOUSEMOTION:
                with self.lock:
                    is_seeking = self.is_seeking
                    has_song = self.current_path is not None
                if is_seeking and has_song:
                    preview_position = self.position_from_progress_x(event.pos[0])
                    with self.lock:
                        self.seek_preview_position = preview_position
                        self.position = preview_position
                        self.current_time = self.format_time(preview_position)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                with self.lock:
                    is_seeking = self.is_seeking
                    has_song = self.current_path is not None
                if is_seeking and has_song:
                    target_seconds = self.position_from_progress_x(event.pos[0])
                    self.seek_to_position(target_seconds)

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
            queue_items = [self.song_name_from_path(path) for path in self.song_queue]
            album_art_surface = self.album_art_surface

        pygame.draw.rect(self.screen, self.sidebar_color, self.sidebar_rect)
        pygame.draw.rect(self.screen, self.panel_color, self.main_panel_rect, border_radius=18)
        pygame.draw.rect(self.screen, self.bottom_bar_color, (0, 528, 980, 112))
        pygame.draw.line(self.screen, self.border_color, (0, 528), (980, 528), 1)

        self.draw_text("Spotify", self.title_font, self.text_color, 28, 26)
        self.draw_text("Home", self.body_font, self.text_color, 28, 92)
        self.draw_text("Search", self.body_font, self.subtext_color, 28, 126)
        self.draw_text("Your Library", self.body_font, self.subtext_color, 28, 160)
        self.draw_text("NOW PLAYING", self.small_font, self.subtext_color, 268, 48)
        self.draw_text("Made For You", self.small_font, self.subtext_color, 676, 48)
        self.draw_text("Liked Songs", self.body_font, self.text_color, 28, 238)
        self.draw_text("Local Queue", self.body_font, self.text_color, 28, 274)

        hero_rect = pygame.Rect(264, 84, 388, 332)
        pygame.draw.rect(self.screen, self.card_color, hero_rect, border_radius=20)

        album_rect = pygame.Rect(292, 114, 188, 188)
        pygame.draw.rect(self.screen, (24, 24, 24), album_rect, border_radius=12)

        if album_art_surface:
            self.screen.blit(album_art_surface, album_rect)
        else:
            pygame.draw.circle(self.screen, self.soft_accent, album_rect.center, 48, width=6)
            pygame.draw.circle(self.screen, self.soft_accent, album_rect.center, 8)
            self.draw_text("Album Art", self.small_font, self.subtext_color, 344, 318)

        self.draw_text(current_song, self.header_font, self.text_color, 292, 328, max_width=330)
        self.draw_text(current_artist, self.body_font, self.subtext_color, 292, 364, max_width=330)

        if status == "playing":
            state_text = "Playing"
            state_color = self.success_color
        elif status == "paused":
            state_text = "Paused"
            state_color = self.warning_color
        else:
            state_text = "Idle"
            state_color = self.subtext_color

        pygame.draw.rect(self.screen, (18, 18, 18), (292, 398, 104, 32), border_radius=16)
        self.draw_text(state_text, self.small_font, state_color, 320, 406)

        pygame.draw.rect(self.screen, self.card_color, self.queue_card_rect, border_radius=18)
        self.draw_text("Queue", self.header_font, self.text_color, 696, 110)
        self.draw_text(f"{len(queue_items)} track(s)", self.small_font, self.subtext_color, 696, 136)
        self.draw_scroll_controls(len(queue_items))
        self.draw_queue_list(queue_items)

        self.draw_bottom_now_playing(current_song, current_artist, album_art_surface)

        pygame.draw.rect(self.screen, self.scroll_track_color, self.progress_bar_rect, border_radius=10)

        progress_width = int(self.progress_bar_rect.width * (position / max(1, song_length)))
        progress_width = min(self.progress_bar_rect.width, max(0, progress_width))

        pygame.draw.rect(
            self.screen,
            self.accent_color,
            (self.progress_bar_rect.x, self.progress_bar_rect.y, progress_width, self.progress_bar_rect.height),
            border_radius=10
        )
        thumb_center_x = self.progress_bar_rect.x + progress_width
        thumb_center_x = max(self.progress_bar_rect.x + 6, min(thumb_center_x, self.progress_bar_rect.right - 6))
        pygame.draw.circle(
            self.screen,
            self.text_color,
            (thumb_center_x, self.progress_bar_rect.centery),
            6
        )
        self.draw_buttons(status)
        self.draw_text(current_time, self.small_font, self.subtext_color, 398, 603)
        self.draw_text(total_time, self.small_font, self.subtext_color, 718, 603)

    def draw_queue_list(self, queue_items):
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self.queue_list_rect)

        visible_items = queue_items[
            self.queue_scroll_index:self.queue_scroll_index + self.visible_queue_count
        ]

        item_y = self.queue_list_rect.y

        for item in visible_items:
            item_rect = pygame.Rect(
                self.queue_list_rect.x,
                item_y,
                self.queue_list_rect.width,
                self.queue_item_height,
            )

            pygame.draw.rect(self.screen, self.card_hover_color, item_rect, border_radius=12)
            self.draw_text(item, self.body_font, self.text_color, item_rect.x + 14, item_rect.y + 8, max_width=145)
            self.draw_text("Queued track", self.small_font, self.subtext_color, item_rect.x + 14, item_rect.y + 28)

            item_y += self.queue_item_height + self.queue_item_gap

        if not queue_items:
            empty_rect = pygame.Rect(
                self.queue_list_rect.x,
                self.queue_list_rect.y,
                self.queue_list_rect.width,
                self.queue_item_height,
            )

            pygame.draw.rect(self.screen, self.card_hover_color, empty_rect, border_radius=12)
            self.draw_text(
                "No queued songs",
                self.small_font,
                self.subtext_color,
                empty_rect.x + 16,
                empty_rect.y + 16
            )

        self.screen.set_clip(old_clip)

    def draw_scroll_controls(self, total_count):
        mouse_pos = pygame.mouse.get_pos()

        up_fill = self.scroll_thumb_color if self.scroll_up_rect.collidepoint(mouse_pos) else self.scroll_track_color
        down_fill = self.scroll_thumb_color if self.scroll_down_rect.collidepoint(mouse_pos) else self.scroll_track_color

        pygame.draw.rect(self.screen, up_fill, self.scroll_up_rect, border_radius=8)
        pygame.draw.rect(self.screen, down_fill, self.scroll_down_rect, border_radius=8)

        pygame.draw.polygon(
            self.screen,
            self.text_color,
            [
                (self.scroll_up_rect.centerx, self.scroll_up_rect.y + 4),
                (self.scroll_up_rect.x + 3, self.scroll_up_rect.bottom - 4),
                (self.scroll_up_rect.right - 3, self.scroll_up_rect.bottom - 4),
            ],
        )

        pygame.draw.polygon(
            self.screen,
            self.text_color,
            [
                (self.scroll_down_rect.centerx, self.scroll_down_rect.bottom - 4),
                (self.scroll_down_rect.x + 3, self.scroll_down_rect.y + 4),
                (self.scroll_down_rect.right - 3, self.scroll_down_rect.y + 4),
            ],
        )

        pygame.draw.rect(self.screen, self.scroll_track_color, self.scrollbar_rect, border_radius=8)

        total_items = max(1, total_count)
        visible_items = min(self.visible_queue_count, total_items)

        thumb_height = max(36, int(self.scrollbar_rect.height * (visible_items / total_items)))
        track_range = self.scrollbar_rect.height - thumb_height

        max_scroll = max(0, total_count - self.visible_queue_count)

        if max_scroll == 0:
            thumb_y = self.scrollbar_rect.y
        else:
            progress = self.queue_scroll_index / max_scroll
            thumb_y = self.scrollbar_rect.y + int(track_range * progress)

        thumb_rect = pygame.Rect(
            self.scrollbar_rect.x + 5,
            thumb_y,
            self.scrollbar_rect.width - 4,
            thumb_height,
        )

        pygame.draw.rect(self.screen, self.scroll_thumb_color, thumb_rect, border_radius=8)

    def draw_buttons(self, status):
        labels = {
            "load": "Load",
            "play": "",
            "pause": "Resume" if status == "paused" else "Pause",
            "queue": "Queue",
            "next": "Next",
        }

        mouse_pos = pygame.mouse.get_pos()

        for key, rect in self.buttons.items():
            if key == "play":
                fill = self.soft_accent if rect.collidepoint(mouse_pos) else self.accent_color
                pygame.draw.ellipse(self.screen, fill, rect)
                self.draw_play_icon(rect)
                continue

            fill = self.card_hover_color if rect.collidepoint(mouse_pos) else self.card_color
            pygame.draw.rect(self.screen, fill, rect, border_radius=21)

            text_surface = self.button_font.render(labels[key], True, self.text_color)
            text_rect = text_surface.get_rect(center=rect.center)
            self.screen.blit(text_surface, text_rect)

    def draw_play_icon(self, rect):
        pygame.draw.polygon(
            self.screen,
            (0, 0, 0),
            [
                (rect.x + 20, rect.y + 14),
                (rect.right - 16, rect.centery),
                (rect.x + 20, rect.bottom - 14),
            ],
        )

    def draw_bottom_now_playing(self, current_song, current_artist, album_art_surface):
        mini_art_rect = pygame.Rect(18, 546, 76, 76)
        pygame.draw.rect(self.screen, self.card_hover_color, mini_art_rect, border_radius=8)
        if album_art_surface:
            mini_surface = pygame.transform.smoothscale(album_art_surface, (76, 76))
            self.screen.blit(mini_surface, mini_art_rect)
        else:
            pygame.draw.circle(self.screen, self.soft_accent, mini_art_rect.center, 18, width=3)
            pygame.draw.circle(self.screen, self.soft_accent, mini_art_rect.center, 4)

        self.draw_text(current_song, self.body_font, self.text_color, 108, 562, max_width=180)
        self.draw_text(current_artist, self.small_font, self.subtext_color, 108, 589, max_width=180)

    def draw_text(self, text, font, color, x, y, max_width=None):
        text = str(text)
        if max_width is not None:
            original = text
            while text and font.size(text + "...")[0] > max_width:
                text = text[:-1]
            if text != original:
                text += "..."
        surface = font.render(str(text), True, color)
        self.screen.blit(surface, (x, y))


if __name__ == "__main__":
    Running(None)
