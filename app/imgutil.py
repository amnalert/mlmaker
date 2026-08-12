from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QComboBox, QFrame, QMainWindow, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QIcon
import sys, os
import json
import math
from pathlib import Path

from crosshair import ImageLabellingControls

class ImageView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.project = ""
        self.species = []
        self.image_label_file = ""

        main_layout = QHBoxLayout(self)

        ### Image stuff

        imglayout = QVBoxLayout()
        imglayout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(imglayout)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.setFixedHeight(40)
        self.back_button.setFixedWidth(120)
        self.back_button.clicked.connect(lambda: self.controller.switch_page(2))
        self.back_button.clicked.connect(lambda: self.controller.home.update_image_page)

        # Image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(QSize(10, 10))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Crosshair on image hover
        self.img_labelling_controls = ImageLabellingControls(self, self.image_label)

        imglayout.addWidget(self.image_label)
        imglayout.addWidget(self.back_button)

        ### Right-side UI

        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout)

        # Top to bottom
        self.image_name = QLabel()
        self.species_list_dropdown = QComboBox()
        self.box_label_1 = QLabel("Point 1: (0, 0)")
        self.box_label_2 = QLabel("Point 2: (0, 0)")

        # Placed boxes scroll area
        self.scroll_boxes_content = QWidget()
        self.scroll_boxes_layout = QGridLayout(self.scroll_boxes_content)
        self.scroll_boxes_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_boxes_layout.setSpacing(5)

        self.scroll_boxes = QScrollArea()
        self.scroll_boxes.setWidgetResizable(True)
        self.scroll_boxes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_boxes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            # Resize policies
        self.species_list_dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.scroll_boxes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # Add to layout
        right_layout.addWidget(self.image_name, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.species_list_dropdown, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.box_label_1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.box_label_2, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.scroll_boxes, stretch=1)

        self.scroll_boxes.setWidget(self.scroll_boxes_content)
        
    def view_image(self, img, prj):
        self.image_name.setText(f"{img.name}")
        self.orig_pixmap = QPixmap(str(img))
        self.project = self.controller.home.project
        self.species = self.controller.home.project_classes
        self.species_list_dropdown.addItems(self.species)
        self.image_label_file = Path(prj / "image_labels" / f"{img.stem}.txt")
        self.image_label_file.parent.mkdir(parents=True, exist_ok=True)
        self.image_label_file.touch()

        scaled_pixmap = self.orig_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size())
        self.img_labelling_controls.load_saved_boxes(self.image_label_file)

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
