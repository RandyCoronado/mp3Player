import pygame
import threading
import queue
import time
import os
import sys
import requests
import subprocess
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
        self.card_elevated_color = (26, 26, 26)
        self.accent_color = (30, 215, 96)
        self.soft_accent = (73, 232, 128)
        self.accent_glow_color = (22, 120, 60)
        self.text_color = (255, 255, 255)
        self.subtext_color = (179, 179, 179)
        self.muted_text_color = (138, 138, 138)
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
        self.volume = 0.7
        self.is_adjusting_volume = False

        self.album_art_surface = None

        # Queue stores file paths
        self.song_queue = []
        self.play_history = []

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
            "queue": pygame.Rect(544, 557, 118, 42),
            "next": pygame.Rect(676, 557, 118, 42),
        }
        self.progress_bar_rect = pygame.Rect(438, 610, 268, 6)
        self.volume_bar_rect = pygame.Rect(250, 610, 120, 6)
        self.hero_rect = pygame.Rect(264, 84, 388, 332)
        self.album_rect = pygame.Rect(292, 114, 188, 188)

        pygame.mixer.music.set_volume(self.volume)

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
        """Open a native MP3 file picker.

        macOS: use AppleScript because Tkinter can crash or hang when opened
        from inside a Pygame event loop on some Apple Python installs.
        Windows/Linux: use Tkinter, which is the most reliable built-in picker there.
        """
        if sys.platform == "darwin":
            return self.choose_mp3_file_macos()
        return self.choose_mp3_file_tk()

    def choose_mp3_file_macos(self):
        try:
            script = '''
            set chosenFile to choose file with prompt "Choose an MP3 file" of type {"mp3", "public.mp3", "public.audio"}
            return POSIX path of chosenFile
            '''
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path and os.path.isfile(path):
                    return path
            elif result.stderr.strip():
                print("File picker cancelled or failed:", result.stderr.strip())
        except Exception as e:
            print("macOS file picker error:", e)
        return None

    def choose_mp3_file_tk(self):
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.update_idletasks()
            try:
                root.attributes("-topmost", True)
            except tk.TclError:
                pass

            file_path = filedialog.askopenfilename(
                parent=root,
                title="Choose an MP3 file",
                filetypes=[("MP3 files", "*.mp3"), ("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")]
            )
            root.destroy()

            if file_path and os.path.isfile(file_path):
                return file_path
        except Exception as e:
            print("Tk file picker error:", e)
        return None

    def song_name_from_path(self, path):
        return os.path.basename(path).replace(".mp3", "")

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

    def volume_from_x(self, mouse_x):
        relative_x = mouse_x - self.volume_bar_rect.x
        relative_x = max(0, min(relative_x, self.volume_bar_rect.width))
        return relative_x / self.volume_bar_rect.width if self.volume_bar_rect.width else 0

    def set_volume_from_x(self, mouse_x):
        volume = self.volume_from_x(mouse_x)
        with self.lock:
            self.volume = volume
        pygame.mixer.music.set_volume(volume)

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

    def add_to_history(self, song_name):
        if not song_name or song_name == "No song loaded":
            return
        with self.lock:
            self.play_history = [item for item in self.play_history if item != song_name]
            self.play_history.insert(0, song_name)
            self.play_history = self.play_history[:6]

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

        self.add_to_history(song_name)
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

                    if self.volume_bar_rect.collidepoint(mouse_pos):
                        self.is_adjusting_volume = True
                        self.set_volume_from_x(mouse_pos[0])
                        continue

                    if self.buttons["load"].collidepoint(mouse_pos):
                        path = self.choose_mp3_file()
                        if path:
                            self.queue_commands.put(("load", path))

                    elif self.buttons["play"].collidepoint(mouse_pos):
                        with self.lock:
                            paused = self.status == "paused"
                            playing = self.status == "playing"

                        if playing:
                            self.playback_commands.put("pause")
                        elif paused:
                            self.playback_commands.put("resume")
                        else:
                            self.playback_commands.put("play")

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

                if self.is_adjusting_volume:
                    self.set_volume_from_x(event.pos[0])

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                with self.lock:
                    is_seeking = self.is_seeking
                    has_song = self.current_path is not None
                if is_seeking and has_song:
                    target_seconds = self.position_from_progress_x(event.pos[0])
                    self.seek_to_position(target_seconds)
                self.is_adjusting_volume = False

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
            volume = self.volume
            play_history = list(self.play_history)

        self.draw_background_glow()
        pygame.draw.rect(self.screen, self.sidebar_color, self.sidebar_rect)
        pygame.draw.rect(self.screen, self.panel_color, self.main_panel_rect, border_radius=24)
        pygame.draw.rect(self.screen, self.bottom_bar_color, (0, 528, 980, 112))
        pygame.draw.line(self.screen, self.border_color, (0, 528), (980, 528), 1)

        self.draw_text("Recently Played", self.body_font, self.text_color, 28, 28)
        self.draw_text("Your local history", self.small_font, self.muted_text_color, 28, 58)
        self.draw_play_history(play_history)
        self.draw_text("NOW PLAYING", self.small_font, self.muted_text_color, 268, 48)
        self.draw_text("UP NEXT", self.small_font, self.muted_text_color, 676, 48)
        self.draw_text("Desktop mix for local tracks", self.small_font, self.subtext_color, 264, 448)

        self.draw_card_shadow(self.hero_rect, 22)
        pygame.draw.rect(self.screen, self.card_color, self.hero_rect, border_radius=22)
        self.draw_card_gradient(self.hero_rect, (36, 36, 36), (24, 24, 24))

        self.draw_card_shadow(self.album_rect, 16)
        pygame.draw.rect(self.screen, (18, 18, 18), self.album_rect, border_radius=14)

        if album_art_surface:
            self.screen.blit(album_art_surface, self.album_rect)
        else:
            pygame.draw.circle(self.screen, self.soft_accent, self.album_rect.center, 48, width=6)
            pygame.draw.circle(self.screen, self.soft_accent, self.album_rect.center, 8)
            self.draw_text("Album Art", self.small_font, self.subtext_color, 344, 318)

        self.draw_text(current_song, self.header_font, self.text_color, 292, 328, max_width=320)
        self.draw_text(current_artist, self.body_font, self.subtext_color, 292, 362, max_width=320)
        self.draw_text("LOCAL TRACK", self.small_font, self.accent_color, 292, 392)

        if status == "playing":
            state_text = "Playing"
            state_color = self.success_color
        elif status == "paused":
            state_text = "Paused"
            state_color = self.warning_color
        else:
            state_text = "Idle"
            state_color = self.subtext_color

        pygame.draw.rect(self.screen, self.card_elevated_color, (528, 368, 92, 34), border_radius=17)
        self.draw_text(state_text, self.small_font, state_color, 551, 377)

        self.draw_card_shadow(self.queue_card_rect, 18)
        pygame.draw.rect(self.screen, self.card_color, self.queue_card_rect, border_radius=20)
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
        self.draw_volume_control(volume)
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

            pygame.draw.rect(self.screen, self.card_hover_color, item_rect, border_radius=14)
            pygame.draw.circle(self.screen, self.accent_color, (item_rect.x + 18, item_rect.y + 24), 4)
            self.draw_text(item, self.body_font, self.text_color, item_rect.x + 14, item_rect.y + 8, max_width=145)
            self.draw_text("Queued track", self.small_font, self.subtext_color, item_rect.x + 28, item_rect.y + 28)

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
            self.scrollbar_rect.x + 2,
            thumb_y,
            self.scrollbar_rect.width - 4,
            thumb_height,
        )

        pygame.draw.rect(self.screen, self.scroll_thumb_color, thumb_rect, border_radius=8)

    def draw_buttons(self, status):
        labels = {
            "load": "Load",
            "play": "",
            "queue": "Queue",
            "next": "Next",
        }

        mouse_pos = pygame.mouse.get_pos()

        for key, rect in self.buttons.items():
            if key == "play":
                fill = self.soft_accent if rect.collidepoint(mouse_pos) else self.accent_color
                pygame.draw.ellipse(self.screen, fill, rect)
                if status == "playing":
                    self.draw_pause_icon(rect)
                else:
                    self.draw_play_icon(rect)
                continue

            fill = self.card_hover_color if rect.collidepoint(mouse_pos) else self.card_elevated_color
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

    def draw_pause_icon(self, rect):
        left_bar = pygame.Rect(rect.x + 17, rect.y + 14, 7, 24)
        right_bar = pygame.Rect(rect.x + 29, rect.y + 14, 7, 24)
        pygame.draw.rect(self.screen, (0, 0, 0), left_bar, border_radius=3)
        pygame.draw.rect(self.screen, (0, 0, 0), right_bar, border_radius=3)

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
        self.draw_text("Now Playing", self.small_font, self.muted_text_color, 108, 544)

    def draw_play_history(self, play_history):
        start_y = 94
        if not play_history:
            empty_rect = pygame.Rect(20, start_y, 184, 46)
            pygame.draw.rect(self.screen, self.card_elevated_color, empty_rect, border_radius=12)
            self.draw_text("Nothing played yet", self.small_font, self.muted_text_color, 34, start_y + 15)
            return

        for index, item in enumerate(play_history[:6]):
            row_y = start_y + (index * 52)
            row_rect = pygame.Rect(20, row_y, 184, 42)
            pygame.draw.rect(self.screen, self.card_elevated_color, row_rect, border_radius=12)
            pygame.draw.circle(self.screen, self.accent_color, (row_rect.x + 14, row_rect.centery), 4)
            self.draw_text(item, self.small_font, self.text_color, row_rect.x + 26, row_rect.y + 8, max_width=132)
            stamp = "Most recent" if index == 0 else f"Played #{index + 1}"
            self.draw_text(stamp, self.small_font, self.muted_text_color, row_rect.x + 26, row_rect.y + 22, max_width=132)

    def draw_volume_control(self, volume):
        self.draw_text("Volume", self.small_font, self.muted_text_color, 250, 586)
        speaker_x = self.volume_bar_rect.x - 24
        speaker_y = self.volume_bar_rect.y - 8
        pygame.draw.polygon(
            self.screen,
            self.subtext_color,
            [
                (speaker_x, speaker_y + 10),
                (speaker_x + 8, speaker_y + 10),
                (speaker_x + 14, speaker_y + 4),
                (speaker_x + 14, speaker_y + 24),
                (speaker_x + 8, speaker_y + 18),
                (speaker_x, speaker_y + 18),
            ],
        )
        pygame.draw.rect(self.screen, self.scroll_track_color, self.volume_bar_rect, border_radius=8)
        filled_width = int(self.volume_bar_rect.width * max(0, min(1, volume)))
        pygame.draw.rect(
            self.screen,
            self.text_color,
            (self.volume_bar_rect.x, self.volume_bar_rect.y, filled_width, self.volume_bar_rect.height),
            border_radius=8,
        )
        thumb_x = self.volume_bar_rect.x + filled_width
        thumb_x = max(self.volume_bar_rect.x + 5, min(thumb_x, self.volume_bar_rect.right - 5))
        pygame.draw.circle(self.screen, self.text_color, (thumb_x, self.volume_bar_rect.centery), 5)

    def draw_background_glow(self):
        glow_surface = pygame.Surface((980, 640), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (*self.accent_glow_color, 40), (300, 80), 170)
        pygame.draw.circle(glow_surface, (70, 40, 20, 28), (760, 120), 150)
        self.screen.blit(glow_surface, (0, 0))

    def draw_card_shadow(self, rect, radius):
        shadow = pygame.Surface((rect.width + 24, rect.height + 24), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 60), (12, 12, rect.width, rect.height), border_radius=radius)
        self.screen.blit(shadow, (rect.x - 12, rect.y - 4))

    def draw_card_gradient(self, rect, top_color, bottom_color):
        gradient = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for y in range(rect.height):
            blend = y / max(1, rect.height - 1)
            color = (
                int(top_color[0] + (bottom_color[0] - top_color[0]) * blend),
                int(top_color[1] + (bottom_color[1] - top_color[1]) * blend),
                int(top_color[2] + (bottom_color[2] - top_color[2]) * blend),
                185,
            )
            pygame.draw.line(gradient, color, (0, y), (rect.width, y))
        self.screen.blit(gradient, rect.topleft)

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
