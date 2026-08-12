from PySide6.QtWidgets import QPushButton, QFileDialog
import sys, os, zipfile
from pathlib import Path
import shutil

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

class UploadImages(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Images")
        self.controller = controller
        self.parent_widget = parents

        self.project = ""

        self.clicked.connect(self.open_dialog)
        self.images = []

    def open_dialog(self):
        self.project = self.parent_widget.project
        files = ImageLoader().load_files(self)
        save_location = Path(self.controller.user_folder) / self.parent_widget.project / "image_uploads"
        save_location.mkdir(parents=True, exist_ok=True)
        if files:
            for file in files:
                path = Path(file)
                dest = save_location / path.name
                counter = 1
                while dest.exists():
                    dest = save_location / f"{path.stem}_{counter}{path.suffix}"
                    counter += 1
                if path.suffix.lower() == ".zip":
                    with zipfile.ZipFile(path, "r") as z:
                        for member in z.infolist():
                            source_name = Path(member.filename)

                            # Skip directories
                            if member.is_dir():
                                continue

                            destination = save_location / source_name.name

                            # Rename if it already exists
                            counter = 1
                            while destination.exists():
                                destination = save_location / f"{source_name.stem}_{counter}{source_name.suffix}"
                                counter += 1

                            with z.open(member) as source, open(destination, "wb") as target:
                                self.images.append(destination)
                                shutil.copyfileobj(source, target)
                elif path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.images.append(dest)
                    shutil.copy2(path, dest)
        self.parent_widget.load_saved_images(self.images)

class ImageLoader:
    def load_files(self, parent):
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Images",
            str(parent.controller.user_folder),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;ZIP Archives(*.zip)"
        )
        return files