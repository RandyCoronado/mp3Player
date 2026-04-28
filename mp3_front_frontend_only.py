import pygame


class Running:
    def __init__(self, root):
        """
        Frontend-only pygame setup.

        What this does:
        - creates the window
        - stores colors, fonts, and layout
        - runs the event loop
        - draws a mock MP3 player interface

        What this does NOT do yet:
        - real music playback
        - real file loading
        - real timers
        - real album art fetching
        - no threads

        """
        # root is kept only to match the required class structure.
        self.root = root

        pygame.init()
        pygame.font.init()

        # Window setup
        self.screen_width = 980
        self.screen_height = 640
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("MP3 Player")
        self.clock = pygame.time.Clock()
        self.running = True

        # Colors used for the clean dark UI
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

        # Fonts for readability
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.header_font = pygame.font.SysFont("arial", 24, bold=True)
        self.body_font = pygame.font.SysFont("arial", 20)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.button_font = pygame.font.SysFont("arial", 22, bold=True)

        # Frontend-only preview data
        self.current_song = "No song loaded"
        self.current_artist = "Frontend preview only"
        self.current_time = "00:00"
        self.total_time = "03:42"
        self.is_paused = False
        self.queue_items = [
            "Midnight Drive",
            "Ocean Echo",
            "Neon Sunset",
            "City Lights",
            "Blue Horizon",
            "Afterglow",
            "Skyline Run",
            "Golden Waves",
        ]

        # Queue layout
        self.queue_scroll_index = 0
        self.visible_queue_count = 4
        self.queue_card_rect = pygame.Rect(650, 112, 300, 360)
        self.queue_list_rect = pygame.Rect(675, 205, 210, 245)
        self.scrollbar_rect = pygame.Rect(895, 190, 30, 206)
        self.scroll_up_rect = pygame.Rect(895, 145, 30, 36)
        self.scroll_down_rect = pygame.Rect(895, 414, 30, 36)
        self.queue_item_height = 58
        self.queue_item_gap = 14

        # Large tap-friendly buttons
        self.buttons = {
            "load": pygame.Rect(60, 510, 140, 72),
            "play": pygame.Rect(220, 510, 140, 72),
            "pause": pygame.Rect(380, 510, 140, 72),
            "queue": pygame.Rect(540, 510, 140, 72),
            "next": pygame.Rect(700, 510, 140, 72),
        }

        # Main frontend loop
        while self.running:
            self.handle_events()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def load_music(self):
        """
        Frontend placeholder.

        This only changes the text on screen so people can tell
        where loaded song info would appear later.
        """
        self.current_song = "Loaded Song Preview"
        self.current_artist = "UI placeholder only"

    def play_music(self):
        """
        Frontend placeholder.

        This does not play real audio.
        It only changes the preview state.
        """
        self.is_paused = False

    def updateTimer(self):
        """
        Frontend placeholder.

        A real version would update the playback time.
        Kept empty on purpose for the frontend-only version.
        """
        pass

    def pause_music(self):
        """
        Frontend placeholder.

        This does not pause real audio.
        It only changes the preview state.
        """
        self.is_paused = True

    def unpause_music(self):
        """
        Frontend placeholder.

        This does not resume real audio.
        It only changes the preview state.
        """
        self.is_paused = False

    def queue_music(self):
        """
        Frontend placeholder.

        This adds a fake song into the visual queue so the list
        can be tested without real MP3 logic.
        """
        self.queue_items.append(f"Preview Song {len(self.queue_items) + 1}")
        self.scroll_to_bottom()

    def next_song(self):
        """
        Frontend placeholder.

        This visually moves to the next fake queued song.
        No real playback happens here.
        """
        if self.queue_items:
            self.current_song = self.queue_items.pop(0)
            self.current_artist = "Queue preview only"
            self.queue_scroll_index = min(self.queue_scroll_index, self.max_scroll_index())

    def fetch_album_art(self, song_query):
        """
        Frontend placeholder.

        A real version would search for and load album art.
        Empty on purpose for the frontend-only version.
        """
        pass

    def check_end(self):
        """
        Frontend placeholder.

        A real version would detect when a song finishes.
        Empty on purpose for the frontend-only version.
        """
        pass

    def max_scroll_index(self):
        """Returns the last allowed queue scroll position."""
        return max(0, len(self.queue_items) - self.visible_queue_count)

    def scroll_queue(self, direction):
        """Moves the visual queue up or down inside the list box."""
        self.queue_scroll_index = max(
            0,
            min(self.queue_scroll_index + direction, self.max_scroll_index())
        )

    def scroll_to_bottom(self):
        """Keeps newly added preview songs visible."""
        self.queue_scroll_index = self.max_scroll_index()

    def handle_events(self):
        """
        Handles clicks and wheel scrolling for the frontend preview.
        These actions only update the mock interface.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos

                if event.button == 1:
                    if self.buttons["load"].collidepoint(mouse_pos):
                        self.load_music()
                    elif self.buttons["play"].collidepoint(mouse_pos):
                        self.play_music()
                    elif self.buttons["pause"].collidepoint(mouse_pos):
                        if self.is_paused:
                            self.unpause_music()
                        else:
                            self.pause_music()
                    elif self.buttons["queue"].collidepoint(mouse_pos):
                        self.queue_music()
                    elif self.buttons["next"].collidepoint(mouse_pos):
                        self.next_song()
                    elif self.scroll_up_rect.collidepoint(mouse_pos):
                        self.scroll_queue(-1)
                    elif self.scroll_down_rect.collidepoint(mouse_pos):
                        self.scroll_queue(1)

                if event.button == 4 and self.queue_card_rect.collidepoint(mouse_pos):
                    self.scroll_queue(-1)
                elif event.button == 5 and self.queue_card_rect.collidepoint(mouse_pos):
                    self.scroll_queue(1)

    def draw_ui(self):
        """
        Draws the full frontend preview.

        Visual design notes:
        - dark background for contrast
        - rounded cards for a modern look
        - large buttons for easier tapping
        - separated queue list and scrollbar so items never overlap controls
        """
        self.screen.fill(self.bg_color)

        # Title bar
        pygame.draw.rect(self.screen, self.panel_color, (30, 24, 920, 70), border_radius=24)
        self.draw_text("MP3 Player", self.title_font, self.text_color, 55, 42)

        # Main player card
        pygame.draw.rect(self.screen, self.panel_color, (30, 112, 590, 360), border_radius=28)

        # Album art placeholder box
        pygame.draw.rect(self.screen, self.card_color, (58, 145, 220, 220), border_radius=28)
        pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 52, width=8)
        pygame.draw.circle(self.screen, self.soft_accent, (168, 255), 10)
        self.draw_text("Album Art", self.small_font, self.subtext_color, 125, 388)

        # Song information
        self.draw_text(self.current_song, self.header_font, self.text_color, 310, 165)
        self.draw_text(self.current_artist, self.body_font, self.subtext_color, 310, 205)

        # Fake progress area
        self.draw_text(self.current_time, self.body_font, self.text_color, 310, 275)
        self.draw_text(self.total_time, self.body_font, self.text_color, 535, 275)
        pygame.draw.rect(self.screen, self.card_color, (310, 310, 250, 14), border_radius=10)
        pygame.draw.rect(self.screen, self.accent_color, (310, 310, 96, 14), border_radius=10)

        # Playback status pill
        play_state = "Paused" if self.is_paused else "Preview Mode"
        state_color = self.warning_color if self.is_paused else self.success_color
        pygame.draw.rect(self.screen, self.card_color, (310, 350, 170, 42), border_radius=18)
        self.draw_text(play_state, self.small_font, state_color, 346, 362)

        # Queue card
        pygame.draw.rect(self.screen, self.panel_color, self.queue_card_rect, border_radius=28)
        self.draw_text("Up Next", self.header_font, self.text_color, 680, 145)
        self.draw_scroll_controls()
        self.draw_queue_list()

        # Bottom controls
        pygame.draw.rect(self.screen, self.panel_color, (30, 490, 920, 120), border_radius=28)
        self.draw_buttons()

    def draw_queue_list(self):
        """
        Draws only the visible queue items inside the queue viewport.

        The clip rectangle makes sure songs stay inside the list area
        and never spill over the scrollbar or outside the box.
        """
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self.queue_list_rect)

        visible_items = self.queue_items[
            self.queue_scroll_index:self.queue_scroll_index + self.visible_queue_count
        ]

        item_y = self.queue_list_rect.y
        item_width = self.queue_list_rect.width

        for item in visible_items:
            item_rect = pygame.Rect(
                self.queue_list_rect.x,
                item_y,
                item_width,
                self.queue_item_height,
            )
            pygame.draw.rect(self.screen, self.card_color, item_rect, border_radius=18)
            self.draw_text(item, self.body_font, self.text_color, item_rect.x + 16, item_rect.y + 17)
            item_y += self.queue_item_height + self.queue_item_gap

        if not self.queue_items:
            empty_rect = pygame.Rect(
                self.queue_list_rect.x,
                self.queue_list_rect.y,
                self.queue_list_rect.width,
                self.queue_item_height,
            )
            pygame.draw.rect(self.screen, self.card_color, empty_rect, border_radius=18)
            self.draw_text("No queued songs", self.body_font, self.subtext_color, empty_rect.x + 16, empty_rect.y + 17)

        self.screen.set_clip(old_clip)

    def draw_scroll_controls(self):
        """
        Draws the separate scrollbar lane for the queue.

        The arrows sit above and below the track.
        The scroll thumb stays inside the track and does not cover the buttons.
        """
        mouse_pos = pygame.mouse.get_pos()
        up_fill = self.soft_accent if self.scroll_up_rect.collidepoint(mouse_pos) else self.card_color
        down_fill = self.soft_accent if self.scroll_down_rect.collidepoint(mouse_pos) else self.card_color

        # Arrow buttons
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

        # Scroll track
        pygame.draw.rect(self.screen, self.scroll_track_color, self.scrollbar_rect, border_radius=16)

        total_items = max(1, len(self.queue_items))
        visible_items = min(self.visible_queue_count, total_items)
        thumb_height = max(42, int(self.scrollbar_rect.height * (visible_items / total_items)))
        track_range = self.scrollbar_rect.height - thumb_height

        if self.max_scroll_index() == 0:
            thumb_y = self.scrollbar_rect.y
        else:
            progress = self.queue_scroll_index / self.max_scroll_index()
            thumb_y = self.scrollbar_rect.y + int(track_range * progress)

        thumb_rect = pygame.Rect(
            self.scrollbar_rect.x + 5,
            thumb_y,
            self.scrollbar_rect.width - 10,
            thumb_height,
        )
        pygame.draw.rect(self.screen, self.scroll_thumb_color, thumb_rect, border_radius=14)

    def draw_buttons(self):
        """
        Draws the main control buttons.

        These are big on purpose so the layout is easy to test
        for touch-friendly spacing.
        """
        button_labels = {
            "load": "Load",
            "play": "Play",
            "pause": "Resume" if self.is_paused else "Pause",
            "queue": "Queue",
            "next": "Next",
        }

        mouse_pos = pygame.mouse.get_pos()

        for key, rect in self.buttons.items():
            hovered = rect.collidepoint(mouse_pos)
            fill = self.soft_accent if hovered else self.accent_color
            pygame.draw.rect(self.screen, fill, rect, border_radius=22)
            pygame.draw.rect(self.screen, self.border_color, rect, width=2, border_radius=22)

            label_surface = self.button_font.render(button_labels[key], True, self.text_color)
            label_rect = label_surface.get_rect(center=rect.center)
            self.screen.blit(label_surface, label_rect)

    def draw_text(self, text, font, color, x, y):
        """Small helper for drawing text."""
        text_surface = font.render(text, True, color)
        self.screen.blit(text_surface, (x, y))


if __name__ == "__main__":
    Running(None)
