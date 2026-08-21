from PySide6.QtWidgets import QPushButton, QFileDialog, QMessageBox
from PySide6.QtCore import QTimer, QThread, QObject, Signal
import zipfile
from pathlib import Path
import shutil
import tempfile

from video_converter import VideoConverter

class VideoConvertWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, video_path, project_path, output_name):
        super().__init__()
        self.video_path = video_path
        self.project_path = project_path
        self.output_name = output_name

    def run(self):
        try:
            converter = VideoConverter(self)
            converted_frames = converter.convert_mp4(self.video_path, self.project_path, self.output_name)
            label_folder = Path(self.project_path) / "image_labels" / Path(self.output_name)
            label_folder.mkdir(parents=True, exist_ok=True)
            for frame in converted_frames:
                (label_folder / f"{Path(frame).stem}.txt").touch()
            self.finished.emit(converted_frames)
        except Exception as exc:
            self.failed.emit(str(exc))

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
LABEL_EXTENSIONS = {".csv", ".tsv", ".xml", ".txt", ".parquet", ".json", ".yml", ".yaml", ".tar"}

def extract_zip_contents(zip_path, image_location, downloads_location):
    image_location.mkdir(parents=True, exist_ok=True)
    downloads_location.mkdir(parents=True, exist_ok=True)
    extracted_files = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                continue

            if member_path.suffix.lower() in IMAGE_EXTENSIONS:
                destination = image_location / member_path.name
            else:
                destination = downloads_location / member_path
                destination.parent.mkdir(parents=True, exist_ok=True)

            counter = 1
            while destination.exists():
                destination = destination.parent / f"{destination.stem}_{counter}{destination.suffix}"
                counter += 1
            extracted_files.append(destination)

            with archive.open(member) as source, open(destination, "wb") as target:
                shutil.copyfileobj(source, target)

    return extracted_files

class UploadImages(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Unlabelled Images/Videos")
        self.controller = controller
        self.parent_widget = parents

        self.project = ""
        self.video_queue = []
        self._video_processing = False
        self._default_text = "Upload Unlabelled Images/Videos"
        self._video_thread = None
        self._video_worker = None

        self.needs_fp = []

        self.clicked.connect(self.open_dialog)
        self.images = []

    def open_dialog(self):
        self.project = self.parent_widget.current_project
        self.project_uuid = self.parent_widget.uuid
        files = ImageLoader().load_files(self)

        save_location = self.project / "image_uploads"
        singlet_location = self.project / "image_uploads" / "singlet_images"
        singlet_location.mkdir(parents=True, exist_ok=True)
        if files:
            for file in files:
                path = Path(file)
                dest = save_location / "singlet_images" / path.name
                counter = 1
                while dest.exists():
                    dest = save_location / "singlet_images" / f"{path.stem}_{counter}{path.suffix}"
                    counter += 1
                if path.suffix.lower() == ".zip":
                    extracted_files = extract_zip_contents(path, save_location, save_location)
                    for destination in extracted_files:
                        if destination.suffix.lower() in VIDEO_EXTENSIONS:
                            resolved_video = self._resolve_video_name(destination)
                            if resolved_video is not None:
                                self.video_queue.append((destination, Path(self.project), resolved_video))
                        elif destination.suffix.lower() in IMAGE_EXTENSIONS:
                            self.images.append(destination)
                elif path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.images.append(dest)
                    shutil.copy2(path, dest)
                elif path.suffix.lower() in VIDEO_EXTENSIONS:
                    resolved_video = self._resolve_video_name(path)
                    if resolved_video is not None:
                        self.video_queue.append((path, Path(self.project), resolved_video))

            if self.video_queue:
                self._process_next_video()
                return

        self.images = []
        self.parent_widget.load_saved_images(self.project, self.parent_widget.username, self.project_uuid, self.needs_fp)

    def _resolve_video_name(self, video_path):
        converted_dir = Path(self.project) / "converting_videos"
        converted_dir.mkdir(parents=True, exist_ok=True)

        base_name = video_path.stem
        candidate = converted_dir / base_name
        if not candidate.exists():
            return base_name

        index = 1
        while True:
            candidate = converted_dir / f"{base_name}_{index}"
            if not candidate.exists():
                break
            index += 1

        msg = QMessageBox(self)
        msg.setWindowTitle("Duplicate converted video folder")
        msg.setText(f"A converted video folder named '{base_name}' already exists.")
        msg.setInformativeText(f"Use '{base_name}_{index}' instead?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        result = msg.exec()
        if result == QMessageBox.StandardButton.Yes:
            return f"{base_name}_{index}"
        return None

    def _process_next_video(self):
        if self._video_processing or not self.video_queue:
            if not self._video_processing and not self.video_queue:
                self.images = []
                self.setText(self._default_text)
                self.setEnabled(True)
                print("[VideoConverter] Finished converting all videos.")
                QTimer.singleShot(0, lambda: self.parent_widget.load_saved_images(self.project, self.parent_widget.username, self.project_uuid, self.needs_fp))
            return

        self._video_processing = True
        self.setEnabled(False)
        self.setText("Converting video 1 of 1 (0/0 Frames)")

        video_path, project_path, output_name = self.video_queue.pop(0)
        self._video_thread = QThread(self)
        self._video_worker = VideoConvertWorker(video_path, project_path, output_name)
        self._video_worker.moveToThread(self._video_thread)

        self._video_thread.started.connect(self._video_worker.run)
        self._video_worker.progress.connect(self._handle_video_progress)
        self._video_worker.finished.connect(self._handle_video_result)
        self._video_worker.failed.connect(self._handle_video_error)
        self._video_worker.finished.connect(self._video_thread.quit)
        self._video_worker.failed.connect(self._video_thread.quit)
        self._video_worker.finished.connect(self._video_worker.deleteLater)
        self._video_worker.failed.connect(self._video_worker.deleteLater)
        self._video_thread.finished.connect(self._video_thread.deleteLater)

        self._video_thread.start()

    def _handle_video_progress(self, processed_frames, total_frames):
        self.setText(
            f"Converting video ({len(self.video_queue) + 1} Remaining) "
            f"(Frame {processed_frames}/{total_frames})"
        )

    def _handle_video_result(self, converted_frames):
        frames = [Path(p) for p in converted_frames]
        self.needs_fp.extend(frames)
        self.images.extend(frames)
        self._video_processing = False
        self._video_thread = None
        self._video_worker = None

        if len(self.video_queue) > 0:
            self._process_next_video()
        else:
            print("Finished converting all videos.")
            self.setText(self._default_text)
            self.setEnabled(True)
            QTimer.singleShot(0, lambda: self.parent_widget.load_saved_images(self.project, self.parent_widget.username, self.project_uuid, self.needs_fp))

    def _handle_video_error(self, exc):
        self._video_processing = False
        self._video_thread = None
        self._video_worker = None
        self.setText(self._default_text)
        self.setEnabled(True)
        self._process_next_video()
        QMessageBox.critical(
            self,
            "Video conversion failed",
            f"Could not process one of the uploaded videos: {exc}",
        )

class ImageLoader:
    def load_files(self, parent):
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Images",
            str(parent.controller.user_folder),
            "Images and Videos(*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.mp4 *.avi *.mov *.mkv);;ZIP Archives(*.zip)"
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
        self.project = self.parent_widget.current_project
        self.project_uuid = self.parent_widget.uuid
        files = LabelLoader().load_files(self)
        save_location_labels = self.project / "image_labels"
        save_location_labels.mkdir(parents=True, exist_ok=True)
        save_location_images = self.project / "image_uploads"
        save_location_images.mkdir(parents=True, exist_ok=True)

        if files:
            for file in files:
                path = Path(file)
                if path.suffix.lower() == ".zip":
                    with tempfile.TemporaryDirectory() as staging_directory:
                        extracted_files = extract_zip_contents(
                            path,
                            save_location_images,
                            Path(staging_directory),
                        )
                        self._add_extracted_files(extracted_files)
                elif path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.images.append(path)
                elif path.suffix.lower() in LABEL_EXTENSIONS:
                    self.labels.append(path)

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
            self.parent_widget.load_saved_images(self.project, self.parent_widget.username, self.project_uuid, [])

    def _add_extracted_files(self, extracted_files):
        for path in extracted_files:
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                self.images.append(path)
            elif path.suffix.lower() in LABEL_EXTENSIONS:
                self.labels.append(path)

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

            if path.suffix.lower() in IMAGE_EXTENSIONS:
                shutil.copy2(path, dest)

        elif type == "labels":
            dest = Path(save_location) / Path(path.name)

            # Label section: if the label does not have a corresponding image, add it to a list of labels that do not have corresponding images that will be shown to the user after the upload is complete
            label_has_corresponding_image = False
            corresponding_image = ""
            # Search for corresponding image in the files that were just uploaded and in the image_uploads folder of the project
            if path.suffix.lower() in LABEL_EXTENSIONS:
                img_folder = Path(self.controller.user_folder) / self.parent_widget.current_project / "image_uploads"
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