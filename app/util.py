from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QFontMetrics
from PySide6.QtCore import QTimer, Qt

class AutoScalingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("font-weight: bold;")
        self._last_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        super().setText(text)
        self.updateGeometry()
        QTimer.singleShot(0, self.scale_font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scale_font()

    def scale_font(self):
        text = self.text()
        if not text:
            return

        target_width = self.width() - 20
        target_height = self.height() - 10
        if target_width <= 20 or target_height <= 10:
            return

        font = self.font()
        font_size = 128 # Max desired
        font.setPointSize(font_size)

        while font_size > 10:
            metrics = QFontMetrics(font)
            rect = metrics.boundingRect(text)
            if rect.width() <= target_width and rect.height() <= target_height:
                break
            font_size -= 1
            font.setPointSize(font_size)

        self.setFont(font)
