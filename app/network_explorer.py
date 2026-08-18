from PySide6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QProgressBar, QMessageBox
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QHostAddress, QHostInfo, QTcpServer, QTcpSocket, QUdpSocket
from PySide6.QtCore import QUrl
from pathlib import Path
from typing import Optional
import json, uuid

class NetworkExplorer(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.username = ""
        self.project = ""
        self.project_name = ""
        self.project_uuid = ""

    def receive_data(self, user, prj_folder):
        self.username = str(user)
        self.project = Path(prj_folder)
        self.project_name = Path(prj_folder.stem)
        