from PySide6.QtWidgets import QApplication, QWidget, QGridLayout, QPushButton, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QPixmap, QIcon, QFont, QKeyEvent
from pathlib import Path

from labelling_controls import ImageLabellingControls

class ImageView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.project = ""
        self.images = []
        self.species = []
        self.image_label_file = ""
        self.default_class = "none"

        main_layout = QHBoxLayout(self)

        # Fonts
        self.pt16 = QFont()
        self.pt8 = QFont()
        self.pt16.setPointSize(16)
        self.pt8.setPointSize(8)

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

        # Image index
        self.img_index = 0
        self.img_index_lbl = QLabel("Image: 0/0")
        self.img_index_lbl.setFont(self.pt8)

        # Image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(QSize(10, 10))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidget(self.image_label)
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.image_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.image_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_scroll_area.setMinimumSize(QSize(120, 120))

        # Crosshair on image hover
        self.img_labelling_controls = ImageLabellingControls(self, self.image_label)

        imglayout.addWidget(self.image_scroll_area, stretch=1)
        imglayout.addWidget(self.back_button)
        imglayout.addWidget(self.img_index_lbl)

        ### Right-side UI

        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout)

        # Top to bottom
        self.image_name = QLabel()
        self.box_label_1 = QLabel("Point 1: (0, 0)")
        self.box_label_2 = QLabel("Point 2: (0, 0)")
        self.mouse_pos_label = QLabel("Mouse: (0, 0)")

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
        self.scroll_boxes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # Add to layout
        right_layout.addWidget(self.image_name, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.box_label_1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.box_label_2, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.mouse_pos_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        right_layout.addWidget(self.scroll_boxes, stretch=1)

        self.scroll_boxes.setWidget(self.scroll_boxes_content)

        # Default class
        self.change_default_class_btn = QPushButton("Change default class")
        self.change_default_class_btn.clicked.connect(self.change_default_class)
        right_layout.addWidget(self.change_default_class_btn)

        # Show all boxes
        self.show_all_boxes_btn = QPushButton("Show all boxes")
        self.show_all_boxes_btn.clicked.connect(lambda: self.img_labelling_controls._draw_all_boxes())
        right_layout.addWidget(self.show_all_boxes_btn, alignment=(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter))

    def change_default_class(self):
        choice, ok = QInputDialog.getItem(
            self,
            "Choose default class",
            "Select a class new boxes will be assigned from the following:",
            self.species
        )
        if ok and choice:
            self.default_class = choice

    def view_image(self, img, prj, img_list):
        self.images = img_list
        self.img_index = img_list.index(img)
        self.image_name.setText(f"{img.parent.name}/{img.name}")
        self.orig_pixmap = QPixmap(str(img))
        self.project = self.controller.home.current_project
        self.species = self.controller.home.project_classes
        label_folder = prj / "image_labels"
        if img.parent.name != "image_uploads":
            label_folder /= img.parent.name
        self.image_label_file = label_folder / f"{img.stem}.txt"
        self.image_label_file.parent.mkdir(parents=True, exist_ok=True)
        self.image_label_file.touch()
        self.img_index_lbl.setText(f"Image: {self.img_index + 1}/{len(self.images)}")
        self.image_label.setPixmap(self.orig_pixmap)
        self.update_image()
        self.img_labelling_controls.load_saved_boxes(self.image_label_file)

    def update_image(self):
        if not hasattr(self, "orig_pixmap") or self.orig_pixmap.isNull():
            return

        available_size = self.image_scroll_area.viewport().size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return

        pixmap = self.orig_pixmap.scaled(
            available_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(pixmap.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "orig_pixmap"):
            self.update_image()

class FirstPass(QWidget):
    def __init__(self, parents, controller):
        super().__init__()
        self.parents = parents
        self.controller = controller

        self.setWindowTitle("First Pass")

        self.controls_dialog = QLabel(
            """
            Left Key    - Mark to delete
            Right Key   - Mark to save
            Spacebar    - Next Frame / Skip
            Shift Key   - Previous Frame / Back

            X Key       - Toggle auto skip to next Frame on Left/Right Key press(Default: True)
            C Key       - Hold to display these controls

            Enter Key   - Display unmarked Frames / Confirm Selection(Opens dialog box before deletion)
            Escape Key  - Open Menu: Cancel this Video's Import, Save for later and Exit
            """
        )

        self.menu_dialog = QWidget(self, Qt.WindowType.Dialog)
        screen = QApplication.primaryScreen().availableGeometry()
        self.menu_dialog.resize(int(screen.width() * 0.5), int(screen.height() * 0.5))
        self.menu_dialog.move(screen.center() - self.menu_dialog.rect().center())
        self.menu_layout = QVBoxLayout()
        self.menu_dialog.setLayout(self.menu_layout)
        self.menu_text = QLabel("First Pass Menu")
        self.cancel_vid_btn = QPushButton("Remove Video From Project")
        self.save_later_btn = QPushButton("Save for later and Exit")
        self.cancel_vid_btn.clicked.connect(lambda _: self.cancel_this_video())
        self.save_later_btn.clicked.connect(lambda _: self.save_and_quit())

        self.menu_layout.addWidget(self.menu_text, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.cancel_vid_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.menu_layout.addWidget(self.save_later_btn, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))

        # Internal info
        self.current_video_folder = ""
        self.current_project = ""

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.menu_dialog.show()

        elif event.key() == Qt.Key.Key_Right:
            pass

        elif event.key() == Qt.Key.Key_Left:
            pass

    def begin_pass(self, video, video_folder, prj_folder):
        self.current_video_folder = video_folder
        self.current_video = video # which is in video_folder / "{video_folder.stem}.mp4/mov/etc"
        self.current_project = prj_folder # video_folder.parent.parent

        QMessageBox.information(
            self,
            "How to do a First Pass",
            f"""
            After uploading a video, it converts itself to individual frames. It is useful to run a 'First Pass' by quickly going through all frames and selecting frames for deletion(e.g. if the frame has no objects in it).

            The controls are as follows:

            {self.controls_dialog.text()}
            """
        )

    def cancel_this_video(self):
        reply = QMessageBox.question(
            self,
            "Remove Video from Project",
            f"Are you sure you want to remove video '{self.current_video.name}' from the project, which will also remove all of its image Frames? All labels will be lost!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            pass

    def save_and_quit(self):
        save_location = Path(self.current_project) / "first_pass_saves"
        save_location.mkdir(parents=True, exist_ok=True)

        