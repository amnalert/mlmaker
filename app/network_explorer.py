from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pathlib import Path
from typing import Any, Optional

INSTALL_LOCATION = Path(__file__).resolve().parent.parent

class NetworkExplorer(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.user_folder = ""
        self.project: Path = Path()
        self.project_uuid = ""

        self.mlayout = QVBoxLayout(self)

        # Fonts
        self.title = QFont()
        self.title.setPointSize(32)
        self.subtitle = QFont()
        self.subtitle.setPointSize(16)

        self.tcp_manager = None

        # Info
        self.setWindowTitle("Network Explorer")
        self.main_label = QLabel("Network Explorer")
        self.main_label.setFont(self.title)
        self.project_label = QLabel("Project: ")
        self.project_label.setFont(self.subtitle)

        self.mlayout.addWidget(self.main_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter))
        self.mlayout.addWidget(self.project_label, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter))


    def init_tcp_manager(self):
        if self.tcp_manager is None:
            self.tcp_manager = TCPManager(self, self.controller)

        # Interactables
        self.start_server_btn = QPushButton("Start TCP Server")
        self.start_server_btn.clicked.connect(lambda checked=False: self.tcp_manager.start_server(self.project)) # type: ignore
        self.check_server_btn = QPushButton("View TCP Servers")
        self.check_server_btn.clicked.connect(self.tcp_manager.check_servers)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addWidget(self.start_server_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.buttons_layout.addWidget(self.check_server_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.mlayout.addLayout(self.buttons_layout)
    
    def receive_prj_info(self, user: str, prj_folder: str | Path) -> None:
        self.init_tcp_manager()

        self.user_folder = user
        self.project = Path(prj_folder)

        self.project_label.setText(f"Project: {self.project.stem}")


class TCPManager(QWidget):
    def __init__(self, parent: NetworkExplorer, controller: Any):
        super().__init__()
        self.controller = controller
        self.parents = parent

        # Connection
        self.server: Optional[QTcpServer] = None
        self.connections: list[QTcpSocket] = []
        self.buffers: dict[QTcpSocket, bytearray] = {}
        self.img_transfers: dict[str, Any] = {}

        # Info
        self.project = Path(INSTALL_LOCATION)
        self.download_folder = Path(INSTALL_LOCATION)

    def start_server(self, prj):
        if self.server is not None:
            self.stop_server()
            return

        reply = QMessageBox.question(
            self,
            "Start TCP Server",
            "Are you ready to start a TCP server which would allow others to connect and share project information?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self.project = Path(prj)
        self.download_folder = self.project / "tcp_downloads"
        self.download_folder.mkdir(parents=True, exist_ok=True)

        self.server = QTcpServer(self)
        self.server.newConnection.connect(
            self.handle_connection
        )

        if not self.server.listen(QHostAddress.SpecialAddress.Any, 5000):
            print("Failed to start server:", self.server.errorString())
            self.server.deleteLater()
            self.server = None
            return

        self.parents.start_server_btn.setText("Stop Server")
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

        self.parents.start_server_btn.setText("Start TCP Server")
        print("TCP server stopped")

    def handle_connection(self) -> None:
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
            message = message.decode("utf-8", errors="replace")
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


    def remove_connection(self, socket: QTcpSocket) -> None:
        print(
            "Disconnected:",
            socket.peerAddress().toString()
        )

        if socket in self.connections:
            self.connections.remove(socket)

        socket.deleteLater()

    def check_servers(self) -> None:
        return