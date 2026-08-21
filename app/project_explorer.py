from PySide6.QtWidgets import QApplication, QSizePolicy, QHBoxLayout, QInputDialog, QGridLayout, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QMessageBox, QScrollArea
from PySide6.QtCore import QSize, Signal, Qt, QTimer
from PySide6.QtGui import QCursor
import math, uuid, json
from pathlib import Path
from functools import partial
import shutil

INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class ProjectExplorer(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        ### INITIALIZE VARIABLES

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

        # Images
        self.pjs_per_page = 20
        self.current_page = 0

        ### WINDOWS

        # Main window
        self.setWindowTitle("Project Explorer - Local Projects")
        self.setMinimumSize(0, 0)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.mlayout = QVBoxLayout(central_widget)
        central_widget.setLayout(self.mlayout)
        self.mlayout.setSpacing(0)

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

        ### INSTANTIATE OBJECTS
        self.show_user = QLabel("")
        self.mlayout.addWidget(self.show_user, alignment=Qt.AlignmentFlag.AlignTop) 

        # Project list
        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(5)

        self.scroll_pjs = QScrollArea(self)
        self.scroll_pjs.setWidgetResizable(True)
        self.scroll_pjs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_pjs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mlayout.addWidget(self.scroll_pjs)
        
        self.scroll_pjs.setWidget(self.scroll_content)

        # Footer layout
            # Create new project button
        self.footer_layout = QHBoxLayout()
        self.footer_layout.addStretch()
        self.create_prj_btn_lbl = QLabel("Create Local Project")
        self.create_prj_btn_lbl.setWordWrap(True)
        self.create_prj_btn = QPushButton(self.create_prj_btn_lbl)
        self.create_prj_btn.setFixedSize(200, 50)
        self.create_prj_btn.clicked.connect(self.create_project)
        self.footer_layout.addWidget(self.create_prj_btn)

            # Switch to network projects list
        self.switch_prj_type_btn_lbl = QLabel("Switch to Shared(Network) Projects")
        self.switch_prj_type_btn_lbl.setWordWrap(True)
        self.switch_prj_type = QPushButton(self.switch_prj_type_btn_lbl)
        self.switch_prj_type.setFixedSize(200, 50)
        self.switch_prj_type.clicked.connect(lambda _: self.load_saved_pjs("local" if self.current_user_location == "shared" else "shared"))
        self.footer_layout.addWidget(self.switch_prj_type)
        self.mlayout.addLayout(self.footer_layout)

    def load_saved_pjs(self, ptype):
        self.user_folder = self.controller.user_folder

        self.load_and_update_json()

        if self.user_folder.exists() and self.user_folder.is_dir():
            prjs = []
            # Local prjs
            if ptype == "local":
                self.setWindowTitle("Project Explorer - Local Projects")
                self.switch_prj_type.setText("Switch to Shared/Network Projects")
                self.create_prj_btn.setText("Create Local Project")

                self.current_user_location = "local"
                prjs = self.local_prjs

            # Network prjs
            else:
                self.setWindowTitle("Project Explorer - Shared/Network Projects")
                self.switch_prj_type.setText("Switch to Local Projects")
                self.create_prj_btn.setText("Create Shared/Network Project")

                self.current_user_location = "shared"
                prjs = self.network_prjs

            self.show_prjs(prjs)

    def load_and_update_json(self):

        # Load saved project data
        data = []
        prj_dataf = Path(self.user_folder / f"{self.username}_projectdata.json")
        prj_dataf.touch(exist_ok=True)
        if prj_dataf.exists() and prj_dataf.stat().st_size > 0:
            with open(prj_dataf, "r") as f:
                data = json.load(f)

        # convert to set(name -> project data, uuid -> project data)
        self.prj_names = {entry["name"]: entry for entry in data if "name" in entry}
        self.prj_uuids = {entry["uuid"]: entry for entry in data if "uuid" in entry}

        # project folders
        self.prj_folder = self.user_folder / "projects"
        self.prj_folder.mkdir(parents=True, exist_ok=True)
        self.network_prj_folder = self.user_folder / "shared_projects"
        self.network_prj_folder.mkdir(parents=True, exist_ok=True)

        self.local_prjs = [
            p for p in self.prj_folder.iterdir() if p.is_dir()
        ]
        self.network_prjs = [
            p for p in self.network_prj_folder.iterdir() if p.is_dir()
        ]
        self.projects = self.local_prjs + self.network_prjs

        # UUID Checking, name and then uuid
        for prj in self.projects:
            prj_uuidfile = Path(prj / "uuid.txt")
            prj_uuidfile.touch(exist_ok=True)

            pname = prj.stem
            project_uuid = ""
            with open(prj_uuidfile, "r") as f:
                project_uuid = f.read().strip()
            prj_type = "CV"
            prj_shared = "local"
            if prj.parent == self.network_prj_folder:
                prj_shared = "network"

            if pname in self.prj_names:
                # Project name exists in JSON, check UUIDs
                existing_prj = self.prj_names[pname]
                existing_prj_uuid = existing_prj["uuid"]

                if project_uuid == "":
                    # project not given a UUID file yet
                    project_uuid = existing_prj_uuid
                    with open(prj_uuidfile, "w") as f:
                        f.write(project_uuid)
                    continue

                elif existing_prj_uuid == project_uuid:
                    # name and UUID match
                    continue

                else:
                    # Project names are the same but the UUIDs aren't. shouldn't happen unless a project was name changed manually
                    if project_uuid in self.prj_uuids:
                        # Project uuid exists, belongs to another project
                        QMessageBox.warning(
                            self,
                            "Project Mismatch",
                            "A project on the JSON has the same name as a saved project but a mismatched UUID. This project was removed from the JSON(no actual project data was deleted)."
                        )
                        data.remove(existing_prj)

                        self.prj_names.pop(pname, None)

                        if self.prj_uuids.get(existing_prj_uuid) is existing_prj:
                            self.prj_uuids.pop(existing_prj_uuid, None)

                        project_data = {
                            "name": pname,
                            "uuid": project_uuid,
                            "type": prj_type,
                            "shared": prj_shared
                        }
                        data.append(project_data)
                        self.prj_names[pname] = project_data
                        self.prj_uuids[project_uuid] = project_data

                    else:
                        # this should never run because it would mean the existing UUID from the JSON is not in the existing UUIDs from the JSON...
                        # manual JSON tampering while program running?
                        print("This block of code should not run unless the JSON is messed with manually while the program is running. Please contact me on GitHub if you see this message and were not tampering with the JSON.")
                        print("The application will now close.")
                        QApplication.quit()
                        return

            else:
                # project name doesnt exist in JSON

                # No project UUID file
                if project_uuid == "": 
                    project_uuid = str(uuid.uuid4())
                    while project_uuid in self.prj_uuids:
                        project_uuid = str(uuid.uuid4())
                    with open(prj_uuidfile, "w") as f:
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
                        with open(prj_uuidfile, "w") as f:
                            f.write(project_uuid)

                        project_data = {
                            "name": pname,
                            "uuid": project_uuid,
                            "type": prj_type,
                            "shared": prj_shared
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
                    # project in files but not in JSON
                    project_data = {
                        "name": pname,
                        "uuid": project_uuid,
                        "type": prj_type,
                        "shared": prj_shared
                    }
                    data.append(project_data)
                    self.prj_names[pname] = project_data
                    self.prj_uuids[project_uuid] = project_data

        # Rewrite JSON
        with open(prj_dataf, "w") as f:
            json.dump(data, f, indent=4)

    def show_prjs(self, prj_list):
        self.projects = prj_list
        self.current_page = 0
        self.update_prj_page()

    def update_prj_page(self):
        self.clear_prjs()
        self.username = self.controller.username

        page_pjs = self.projects[
            self.current_page * self.pjs_per_page:
            (self.current_page + 1) * self.pjs_per_page
        ]

        num_prjs = len(page_pjs)
        if num_prjs == 0:
            self.page_lbl.setText("No projects. Create one with the 'Create projects' button.")
            return
        
        for prj in page_pjs:
            # Container for individual project controls
            prj_container = QWidget()
            prj_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            prj_container_layout = QHBoxLayout(prj_container)
            prj_container_layout.setContentsMargins(0, 0, 0, 0)
            prj_container_layout.setSpacing(5)
            
            prj_btn = QPushButton(self.scroll_content)
            prj_btn.setText(prj.name)
            prj_btn.setMaximumHeight(30)

            prj_btn.clicked.connect(partial(self.open_project, prj))

            # Delete project
            delete_btn = QPushButton("Delete")
            delete_btn.setMaximumHeight(30)
            delete_btn.adjustSize()
            delete_btn.clicked.connect(partial(self.delete_project, prj))

            # Move to shared/network projects
            move_prj_btn = QPushButton("Copy to Shared/Network Projects")
            move_prj_btn.setMaximumHeight(30)
            move_prj_btn.adjustSize()
            move_prj_btn.clicked.connect(partial(self.move_to_shared, prj, self.current_user_location))

            # Set the button itself to be 75% the width of the prj_container widget
            prj_container_layout.addWidget(prj_btn, 3)
            prj_container_layout.addWidget(delete_btn)
            prj_container_layout.addWidget(move_prj_btn)
            
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

        self.controller.switch_page(2)
        self.controller.home.load_saved_images(
            prj, self.user_folder, project_data["uuid"], []
        )

    def move_to_shared(self, prj, ptype):
        copytotype = ("local" if ptype == "shared" else "shared") # what have i done to myself
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
            #prj_name = prj.stem.split('_')[-1]
            prj_name = prj.name
            while prj_name in [p.stem for p in self.projects]:
                n += 1
                prj_name = f"{prj_name}_{n}"
            copy_allowed = True
            if n > 1:
                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"Are you sure you want to copy '{prj.stem}', which is the same name as an existing {ptype} project? It will be stored in '{self.username}/{"projects" if copytotype == "local" else "shared_projects"}/{prj_name}'",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                copy_allowed = reply == QMessageBox.StandardButton.Yes
            if copy_allowed:
                folder = Path(INSTALL_LOCATION)
                if copytotype == "shared": # backwards logic sob
                    folder = self.network_prj_folder
                else:
                    folder = self.prj_folder
                shutil.copytree(prj, folder / Path(prj_name).name, dirs_exist_ok=True)
                copied = True
                copied_uuid = str(uuid.uuid4())
                copied_uuidfile = folder / prj_name / "uuid.txt"
                with open(copied_uuidfile, "w") as f:
                    f.write(copied_uuid)
                # print(f"Copied {prj} to {folder / Path(prj_name).name}")
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
        total_pages = math.ceil(
            len(self.projects) / self.pjs_per_page
        )

        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.load_saved_pjs(self.current_user_location)

    def update_pagination_controls(self):
        total_pages = math.ceil(
            len(self.projects) / self.pjs_per_page
        )

        if total_pages == 0:
            self.page_lbl.setText("No projects. Create one with the 'Create project' button.")
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

    def create_project(self):
        # Check saved project data again
        prj_dataf = Path(self.user_folder / f"{self.username}_projectdata.json")
        prj_dataf.touch(exist_ok=True)
        with open(prj_dataf, "r") as f:
            data = json.load(f)

        self.prj_names = {entry["name"]: entry for entry in data if "name" in entry}
        self.prj_uuids = {entry["uuid"]: entry for entry in data if "uuid" in entry}

        # New UUID
        project_uuid = str(uuid.uuid4())
        while project_uuid in self.prj_uuids:
            project_uuid = str(uuid.uuid4())

        # info for project data JSON
        prj_name = ""
        prj_type = "CV" # only does cv right now, hoping to extend to language soon
        prj_share = False

        new_prj_folder = Path(INSTALL_LOCATION)
        # local prj
        if self.current_user_location == "local":
            prj_name, ok = QInputDialog().getText(self, "Create Project", "Project name:", QLineEdit.EchoMode.Normal, "")
            n = 1
            if prj_name in [p.stem for p in self.projects]:
                prj_name = f"{prj_name}_{n}"
                while prj_name in [p.stem for p in self.projects]:
                    n += 1
                    prj_name = f"{prj_name}_{n}"

                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"Are you sure you want to create '{prj_name}', which is the same name as an existing local project? It will be stored in '{self.username}/projects/{prj_name}_{n}'",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    new_prj_folder = Path(self.prj_folder / prj_name)
                else:
                    return

            if ok and prj_name != '':
                new_prj_folder = Path(self.prj_folder / prj_name)
                new_prj_folder.mkdir(parents=True, exist_ok=True)
            else:
                return
        # shared prj
        else:
            prj_share = True
            prj_name, ok = QInputDialog().getText(self, "Create Shared Project", "Project name:", QLineEdit.EchoMode.Normal, "")
            n = 1
            if prj_name in [p.stem for p in self.projects]:
                prj_name = f"{prj_name}_{n}"
                while prj_name in [p.stem for p in self.projects]:
                    n += 1
                    prj_name = f"{prj_name}_{n}"

                reply = QMessageBox.question(
                    self,
                    "Duplicate Project Name",
                    f"Are you sure you want to create '{prj_name}', which is the same name as an existing network project? It will be stored in '{self.username}/shared_projects/{prj_name}_{n}'",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    new_prj_folder = Path(self.prj_folder / prj_name)
                else:
                    return
                
            if ok and prj_name != '':
                new_prj_folder = Path(self.network_prj_folder / prj_name)
                new_prj_folder.mkdir(parents=True, exist_ok=True)
            else:
                return

        # UUID storage
        data.append( {"name": prj_name, "uuid": project_uuid, "type": prj_type, "shared": prj_share} )
        with open(prj_dataf, "w") as f:
            json.dump(data, f, indent=4)

        prj_uuidfile = Path(new_prj_folder / "uuid.txt")
        prj_uuidfile.touch(exist_ok=True)
        with open(prj_uuidfile, "w") as f:
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
