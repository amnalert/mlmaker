from PySide6.QtWidgets import QApplication, QHBoxLayout, QInputDialog, QGridLayout, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QMessageBox, QScrollArea
from PySide6.QtCore import QSize, Signal, Qt, QTimer
from PySide6.QtGui import QCursor
import math
from pathlib import Path

class ProjectExplorer(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        ### INITIALIZE VARIABLES

        # User info
        self.username = self.controller.username

        # Images
        self.projects = []
        self.pjs_per_page = 20
        self.current_page = 0

        ### WINDOWS

        # Main window
        self.setWindowTitle("Project Explorer")
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
        self.scroll_pjs.resizeEvent = lambda event: (
            self.scroll_pjs.setMinimumWidth(
                self.scroll_pjs.viewport().width()
            )
        )

        # Create new project and footer layout
        self.footer_layout = QHBoxLayout()
        self.footer_layout.addStretch()
        self.create_prj_btn = QPushButton("Create project")
        self.create_prj_btn.setFixedSize(200, 50)
        self.create_prj_btn.clicked.connect(lambda: self.create_project())
        self.footer_layout.addWidget(self.create_prj_btn)
        self.mlayout.addLayout(self.footer_layout)

    def load_saved_pjs(self):
        print("Loading saved projects...")
        self.user_folder = self.controller.user_folder
        if self.user_folder.exists() and self.user_folder.is_dir():
            self.prj_folder = self.user_folder / "projects"
            self.prj_folder.mkdir(parents=True, exist_ok=True)
            prjs = [
                Path(p) for p in self.prj_folder.iterdir()
                if p.is_dir()
            ]
            self.show_prjs(prjs)

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
        
        for index, prj in enumerate(page_pjs):
            prj_btn = QPushButton(self.scroll_content)
            prj_btn.setText(prj.name)
            prj_btn.setMaximumSize(self.scroll_pjs.viewport().width(), 30)

            prj_btn.clicked.connect(lambda: self.open_project(prj))
            self.scroll_layout.addWidget(prj_btn)

        self.update_pagination_controls()

    def open_project(self, prj):
        self.controller.switch_page(2)
        self.controller.home.load_project(prj)

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_prj_page()

    def next_page(self):
        total_pages = math.ceil(
            len(self.projects) / self.pjs_per_page
        )

        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_prj_page()

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
        prj_name, ok_pressed = QInputDialog().getText(self, "Create Project","Project name:", QLineEdit.EchoMode.Normal, "")
        if ok_pressed and prj_name != '':
            new_prj_folder = self.prj_folder / prj_name
            new_prj_folder.mkdir(parents=True, exist_ok=True)
        self.update_prj_page()

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

        if len(self.projects) > 0:
            self.update_prj_page()
