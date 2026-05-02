import pygame
import threading
import queue
import time


class Running:
    def __init__(self, root):
        self.root = root

        pygame.init()
        pygame.font.init()

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
        self.border_color = (58, 69, 96)
        self.scroll_track_color = (19, 24, 37)
        self.scroll_thumb_color = (150, 156, 168)

        # Fonts
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.header_font = pygame.font.SysFont("arial", 24, bold=True)
        self.body_font = pygame.font.SysFont("arial", 20)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.button_font = pygame.font.SysFont("arial", 22, bold=True)

        # Shared state
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # Separate command queues for clearer thread roles
        self.queue_commands = queue.Queue()
        self.playback_commands = queue.Queue()

        # Player state
        self.current_song = "No song loaded"
        self.current_artist = "Frontend preview only"
        self.current_time = "00:00"
        self.total_time = "03:42"
        self.song_length = 222
        self.position = 0
        self.status = "idle"  # idle, playing, paused

        # Visible queue
        self.queue_items = [
            "Midnight Drive",
            "Ocean Echo",
            "Neon Sunset",
            "City Lights",
        ]

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

        # Threads
        self.queue_thread = threading.Thread(target=self.queue_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.timer_thread = threading.Thread(target=self.timer_worker, daemon=True)

        self.queue_thread.start()
        self.playback_thread.start()
        self.timer_thread.start()

        while self.running:
            self.handle_events()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(60)

        self.shutdown()
        pygame.quit()

    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    def max_scroll_index(self):
        with self.lock:
            return max(0, len(self.queue_items) - self.visible_queue_count)

    def scroll_queue(self, direction):
        self.queue_scroll_index = max(
            0,
            min(self.queue_scroll_index + direction, self.max_scroll_index())
        )

    def scroll_to_bottom(self):
        self.queue_scroll_index = self.max_scroll_index()

    def load_next_song(self):
        if self.queue_items:
            self.current_song = self.queue_items.pop(0)
            self.current_artist = "Queue preview only"
            self.position = 0
            self.current_time = "00:00"
            self.total_time = self.format_time(self.song_length)
            self.status = "playing"
        else:
            self.current_song = "No song loaded"
            self.current_artist = "Frontend preview only"
            self.position = 0
            self.current_time = "00:00"
            self.total_time = self.format_time(self.song_length)
            self.status = "idle"

    # --------------------------
    # THREAD 1: queue control
    # --------------------------
    def queue_worker(self):
        while not self.stop_event.is_set():
            try:
                command = self.queue_commands.get(timeout=0.1)

                with self.lock:
                    if command == "load":
                        self.current_song = "Loaded Song Preview"
                        self.current_artist = "UI placeholder only"
                        self.position = 0
                        self.current_time = "00:00"
                        self.total_time = self.format_time(self.song_length)
                        self.status = "paused"

                    elif command == "queue":
                        self.queue_items.append(f"Preview Song {len(self.queue_items) + 1}")

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

                with self.lock:
                    if command == "play":
                        if self.current_song == "No song loaded":
                            self.load_next_song()
                        else:
                            self.status = "playing"

                    elif command == "pause":
                        if self.status == "playing":
                            self.status = "paused"

                    elif command == "resume":
                        if self.status == "paused":
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
                if self.status == "playing":
                    self.position += 1
                    self.current_time = self.format_time(self.position)

                    if self.position >= self.song_length:
                        self.load_next_song()

    def shutdown(self):
        self.running = False
        self.stop_event.set()
        self.queue_commands.put("quit")
        self.playback_commands.put("quit")
        self.queue_thread.join(timeout=1)
        self.playback_thread.join(timeout=1)
        self.timer_thread.join(timeout=1)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos

                if event.button == 1:
                    if self.buttons["load"].collidepoint(mouse_pos):
                        self.queue_commands.put("load")

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
                        self.queue_commands.put("queue")
                        self.scroll_to_bottom()

                    elif self.buttons["next"].collidepoint(mouse_pos):
                        self.queue_commands.put("next")

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
            queue_items = self.queue_items[:]

        # Title bar
        pygame.draw.rect(self.screen, self.panel_color, (30, 24, 920, 70), border_radius=24)
        self.draw_text("MP3 Player", self.title_font, self.text_color, 55, 42)

        # Main player card
        pygame.draw.rect(self.screen, self.panel_color, (30, 112, 590, 360), border_radius=28)

        # Album art
        pygame.draw.rect(self.screen, self.card_color, (58, 145, 220, 220), border_radius=28)
        pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 52, width=8)
        pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 10)
        self.draw_text("Album Art", self.small_font, self.subtext_color, 125, 388)

        # Song info
        self.draw_text(current_song, self.header_font, self.text_color, 310, 165)
        self.draw_text(current_artist, self.body_font, self.subtext_color, 310, 205)

        # Progress
        self.draw_text(current_time, self.body_font, self.text_color, 310, 275)
        self.draw_text(total_time, self.body_font, self.text_color, 535, 275)
        pygame.draw.rect(self.screen, self.card_color, (310, 310, 250, 14), border_radius=10)

        progress_width = int(250 * (position / max(1, self.song_length)))
        pygame.draw.rect(self.screen, self.accent_color, (310, 310, progress_width, 14), border_radius=10)

        # Status
        if status == "playing":
            state_text = "Playing"
            state_color = self.success_color
        elif status == "paused":
            state_text = "Paused"
            state_color = self.warning_color
        else:
            state_text = "Idle"
            state_color = self.subtext_color

        pygame.draw.rect(self.screen, self.card_color, (310, 350, 170, 42), border_radius=18)
        self.draw_text(state_text, self.small_font, state_color, 346, 362)

        # Queue card
        pygame.draw.rect(self.screen, self.panel_color, self.queue_card_rect, border_radius=28)
        self.draw_text("Up Next", self.header_font, self.text_color, 680, 145)
        self.draw_scroll_controls(len(queue_items))
        self.draw_queue_list(queue_items)

        # Controls
        pygame.draw.rect(self.screen, self.panel_color, (30, 490, 920, 120), border_radius=28)
        self.draw_buttons(status)

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
            pygame.draw.rect(self.screen, self.card_color, item_rect, border_radius=18)
            self.draw_text(item, self.body_font, self.text_color, item_rect.x + 16, item_rect.y + 17)
            item_y += self.queue_item_height + self.queue_item_gap

        if not queue_items:
            empty_rect = pygame.Rect(
                self.queue_list_rect.x,
                self.queue_list_rect.y,
                self.queue_list_rect.width,
                self.queue_item_height,
            )
            pygame.draw.rect(self.screen, self.card_color, empty_rect, border_radius=18)
            self.draw_text("No queued songs", self.body_font, self.subtext_color, empty_rect.x + 16, empty_rect.y + 17)

        self.screen.set_clip(old_clip)

    def draw_scroll_controls(self, total_count):
        mouse_pos = pygame.mouse.get_pos()
        up_fill = self.soft_accent if self.scroll_up_rect.collidepoint(mouse_pos) else self.card_color
        down_fill = self.soft_accent if self.scroll_down_rect.collidepoint(mouse_pos) else self.card_color

        pygame.draw.rect(self.screen, up_fill, self.scroll_up_rect, border_radius=12)
        pygame.draw.rect(self.screen, down_fill, self.scroll_down_rect, border_radius=12)

        pygame.draw.polygon(
            self.screen,
            self.text_color,
            [
                (self.scroll_up_rect.centerx, self.scroll_up_rect.y + 10),
                (self.scroll_up_rect.x + 8, self.scroll_up_rect.bottom - 10),
                (self.scroll_up_rect.right - 8, self.scroll_up_rect.bottom - 10),
            ],
        )
        pygame.draw.polygon(
            self.screen,
            self.text_color,
            [
                (self.scroll_down_rect.centerx, self.scroll_down_rect.bottom - 10),
                (self.scroll_down_rect.x + 8, self.scroll_down_rect.y + 10),
                (self.scroll_down_rect.right - 8, self.scroll_down_rect.y + 10),
            ],
        )

        pygame.draw.rect(self.screen, self.scroll_track_color, self.scrollbar_rect, border_radius=16)

        total_items = max(1, total_count)
        visible_items = min(self.visible_queue_count, total_items)
        thumb_height = max(42, int(self.scrollbar_rect.height * (visible_items / total_items)))
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
            self.scrollbar_rect.width - 10,
            thumb_height,
        )
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

    def draw_text(self, text, font, color, x, y):
        surface = font.render(str(text), True, color)
        self.screen.blit(surface, (x, y))


if __name__ == "__main__":
    Running(None)