from PySide6.QtWidgets import QWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QProgressBar, QMessageBox
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QHostAddress, QHostInfo, QTcpServer, QTcpSocket, QUdpSocket
from PySide6.QtCore import QUrl
from pathlib import Path
from typing import Optional
import json, uuid

INSTALL_LOCATION = Path(__file__).resolve().parent.parent.parent

class TCPManager(QWidget):
    def __init__(self, parent, controller):
        super().__init__()
        self.controller = controller
        self.parents = parent

        # Connection
        self.server = None
        self.connections = []
        self.buffers = {}
        self.img_transfers = {}

        # Download
        self.download_folder = Path(INSTALL_LOCATION)
        self.download_folder.mkdir(parents=True, exist_ok=True)

    def show_page(self, prj):
        self.download_folder = Path( prj / "downloads")
        self.download_folder.mkdir(parents=True, exist_ok=True)

    def start_server(self):
        # Download
        self.download_folder = Path(self.parents.current_project) / "image_downloads"
        self.download_folder.mkdir(parents=True, exist_ok=True)


        if self.server is not None:
            self.stop_server()
            return

        self.server = QTcpServer(self)
        self.server.newConnection.connect(
            self.handle_connection
        )

        if not self.server.listen(QHostAddress.SpecialAddress.Any, 5000):
            print("Failed to start server:", self.server.errorString())
            self.server.deleteLater()
            self.server = None
            return

        self.parents.tcp_connect_button.setText("Stop Server")
        print("TCP server listening on port 5000")

    def stop_server(self):
        if self.server is None:
            return

        self.server.close()

        for socket in self.connections:
            self.remove_connection(socket)

        self.connections.clear()
        self.buffers.clear()
        self.img_transfers.clear()

        self.server.deleteLater()
        self.server = None

        self.parents.tcp_connect_button.setText("Send/Receive Data")
        print("TCP server stopped")

    def handle_connection(self):
        if self.server is None:
            return

        socket = self.server.nextPendingConnection()

        if socket is None:
            return

        self.connections.append(socket)
        self.buffers[socket] = bytearray()

        print(
            "Connected",
            socket.peerAddress().toString(),
            socket.peerPort()
        )

        # "tell me when the other computer has sent me data"
        socket.readyRead.connect(
            lambda socket=socket: self.read_data(socket)
        )

        socket.disconnected.connect(
            lambda socket=socket: self.remove_connection(socket)
        )

    def read_data(self, socket):
        # Read all available bytes
        # data = socket.readAll()
        # print(f"Received: {bytes(data)}")

        self.buffers[socket].extend(bytes(socket.readAll()))
        # Protocol: newline
        while b"\n" in self.buffers[socket]:
            message, self.buffers[socket] = \
                self.buffers[socket].split(b"\n", 1)

            # receive as string
            message = message.decode("utf-8")
            print("Received:", message)

    def send_data(self, socket, message):
        # Send string as bytes
        # readyRead doesn't necessarily mean that the data goes all in one piece, so we need a protocol
        # one way is to buffer incoming data to wait for \n (newlines)
        # socket.write(b"b for convert to bytes\n") # \n signals the end of this chunk
        # socket.write(b"hello client\n")

        # send a python string
        # socket.write(message.encode("utf-8"))

        # JSON messages
        # {"type":"message","data":"hello"}
        # {"type":"image","name":"img1.jpg","size":999999,"id":"8ufna02"}
        # <999999 bytes of JPEG data>
        pass


    def remove_connection(self, socket):
        print(
            "Disconnected:",
            socket.peerAddress().toString()
        )

        if socket in self.connections:
            self.connections.remove(socket)

        socket.deleteLater()