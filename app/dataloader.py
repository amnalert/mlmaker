from PySide6.QtWidgets import QPushButton, QFileDialog, QMessageBox, QInputDialog, QLineEdit, QSpinBox
from PySide6.QtCore import QTimer, QThread, QObject, Signal
import zipfile
from pathlib import Path
import shutil
import tempfile

from video_converter import VideoConverterFFMPEG
from box_manager import UploadFromBox

class VideoConvertWorker(QObject):
    finished = Signal(object, object)
    failed = Signal(str, object)
    progress = Signal(int, int)

    def __init__(self, video_path, project_path, frame_keep_percentage, output_name):
        super().__init__()

        self.video_path = video_path
        self.project_path = project_path
        self.output_name = output_name
        self.frame_keep = frame_keep_percentage

    def run(self):
        try:
            converter = VideoConverterFFMPEG(self)
            converted_frames = converter.probe(self.video_path, self.project_path, self.frame_keep, self.output_name)

            label_folder = (Path(self.project_path) / "image_labels" / self.output_name)
            label_folder.mkdir(parents=True, exist_ok=True)

            for frame in converted_frames:
                label_path = (label_folder / f"{Path(frame).stem}.txt")
                label_path.touch()

            self.finished.emit(converted_frames, self.video_path)

        except Exception as exc:
            print(f"[VideoConverter] Worker exception: {exc}")

            self.failed.emit(str(exc), self.video_path)

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

class UploadFiles(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload from Computer")

        self.controller = controller
        self.parent_widget = parents

        self.project = ""
        self.project_uuid = None
        self.image_uploads = ""

        self.video_queue = []
        self.images = []

        self._video_processing = False
        self._default_text = "Upload Images/Videos"

        self._video_thread = None
        self._video_worker = None

        self._current_video = None
        self._current_video_directory = None

        self.clicked.connect(self.open_dialog)

    def open_dialog(self):
        self.project = Path(
            self.parent_widget.current_project
        )

        self.project_uuid = (
            self.parent_widget.uuid
        )

        files = ImageLoader().load_files(self)

        self.image_uploads = (
            self.project / "image_uploads"
        )

        singlet_location = (
            self.image_uploads /
            "singlet_images"
        )

        singlet_location.mkdir(
            parents=True,
            exist_ok=True
        )

        if not files:
            return

        for file in files:
            path = Path(file)

            if path.suffix.lower() == ".zip":
                extracted_files = extract_zip_contents(
                    path,
                    self.image_uploads,
                    self.image_uploads
                )

                for destination in extracted_files:

                    if (
                        destination.suffix.lower()
                        in VIDEO_EXTENSIONS
                    ):
                        self.video_queue.append(
                            (
                                destination,
                                Path(self.project),
                                destination.stem
                            )
                        )

                    elif (
                        destination.suffix.lower()
                        in IMAGE_EXTENSIONS
                    ):
                        self.images.append(
                            destination
                        )

            elif (
                path.suffix.lower()
                in IMAGE_EXTENSIONS
            ):
                dest = (
                    singlet_location /
                    path.name
                )

                counter = 1

                while dest.exists():
                    dest = (
                        singlet_location /
                        f"{path.stem}_{counter}"
                        f"{path.suffix}"
                    )

                    counter += 1

                shutil.copy2(
                    path,
                    dest
                )

                self.images.append(dest)

            elif (
                path.suffix.lower()
                in VIDEO_EXTENSIONS
            ):
                self.video_queue.append(
                    (
                        path,
                        Path(self.project),
                        path.stem
                    )
                )

        if self.video_queue:
            self._process_next_video()
            return

        self.images = []

        self.parent_widget.load_saved_images(
            self.project,
            self.parent_widget.username,
            self.project_uuid
        )

    def _resolve_video_name(self, video_name):
        base_name = video_name
        candidate = (Path(self.image_uploads) / base_name)
        if not candidate.exists():
            return base_name

        index = 1
        while True:
            candidate = (Path(self.image_uploads) / f"{base_name}_{index}")
            if not candidate.exists():
                break
            index += 1

        return f"{base_name}_{index}"

    def _process_next_video(self):

        if self._video_processing:
            return

        if not self.video_queue:
            self._finish_video_processing()
            return

        self._video_processing = True

        self.setEnabled(False)

        remaining = len(self.video_queue)

        self.setText(
            f"Converting video "
            f"({remaining + 1} Remaining) "
            f"(Frame 0/0)"
        )

        video_path, project_path, output_name = (
            self.video_queue.pop(0)
        )

        self._current_video = Path(video_path)

        input_name, ok = QInputDialog.getText(
            self,
            "Video Name",
            "Please enter a unique video name "
            "(leave blank for video original name, "
            "but preferably describe the video contents "
            "with the name):",
            QLineEdit.EchoMode.Normal,
            output_name if output_name else ""
        )

        if not ok:
            QMessageBox.information(
                self,
                "Cancelled",
                f"Video upload cancelled: "
                f"{video_path.stem}"
            )

            self._video_processing = False
            self._current_video = None

            QTimer.singleShot(
                0,
                self._process_next_video
            )

            return

        if input_name.strip() == "":
            input_name = output_name

        resolved_name = (
            self._resolve_video_name(
                input_name.strip()
            )
        )

        dest_path = (Path(self.image_uploads) / resolved_name)

        dest_path.mkdir(
            parents=True,
            exist_ok=True
        )

        dest_fpath = (
            f"{resolved_name}"
            f"{video_path.suffix}"
        )

        destination_video = (
            dest_path /
            dest_fpath
        )

        try:
            shutil.copy2(
                video_path,
                destination_video
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to copy video:\n\n{e}"
            )

            try:
                if dest_path.exists():
                    shutil.rmtree(dest_path)
            except OSError:
                pass

            self._video_processing = False
            self._current_video = None

            QTimer.singleShot(
                0,
                self._process_next_video
            )

            return

        self._current_video_directory = dest_path

        frame_keep, ok = QInputDialog.getInt(
            self,
            "Frame Keep Percentage",
            "Choose % of frames to keep "
            "(0-100, where 0 is delete the video "
            "and 100 is keep all frames):",
            value=100,
            minValue=0,
            maxValue=100,
            step=5
        )

        if not ok:
            QMessageBox.information(
                self,
                "Cancelled",
                f"Video upload cancelled: "
                f"{video_path.stem}"
            )

            try:
                if dest_path.exists():
                    shutil.rmtree(dest_path)
            except OSError:
                pass

            self._video_processing = False
            self._current_video = None
            self._current_video_directory = None

            QTimer.singleShot(
                0,
                self._process_next_video
            )

            return

        if frame_keep == 0:
            print(
                f"[VideoConverter] Frame keep percentage "
                f"is 0. Skipping video: "
                f"{destination_video}"
            )

            try:
                if dest_path.exists():
                    shutil.rmtree(dest_path)
            except OSError as e:
                print(
                    f"[VideoConverter] Could not remove "
                    f"skipped video: {e}"
                )

            self._video_processing = False
            self._current_video = None
            self._current_video_directory = None

            QTimer.singleShot(
                0,
                self._process_next_video
            )

            return

        self._video_thread = QThread(self)

        self._video_worker = VideoConvertWorker(
            destination_video,
            project_path,
            frame_keep,
            resolved_name
        )

        self._video_worker.moveToThread(
            self._video_thread
        )

        self._video_thread.started.connect(
            self._video_worker.run
        )

        self._video_worker.progress.connect(
            self._handle_video_progress
        )

        self._video_worker.finished.connect(
            self._handle_video_result
        )

        self._video_worker.failed.connect(
            self._handle_video_error
        )

        self._video_worker.finished.connect(
            self._video_thread.quit
        )

        self._video_worker.failed.connect(
            self._video_thread.quit
        )

        self._video_thread.finished.connect(
            self._video_worker.deleteLater
        )

        self._video_thread.finished.connect(
            self._video_thread_finished
        )

        print(
            "[VideoConverter] Starting worker thread."
        )

        self._video_thread.start()

    def _handle_video_progress(
        self,
        processed_frames,
        total_frames
    ):
        if total_frames > 0:
            self.setText(
                f"Converting video "
                f"({len(self.video_queue) + 1} Remaining) "
                f"(Frame "
                f"{processed_frames}/"
                f"{total_frames})"
            )

        else:
            self.setText(
                f"Converting video "
                f"({len(self.video_queue) + 1} Remaining) "
                f"(Frame "
                f"{processed_frames}/?)"
            )

    def _handle_video_result(
        self,
        converted_frames,
        video
    ):
        print(
            "[VideoConverter] Worker reported successful "
            "conversion."
        )

        frames = [
            Path(p)
            for p in converted_frames
        ]

        self.images.extend(frames)

        video = Path(video)

        try:
            if video.exists():
                source_directory = video.parent

                if source_directory.exists():
                    print(
                        f"[VideoConverter] Video stored at "
                        f"{source_directory}"
                    )

        except Exception as e:
            print(
                f"[VideoConverter] Could not finalize "
                f"video location: {e}"
            )

    def _handle_video_error(
        self,
        exc,
        video
    ):
        print(
            f"[VideoConverter] Conversion failed: "
            f"{exc}"
        )

        if exc == "import_fail":
            QMessageBox.critical(
                self,
                "Video conversion failed",
                "At least one of the following packages "
                "is required for video conversion:\n\n"
                "ffmpeg-python\n"
                "opencv-python"
            )

        else:
            QMessageBox.critical(
                self,
                "Video conversion failed",
                f"Could not process one of the "
                f"uploaded videos:\n\n"
                f"{exc}\n\n"
                f"Video: {video}"
            )

    def _video_thread_finished(self):
        print(
            "[VideoConverter] QThread finished."
        )

        finished_thread = self._video_thread
        finished_worker = self._video_worker

        self._video_thread = None
        self._video_worker = None

        self._video_processing = False

        self._current_video = None
        self._current_video_directory = None

        if self.video_queue:
            print(
                "[VideoConverter] Starting next video."
            )

            QTimer.singleShot(
                0,
                self._process_next_video
            )

            return

        self._finish_video_processing()

    def _finish_video_processing(self):
        print(
            "[VideoConverter] Finished converting "
            "all videos."
        )

        self._video_processing = False

        self.setText(
            self._default_text
        )

        self.setEnabled(True)

        QTimer.singleShot(
            0,
            lambda: self.parent_widget.load_saved_images(
                self.project,
                self.parent_widget.username,
                self.project_uuid
            )
        )

class ImageLoader:
    def load_files(self, parent):
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Images",
            str(parent.controller.user_folder),
            "Images and Videos(*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.mp4 *.avi *.mov *.mkv);;ZIP Archives(*.zip *.7z *.tar)"
        )
        return files

class UploadLabels(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Labels with Corresponding Images")

        self.controller = controller
        self.parent_widget = parents

        self.project = ""
        self.image_uploads = ""

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
        self.image_uploads = self.project / "image_uploads"
        self.image_uploads.mkdir(parents=True, exist_ok=True)

        if files:
            for file in files:
                path = Path(file)
                if path.suffix.lower() == ".zip":
                    with tempfile.TemporaryDirectory() as staging_directory:
                        extracted_files = extract_zip_contents(
                            path,
                            self.image_uploads,
                            Path(staging_directory),
                        )
                        self._add_extracted_files(extracted_files)
                elif path.suffix.lower() in IMAGE_EXTENSIONS:
                    self.images.append(path)
                elif path.suffix.lower() in LABEL_EXTENSIONS:
                    self.labels.append(path)

            for path in self.images:
                self.copy_to_project(path, "images", self.image_uploads)
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
            self.parent_widget.load_saved_images(self.project, self.parent_widget.username, self.project_uuid)

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
                for other_file in self.images:
                    if Path(other_file).stem == Path(path).stem and other_file != path:
                        label_has_corresponding_image = True
                        corresponding_image = Path(other_file)
                        break
                if corresponding_image == "":
                    for image in Path(self.image_uploads).iterdir():
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