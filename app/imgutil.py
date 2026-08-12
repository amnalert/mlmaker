from PySide6.QtWidgets import QWidget, QPushButton, QComboBox, QFrame, QMainWindow, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
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

        main_layout = QHBoxLayout()

        ### Image stuff

        imglayout = QVBoxLayout()
        imglayout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(imglayout)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.setFixedHeight(40)
        self.back_button.clicked.connect(lambda: self.controller.switch_page(2))
        self.back_button.clicked.connect(lambda: self.controller.home.update_image_page)

        # Image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(0, 0)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
        )

        imglayout.addWidget(self.image_label, 1)
        imglayout.addWidget(self.back_button, 0)

        ### Right-side UI

        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout)

        # Top to bottom
        self.image_name = QLabel()
        self.image_name.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        right_layout.addWidget(self.image_name)

        self.species_list = QComboBox()
        right_layout.addWidget(self.species_list)

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
