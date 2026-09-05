from PySide6.QtWidgets import (
    QGridLayout, QWidget, QPushButton, QMainWindow, QLabel,
    QLineEdit, QHBoxLayout, QVBoxLayout, QInputDialog, QMessageBox,
    QScrollArea
)
from PySide6.QtCore import QSize, Qt, QObject, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QPixmap, QIcon, QFont
import math, json
from pathlib import Path

from dataloader import UploadFiles
from sam_handling import SAMPass

INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class ProjectLoadWorker(QObject):
    finished = Signal(object, object, object, object)
    failed = Signal(str)

    def __init__(self, project_folder, needs_fp_file):
        super().__init__()
        self.project_folder = Path(project_folder)
        self.needs_fp_file = Path(needs_fp_file)

    @Slot()
    def run(self):
        try:
            uploads = self.project_folder / "image_uploads"
            labels = self.project_folder / "image_labels"
            class_file = self.project_folder / "class_list.txt"

            uploads.mkdir(parents=True, exist_ok=True)
            labels.mkdir(parents=True, exist_ok=True)
            class_file.touch(exist_ok=True)
            self.needs_fp_file.touch(exist_ok=True)

            needs_fp = []
            raw = self.needs_fp_file.read_text(errors="ignore").strip()

            if raw:
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    path = Path(line)
                    if not path.is_absolute():
                        path = self.project_folder / path

                    path = path.resolve()

                    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                        needs_fp.append(path)

            needs_fp_set = set(needs_fp)

            images = []
            if uploads.exists():
                for path in uploads.rglob("*"):
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in IMAGE_EXTENSIONS:
                        continue

                    resolved = path.resolve()
                    if resolved in needs_fp_set:
                        continue

                    images.append(path)

            images.sort(key=lambda p: p.as_posix().lower())

            relative_needs_fp = []
            for path in needs_fp:
                try:
                    relative_needs_fp.append(
                        str(path.relative_to(self.project_folder))
                    )
                except ValueError:
                    pass

            self.needs_fp_file.write_text(
                "\n".join(relative_needs_fp)
            )

            class_data = class_file.read_text(errors="ignore").strip()
            project_classes = [
                cls.strip()
                for cls in class_data.split(",")
                if cls.strip()
            ] if class_data else []

            self.finished.emit(
                images,
                needs_fp,
                project_classes,
                labels
            )

        except Exception as exc:
            self.failed.emit(str(exc))


class ProjectLabelWorker(QObject):
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, image_uploads, image_labels, image_paths):
        super().__init__()
        self.image_uploads = Path(image_uploads)
        self.image_labels = Path(image_labels)
        self.image_paths = [Path(p) for p in image_paths]

    @Slot()
    def run(self):
        try:
            self.image_uploads.mkdir(parents=True, exist_ok=True)
            self.image_labels.mkdir(parents=True, exist_ok=True)

            expected_labels = set()

            for image in self.image_paths:
                try:
                    relative = image.relative_to(self.image_uploads)
                except ValueError:
                    continue

                label = (
                    self.image_labels
                    / relative.parent
                    / f"{relative.stem}.txt"
                )

                label.parent.mkdir(parents=True, exist_ok=True)
                label.touch(exist_ok=True)
                expected_labels.add(label.resolve())

            unmatched = []

            for label in self.image_labels.rglob("*.txt"):
                if label.resolve() not in expected_labels:
                    unmatched.append(label)

            unmatched.sort(key=lambda p: p.as_posix().lower())

            self.finished.emit(expected_labels, unmatched)

        except Exception as exc:
            self.failed.emit(str(exc))


class ProjectView(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.username = ""
        self.user_folder = Path(INSTALL_LOCATION)
        self.folder_icon = Path(INSTALL_LOCATION) / "assets" / "app_pics" / "folder.png"

        self.images = []
        self.images_per_page = 16
        self.current_page = 0
        self.needs_fp = []
        self._needs_fp_set = set()
        self.needs_fp_file = Path(INSTALL_LOCATION)

        self.project_classes = []
        self.labels_without_images = []
        self.current_project = Path(INSTALL_LOCATION)
        self.prj_folder = Path(INSTALL_LOCATION)
        self.uuid = ""

        self._load_thread = None
        self._load_worker = None
        self._loading_project = False

        self._label_thread = None
        self._label_worker = None

        self._thumbnail_cache = {}
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(200)
        self._resize_timer.timeout.connect(self._update_after_resize)
        self._last_grid_width = 0
        self._grid_update_pending = False

        self.pt16 = QFont()
        self.pt16.setPointSize(16)

        self.pt8 = QFont()
        self.pt8.setPointSize(8)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.mlayout = QVBoxLayout(central_widget)
        self.mlayout.setSpacing(2)

        self.show_user = QLabel("")
        self.show_project = QLabel("")
        self.show_uuid = QLabel("")
        self.show_uuid.setFont(self.pt8)

        self.mlayout.addWidget(self.show_user)
        self.mlayout.addWidget(self.show_project)
        self.mlayout.addWidget(self.show_uuid)

        self.upload_files = UploadFiles(self, self.controller)
        self.mlayout.addWidget(self.upload_files)

        self.labels_without_images_label = QLabel(
            "Labels missing images: 0"
        )
        self.labels_without_images_label.setFont(self.pt16)

        self.view_missing_images_list = QPushButton(
            "View Unmatched Label Files"
        )
        self.view_missing_images_list.setEnabled(False)
        self.view_missing_images_list.clicked.connect(
            lambda: self.view_missing_images(self.labels_without_images)
        )

        self.mlayout.addWidget(self.labels_without_images_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.mlayout.addWidget(self.view_missing_images_list, alignment=Qt.AlignmentFlag.AlignRight)

        self.edit_class_btn = QPushButton("Edit class list")
        self.edit_class_btn.clicked.connect(self.edit_class_list)
        self.mlayout.addWidget(
            self.edit_class_btn,
            alignment=Qt.AlignmentFlag.AlignRight
        )

        self.loading_label = QLabel("")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()
        self.mlayout.addWidget(self.loading_label)

        self.scroll_imgs = QScrollArea(self)
        self.scroll_imgs.setWidgetResizable(True)
        self.scroll_imgs.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_imgs.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)

        self.scroll_imgs.setWidget(self.scroll_content)
        self.mlayout.addWidget(self.scroll_imgs)

        self.page_layout = QHBoxLayout()

        self.prev_btn = QPushButton("Previous")
        self.next_btn = QPushButton("Next")
        self.page_lbl = QLabel("Page 0 of 0")

        self.prev_btn.clicked.connect(self.previous_page)
        self.next_btn.clicked.connect(self.next_page)

        self.page_layout.addWidget(self.prev_btn)
        self.page_layout.addWidget(self.next_btn)
        self.page_layout.addWidget(self.page_lbl)

        self.image_count_label = QLabel("Images per page:")

        self.image_count_input = QLineEdit("16")
        self.image_count_input.setFixedWidth(50)
        self.image_count_input.returnPressed.connect(
            self.change_images_per_page
        )

        self.page_layout.addWidget(self.image_count_label)
        self.page_layout.addWidget(self.image_count_input)

        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedHeight(40)
        self.back_btn.clicked.connect(
            lambda: self.controller.switch_page(4)
        )
        self.page_layout.addWidget(self.back_btn)

        self.mlayout.addLayout(self.page_layout)
        
    def tcp_button(self):
        self.controller.network_page.receive_prj_info(
            self.user_folder,
            self.prj_folder
        )
        self.controller.switch_page(5)

    def load_saved_images(self, prj, username, user_folder, prj_uuid):
        if self.controller.proj_explorer.current_user_location == "shared":
            self.tcp_connect_button = QPushButton("Send/Receive Data")
            self.tcp_connect_button.setEnabled(True)
            self.tcp_connect_button.setFixedHeight(40)
            self.tcp_connect_button.clicked.connect(self.tcp_button)
            self.page_layout.addWidget(self.tcp_connect_button)

        if self._load_thread is not None:
            return

        self.username = username
        self.user_folder = user_folder
        self.user_folder = Path(INSTALL_LOCATION) / "users" / username
        self.prj_folder = self.user_folder / Path(prj)
        self.current_project = self.prj_folder
        self.uuid = prj_uuid
        self.needs_fp_file = self.prj_folder / "needs_first_pass.txt"

        self.images.clear()
        self.needs_fp.clear()
        self._needs_fp_set.clear()
        self.labels_without_images.clear()
        self._thumbnail_cache.clear()
        self.current_page = 0

        self.show_user.setText(f"User: {username}")
        self.show_project.setText(
            f"Project: {self.prj_folder.name}"
        )
        self.show_uuid.setText(f"UUID: {prj_uuid}")

        self.clear_img_grid()

        self._loading_project = True
        self.loading_label.setText("Loading project...")
        self.loading_label.show()

        self.upload_files.setEnabled(False)
        self.edit_class_btn.setEnabled(False)
        self.view_missing_images_list.setEnabled(False)

        self._load_thread = QThread(self)
        self._load_worker = ProjectLoadWorker(
            self.prj_folder,
            self.needs_fp_file
        )
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(
            self._load_worker.run
        )
        self._load_worker.finished.connect(
            self._images_loaded
        )
        self._load_worker.failed.connect(
            self._image_load_failed
        )

        self._load_worker.finished.connect(
            self._load_thread.quit
        )
        self._load_worker.failed.connect(
            self._load_thread.quit
        )

        self._load_thread.finished.connect(
            self._load_thread_finished
        )

        self._load_thread.start()

    @Slot(object, object, object, object)
    def _images_loaded(self, images, needs_fp, project_classes, labels_folder):
        self.images = [
            Path(image)
            for image in images
            if Path(image).is_file()
        ]

        self.needs_fp = [
            Path(image)
            for image in needs_fp
            if Path(image).is_file()
        ]

        self._needs_fp_set = {
            path.resolve()
            for path in self.needs_fp
        }

        self.project_classes = list(project_classes)
        self._loading_project = False

        self.loading_label.hide()
        self.upload_files.setEnabled(True)
        self.edit_class_btn.setEnabled(True)

        self.current_page = 0

        print(
            f"[ProjectView] Loaded {len(self.images)} images."
        )
        print(
            f"[ProjectView] {len(self.needs_fp)} images need first pass."
        )

        self.update_image_page()
        self.check_uploaded_labels()

    @Slot(str)
    def _image_load_failed(self, error):
        self._loading_project = False
        self.loading_label.hide()
        self.upload_files.setEnabled(True)
        self.edit_class_btn.setEnabled(True)

        QMessageBox.critical(
            self,
            "Project Loading Error",
            f"Could not load project:\n\n{error}"
        )

    def _load_thread_finished(self):
        print("[ProjectView] Image loader thread finished.")
        thread = self._load_thread
        worker = self._load_worker
        self._load_thread = None
        self._load_worker = None

        if worker is not None:
            worker.deleteLater()

        if thread is not None:
            thread.deleteLater()

    def show_images(self, img_list):
        self.images = [
            Path(image)
            for image in img_list
            if Path(image).is_file()
            and Path(image).resolve() not in self._needs_fp_set
        ]

        self.images.sort(
            key=lambda p: p.as_posix().lower()
        )

        self.current_page = 0
        self.update_image_page()

    def finish_loading_images(self, images):
        self.images = [
            Path(image)
            for image in images
            if Path(image).is_file()
            and Path(image).resolve() not in self._needs_fp_set
        ]

        self.images.sort(
            key=lambda p: p.as_posix().lower()
        )

        self.current_page = 0
        self.update_image_page()

    def update_image_page(self):
        if self._loading_project:
            return

        self.clear_img_grid()

        self.images = [
            image for image in self.images
            if image.is_file()
            and image.resolve() not in self._needs_fp_set
        ]

        page_start = self.current_page * self.images_per_page
        page_end = page_start + self.images_per_page
        page_images = self.images[page_start:page_end]

        display_items = []

        if self.needs_fp and self.current_page == 0:
            display_items.append(self.folder_icon)

        display_items.extend(page_images)

        if not display_items:
            self.page_lbl.setText("No images")
            self.update_pagination_controls()
            return

        num_images = len(display_items)
        columns = max(1, math.ceil(math.sqrt(num_images)))

        area_width = max(
            100,
            self.scroll_imgs.viewport().width() - 10
        )

        thumb_width = max(
            50,
            area_width // columns
        )

        thumb_height = thumb_width

        for index, image in enumerate(display_items):
            row = index // columns
            column = index % columns

            if image == self.folder_icon:
                self._add_needs_fp_widget(
                    row,
                    column,
                    thumb_width,
                    thumb_height
                )
            else:
                self._add_image_widget(
                    image,
                    row,
                    column,
                    thumb_width,
                    thumb_height
                )

        self.update_pagination_controls()

    def _add_needs_fp_widget(self, row, column, thumb_width, thumb_height):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        info = QHBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)

        info.addWidget(
            QLabel(f"Images Needing SAM Pass: {len(self.needs_fp)}")
        )

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(
            self.delete_all_needs_fp_images
        )
        info.addWidget(delete_button)

        layout.addLayout(info)

        button = QPushButton()
        button.setFixedSize(thumb_width, thumb_height)

        thumb = self.get_thumbnail(
            self.folder_icon,
            max(1, thumb_width - 10),
            max(1, thumb_height - 10)
        )

        if not thumb.isNull():
            button.setIcon(QIcon(thumb))
            button.setIconSize(
                QSize(
                    max(1, thumb_width - 10),
                    max(1, thumb_height - 10)
                )
            )

        button.clicked.connect(self.sam_pass)

        layout.addWidget(button)
        self.scroll_layout.addWidget(widget, row, column)

    def sam_pass(self):
        user_df = self.user_folder / "user_data.json"
        user_df.touch()
        with open(user_df, "r") as f:
            data = json.load(f)
            if "default_sam_size" in data[self.username]:
                default_sam_size = str(data[self.username]["default_sam_size"])
            else:
                default_sam_size = None
        if not hasattr(self, "sam_passer"):
            self.sampasser = SAMPass(self, self.controller)

        self.sampasser.begin_sam_pass(self.needs_fp, self.current_project, self.username, user_df, default_sam_size)

    def _add_image_widget(self, image, row, column, thumb_width, thumb_height):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        info = QHBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)

        label_file = self._label_path_for_image(image)

        label_count = 0

        try:
            if label_file.exists():
                with open(label_file, "r", errors="ignore") as f:
                    label_count = sum(1 for line in f if line.strip())
        except OSError:
            pass

        label_info = QLabel(f"Labels: {label_count}")

        if label_count == 0:
            label_info.setStyleSheet(
                "color: #FF5733; font-size: 16px; font-weight: bold"
            )

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(
            lambda checked=False, img=image:
            self.delete_this_image(img)
        )

        info.addWidget(label_info)
        info.addWidget(delete_button)
        layout.addLayout(info)

        button = QPushButton()
        button.setFixedSize(thumb_width, thumb_height)

        thumb = self.get_thumbnail(
            image,
            max(1, thumb_width - 10),
            max(1, thumb_height - 10)
        )

        if not thumb.isNull():
            button.setIcon(QIcon(thumb))
            button.setIconSize(
                QSize(
                    max(1, thumb_width - 10),
                    max(1, thumb_height - 10)
                )
            )

        button.clicked.connect(
            lambda checked=False, img=image:
            self.inspect_img(img)
        )

        layout.addWidget(button)
        self.scroll_layout.addWidget(widget, row, column)

    def _label_path_for_image(self, image):
        image = Path(image)
        relative = image.relative_to(self.prj_folder / "image_uploads")

        return (
            self.prj_folder
            / "image_labels"
            / relative.parent
            / f"{relative.stem}.txt"
        )

    def delete_this_image(self, image):
        image = Path(image)

        if not image.is_file():
            return

        reply = QMessageBox.question(
            self,
            "Remove Image",
            f"Are you sure you want to remove {image.name} from the project?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            image.unlink()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"Could not remove image:\n{exc}"
            )
            return

        label_file = self._label_path_for_image(image)

        try:
            if label_file.exists():
                label_file.unlink()
        except OSError:
            pass

        self._thumbnail_cache = {
            key: value
            for key, value in self._thumbnail_cache.items()
            if key[0] != str(image.resolve())
        }

        self.images = [
            img for img in self.images
            if img.resolve() != image.resolve()
        ]

        self.update_image_page()
        self.check_uploaded_labels()

    def delete_all_needs_fp_images(self):
        if not self.needs_fp:
            return

        reply = QMessageBox.question(
            self,
            "Remove Images",
            "Are you sure you want to remove all files that need a First Pass from the project? This action cannot be undone, but you can reupload the videos.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        for image in self.needs_fp.copy():
            try:
                if image.exists():
                    image.unlink()
            except OSError:
                pass

        self.needs_fp.clear()
        self._needs_fp_set.clear()

        try:
            self.needs_fp_file.write_text("")
        except OSError:
            pass

        self.update_image_page()
        self.check_uploaded_labels()

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
        except ValueError:
            return

        if value < 1:
            return

        self.images_per_page = value
        self.current_page = 0
        self.update_image_page()

    def inspect_img(self, image):
        image = Path(image)

        if not image.is_file():
            return

        image_list = self.images.copy()

        self.controller.switch_page(3)
        self.controller.image_viewer.view_image(
            image,
            self.prj_folder,
            image_list
        )

    def previous_page(self):
        if self.current_page <= 0:
            return

        self.current_page -= 1
        self.update_image_page()

    def next_page(self):
        total_pages = math.ceil(
            len(self.images) / self.images_per_page
        )

        if self.current_page >= total_pages - 1:
            return

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
        class_file.touch(exist_ok=True)

        try:
            content = class_file.read_text(errors="ignore").strip()
        except OSError:
            content = ""

        class_input, ok = QInputDialog.getText(
            self,
            "Edit Classes",
            "Type the name of each class separated by a comma:",
            QLineEdit.EchoMode.Normal,
            content
        )

        if not ok:
            return

        if not class_input.strip():
            QMessageBox.warning(
                self,
                "Invalid Class List",
                "You must add at least one object class. Simply type 'object' if you only have 1 class."
            )
            return

        class_file.write_text(class_input)

        self.project_classes = [
            cls.strip()
            for cls in class_input.split(",")
            if cls.strip()
        ]

    def check_uploaded_labels(self):
        if self._label_thread is not None:
            return

        image_uploads = self.prj_folder / "image_uploads"
        image_labels = self.prj_folder / "image_labels"

        image_uploads.mkdir(parents=True, exist_ok=True)
        image_labels.mkdir(parents=True, exist_ok=True)

        image_paths = [
            Path(image)
            for image in self.images
            if Path(image).is_file()
        ]

        self._label_thread = QThread(self)
        self._label_worker = ProjectLabelWorker(
            image_uploads,
            image_labels,
            image_paths
        )

        self._label_worker.moveToThread(self._label_thread)

        self._label_thread.started.connect(
            self._label_worker.run
        )

        self._label_worker.finished.connect(
            self._labels_checked
        )

        self._label_worker.failed.connect(
            self._labels_check_failed
        )

        self._label_worker.finished.connect(
            self._label_thread.quit
        )

        self._label_worker.failed.connect(
            self._label_thread.quit
        )

        self._label_thread.finished.connect(
            self._label_thread_finished
        )

        self._label_thread.start()

    @Slot(object, object)
    def _labels_checked(self, image_label_paths, unmatched_labels):
        self.labels_without_images = [
            Path(label)
            for label in unmatched_labels
            if Path(label).is_file()
        ]

        self.view_missing_images_list.setEnabled(
            bool(self.labels_without_images)
        )

        self.labels_without_images_label.setText(
            f"Labels missing images: {len(self.labels_without_images)}"
        )

    @Slot(str)
    def _labels_check_failed(self, error):
        print(f"[ProjectLabelWorker] Error: {error}")

        self.labels_without_images.clear()
        self.view_missing_images_list.setEnabled(False)
        self.labels_without_images_label.setText(
            "Labels missing images: 0"
        )

    def _label_thread_finished(self):
        worker = self._label_worker
        thread = self._label_thread

        self._label_worker = None
        self._label_thread = None

        if worker is not None:
            worker.deleteLater()

        if thread is not None:
            thread.deleteLater()

    def view_missing_images(self, labels):
        labels_str = "\n".join(
            str(label)
            for label in labels
        )

        msg = QMessageBox(self)
        msg.setWindowTitle("Warning")
        msg.setText(
            "The following labels do not have corresponding images."
        )
        msg.setInformativeText(
            "Please upload the images that correspond with these labels."
        )
        msg.setDetailedText(labels_str)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok |
            QMessageBox.StandardButton.Cancel
        )

        delete_button = msg.addButton(
            "Delete these files",
            QMessageBox.ButtonRole.ActionRole
        )

        msg.setDefaultButton(
            QMessageBox.StandardButton.Ok
        )

        msg.exec()

        if msg.clickedButton() != delete_button:
            return

        for label in labels:
            try:
                label = Path(label)

                if label.is_file():
                    label.unlink()

                elif label.is_dir():
                    for path in sorted(
                        label.rglob("*"),
                        key=lambda p: len(p.parts),
                        reverse=True
                    ):
                        if path.is_file():
                            path.unlink()
                        elif path.is_dir():
                            try:
                                path.rmdir()
                            except OSError:
                                pass

                    try:
                        label.rmdir()
                    except OSError:
                        pass

            except OSError:
                pass

        self.labels_without_images.clear()
        self.check_uploaded_labels()

    def get_thumbnail(self, image, width, height):
        image = Path(image).resolve()
        key = (str(image), width, height)

        cached = self._thumbnail_cache.get(key)
        if cached is not None:
            return cached

        pixmap = QPixmap(str(image))

        if pixmap.isNull():
            return QPixmap()

        thumbnail = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        if len(self._thumbnail_cache) >= 500:
            self._thumbnail_cache.clear()

        self._thumbnail_cache[key] = thumbnail
        return thumbnail

    def _update_after_resize(self):
        self._grid_update_pending = False

        if self._loading_project:
            return

        if not self.isVisible():
            return

        width = self.scroll_imgs.viewport().width()

        if width <= 0:
            return

        if width == self._last_grid_width:
            return

        self._last_grid_width = width
        self.update_image_page()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self._loading_project:
            return

        if not self.images and not self.needs_fp:
            return

        self._resize_timer.start()

    def logout_clear(self):
        self._resize_timer.stop()

        if self._load_thread is not None:
            self._load_thread.quit()
            self._load_thread.wait(1000)

        if self._label_thread is not None:
            self._label_thread.quit()
            self._label_thread.wait(1000)

        self._load_thread = None
        self._load_worker = None
        self._label_thread = None
        self._label_worker = None

        self.clear_img_grid()
        self._thumbnail_cache.clear()

        self.username = ""
        self.user_folder = Path(INSTALL_LOCATION)
        self.images.clear()
        self.images_per_page = 16
        self.current_page = 0
        self.needs_fp.clear()
        self._needs_fp_set.clear()
        self.needs_fp_file = Path(INSTALL_LOCATION)
        self.project_classes.clear()
        self.labels_without_images.clear()
        self.current_project = Path(INSTALL_LOCATION)
        self.prj_folder = Path(INSTALL_LOCATION)
        self.uuid = ""

        self._loading_project = False

        self.loading_label.hide()
        self.show_user.setText("")
        self.show_project.setText("")
        self.show_uuid.setText("")
        self.page_lbl.setText("Page 0 of 0")
        self.labels_without_images_label.setText(
            "Labels missing images: 0"
        )
        self.view_missing_images_list.setEnabled(False)