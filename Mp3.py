import tkinter as tk
import pygame  
class Running:
    def __init__(self, root):
        pygame.mixer.init()  

        self.root = root
        self.root.title("Music Player")  
        self.root.geometry("1000x700")
        self.root.configure(bg="white")
        
        
    def load_song(self):
         file = filedialog.askopenfilename(filetypes=[("MP3 Files", "*.mp3")])
         if file:
            self.current_song = file
            self.label.config(text=file)
    def play_music(self):
        

    def updateTimer(self):
        

    def pause_music(self):
        

    def unpause_music(self):
        

    def queue_music(self):
        

    def next_song(self):
       

    def fetch_album_art(self, song_query):
       

    def check_end(self):


if __name__ == "__main__":