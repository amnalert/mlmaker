from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QMainWindow
import random

SONG_EXTS = {".mp3", ".wav", ".flac", ".m4a"}

class MusicLoop(QMainWindow):
    def __init__(self, musicdir, volume, controller):
        super(MusicLoop, self).__init__(controller)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.play_button = QPushButton("Play/Pause")
        self.play_button.clicked.connect(lambda: self.play_or_pause())
        layout.addWidget(self.play_button, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignHCenter)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput()

        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(volume)

        self.songs = [path for path in musicdir.iterdir() if path.is_file() and path.suffix.lower() in SONG_EXTS]
        if not self.songs:
            print("No songs found.")
        self.queue = self.songs.copy()
        random.shuffle(self.queue)
        self.song_index = 0
        self.player.setSource(QUrl.fromLocalFile(str(self.queue[0])))

    def play_or_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            print("Pausing")
        else:
            self.player.play()
            print("Playing")

    def stop(self):
        self.player.stop()

    def set_volume(self, volume):
        self.audio_output.setVolume(volume)