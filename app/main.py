from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QMainWindow, QHBoxLayout, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Qt
import sys
import json
from pathlib import Path

from login import LoginWindow, NewAccountWindow
from imgutil import ImageContainer, FirstPass
from audioutil import MusicHandler 
from project_explorer import ProjectExplorer
from project_viewer import ProjectWindow
from network_explorer import NetworkExplorer

SAVED_USER_DATA = ""
INSTALL_LOCATION = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

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
        self.image_viewer = ImageContainer(True, self, self)
        self.proj_explorer = ProjectExplorer(self)
        self.network_page = NetworkExplorer(self)
        self.first_pass_page = FirstPass(self)
            # Add to stacked widget
        self.sw.addWidget(self.login_page)          # self.controller.switch_page(0)
        self.sw.addWidget(self.create_account_page) # self.controller.switch_page(1)
        self.sw.addWidget(self.home)                # self.controller.switch_page(2)
        self.sw.addWidget(self.image_viewer)        # self.controller.switch_page(3)
        self.sw.addWidget(self.proj_explorer)       # self.controller.switch_page(4)
        self.sw.addWidget(self.network_page)        # self.controller.switch_page(5)
        self.sw.addWidget(self.first_pass_page)     # self.controller.switch_page(6)

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
            self.proj_explorer.logout_clear()
            self.home.logout_clear()
            self.switch_page(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.size()
    window = MainController()
    window.show()
    sys.exit(app.exec())
