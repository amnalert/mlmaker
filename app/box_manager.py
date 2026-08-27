from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import QObject, Signal
from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig, GetAuthorizeUrlOptions, FileWithInMemoryCacheTokenStorage

import threading, secrets, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

class UploadFromBox(QPushButton):
    def __init__(self, parents, controller):
        super().__init__("Upload Files from Box")
        self.parents = parents
        self.controller = controller

        self.clicked.connect(self.start_box)

    def start_box(self):
        # not ready yet
        print("In progress, try again in a later commit")
        return

        self.box_manager = BoxManager(
            client_id="",
            client_secret="",
            token_file=Path(self.controller.user_folder) / "box_token.json",
            parent=self
        )
        self.box_manager.authenticate()

    def box_authentication_finished(self, success, message):
        if success:
            print(message)

        else:
            QMessageBox.warning(
                self,
                "Box Authentication",
                message
            )

        

class BoxManager(QObject):
    authentication_finished = Signal(bool, str)

    def __init__(self, client_id: str, client_secret: str, token_file: str | Path, parent=None):
        super().__init__(parent)

        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = Path(token_file)

        self.redirect_host = "127.0.0.1"
        self.redirect_port = 53682
        self.redirect_uri = (f"http://{self.redirect_host}:{self.redirect_port}")

        self.auth: BoxOAuth
        self.client: BoxClient | None = None

        self._server = None
        self._server_thread = None
        self._state = None

        self._create_auth()

    def _create_auth(self):
        """
        Create the box OAuth object.

        FileWithInMemoryCacheTokenStorage keeps the token in memory and persists it so the user does not need to login every time.
        """

        token_storage = FileWithInMemoryCacheTokenStorage(filename=str(self.token_file))

        config = OAuthConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_storage=token_storage
        )

        self.auth = BoxOAuth(config)

    def authenticate(self):
        if not self.client_id:
            self.authentication_finished.emit(
                False,
                "Box Client ID has not been configured."
            )
            return

        if not self.client_secret:
            self.authentication_finished.emit(
                False,
                "Box Client Secret has not been configured."
            )
            return

        # try usable token if available first
        try:
            self.client = BoxClient(auth=self.auth)

            # API request
            self.client.users.get_user_me()

            self.authentication_finished.emit(
                True,
                "Already authenticated with Box."
            )
            return

        except Exception:
            self.client = None

        self._start_oauth_server()
        self._state = secrets.token_urlsafe(32)

        options = GetAuthorizeUrlOptions(redirect_uri=self.redirect_uri, state=self._state)
        auth_url = self.auth.get_authorize_url(options=options)

        webbrowser.open(auth_url)

    def _start_oauth_server(self):
        manager = self

        class OAuthHandler(BaseHTTPRequestHandler):

            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)

                code = query.get("code", [None])[0]
                state = query.get("state", [None])[0]
                error = query.get("error", [None])[0]

                if error:
                    manager._send_response(
                        self,
                        f"Box authentication failed: {error}"
                    )

                    manager._authentication_failed(
                        f"Box authentication failed: {error}"
                    )
                    return

                if not code:
                    manager._send_response(
                        self,
                        "No authorization code was returned by Box."
                    )

                    manager._authentication_failed(
                        "No authorization code was returned by Box."
                    )
                    return

                if state != manager._state:
                    manager._send_response(
                        self,
                        "Invalid OAuth state."
                    )

                    manager._authentication_failed(
                        "Invalid OAuth state."
                    )
                    return

                manager._send_response(
                    self,
                    "Box authentication successful. "
                    "You may close this browser window."
                )

                manager._authentication_code_received(code)

            def log_message(self, format, *args):
                # Prevent HTTP server logging to the console.
                pass

        try:
            self._server = HTTPServer(
                (
                    self.redirect_host,
                    self.redirect_port,
                ),
                OAuthHandler,
            )

        except OSError as e:
            self.authentication_finished.emit(
                False,
                f"Could not start Box OAuth callback server: {e}"
            )
            return

        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )

        self._server_thread.start()

    def _authentication_code_received(self, code):
        """
        Exchange the authorization code for Box access/refresh tokens.
        """

        try:
            self.auth.get_tokens_authorization_code_grant(code)

            self.client = BoxClient(auth=self.auth)

            # Verify authentication.
            me = self.client.users.get_user_me()

            self._stop_oauth_server()

            self.authentication_finished.emit(
                True,
                f"Authenticated as {me.name}"
            )

        except Exception as e:
            self._stop_oauth_server()

            self.authentication_finished.emit(
                False,
                f"Box authentication failed: {e}"
            )

    def _authentication_failed(self, message):
        self._stop_oauth_server()

        self.authentication_finished.emit(
            False,
            message
        )

    def _send_response(self, handler, message):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Box Authentication</title>
        </head>
        <body>
            <h2>{message}</h2>
        </body>
        </html>
        """

        data = html.encode("utf-8")

        handler.send_response(200)
        handler.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )
        handler.send_header(
            "Content-Length",
            str(len(data))
        )
        handler.end_headers()

        handler.wfile.write(data)

    def _stop_oauth_server(self):
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass

            self._server = None

        self._server_thread = None

    def is_authenticated(self):
        return self.client is not None