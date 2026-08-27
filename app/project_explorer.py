from PySide6.QtWidgets import (
    QApplication,
    QSizePolicy,
    QHBoxLayout,
    QInputDialog,
    QGridLayout,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QScrollArea,
)

from PySide6.QtCore import (
    QSize,
    Signal,
    Qt,
    QTimer,
    QThread,
    QObject,
)

import math
import uuid
import json
from pathlib import Path
from functools import partial
import shutil


INSTALL_LOCATION = Path(__file__).resolve().parent.parent


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
}


class ProjectImageLoader(QObject):
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, project_path, generation):
        super().__init__()
        self.project_path = Path(project_path)
        self.generation = generation

    def run(self):
        try:
            images = []

            uploads = self.project_path / "image_uploads"

            if uploads.exists():
                for path in uploads.rglob("*"):
                    if (
                        path.is_file()
                        and path.suffix.lower() in IMAGE_EXTENSIONS
                    ):
                        images.append(path)

            print(
                f"[ProjectImageLoader] Found {len(images)} images "
                f"in {self.project_path}"
            )

            self.finished.emit(images, self.generation)

        except Exception as exc:
            self.failed.emit(str(exc))

class ProjectExplorer(QMainWindow):

    def __init__(self, controller):
        super().__init__()

        self.controller = controller

        # --------------------------------------------------
        # INITIALIZE VARIABLES
        # --------------------------------------------------

        # User info
        self.username = ""
        self.user_folder = Path(INSTALL_LOCATION)

        # Projects
        self.projects = []
        self.prj_folder = Path(INSTALL_LOCATION)
        self.prj_names = {}
        self.prj_uuids = {}
        self.network_prj_folder = Path(INSTALL_LOCATION)

        self.current_user_location = "local"

        self.local_prjs = []
        self.network_prjs = []

        # Project pagination
        self.pjs_per_page = 20
        self.current_page = 0

        # --------------------------------------------------
        # IMAGE LOADING THREAD STATE
        # --------------------------------------------------

        self._image_load_thread = None
        self._image_load_worker = None

        # Every time a project is opened this number is
        # incremented.
        #
        # This lets us ignore results from an older worker
        # if the user opens another project.
        self._image_load_generation = 0

        # --------------------------------------------------
        # MAIN WINDOW
        # --------------------------------------------------

        self.setWindowTitle(
            "Project Explorer - Local Projects"
        )

        self.setMinimumSize(0, 0)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.mlayout = QVBoxLayout(
            central_widget
        )

        self.mlayout.setSpacing(0)

        # --------------------------------------------------
        # PAGE CONTROLS
        # --------------------------------------------------

        self.page_layout = QHBoxLayout()

        self.prev_btn = QPushButton(
            "Previous"
        )

        self.next_btn = QPushButton(
            "Next"
        )

        self.page_lbl = QLabel(
            "Page 0 of 0"
        )

        self.prev_btn.clicked.connect(
            self.previous_page
        )

        self.next_btn.clicked.connect(
            self.next_page
        )

        self.page_layout.addWidget(
            self.prev_btn
        )

        self.page_layout.addWidget(
            self.next_btn
        )

        self.page_layout.addWidget(
            self.page_lbl
        )

        self.mlayout.addLayout(
            self.page_layout
        )

        # --------------------------------------------------
        # USER LABEL
        # --------------------------------------------------

        self.show_user = QLabel("")

        self.mlayout.addWidget(
            self.show_user,
            alignment=Qt.AlignmentFlag.AlignTop
        )

        # --------------------------------------------------
        # PROJECT LIST
        # --------------------------------------------------

        self.scroll_content = QWidget()

        self.scroll_layout = QGridLayout(
            self.scroll_content
        )

        self.scroll_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.scroll_layout.setSpacing(5)

        self.scroll_pjs = QScrollArea(self)

        self.scroll_pjs.setWidgetResizable(
            True
        )

        self.scroll_pjs.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_pjs.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_pjs.setWidget(
            self.scroll_content
        )

        self.mlayout.addWidget(
            self.scroll_pjs
        )

        # --------------------------------------------------
        # FOOTER
        # --------------------------------------------------

        self.footer_layout = QHBoxLayout()

        self.footer_layout.addStretch()

        # Create project
        self.create_prj_btn_lbl = QLabel(
            "Create Local Project"
        )

        self.create_prj_btn_lbl.setWordWrap(
            True
        )

        self.create_prj_btn = QPushButton(
            self.create_prj_btn_lbl
        )

        self.create_prj_btn.setFixedSize(
            200,
            50
        )

        self.create_prj_btn.clicked.connect(
            self.create_project
        )

        self.footer_layout.addWidget(
            self.create_prj_btn
        )

        # Switch project type
        self.switch_prj_type_btn_lbl = QLabel(
            "Switch to Shared(Network) Projects"
        )

        self.switch_prj_type_btn_lbl.setWordWrap(
            True
        )

        self.switch_prj_type = QPushButton(
            self.switch_prj_type_btn_lbl
        )

        self.switch_prj_type.setFixedSize(
            200,
            50
        )

        self.switch_prj_type.clicked.connect(
            lambda _:
                self.load_saved_pjs(
                    "local"
                    if self.current_user_location == "shared"
                    else "shared"
                )
        )

        self.footer_layout.addWidget(
            self.switch_prj_type
        )

        self.mlayout.addLayout(
            self.footer_layout
        )

    # ======================================================
    # PROJECT LOADING
    # ======================================================

    def load_saved_pjs(self, ptype):

        self.user_folder = (
            self.controller.user_folder
        )

        self.username = (
            self.controller.username
        )

        self.load_and_update_json()

        if (
            self.user_folder.exists()
            and self.user_folder.is_dir()
        ):

            if ptype == "local":

                self.setWindowTitle(
                    "Project Explorer - Local Projects"
                )

                self.switch_prj_type.setText(
                    "Switch to Shared/Network Projects"
                )

                self.create_prj_btn.setText(
                    "Create Local Project"
                )

                self.current_user_location = (
                    "local"
                )

                prjs = self.local_prjs

            else:

                self.setWindowTitle(
                    "Project Explorer - Shared/Network Projects"
                )

                self.switch_prj_type.setText(
                    "Switch to Local Projects"
                )

                self.create_prj_btn.setText(
                    "Create Shared/Network Project"
                )

                self.current_user_location = (
                    "shared"
                )

                prjs = self.network_prjs

            self.show_prjs(prjs)

    # ======================================================
    # PROJECT JSON
    # ======================================================

    def load_and_update_json(self):

        data = []

        prj_dataf = (
            Path(self.user_folder)
            / f"{self.username}_projectdata.json"
        )

        prj_dataf.touch(
            exist_ok=True
        )

        if (
            prj_dataf.exists()
            and prj_dataf.stat().st_size > 0
        ):

            with open(
                prj_dataf,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

        self.prj_names = {
            entry["name"]: entry
            for entry in data
            if "name" in entry
        }

        self.prj_uuids = {
            entry["uuid"]: entry
            for entry in data
            if "uuid" in entry
        }

        # --------------------------------------------------
        # PROJECT FOLDERS
        # --------------------------------------------------

        self.prj_folder = (
            self.user_folder / "projects"
        )

        self.prj_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        self.network_prj_folder = (
            self.user_folder / "shared_projects"
        )

        self.network_prj_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        self.local_prjs = [
            p
            for p in self.prj_folder.iterdir()
            if p.is_dir()
        ]

        self.network_prjs = [
            p
            for p in self.network_prj_folder.iterdir()
            if p.is_dir()
        ]

        self.projects = (
            self.local_prjs
            + self.network_prjs
        )

        # --------------------------------------------------
        # UUID CHECKING
        # --------------------------------------------------

        for prj in self.projects:

            prj_uuidfile = (
                prj / "uuid.txt"
            )

            prj_uuidfile.touch(
                exist_ok=True
            )

            pname = prj.stem

            with open(
                prj_uuidfile,
                "r",
                encoding="utf-8"
            ) as f:

                project_uuid = f.read().strip()

            prj_type = "CV"

            prj_shared = "local"

            if (
                prj.parent
                == self.network_prj_folder
            ):
                prj_shared = "network"

            # --------------------------------------------------
            # NAME EXISTS
            # --------------------------------------------------

            if pname in self.prj_names:

                existing_prj = (
                    self.prj_names[pname]
                )

                existing_prj_uuid = (
                    existing_prj["uuid"]
                )

                # UUID missing from project
                if project_uuid == "":

                    project_uuid = (
                        existing_prj_uuid
                    )

                    with open(
                        prj_uuidfile,
                        "w",
                        encoding="utf-8"
                    ) as f:

                        f.write(project_uuid)

                    continue

                # Everything matches
                elif (
                    existing_prj_uuid
                    == project_uuid
                ):

                    continue

                # Name matches but UUID doesn't
                else:

                    if (
                        project_uuid
                        in self.prj_uuids
                    ):

                        QMessageBox.warning(
                            self,
                            "Project Mismatch",
                            "A project on the JSON has "
                            "the same name as a saved "
                            "project but a mismatched "
                            "UUID. This project was removed "
                            "from the JSON(no actual project "
                            "data was deleted)."
                        )

                        data.remove(
                            existing_prj
                        )

                        self.prj_names.pop(
                            pname,
                            None
                        )

                        if (
                            self.prj_uuids.get(
                                existing_prj_uuid
                            )
                            is existing_prj
                        ):

                            self.prj_uuids.pop(
                                existing_prj_uuid,
                                None
                            )

                        project_data = {
                            "name": pname,
                            "uuid": project_uuid,
                            "type": prj_type,
                            "shared": prj_shared,
                        }

                        data.append(
                            project_data
                        )

                        self.prj_names[
                            pname
                        ] = project_data

                        self.prj_uuids[
                            project_uuid
                        ] = project_data

                    else:

                        print(
                            "This block of code should not "
                            "run unless the JSON is messed "
                            "with manually while the "
                            "program is running."
                        )

                        QApplication.quit()
                        return

            # --------------------------------------------------
            # NAME DOES NOT EXIST
            # --------------------------------------------------

            else:

                if project_uuid == "":

                    project_uuid = str(
                        uuid.uuid4()
                    )

                    while (
                        project_uuid
                        in self.prj_uuids
                    ):

                        project_uuid = str(
                            uuid.uuid4()
                        )

                    with open(
                        prj_uuidfile,
                        "w",
                        encoding="utf-8"
                    ) as f:

                        f.write(project_uuid)

                if project_uuid in self.prj_uuids:

                    existing_prj = (
                        self.prj_uuids[
                            project_uuid
                        ]
                    )

                    old_name = (
                        existing_prj["name"]
                    )

                    old_folder_exists = any(
                        existing_folder.stem
                        == old_name
                        for existing_folder
                        in self.projects
                    )

                    if old_folder_exists:

                        project_uuid = str(
                            uuid.uuid4()
                        )

                        while (
                            project_uuid
                            in self.prj_uuids
                        ):

                            project_uuid = str(
                                uuid.uuid4()
                            )

                        with open(
                            prj_uuidfile,
                            "w",
                            encoding="utf-8"
                        ) as f:

                            f.write(project_uuid)

                        project_data = {
                            "name": pname,
                            "uuid": project_uuid,
                            "type": prj_type,
                            "shared": prj_shared,
                        }

                        data.append(
                            project_data
                        )

                        self.prj_names[
                            pname
                        ] = project_data

                        self.prj_uuids[
                            project_uuid
                        ] = project_data

                    else:

                        existing_prj[
                            "name"
                        ] = pname

                        existing_prj[
                            "type"
                        ] = prj_type

                        existing_prj[
                            "shared"
                        ] = prj_shared

                        self.prj_names.pop(
                            old_name,
                            None
                        )

                        self.prj_names[
                            pname
                        ] = existing_prj

                else:

                    project_data = {
                        "name": pname,
                        "uuid": project_uuid,
                        "type": prj_type,
                        "shared": prj_shared,
                    }

                    data.append(
                        project_data
                    )

                    self.prj_names[
                        pname
                    ] = project_data

                    self.prj_uuids[
                        project_uuid
                    ] = project_data

        # --------------------------------------------------
        # WRITE JSON
        # --------------------------------------------------

        with open(
            prj_dataf,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )

    # ======================================================
    # PROJECT DISPLAY
    # ======================================================

    def show_prjs(self, prj_list):

        self.projects = prj_list
        self.current_page = 0

        self.update_prj_page()

    def update_prj_page(self):

        self.clear_prjs()

        self.username = (
            self.controller.username
        )

        page_pjs = self.projects[
            self.current_page
            * self.pjs_per_page:
            (
                self.current_page + 1
            )
            * self.pjs_per_page
        ]

        num_prjs = len(page_pjs)

        if num_prjs == 0:

            self.page_lbl.setText(
                "No projects. Create one with "
                "the 'Create projects' button."
            )

            self.update_pagination_controls()
            return

        for prj in page_pjs:

            # --------------------------------------------------
            # PROJECT CONTAINER
            # --------------------------------------------------

            prj_container = QWidget()

            prj_container.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )

            prj_container_layout = (
                QHBoxLayout(
                    prj_container
                )
            )

            prj_container_layout.setContentsMargins(
                0,
                0,
                0,
                0
            )

            prj_container_layout.setSpacing(
                5
            )

            # --------------------------------------------------
            # OPEN PROJECT
            # --------------------------------------------------

            prj_btn = QPushButton(
                self.scroll_content
            )

            prj_btn.setText(
                prj.name
            )

            prj_btn.setMaximumHeight(
                30
            )

            prj_btn.clicked.connect(
                partial(
                    self.open_project,
                    prj
                )
            )

            # --------------------------------------------------
            # DELETE
            # --------------------------------------------------

            delete_btn = QPushButton(
                "Delete"
            )

            delete_btn.setMaximumHeight(
                30
            )

            delete_btn.adjustSize()

            delete_btn.clicked.connect(
                partial(
                    self.delete_project,
                    prj
                )
            )

            # --------------------------------------------------
            # COPY TO SHARED
            # --------------------------------------------------

            move_prj_btn = QPushButton(
                "Copy to Shared/Network Projects"
            )

            move_prj_btn.setMaximumHeight(
                30
            )

            move_prj_btn.adjustSize()

            move_prj_btn.clicked.connect(
                partial(
                    self.move_to_shared,
                    prj,
                    self.current_user_location
                )
            )

            # --------------------------------------------------
            # LAYOUT
            # --------------------------------------------------

            prj_container_layout.addWidget(
                prj_btn,
                3
            )

            prj_container_layout.addWidget(
                delete_btn
            )

            prj_container_layout.addWidget(
                move_prj_btn
            )

            self.scroll_layout.addWidget(
                prj_container
            )

        self.update_pagination_controls()

    # ======================================================
    # OPEN PROJECT
    # ======================================================

    def open_project(self, prj):

        project_data = (
            self.prj_names.get(
                prj.name
            )
        )

        if project_data is None:

            self.load_and_update_json()

            project_data = (
                self.prj_names.get(
                    prj.name
                )
            )

        if project_data is None:

            QMessageBox.warning(
                self,
                "Project Metadata Missing",
                f"Project metadata for "
                f"'{prj.name}' could not be found."
            )

            return

        project_uuid = (
            project_data["uuid"]
        )

        # --------------------------------------------------
        # CANCEL / INVALIDATE OLD LOAD
        # --------------------------------------------------

        self._image_load_generation += 1

        generation = (
            self._image_load_generation
        )

        print(
            f"[ProjectExplorer] Opening project: "
            f"{prj.name}"
        )

        self.controller.switch_page(2)

        self.controller.home.load_saved_images(
            prj,
            self.user_folder,
            project_uuid
        )

        if (self._image_load_thread is not None and self._image_load_thread.isRunning()):
            print("[ProjectExplorer] An image loader is already running. The current load will finish before the new one starts.")
            return

        self._image_load_thread = QThread(self)

        self._image_load_worker = (ProjectImageLoader(prj, generation))

        self._image_load_worker.moveToThread(
            self._image_load_thread
        )

        # --------------------------------------------------
        # THREAD START
        # --------------------------------------------------

        self._image_load_thread.started.connect(
            self._image_load_worker.run
        )

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        self._image_load_worker.finished.connect(
            self._images_loaded
        )

        # --------------------------------------------------
        # FAILURE
        # --------------------------------------------------

        self._image_load_worker.failed.connect(
            self._image_load_failed
        )

        # --------------------------------------------------
        # CLEAN SHUTDOWN
        # --------------------------------------------------

        self._image_load_worker.finished.connect(
            self._image_load_thread.quit
        )

        self._image_load_worker.failed.connect(
            self._image_load_thread.quit
        )

        self._image_load_worker.finished.connect(
            self._image_load_worker.deleteLater
        )

        self._image_load_worker.failed.connect(
            self._image_load_worker.deleteLater
        )

        self._image_load_thread.finished.connect(
            self._image_loader_thread_finished
        )

        self._image_load_thread.finished.connect(
            self._image_load_thread.deleteLater
        )

        self._image_load_thread.start()

    # ======================================================
    # IMAGE LOAD COMPLETE
    # ======================================================

    def _images_loaded(
        self,
        images,
        generation
    ):

        print(
            f"[ProjectExplorer] Image scan finished. "
            f"Found {len(images)} images."
        )

        # --------------------------------------------------
        # IGNORE STALE RESULT
        # --------------------------------------------------

        if (
            generation
            != self._image_load_generation
        ):

            print(
                "[ProjectExplorer] Ignoring stale "
                "image-loader result."
            )

            return

        # --------------------------------------------------
        # SEND PATHS TO PROJECT VIEWER
        # --------------------------------------------------

        self.controller.home.finish_loading_images(
            images
        )

    # ======================================================
    # IMAGE LOAD FAILURE
    # ======================================================

    def _image_load_failed(
        self,
        error,
        generation
    ):

        if (
            generation
            != self._image_load_generation
        ):

            return

        print(
            f"[ProjectExplorer] Failed to load "
            f"project images: {error}"
        )

        QMessageBox.critical(
            self,
            "Failed to Load Project",
            "Could not load the project's images:\n\n"
            f"{error}"
        )

    # ======================================================
    # IMAGE LOADER THREAD FINISHED
    # ======================================================

    def _image_loader_thread_finished(self):

        print(
            "[ProjectExplorer] Image loader thread "
            "finished."
        )

        thread = (
            self._image_load_thread
        )

        self._image_load_thread = None
        self._image_load_worker = None

        if thread is not None:
            thread.deleteLater()

    # ======================================================
    # COPY PROJECT
    # ======================================================

    def move_to_shared(
        self,
        prj,
        ptype
    ):

        copytotype = (
            "local"
            if ptype == "shared"
            else "shared"
        )

        reply = QMessageBox.question(
            self,
            "Copy to Shared",
            f"Are you sure you want to copy "
            f"'{prj.name}' to {copytotype} projects?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        copied = False

        if (
            reply
            == QMessageBox.StandardButton.Yes
        ):

            n = 1
            prj_name = prj.name

            existing_names = [
                p.stem
                for p in self.projects
            ]

            while prj_name in existing_names:

                n += 1

                prj_name = (
                    f"{prj.name}_{n}"
                )

            copy_allowed = True

            if n > 1:

                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"Are you sure you want to copy "
                    f"'{prj.stem}', which is the same "
                    f"name as an existing {ptype} project? "
                    f"It will be stored in "
                    f"'{self.username}/"
                    f"{'projects' if copytotype == 'local' else 'shared_projects'}/"
                    f"{prj_name}'",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                copy_allowed = (
                    reply
                    == QMessageBox.StandardButton.Yes
                )

            if copy_allowed:

                if copytotype == "shared":
                    folder = (
                        self.network_prj_folder
                    )
                else:
                    folder = (
                        self.prj_folder
                    )

                destination = (
                    folder
                    / prj_name
                )

                shutil.copytree(
                    prj,
                    destination,
                    dirs_exist_ok=True
                )

                copied = True

                copied_uuid = str(
                    uuid.uuid4()
                )

                copied_uuidfile = (
                    destination
                    / "uuid.txt"
                )

                with open(
                    copied_uuidfile,
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(
                        copied_uuid
                    )

        if copied:

            self.load_and_update_json()

            self.load_saved_pjs(
                ptype
            )

    # ======================================================
    # DELETE PROJECT
    # ======================================================

    def delete_project(self, prj):

        reply = QMessageBox.question(
            self,
            "Delete Project",
            f"Are you sure you want to delete "
            f"'{prj.name}'?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if (
            reply
            == QMessageBox.StandardButton.Yes
        ):

            shutil.rmtree(prj)

            self.load_saved_pjs(
                self.current_user_location
            )

    # ======================================================
    # PAGINATION
    # ======================================================

    def previous_page(self):

        if self.current_page > 0:

            self.current_page -= 1

            self.load_saved_pjs(
                self.current_user_location
            )

    def next_page(self):

        total_pages = math.ceil(
            len(self.projects)
            / self.pjs_per_page
        )

        if (
            self.current_page
            < total_pages - 1
        ):

            self.current_page += 1

            self.load_saved_pjs(
                self.current_user_location
            )

    def update_pagination_controls(self):

        total_pages = math.ceil(
            len(self.projects)
            / self.pjs_per_page
        )

        if total_pages == 0:

            self.page_lbl.setText(
                "No projects. Create one with "
                "the 'Create project' button."
            )

        else:

            self.page_lbl.setText(
                f"Page {self.current_page + 1} "
                f"of {total_pages}"
            )

        self.prev_btn.setEnabled(
            self.current_page > 0
        )

        self.next_btn.setEnabled(
            self.current_page
            < total_pages - 1
        )

    # ======================================================
    # CREATE PROJECT
    # ======================================================

    def create_project(self):

        prj_dataf = (
            Path(self.user_folder)
            / f"{self.username}_projectdata.json"
        )

        prj_dataf.touch(
            exist_ok=True
        )

        with open(
            prj_dataf,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        self.prj_names = {
            entry["name"]: entry
            for entry in data
            if "name" in entry
        }

        self.prj_uuids = {
            entry["uuid"]: entry
            for entry in data
            if "uuid" in entry
        }

        project_uuid = str(
            uuid.uuid4()
        )

        while (
            project_uuid
            in self.prj_uuids
        ):

            project_uuid = str(
                uuid.uuid4()
            )

        prj_type = "CV"

        prj_share = False

        new_prj_folder = Path(
            INSTALL_LOCATION
        )

        # --------------------------------------------------
        # LOCAL PROJECT
        # --------------------------------------------------

        if (
            self.current_user_location
            == "local"
        ):

            prj_name, ok = (
                QInputDialog.getText(
                    self,
                    "Create Project",
                    "Project name:",
                    QLineEdit.EchoMode.Normal,
                    ""
                )
            )

            if not ok or not prj_name:
                return

            n = 1

            original_name = prj_name

            while prj_name in [
                p.stem
                for p in self.projects
            ]:

                n += 1

                prj_name = (
                    f"{original_name}_{n}"
                )

            if n > 1:

                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"'{original_name}' already exists. "
                    f"The new project will be stored as "
                    f"'{prj_name}'. Continue?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if (
                    reply
                    != QMessageBox.StandardButton.Yes
                ):
                    return

            new_prj_folder = (
                self.prj_folder
                / prj_name
            )

            new_prj_folder.mkdir(
                parents=True,
                exist_ok=True
            )

        # --------------------------------------------------
        # SHARED PROJECT
        # --------------------------------------------------

        else:

            prj_share = True

            prj_name, ok = (
                QInputDialog.getText(
                    self,
                    "Create Shared Project",
                    "Project name:",
                    QLineEdit.EchoMode.Normal,
                    ""
                )
            )

            if not ok or not prj_name:
                return

            n = 1

            original_name = prj_name

            while prj_name in [
                p.stem
                for p in self.projects
            ]:

                n += 1

                prj_name = (
                    f"{original_name}_{n}"
                )

            if n > 1:

                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"'{original_name}' already exists. "
                    f"The new project will be stored as "
                    f"'{prj_name}'. Continue?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if (
                    reply
                    != QMessageBox.StandardButton.Yes
                ):
                    return

            new_prj_folder = (
                self.network_prj_folder
                / prj_name
            )

            new_prj_folder.mkdir(
                parents=True,
                exist_ok=True
            )

        # --------------------------------------------------
        # SAVE JSON
        # --------------------------------------------------

        data.append(
            {
                "name": prj_name,
                "uuid": project_uuid,
                "type": prj_type,
                "shared": prj_share,
            }
        )

        with open(
            prj_dataf,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )

        # --------------------------------------------------
        # SAVE UUID
        # --------------------------------------------------

        prj_uuidfile = (
            new_prj_folder
            / "uuid.txt"
        )

        with open(
            prj_uuidfile,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                project_uuid
            )

        self.load_and_update_json()

        self.load_saved_pjs(
            self.current_user_location
        )

    # ======================================================
    # CLEAR PROJECT BUTTONS
    # ======================================================

    def clear_prjs(self):

        while self.scroll_layout.count():

            item = (
                self.scroll_layout.takeAt(0)
            )

            if item is None:
                continue

            widget = item.widget()

            if widget is not None:

                widget.deleteLater()

    # ======================================================
    # LOGOUT
    # ======================================================

    def logout_clear(self):

        # Invalidate any image-loading result.
        self._image_load_generation += 1

        self.clear_prjs()

        self.prj_folder = Path(
            INSTALL_LOCATION
        )

        self.username = ""

        self.user_folder = Path(
            INSTALL_LOCATION
        )

        self.projects.clear()

        self.network_prj_folder = Path(
            INSTALL_LOCATION
        )

        self.prj_names.clear()
        self.prj_uuids.clear()

        self.local_prjs.clear()
        self.network_prjs.clear()

        self.current_user_location = (
            "local"
        )

        self.pjs_per_page = 20
        self.current_page = 0

        self.show_user.setText("")

    # ======================================================
    # RESIZE
    # ======================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)