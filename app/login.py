import keyring
import argparse
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QCursor
from datetime import datetime

APP_NAME = "ML Maker"
USERNAME = "default"

class LoginWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # Main window
        self.setFixedSize(QSize(350, 200))
        layout = QVBoxLayout()
        cscreen = QApplication.screenAt(QCursor.pos())
        if not cscreen:
            cscreen = QApplication.primaryScreen()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setLayout(layout)
        self.label = QLabel("Login")

        ### INSTANTIATE OBJECTS

        # Instruction label
        self.instr = QLabel("Enter username and password:")
        layout.addWidget(self.instr)

        # Username Input Field
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        layout.addWidget(self.user_input)

        # PW Input Field
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Password")
        layout.addWidget(self.pw_input)

        # Login button
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self.login)
        layout.addWidget(self.login_btn)

        # Create account button
        self.newacc_btn = QPushButton("Create account")
        self.newacc_btn.clicked.connect(lambda: controller.switch_page(1))    
        layout.addWidget(self.newacc_btn, alignment=Qt.AlignmentFlag.AlignRight)

    ### FUNCTIONS

    # Login
    def login(self):
        is_valid = False
        password = self.pw_input.text()
        username = self.user_input.text()
        stored_password = keyring.get_password(APP_NAME, username)

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter a username and password.")
            is_valid = False
        elif stored_password is None:
            reply = QMessageBox.question(
                self,
                "Notice",
                "Username not associated with account. Create one?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.controller.switch_page(1)
            else:
                return
        elif stored_password == password:
            is_valid = True

        if is_valid:
            self.controller.showMaximized()
            payload = {
                "username": username,
                "access_date": str(datetime.now())
            }
            self.controller.receive_user_data(payload)
            QMessageBox.information(
                self, "Success",
                f"Login successful for {username}"
            )
            self.controller.switch_page(2)
        else:
            QMessageBox.critical(
                self, "Failure",
                "Invalid username or password. Try again."
            )
            return

class NewAccountWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # Main window
        self.setFixedSize(QSize(350, 200))
        layout = QVBoxLayout()
        cscreen = QApplication.screenAt(QCursor.pos())
        if not cscreen:
            cscreen = QApplication.primaryScreen()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setLayout(layout)
        self.label = QLabel("Login")

        ### INSTANTIATE OBJECTS

        # Instruction label
        self.instr = QLabel("Enter username and password to create new account:")
        layout.addWidget(self.instr)

        # Username Input Field
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        layout.addWidget(self.user_input)

        # PW Input Field
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Password")
        layout.addWidget(self.pw_input)

        # Return to login button
        self.login_btn = QPushButton("Return to Login")
        self.login_btn.clicked.connect(self.return_to_login)
        layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Create account button
        self.newacc_btn = QPushButton("Create account")
        self.newacc_btn.clicked.connect(self.create)
        layout.addWidget(self.newacc_btn)

    ### FUNCTIONS
    def create(self):
        u = self.user_input.text()
        p = self.pw_input.text()
        if not u or not p:
            QMessageBox.warning(self, "Error", "Please enter a username and password.")
            return
        existing = keyring.get_password(APP_NAME, u)
        if existing is not None:
            QMessageBox.warning(
                self,
                "Username Taken",
                "That username already exists. Please choose another."
            )
            return
        try:
            keyring.set_password(APP_NAME, u, p)
            QMessageBox.information(self, "Success", "Logged in!")
            self.pw_input.clear()
            payload = {
                "username": self.user_input.text(),
                "access_date": str(datetime.now())
            }
            self.controller.receive_user_data(payload)
            self.controller.switch_page(2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def return_to_login(self):
        self.controller.switch_page(0)