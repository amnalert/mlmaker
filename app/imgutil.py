from PySide6.QtWidgets import QWidget, QPushButton, QMainWindow, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon, QCursor
import sys, os
import json
import math
from pathlib import Path

class ImageView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.mlayout = QVBoxLayout(self)
        self.mlayout.setContentsMargins(10, 10, 10, 10)



        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.setFixedHeight(40)
        self.back_button.clicked.connect(lambda: self.controller.switch_page(2))
        self.back_button.clicked.connect(lambda: self.controller.home.update_image_page)

        # Image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(0, 0)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
        )

        self.image_name = QLabel()
        self.image_name.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.mlayout.addWidget(self.image_name)
        self.mlayout.addWidget(self.image_label)
        self.mlayout.addWidget(self.back_button, 1)

    def view_image(self, img):
        self.image_name.setText(f"{img.name}")
        self.orig_pixmap = QPixmap(str(img))

        self.image_label.setPixmap(
            self.orig_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )

    def update_image(self):
        if self.orig_pixmap.isNull():
            return

        avail_size = self.image_label.size()
        pixmap = self.orig_pixmap.scaled(
            avail_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "orig_pixmap"):
            self.update_image()
