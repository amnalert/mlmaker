from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PySide6.QtCore import QUrl, Qt, Slot
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QLabel, QVBoxLayout
import random
import time
from pathlib import Path

SONG_EXTS = {".mp3", ".wav", ".flac", ".m4a"}
INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class MusicHandler(QWidget):
    def __init__(self, musicdir, volume, controller):
        super().__init__(controller)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        button_layout = QHBoxLayout()
        label_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addLayout(label_layout)

        self.volume = volume
        self.musicdir = musicdir
        self.looping = False

        self.play_button = QPushButton("Play/Pause")
        self.skip_button = QPushButton("Skip Song")
        self.prev_song_button = QPushButton("Previous Song")
        self.prev_song_button.setEnabled(False)
        self.loop_button = QPushButton("Loop: False")
        self.play_button.clicked.connect(lambda: self.play_or_pause())
        self.skip_button.clicked.connect(lambda: self.skip_song())
        self.prev_song_button.clicked.connect(lambda: self.prev_song())
        self.loop_button.clicked.connect(lambda: self.loop())
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addWidget(self.prev_song_button)
        button_layout.addWidget(self.loop_button)

        self.song_label = QLabel("Now playing:")
        self.next_song_label = QLabel("Up next:")
        self.queue_info = QLabel("Queue: (0/0)")
        label_layout.addWidget(self.song_label)
        label_layout.addWidget(self.next_song_label)
        label_layout.addWidget(self.queue_info)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput()

        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(volume)

        self.songs = [path for path in self.musicdir.iterdir() if path.is_file() and path.suffix.lower() in SONG_EXTS]
        if not self.songs:
            music_folder = INSTALL_LOCATION / "assets" / "music"
            music_folder.mkdir(parents=True, exist_ok=True)
            print(f"No songs found. Place songs in {music_folder}.")
        self.queue = self.songs.copy()
        random.shuffle(self.queue)
        self.song_index = 0
        self.player.setSource(QUrl.fromLocalFile(str(self.queue[self.song_index])))
        self.song_label.setText(f"Now playing: {Path(self.queue[self.song_index]).stem}")
        self.next_song_label.setText(f"Next up: {Path(self.queue[self.song_index + 1]).stem}")
        self.queue_info.setText(f"Queue: {self.song_index + 1}/{len(self.queue)} Songs")

        self.player.mediaStatusChanged.connect(self.next_song)
        self.player.errorOccurred.connect(self._error)

        self.media_devices = QMediaDevices()
        #self.media_devices.audioOutputsChanged.connect(self.audio_dev_change)
        self.em_pause = False

        self.startup = True

    def loop(self):
        if self.looping == False:
            self.looping = True
        else:
            self.looping = False
        self.loop_button.setText(f"Loop: {str(self.looping)}")

    def play_or_pause(self):
        self.em_pause = False
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            #print("Pausing")
        else:
            self.player.play()
            #print("Playing")

    def next_song(self, status):
        #print(status)
        if self.startup == True:
            self.startup = False
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.looping == True:
                self.player.setPosition(0)
            else:
                #print("End of song.")
                self.song_index += 1
                self.reset_source()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia and self.em_pause == False:
            self.player.play()

    def skip_song(self):
        self.song_index += 1
        self.reset_source()
        
    def prev_song(self):
        if self.song_index == 0:
            self.player.setPosition(0)
            self.reset_source()
        else:
            self.song_index -= 1
            self.reset_source()    

    def set_volume(self, volume):
        self.audio_output.setVolume(volume)

    def reset_source(self):
        if self.song_index == 0:
            self.prev_song_button.setEnabled(False)
        else:
            self.prev_song_button.setEnabled(True)

        if self.song_index == len(self.queue) - 1:
            self.next_song_label.setText(f"Songs will reshuffle after this song!")

        elif self.song_index == (len(self.queue)):
            #print("End of queue. Reshuffling songs.")
            self.songs = [path for path in self.musicdir.iterdir() if path.is_file() and path.suffix.lower() in SONG_EXTS]

            old_song = self.queue[-1]

            self.queue = self.songs.copy()
            random.shuffle(self.queue)

            # dont immediately repeat the previous song
            while len(self.queue) > 1 and self.queue[0] == old_song:
                random.shuffle(self.queue)

            self.song_index = 0
            self.next_song_label.setText(f"Next up: {Path(self.queue[1]).stem}")

        elif self.song_index < 0:
            self.song_index = 0

        else:
            self.next_song_label.setText(f"Next up: {Path(self.queue[self.song_index + 1]).stem}")

        self.song_label.setText(f"Now playing: {Path(self.queue[self.song_index]).stem}")
        self.queue_info.setText(f"Queue: {self.song_index + 1}/{len(self.queue)} Songs")

        self.player.setSource(
            QUrl.fromLocalFile(str(self.queue[self.song_index]))
        )

        if not self.player.PlaybackState.PlayingState:
            self.player.play()

    def audio_dev_change(self):
        self.em_pause = True
        print(f"Detected audio device change. Pausing.")

        pos = self.player.position()
        source = self.player.source()

        old_output = self.audio_output
        self.audio_output = QAudioOutput(self)
        self.audio_output.setDevice(
            self.media_devices.defaultAudioOutput()
        )
        self.audio_output.setVolume(self.volume)
        self.player.setAudioOutput(self.audio_output)

        old_output.deleteLater()

        if source.isValid():
            self.player.setSource(source)
            self.player.setPosition(pos)

        self.player.pause()

    def _error(self, error):
        print("========== MEDIA ERROR ==========")
        print("Error:", error)
        print("String:", self.player.errorString())
        print("Source:", self.player.source().toString())
        print("Status:", self.player.mediaStatus())
        print("State:", self.player.playbackState())