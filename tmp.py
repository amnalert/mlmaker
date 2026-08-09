import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


app = QApplication(sys.argv)

player = QMediaPlayer()
audio = QAudioOutput()

player.setAudioOutput(audio)
audio.setVolume(1.0)

player.positionChanged.connect(
    lambda p: print("POSITION:", p)
)

player.mediaStatusChanged.connect(
    lambda s: print("STATUS:", s)
)

player.playbackStateChanged.connect(
    lambda s: print("STATE:", s)
)

player.errorOccurred.connect(
    lambda e: print("ERROR:", e, player.errorString())
)

player.setSource(
    QUrl.fromLocalFile(
        r"A:\VS Projects\Machine Learning Species ID\mlmaker\assets\music\thrash-machine.wav"
    )
)

player.play()

sys.exit(app.exec())