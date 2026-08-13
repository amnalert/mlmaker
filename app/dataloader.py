from PySide6.QtWidgets import QPushButton, QFileDialog, QMessageBox
import sys, os, zipfile
from pathlib import Path
import shutil

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
LABEL_EXTENSIONS = {".csv", ".tsv", ".xml", ".txt", ".parquet", ".json", ".yml", ".yaml", ".tar"}

class UploadImages(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Unlabelled Images")
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
        self.images = []
        self.parent_widget.load_saved_images(self.project)

class ImageLoader:
    def load_files(self, parent):
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Images",
            str(parent.controller.user_folder),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;ZIP Archives(*.zip)"
        )
        return files

class UploadLabels(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Labels with Corresponding Images")

        self.controller = controller
        self.parent_widget = parents

        self.project = ""

        self.clicked.connect(self.open_dialog)
        self.images = []
        self.labels = []
        self.duplicate_labels = []

    def open_dialog(self):
        self.project = self.parent_widget.project
        files = LabelLoader().load_files(self)
        save_location_labels = Path(self.controller.user_folder) / self.parent_widget.project / "image_labels"
        save_location_labels.mkdir(parents=True, exist_ok=True)
        save_location_images = Path(self.controller.user_folder) / self.parent_widget.project / "image_uploads"
        save_location_images.mkdir(parents=True, exist_ok=True)

        if files:
            for file in files:
                if Path(file).suffix.lower() in IMAGE_EXTENSIONS:
                    self.images.append(Path(file))
                elif Path(file).suffix.lower() in LABEL_EXTENSIONS:
                    self.labels.append(Path(file))

            for path in self.images:
                self.copy_to_project(path, "images", save_location_images)
            for path in self.labels:
                self.copy_to_project(path, "labels", save_location_labels)

            if len(self.duplicate_labels) > 0:
                duplicate_labels_str = "\n".join([str(label.name) for label in self.duplicate_labels])
                QMessageBox.critical(
                    self,
                    "Error",
                    f"The following labels were not copied because they have the same name as existing labels(that also do not have corresponding images). The only way this could happen is if you uploaded multiple labels with the exact same file name, or uploaded the same label file(that had no matching image) twice. Please rename the labels and try again. If you upload an image with the same name as an already existing image and its corresponding label, both the image and the label stems will automatically have _n appended to them. \n\n{duplicate_labels_str}"
                )

            self.images = []
            self.labels = []
            self.duplicate_labels = []
            self.parent_widget.load_saved_images(self.project)

    def copy_to_project(self, path, type, save_location):
        if type == "images":
            dest = Path(save_location) / Path(path.name)
            counter = 1
            while dest.exists():
                dest = save_location / f"{path.stem}_{counter}{path.suffix}"
                # Change the image name in the list of images to match the new name
                self.images = [img if img != path else dest for img in self.images]
                # change the corresponding label file name to match the new image name
                if path.stem in [label.stem for label in self.labels]:
                    label_ext = next(label.suffix for label in self.labels if label.stem == path.stem)
                    new_label_name = f"{dest.stem}{label_ext}"
                    self.labels = [label if label.stem != path.stem else Path(label.parent / new_label_name) for label in self.labels]
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
                            self.labels.append(destination)
                            shutil.copyfileobj(source, target)
            elif path.suffix.lower() in IMAGE_EXTENSIONS:
                shutil.copy2(path, dest)

        elif type == "labels":
            dest = Path(save_location) / Path(path.name)

            # Label section: if the label does not have a corresponding image, add it to a list of labels that do not have corresponding images that will be shown to the user after the upload is complete
            label_has_corresponding_image = False
            corresponding_image = ""
            # Search for corresponding image in the files that were just uploaded and in the image_uploads folder of the project
            if path.suffix.lower() in LABEL_EXTENSIONS:
                img_folder = Path(self.controller.user_folder) / self.parent_widget.project / "image_uploads"
                for other_file in self.images:
                    if Path(other_file).stem == Path(path).stem and other_file != path:
                        label_has_corresponding_image = True
                        corresponding_image = Path(other_file)
                        break
                if corresponding_image == "":
                    for image in img_folder.iterdir():
                        if Path(image).stem == Path(path).stem:
                            label_has_corresponding_image = True
                            corresponding_image = Path(image)
                            break
                if dest.exists():
                    # the only reason this could happen is if the user uploaded a label with the same name as an existing label that also has no corresponding image, so we will not copy the label file and instead just display a warning box at the end showing which labels were not copied
                    self.duplicate_labels.append(dest)
                    return
                else:
                    shutil.copy2(path, dest)
            
            if not label_has_corresponding_image:
                self.parent_widget.labels_without_images.append(path)

class LabelLoader:
    def load_files(self, parent):
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Label Files",
            str(parent.controller.user_folder),
            "Sidecar Labels (*.txt *.xml);;Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;Tabular Labels (*.csv *.tsv *.parquet);;Manifest Labels (*.json *.yaml);;Archives (*.zip *.tar)"
        )
        return files