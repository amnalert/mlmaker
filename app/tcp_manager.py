from PySide6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QProgressBar, QMessageBox
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QHostAddress, QHostInfo, QTcpServer, QTcpSocket, QUdpSocket
from PySide6.QtCore import QUrl

class TCPManager(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.server = QTcpServer(controller)
        self.connections = []

        self.server.listen(QHostAddress.SpecialAddress.Any, 5000)

        self.server.newConnection.connect(self.handle_connection)


    def handle_connection(self):
        socket = self.server.nextPendingConnection()

        if socket is None:
            return

        self.connections.append(socket)

        # "tell me when the other computer has sent me data"
        socket.readyRead.connect(
            lambda socket=socket: self.read_data(socket)
        )

        socket.disconnected.connect(
            lambda socket=socket: self.remove_connection(socket)
        )

    def read_data(self, socket):
        # Read all available bytes
        data = socket.readAll()
        print(f"Received: {bytes(data)}")

    def send_data(self, socket):
        # Send string as bytes
        socket.write(b"b for convert to bytes")


    def remove_connection(self, socket):
        print(
            "Disconnected:",
            socket.peerAddress().toString()
        )

        if socket in self.connections:
            self.connections.remove(socket)

        socket.deleteLater()
        