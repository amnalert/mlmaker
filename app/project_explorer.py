from PySide6.QtWidgets import (
    QApplication, QSizePolicy, QHBoxLayout, QInputDialog, QGridLayout,
    QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QMessageBox, QScrollArea
)
from PySide6.QtCore import QSize, Signal, Qt, QTimer, QThread, QObject

import math
import uuid
import json
import shutil
from pathlib import Path
from functools import partial

INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

class ProjectImageLoader(QObject):
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, project_path, generation):
        super().__init__()
        self.project_path = Path(project_path)
        self.generation = generation

    def run(self):
        try:
            uploads = self.project_path / "image_uploads"
            images = [
                path for path in uploads.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ] if uploads.exists() else []

            print(f"[ProjectImageLoader] Found {len(images)} images in {self.project_path}")
            self.finished.emit(images, self.generation)

        except Exception as exc:
            self.failed.emit(str(exc))


class ProjectExplorer(QMainWindow):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller

        self.username = ""
        self.user_folder = Path(INSTALL_LOCATION)

        self.projects = []
        self.prj_folder = Path(INSTALL_LOCATION)
        self.prj_names = {}
        self.prj_uuids = {}
        self.network_prj_folder = Path(INSTALL_LOCATION)

        self.current_user_location = "local"
        self.local_prjs = []
        self.network_prjs = []

        self.pjs_per_page = 20
        self.current_page = 0

        self._image_load_thread = None
        self._image_load_worker = None
        self._image_load_generation = 0

        self.setWindowTitle("Project Explorer - Local Projects")
        self.setMinimumSize(0, 0)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.mlayout = QVBoxLayout(central_widget)
        self.mlayout.setSpacing(0)

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

        self.show_user = QLabel("")
        self.mlayout.addWidget(
            self.show_user,
            alignment=Qt.AlignmentFlag.AlignTop
        )

        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)

        self.scroll_pjs = QScrollArea(self)
        self.scroll_pjs.setWidgetResizable(True)
        self.scroll_pjs.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_pjs.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_pjs.setWidget(self.scroll_content)
        self.mlayout.addWidget(self.scroll_pjs)

        self.footer_layout = QHBoxLayout()
        self.footer_layout.addStretch()

        self.create_prj_btn = QPushButton("Create Local Project")
        self.create_prj_btn.setFixedSize(200, 50)
        self.create_prj_btn.clicked.connect(self.create_project)
        self.footer_layout.addWidget(self.create_prj_btn)

        self.switch_prj_type = QPushButton("Switch to Shared/Network Projects")
        self.switch_prj_type.setFixedSize(200, 50)
        self.switch_prj_type.clicked.connect(
            lambda _: self.load_saved_pjs(
                "local" if self.current_user_location == "shared" else "shared"
            )
        )
        self.footer_layout.addWidget(self.switch_prj_type)

        self.mlayout.addLayout(self.footer_layout)

    def load_saved_pjs(self, ptype):
        self.user_folder = self.controller.user_folder
        self.username = self.controller.username

        self.load_and_update_json()

        if not self.user_folder.exists() or not self.user_folder.is_dir():
            return

        if ptype == "local":
            self.setWindowTitle("Project Explorer - Local Projects")
            self.switch_prj_type.setText("Switch to Shared/Network Projects")
            self.create_prj_btn.setText("Create Local Project")
            self.current_user_location = "local"
            prjs = self.local_prjs
        else:
            self.setWindowTitle("Project Explorer - Shared/Network Projects")
            self.switch_prj_type.setText("Switch to Local Projects")
            self.create_prj_btn.setText("Create Shared/Network Project")
            self.current_user_location = "shared"
            prjs = self.network_prjs

        self.show_prjs(prjs)

    def load_and_update_json(self):
        data = []

        prj_dataf = self.user_folder / f"{self.username}_projectdata.json"
        prj_dataf.touch(exist_ok=True)

        if prj_dataf.stat().st_size > 0:
            with open(prj_dataf, "r", encoding="utf-8") as f:
                data = json.load(f)

        self.prj_names = {
            entry["name"]: entry for entry in data if "name" in entry
        }
        self.prj_uuids = {
            entry["uuid"]: entry for entry in data if "uuid" in entry
        }

        self.prj_folder = self.user_folder / "projects"
        self.prj_folder.mkdir(parents=True, exist_ok=True)

        self.network_prj_folder = self.user_folder / "shared_projects"
        self.network_prj_folder.mkdir(parents=True, exist_ok=True)

        self.local_prjs = [p for p in self.prj_folder.iterdir() if p.is_dir()]
        self.network_prjs = [
            p for p in self.network_prj_folder.iterdir() if p.is_dir()
        ]
        self.projects = self.local_prjs + self.network_prjs

        for prj in self.projects:
            prj_uuidfile = prj / "uuid.txt"
            prj_uuidfile.touch(exist_ok=True)

            pname = prj.stem

            with open(prj_uuidfile, "r", encoding="utf-8") as f:
                project_uuid = f.read().strip()

            prj_type = "CV"
            prj_shared = prj.parent == self.network_prj_folder

            if pname in self.prj_names:
                existing_prj = self.prj_names[pname]
                existing_prj_uuid = existing_prj["uuid"]

                if not project_uuid:
                    project_uuid = existing_prj_uuid
                    with open(prj_uuidfile, "w", encoding="utf-8") as f:
                        f.write(project_uuid)
                    continue

                if existing_prj_uuid == project_uuid:
                    continue

                if project_uuid in self.prj_uuids:
                    QMessageBox.warning(
                        self,
                        "Project Mismatch",
                        "A project on the JSON has the same name as a saved "
                        "project but a mismatched UUID. This project was removed "
                        "from the JSON (no actual project data was deleted)."
                    )

                    data.remove(existing_prj)
                    self.prj_names.pop(pname, None)

                    if self.prj_uuids.get(existing_prj_uuid) is existing_prj:
                        self.prj_uuids.pop(existing_prj_uuid, None)

                    project_data = {
                        "name": pname,
                        "uuid": project_uuid,
                        "type": prj_type,
                        "shared": prj_shared,
                    }

                    data.append(project_data)
                    self.prj_names[pname] = project_data
                    self.prj_uuids[project_uuid] = project_data
                else:
                    print(
                        "This block should not run unless the JSON was "
                        "manually modified while the program is running."
                    )
                    QApplication.quit()
                    return

            else:
                if not project_uuid:
                    project_uuid = str(uuid.uuid4())
                    while project_uuid in self.prj_uuids:
                        project_uuid = str(uuid.uuid4())

                    with open(prj_uuidfile, "w", encoding="utf-8") as f:
                        f.write(project_uuid)

                if project_uuid in self.prj_uuids:
                    existing_prj = self.prj_uuids[project_uuid]
                    old_name = existing_prj["name"]

                    old_folder_exists = any(
                        existing_folder.stem == old_name
                        for existing_folder in self.projects
                    )

                    if old_folder_exists:
                        project_uuid = str(uuid.uuid4())
                        while project_uuid in self.prj_uuids:
                            project_uuid = str(uuid.uuid4())

                        with open(prj_uuidfile, "w", encoding="utf-8") as f:
                            f.write(project_uuid)

                        project_data = {
                            "name": pname,
                            "uuid": project_uuid,
                            "type": prj_type,
                            "shared": prj_shared,
                        }

                        data.append(project_data)
                        self.prj_names[pname] = project_data
                        self.prj_uuids[project_uuid] = project_data

                    else:
                        existing_prj["name"] = pname
                        existing_prj["type"] = prj_type
                        existing_prj["shared"] = prj_shared

                        self.prj_names.pop(old_name, None)
                        self.prj_names[pname] = existing_prj

                else:
                    project_data = {
                        "name": pname,
                        "uuid": project_uuid,
                        "type": prj_type,
                        "shared": prj_shared,
                    }

                    data.append(project_data)
                    self.prj_names[pname] = project_data
                    self.prj_uuids[project_uuid] = project_data

        with open(prj_dataf, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def show_prjs(self, prj_list):
        self.projects = prj_list
        self.current_page = 0
        self.update_prj_page()

    def update_prj_page(self):
        self.clear_prjs()
        self.username = self.controller.username

        start = self.current_page * self.pjs_per_page
        end = (self.current_page + 1) * self.pjs_per_page
        page_pjs = self.projects[start:end]

        if not page_pjs:
            self.page_lbl.setText(
                "No projects. Create one with the 'Create projects' button."
            )
            self.update_pagination_controls()
            return

        for prj in page_pjs:
            prj_container = QWidget()
            prj_container.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed
            )

            layout = QHBoxLayout(prj_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            prj_btn = QPushButton(prj.name, self.scroll_content)
            prj_btn.setMaximumHeight(30)
            prj_btn.clicked.connect(partial(self.open_project, prj))

            delete_btn = QPushButton("Delete")
            delete_btn.setMaximumHeight(30)
            delete_btn.adjustSize()
            delete_btn.clicked.connect(partial(self.delete_project, prj))

            move_prj_btn = QPushButton("Copy to Shared/Network Projects")
            move_prj_btn.setMaximumHeight(30)
            move_prj_btn.adjustSize()
            move_prj_btn.clicked.connect(
                partial(self.move_to_shared, prj, self.current_user_location)
            )

            layout.addWidget(prj_btn, 3)
            layout.addWidget(delete_btn)
            layout.addWidget(move_prj_btn)

            self.scroll_layout.addWidget(prj_container)

        self.update_pagination_controls()

    def open_project(self, prj):
        project_data = self.prj_names.get(prj.name)

        if project_data is None:
            self.load_and_update_json()
            project_data = self.prj_names.get(prj.name)

        if project_data is None:
            QMessageBox.warning(
                self,
                "Project Metadata Missing",
                f"Project metadata for '{prj.name}' could not be found."
            )
            return

        project_uuid = project_data["uuid"]

        self._image_load_generation += 1
        generation = self._image_load_generation

        print(f"[ProjectExplorer] Opening project: {prj.name}")

        self.controller.switch_page(2)
        self.controller.home.load_saved_images(
            prj, self.username, self.user_folder, project_uuid
        )

        if self._image_load_thread is not None and self._image_load_thread.isRunning():
            print(
                "[ProjectExplorer] An image loader is already running. "
                "The current load will finish before the new one starts."
            )
            return

        self._image_load_thread = QThread(self)
        self._image_load_worker = ProjectImageLoader(prj, generation)
        self._image_load_worker.moveToThread(self._image_load_thread)

        self._image_load_thread.started.connect(self._image_load_worker.run)

        self._image_load_worker.finished.connect(self._images_loaded)
        self._image_load_worker.failed.connect(self._image_load_failed)

        self._image_load_worker.finished.connect(self._image_load_thread.quit)
        self._image_load_worker.failed.connect(self._image_load_thread.quit)

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

    def _images_loaded(self, images, generation):
        print(f"[ProjectExplorer] Image scan finished. Found {len(images)} images.")

        if generation != self._image_load_generation:
            print("[ProjectExplorer] Ignoring stale image-loader result.")
            return

        self.controller.home.finish_loading_images(images)

    def _image_load_failed(self, error, generation):
        if generation != self._image_load_generation:
            return

        print(f"[ProjectExplorer] Failed to load project images: {error}")

        QMessageBox.critical(
            self,
            "Failed to Load Project",
            f"Could not load the project's images:\n\n{error}"
        )

    def _image_loader_thread_finished(self):
        print("[ProjectExplorer] Image loader thread finished.")

        thread = self._image_load_thread
        self._image_load_thread = None
        self._image_load_worker = None

        if thread is not None:
            thread.deleteLater()

    def move_to_shared(self, prj, ptype):
        copytotype = "local" if ptype == "shared" else "shared"

        reply = QMessageBox.question(
            self,
            "Copy to Shared",
            f"Are you sure you want to copy '{prj.name}' to {copytotype} projects?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        copied = False

        if reply == QMessageBox.StandardButton.Yes:
            n = 1
            prj_name = prj.name
            existing_names = [p.stem for p in self.projects]

            while prj_name in existing_names:
                n += 1
                prj_name = f"{prj.name}_{n}"

            copy_allowed = True

            if n > 1:
                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"Are you sure you want to copy '{prj.stem}', which is the "
                    f"same name as an existing {ptype} project? It will be stored "
                    f"in '{self.username}/"
                    f"{'projects' if copytotype == 'local' else 'shared_projects'}/"
                    f"{prj_name}'",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                copy_allowed = reply == QMessageBox.StandardButton.Yes

            if copy_allowed:
                folder = (
                    self.network_prj_folder
                    if copytotype == "shared"
                    else self.prj_folder
                )
                destination = folder / prj_name

                shutil.copytree(prj, destination, dirs_exist_ok=True)

                copied = True
                copied_uuid = str(uuid.uuid4())

                with open(destination / "uuid.txt", "w", encoding="utf-8") as f:
                    f.write(copied_uuid)

        if copied:
            self.load_and_update_json()
            self.load_saved_pjs(ptype)

    def delete_project(self, prj):
        reply = QMessageBox.question(
            self,
            "Delete Project",
            f"Are you sure you want to delete '{prj.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            shutil.rmtree(prj)
            self.load_saved_pjs(self.current_user_location)

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_saved_pjs(self.current_user_location)

    def next_page(self):
        total_pages = math.ceil(len(self.projects) / self.pjs_per_page)

        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.load_saved_pjs(self.current_user_location)

    def update_pagination_controls(self):
        total_pages = math.ceil(len(self.projects) / self.pjs_per_page)

        if total_pages == 0:
            self.page_lbl.setText(
                "No projects. Create one with the 'Create project' button."
            )
        else:
            self.page_lbl.setText(
                f"Page {self.current_page + 1} of {total_pages}"
            )

        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)

    def create_project(self):
        prj_dataf = self.user_folder / f"{self.username}_projectdata.json"
        prj_dataf.touch(exist_ok=True)

        with open(prj_dataf, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.prj_names = {
            entry["name"]: entry for entry in data if "name" in entry
        }
        self.prj_uuids = {
            entry["uuid"]: entry for entry in data if "uuid" in entry
        }

        project_uuid = str(uuid.uuid4())
        while project_uuid in self.prj_uuids:
            project_uuid = str(uuid.uuid4())

        prj_type = "CV"
        prj_share = self.current_user_location == "shared"

        title = (
            "Create Shared Project"
            if prj_share
            else "Create Project"
        )

        prj_name, ok = QInputDialog.getText(
            self,
            title,
            "Project name:",
            QLineEdit.EchoMode.Normal,
            ""
        )

        if not ok or not prj_name:
            return

        n = 1
        original_name = prj_name
        existing_names = [p.stem for p in self.projects]

        while prj_name in existing_names:
            n += 1
            prj_name = f"{original_name}_{n}"

        if n > 1:
            reply = QMessageBox.question(
                self,
                "Duplicate Project Name",
                f"'{original_name}' already exists. The new project will be "
                f"stored as '{prj_name}'. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        folder = (
            self.network_prj_folder
            if prj_share
            else self.prj_folder
        )
        new_prj_folder = folder / prj_name
        new_prj_folder.mkdir(parents=True, exist_ok=True)

        data.append({
            "name": prj_name,
            "uuid": project_uuid,
            "type": prj_type,
            "shared": prj_share,
        })

        with open(prj_dataf, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        with open(new_prj_folder / "uuid.txt", "w", encoding="utf-8") as f:
            f.write(project_uuid)

        self.load_and_update_json()
        self.load_saved_pjs(self.current_user_location)

    def clear_prjs(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)

            if item is None:
                continue

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def logout_clear(self):
        self._image_load_generation += 1

        self.clear_prjs()

        self.prj_folder = Path(INSTALL_LOCATION)
        self.username = ""
        self.user_folder = Path(INSTALL_LOCATION)
        self.projects.clear()
        self.network_prj_folder = Path(INSTALL_LOCATION)

        self.prj_names.clear()
        self.prj_uuids.clear()
        self.local_prjs.clear()
        self.network_prjs.clear()

        self.current_user_location = "local"
        self.pjs_per_page = 20
        self.current_page = 0

        self.show_user.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)