from PySide6.QtWidgets import QApplication, QGridLayout, QWidget, QPushButton, QMainWindow, QLabel, QLineEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QInputDialog, QMessageBox, QStackedWidget, QScrollArea
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon, QFontMetrics, QCursor, QIntValidator, QFont
import sys
import json, uuid
import math
from pathlib import Path

from login import LoginWindow, NewAccountWindow
from util import AutoScalingLabel
from dataloader import UploadImages, UploadLabels
from imgutil import ImageView, FirstPass
from audioutil import MusicHandler 
from project_explorer import ProjectExplorer
from tcp_manager import TCPManager
from network_explorer import NetworkExplorer

SAVED_USER_DATA = ""
INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

class ProjectWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        ### INITIALIZE VARIABLES

        # User info
        self.username = self.controller.username

        # Images
        self.images = []
        self.images_per_page = 20
        self.current_page = 0

        # Project
        self.project_classes = []
        self.labels_without_images = []
        self.current_project = ""
        self.uuid = ""

        # Fonts
        self.pt16 = QFont()
        self.pt8 = QFont()
        self.pt16.setPointSize(16)
        self.pt8.setPointSize(8)
        self.current_project = ""

        ### WINDOW SIZING

        # Main window
        current_screen = QApplication.screenAt(QCursor.pos())
        if not current_screen:
            current_screen = QApplication.primaryScreen()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.mlayout = QVBoxLayout(central_widget)
        central_widget.setLayout(self.mlayout)

        ### INSTANTIATE OBJECTS
        self.show_user = QLabel("")
        self.show_project = QLabel("")
        self.show_uuid = QLabel("")
        self.show_uuid.setFont(self.pt8)
        self.mlayout.addWidget(self.show_user, alignment=Qt.AlignmentFlag.AlignTop) 
        self.mlayout.addWidget(self.show_project, alignment=Qt.AlignmentFlag.AlignTop) 
        self.mlayout.addWidget(self.show_uuid, alignment=Qt.AlignmentFlag.AlignTop)

        self.upload_imgs = UploadImages(self, self.controller)
        self.mlayout.addWidget(self.upload_imgs, alignment=Qt.AlignmentFlag.AlignBottom)

        self.upload_labels = UploadLabels(self, self.controller)
        self.mlayout.addWidget(self.upload_labels, alignment=Qt.AlignmentFlag.AlignBottom)

        self.labels_without_images_label = QLabel("Labels missing images: 0")
        self.pt16 = QFont()
        self.pt16.setPointSize(16)
        self.labels_without_images_label.setFont(self.pt16)
        self.view_missing_images_list = QPushButton("View Unmatched Label Files")
        self.view_missing_images_list.setEnabled(False)
        self.view_missing_images_list.clicked.connect(lambda _: self.view_missing_images(self.labels_without_images))
        self.mlayout.addWidget(self.labels_without_images_label, alignment=Qt.AlignmentFlag.AlignBottom)
        self.mlayout.addWidget(self.view_missing_images_list, alignment=Qt.AlignmentFlag.AlignBottom)

        # Species information for this project
        self.edit_class_btn = QPushButton("Edit class list")
        self.edit_class_btn.clicked.connect(self.edit_class_list)
        self.mlayout.addWidget(self.edit_class_btn, alignment=(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom))

        # Showing images
        self.scroll_imgs = QScrollArea(self)
        self.scroll_imgs.setWidgetResizable(True)
        self.scroll_imgs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_imgs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mlayout.addWidget(self.scroll_imgs)

        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)
        for i in range(8):
            self.scroll_layout.setColumnStretch(i, 1)
        for i in range(6):
            self.scroll_layout.setRowStretch(i, 1)

        self.scroll_imgs.setWidget(self.scroll_content)

        # Page layout 
        self.page_layout = QHBoxLayout()

        self.prev_btn = QPushButton("Previous")
        self.next_btn = QPushButton("Next")
        self.page_lbl = QLabel("Page 0 of 0")

        self.prev_btn.clicked.connect(self.previous_page)
        self.next_btn.clicked.connect(self.next_page)

        self.page_layout.addWidget(self.prev_btn)
        self.page_layout.addWidget(self.next_btn)
        self.page_layout.addWidget(self.page_lbl)

        self.mlayout.addLayout(self.page_layout)

        self.image_count_label = QLabel("Images per page:")
        self.image_count_input = QLineEdit()
        self.image_count_input.setText("20")
        self.image_count_input.setFixedWidth(50)
        self.image_count_input.setValidator(QIntValidator(1, 100))
        self.image_count_input.returnPressed.connect(self.change_images_per_page)

        self.page_layout.addWidget(self.image_count_label)
        self.page_layout.addWidget(self.image_count_input)

        # Exit project
        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedHeight(40)
        self.back_btn.clicked.connect(lambda _: self.controller.switch_page(4))
        self.back_btn.clicked.connect(lambda _: self.update_image_page)
        self.page_layout.addWidget(self.back_btn)

        # Connect to TCP/UDP
        self.tcp_manager = TCPManager(self, self.controller)

        self.tcp_connect_button = QPushButton("Send/Receive Data")
        self.tcp_connect_button.setEnabled(False)
        self.tcp_connect_button.setFixedHeight(40)
        self.tcp_connect_button.clicked.connect(lambda _: self.tcp_button)
        self.page_layout.addWidget(self.tcp_connect_button)

    def tcp_button(self):
        self.controller.network_page.receive_data(self.username, self.prj_folder)
        self.controller.switch_page(5)

    def load_saved_images(self, prj, user_folder, prj_uuid):
        self.user_folder = user_folder
        self.user_folder = Path(INSTALL_LOCATION / "users" / self.user_folder.stem )
        self.prj_folder = Path(self.user_folder / prj)
        self.current_project = prj
        self.uuid = prj_uuid
        self.current_project = prj

        # Show images
        if self.prj_folder.exists() and self.prj_folder.is_dir():
            img_uploads = self.prj_folder / "image_uploads"
            img_uploads.mkdir(parents=True, exist_ok=True)
            imgs = [
                p for p in img_uploads.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            ]
            imgs = list(dict.fromkeys(imgs))
            self.show_images(imgs)
            cls_list = self.prj_folder / "class_list.txt"
            cls_list.touch()
            with open(cls_list, "r") as f:
                self.project_classes = f.read().strip().split(',')

        self.show_project.setText(f"Project: {prj.name}")
        self.check_uploaded_labels()

    def show_images(self, img_list):
        self.images = [f for f in img_list if Path(f).is_file()]
        self.current_page = 0
        self.update_image_page()

    def update_image_page(self):
        self.clear_img_grid()

        page_images = self.images[
            self.current_page * self.images_per_page:
            (self.current_page + 1) * self.images_per_page
        ]

        num_images = len(page_images)
        if num_images == 0:
            self.page_lbl.setText("No images")
            return
        
        columns = math.ceil(math.sqrt(num_images))
        rows = math.ceil(num_images / columns)

        # Actual size
        area_width = self.scroll_imgs.viewport().width()
        area_height = self.scroll_imgs.viewport().height()

        thumb_width = area_width // columns
        thumb_height = area_height // rows

        for index, img in enumerate(page_images):
            if not Path(img).is_file():
                continue

            row = index // columns
            column = index % columns

            img_btn = QPushButton(self.scroll_content)
            img_btn.setFixedSize(thumb_width, thumb_height)

            thumb = QPixmap(str(img)).scaled(
                thumb_width - 10,
                thumb_height - 10,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            img_btn.setIcon(QIcon(thumb))
            img_btn.setIconSize(QSize(thumb_width - 10, thumb_height - 10))

            img_btn.clicked.connect(lambda checked=False, image=img: self.inspect_img(image))
            self.scroll_layout.addWidget(img_btn, row, column)

        self.update_pagination_controls()

    def update_pagination_controls(self):
        total_pages = math.ceil(
            len(self.images) / self.images_per_page
        )

        if total_pages == 0:
            self.page_lbl.setText("No images")
        else:
            self.page_lbl.setText(
                f"Page {self.current_page + 1} of {total_pages}"
            )

        self.prev_btn.setEnabled(
            self.current_page > 0
        )
        self.next_btn.setEnabled(
            self.current_page < total_pages - 1
        )

    def change_images_per_page(self):
        try:
            value = int(self.image_count_input.text())
            if value < 1:
                return
            self.images_per_page = value
            self.current_page = 0
            self.update_image_page()
        except ValueError:
            pass

    def inspect_img(self, image):
        image_list = self.images
        if image:
            self.controller.switch_page(3)
            self.controller.image_viewer.view_image(image, self.prj_folder, image_list)

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_image_page()

    def next_page(self):
        total_pages = math.ceil(
            len(self.images) / self.images_per_page
        )

        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_image_page()

    def clear_img_grid(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def edit_class_list(self):
        class_file = self.prj_folder / "class_list.txt"
        class_file.touch()
        with open(class_file, "r") as f:
            content = f.read().strip()
            
        class_input, ok = QInputDialog().getText(self, "Edit Classes","Type the name of each class separated by a comma:", QLineEdit.EchoMode.Normal, content if content else "")
        if class_input != "":
            with open(class_file, "w") as f:
                f.write(class_input)
            self.project_classes = class_input.strip().split(',')
        else:
            QMessageBox.warning(
                self,
                "",
                "You must add at least one object class. Simply type 'object' if you only have 1 class."
            )
            self.edit_class_list()

    def check_uploaded_labels(self):
        image_uploads = Path(self.prj_folder) / "image_uploads"
        image_labels = Path(self.prj_folder) / "image_labels"
        image_uploads.mkdir(parents=True, exist_ok=True)
        image_labels.mkdir(parents=True, exist_ok=True)
        self.labels_without_images = []
        for label in image_labels.iterdir():
            label_has_corresponding_image = False
            for image in image_uploads.iterdir():
                if Path(image).stem == Path(label).stem:
                    label_has_corresponding_image = True
                    break

            if not label_has_corresponding_image:
                self.labels_without_images.append(label)

        if len(self.labels_without_images) > 0:
            self.view_missing_images(self.labels_without_images)
            self.view_missing_images_list.setEnabled(True)
        else:
            self.view_missing_images_list.setEnabled(False)

        self.labels_without_images_label.setText(f"Labels missing images: {len(self.labels_without_images)}")

    def view_missing_images(self, labels):
        labels_str = "\n".join([str(label.name) for label in labels])
        msg = QMessageBox(self)
        msg.setWindowTitle("Warning")
        msg.setText("The following labels do not have corresponding images.")
        msg.setInformativeText(
            "Please upload the images that correspond (with the same file name, e.g., image.jpg and image.txt) in order to view the label information."
        )
        msg.setDetailedText(labels_str)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        delete_button = msg.addButton("Delete these files", QMessageBox.ButtonRole.ActionRole)
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)

        result = msg.exec()
        if msg.clickedButton() == delete_button:
            for label in labels:
                try:
                    if label.exists():
                        label.unlink()
                except OSError:
                    pass
            self.labels_without_images = []
            self.check_uploaded_labels()
            self.view_missing_images_list.setEnabled(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.images:
            self.update_image_page()

class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ML Maker 1.0.0")

        ### INITIALIZE VARIABLES

        # User variables
        self.username = ""

        ### INSTANTIATE OBJECTS


        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        self.setMinimumSize(0, 0)
        layout = QVBoxLayout(central)

        # Stacked widget
        self.sw = QStackedWidget()
        layout.addWidget(self.sw, 1)

        # Bottom controls layout
        bottom_layout = QHBoxLayout()
        
        # Audio
        self.music_folder = INSTALL_LOCATION / "assets" / "music"
        self.music_folder.mkdir(parents=True, exist_ok=True)
        self.volume = 0.25
        self.music = MusicHandler(self.music_folder, self.volume, self)
        bottom_layout.addWidget(self.music)

        # Logout
        self.logout_button = QPushButton("Exit")
        self.logout_button.clicked.connect(lambda _: self.logout())
        bottom_layout.addWidget(self.logout_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(bottom_layout)

        # Pages
            # Instantiate
        self.login_page = LoginWindow(self)
        self.create_account_page = NewAccountWindow(self)
        self.home = ProjectWindow(self)
        self.image_viewer = ImageView(self)
        self.proj_explorer = ProjectExplorer(self)
        self.network_page = NetworkExplorer(self)
            # Add to stacked widget
        self.sw.addWidget(self.login_page)          # self.controller.switch_page(0)
        self.sw.addWidget(self.create_account_page) # self.controller.switch_page(1)
        self.sw.addWidget(self.home)                # self.controller.switch_page(2)
        self.sw.addWidget(self.image_viewer)        # self.controller.switch_page(3)
        self.sw.addWidget(self.proj_explorer)       # self.controller.switch_page(4)
        self.sw.addWidget(self.network_page)        # self.controller.switch_page(5)

        self.sw.setCurrentIndex(0)

    def switch_page(self, index):
        self.sw.setCurrentIndex(index)
        if self.sw.currentIndex() == 0:
            self.logout_button.setText("Exit")
        else:
            self.logout_button.setText("Logout")

    def receive_user_data(self, data: dict):
        #cud = current user data
        self.cud = data
        self.username = str(self.cud.get('username'))
        self.home.username = self.username
        print(f"Welcome user: {self.username}")
        print(f"Access date: {self.cud.get('access_date')}")
        self.load_user_data(data)
        self.home.show_user.setText(f"User: {self.username}")
        self.user_folder = INSTALL_LOCATION / "users" / self.username
        self.proj_explorer.load_saved_pjs("local")

    def load_user_data(self, data: dict):
        SAVED_USER_DATA = INSTALL_LOCATION / "users" / self.username / "user_data.json"
        SAVED_USER_DATA.parent.mkdir(parents=True, exist_ok=True)
        SAVED_USER_DATA.touch(exist_ok=True)
        try:
            with open(SAVED_USER_DATA, "r") as f:
                # Guard against reading empty or broken files
                content = f.read().strip()
                udata = json.loads(content) if content else {}
            
            if not isinstance(udata, dict):
                udata = {}
                
            if self.username in udata:
                print(f"Last access date: {udata[self.username].get('last_access')}")
                logins = 0
                if udata[self.username].get('logins'):
                    print(f"Number of logins: {udata[self.username].get('logins') + 1}")
                    logins = udata[self.username].get('logins') + 1
                else:
                    logins = 1
                udata[self.username] = {
                    "username": self.username,
                    "last_access": data.get('access_date'),
                    "logins": logins
                }
                with open(SAVED_USER_DATA, "w") as f:
                    json.dump(udata, f, indent=4)
            else:
                print("No existing user data found. Populated user data file!")
                udata[self.username] = {
                    "username": self.username,
                    "last_access": data.get('access_date'),
                    "logins": 1
                }
                print(f"Last access date: N/A")

                with open(SAVED_USER_DATA, "w") as f:
                    json.dump(udata, f, indent=4)

        except Exception as e:
            print(f"Failed to access user data: {e}")

    def logout(self):
        if self.sw.currentIndex() == 0:
            QApplication.quit()
        else:
            self.username = ""
            self.user_folder = ""
            self.switch_page(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.size()
    window = MainController()
    window.show()
    sys.exit(app.exec())
