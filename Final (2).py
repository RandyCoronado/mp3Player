import tkinter as tk
import pygame  # pip3 install pygame
from tkinter import filedialog
import requests  # pip3 install requests
from PIL import Image, ImageTk  # pip3 install pillow
from io import BytesIO


class Running:
    def __init__(self, root):
        pygame.mixer.init()  # initializes the mixer module

        self.root = root
        self.root.title("Music Player")  # sets the title of the window
        self.root.geometry("800x500")
        self.root.configure(bg="ghostwhite")

        self.song_queue = []  # List of song queue

        self.mainFrame = tk.Frame(self.root, bg="black", height=250)
        self.mainFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.song_label = tk.Label(self.mainFrame, text=" No song loaded ", wraplength=250,
                                   bg="grey20", font=("San Francisco", 25, "bold"), fg="white")
        self.song_label.pack(pady=10)

        # Album art display
        self.album_art_label = tk.Label(self.mainFrame, bg="black")
        self.album_art_label.pack(pady=10)

        nextUpLabel = tk.Label(self.mainFrame, text="Next Up", bg="black", fg="white", font=("San Francisco", 15))
        nextUpLabel.pack(pady=2)
        self.nextUp = tk.Listbox(self.mainFrame, bg="dimgrey", fg="white", font=("San Francisco", 15), height=3,
                                 width=20)
        self.nextUp.pack(pady=2)

        # intial buttons when the program starts

        buttonFrame = tk.Frame(root, bg="midnightblue")
        buttonFrame.pack(expand=False, padx=10, pady=10)

        loadButton = tk.Button(buttonFrame, text="Load Music", command=self.load_music)
        loadButton.pack()

        rewindButton = tk.Button(buttonFrame, text="Rewind", command=self.play_music)
        rewindButton.pack(side=tk.LEFT, padx=5, expand=True)

        self.playButton = tk.Button(buttonFrame, text="Play", command=self.play_music)
        self.playButton.pack(side=tk.LEFT, padx=5, expand=True)

        pauseButton = tk.Button(buttonFrame, text="Pause", command=self.pause_music)
        pauseButton.pack(side=tk.LEFT, padx=5, expand=True)

        queueButton = tk.Button(buttonFrame, text="Queue", command=self.queue_music)
        queueButton.pack(side=tk.LEFT, padx=5, expand=True)

        nextButton = tk.Button(buttonFrame, text="Next", command=self.next_song)
        nextButton.pack(side=tk.LEFT, padx=5, expand=True)

    def load_music(self):
        self.playButton.configure(command=self.play_music)
        # opens a file dialog to select an mp3 file and only mp3 files
        self.file_path = filedialog.askopenfilename(filetypes=[("MP3", "*.mp3")])
        if self.file_path:
            pygame.mixer.music.load(self.file_path)
            # splits the file path to get the song name and removes the .mp3
            song_name = self.file_path.split("/")[-1].replace(".mp3", "")
            self.song_label.configure(text=song_name, font=("San Francisco", 25, "bold"))
            self.fetch_album_art(song_name)
            if hasattr(self, 'music_position'):
                self.music_position.destroy()  # destroys the previous time label if it exists

    def play_music(self):
        if hasattr(self, 'music_position'):
            self.music_position.destroy()
        pygame.mixer.music.play()
        pygame.mixer.music.get_pos()
        self.music_position = tk.Label(self.mainFrame, text="0:00", fg="white", bg="black", font=("San Francisco", 15))
        self.music_position.pack()
        self.playButton.configure(command=self.unpause_music)
        self.updateTimer()
        self.check_end()

    def updateTimer(self):
        if pygame.mixer.music.get_busy():  # checks if the music is playing
            pos = pygame.mixer.music.get_pos()  # in milliseconds check the position of the song
            seconds = pos // 1000
            minutes = seconds // 60
            seconds = seconds % 60
            songTime = (f"{minutes:02}:{seconds:02}")  # format as mm:ss
            self.music_position.configure(text=songTime, fg="white")  # keeps updating the label
            self.root.after(1000, self.updateTimer)  # updates every 1000 milliseconds or 1 second

    def pause_music(self):
        pygame.mixer.music.pause()
        self.playButton.configure(command=self.unpause_music)

    def unpause_music(self):
        pygame.mixer.music.unpause()
        self.root.after(1000, self.updateTimer)

    def queue_music(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP3", "*.mp3")])
        if file_path:
            self.song_queue.append(file_path)  # Add to internal queue
            next_song_name = file_path.split("/")[-1].replace(".mp3", "")
            self.nextUp.insert(tk.END, next_song_name)  # Display in listbox
            self.nextUp.configure(font=("San Francisco", 15), bg="dimgrey", fg="white")

    def next_song(self):
        if self.song_queue:
            next_path = self.song_queue.pop(0)
            next_name = next_path.split("/")[-1].replace(".mp3", "")
            self.song_label.configure(text=next_name)
            pygame.mixer.music.load(next_path)
            pygame.mixer.music.play()
            self.fetch_album_art(next_name)

            if hasattr(self, 'music_position'):
                self.music_position.destroy()
            self.music_position = tk.Label(self.mainFrame, text="0:00", fg="white", bg="black",
                                           font=("San Francisco", 15))
            self.music_position.pack()
            self.updateTimer()

            if self.nextUp.size() > 0:
                self.nextUp.delete(0, 0)

            self.check_end()

    def fetch_album_art(self, song_query):
        # Search on Apple Music/Itunes
        response = requests.get("https://itunes.apple.com/search", params={
            "term": song_query,  # search term
            "media": "music",  # restrict to music
            "entity": "song",  # Specify that we are searching for songs
            "limit": 1
        })

        # Parse response
        data = response.json()
        if hasattr(self, 'album_art_label'):
            self.album_art_label.configure(image=None)
        else:
            self.album_art_label.configure(image=None)
            self.album_art_label.image = None
        if data["resultCount"] > 0:  # checks if there are results
            result = data["results"][0]  # gets the first result
            artwork_url = result["artworkUrl100"].replace("100x100", "600x600")  # gets the URL for the album art
            img_data = requests.get(artwork_url).content  # downloads the image data
            img = Image.open(BytesIO(img_data))  # opens the image using PIL
            img = img.resize((150, 150))  # resizes the image to 150x150 pixels
            album_art = ImageTk.PhotoImage(img)  # converts the image to a format Tkinter can use
            self.album_art_label.configure(image=album_art, bg="ghostwhite")
            self.album_art_label.image = album_art  # Keeps a reference to the image os it gets displayed

    def check_end(self):
        if not pygame.mixer.music.get_busy():
            self.next_song()
        else:
            self.root.after(1000, self.check_end)


if __name__ == "__main__":
    root = tk.Tk()
    app = Running(root)
    root.mainloop()
