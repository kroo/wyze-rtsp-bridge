from typing import List, Optional

import signal
import sys
import time
import traceback

import wyzecam
from rich.errors import LiveError
from rich.live import Live
from rich.table import Table
from wyze_rtsp_bridge import config
from wyze_rtsp_bridge.db import db
from wyze_rtsp_bridge.db.db import WyzeRtspDatabase
from wyze_rtsp_bridge.iotc_video_mux import WyzeIOTCVideoMux
from wyze_rtsp_bridge.rtsp_server_media_factory import WyzeCameraMediaFactory
from wyzecam import api, api_models
from wyzecam.iotc import WyzeIOTC
from wyzecam.tutk import tutk
from wyzecam.tutk.tutk import SInfoStruct

from .glib_init import GstRtspServer, loop


class GstServer:
    def __init__(self, conf: config.Config):
        if (
            conf.wyze_credentials.email == "<REQUIRED>"
            or conf.wyze_credentials.password == "<REQUIRED>"
        ):
            raise ValueError(
                "Missing Wyze credentials!  Please specify "
                "these in the config file, or as "
                "WYZE_EMAIL and WYZE_PASSWORD environment variables"
            )

        self.server = GstRtspServer.RTSPServer()
        self.db = WyzeRtspDatabase(conf)
        self.config: config.Config = conf
        self.iotc: Optional[WyzeIOTC] = None
        self.auth_info: Optional[api_models.WyzeCredential] = None
        self.account_info: Optional[api_models.WyzeAccount] = None
        self.cameras: List[api_models.WyzeCamera] = []
        self.mux: Optional[WyzeIOTCVideoMux] = None
        self.is_shutting_down = False

    def startup(self):
        self.init_db()
        self.authenticate_with_wyze()
        self.configure_server()
        self.init_iotc()
        self.connect_to_cameras()
        self.configure_mount_points()

    def shutdown(self, *args):
        if self.iotc is None:
            return

        if self.mux is None:
            return

        if self.is_shutting_down:
            sys.exit(1)

        self.is_shutting_down = True
        self.mux.stop(block=False)
        while self.mux.is_any_connected():
            try:
                with Live(
                    self.camera_statuses(title="Shutting down"),
                    refresh_per_second=4,
                ) as live:
                    while self.mux.is_any_connected():
                        time.sleep(0.25)
                        live.update(self.camera_statuses(title="Shutting down"))
            except LiveError:
                pass

        self.iotc.deinitialize()
        loop.quit()
        sys.exit(0)

    def init_db(self):
        self.db.open()

    def authenticate_with_wyze(self):
        success = True
        self.auth_info = db.get_credentials(self.db)
        # noinspection PyBroadException
        try:
            if self.auth_info:
                self.account_info = wyzecam.api.get_user_info(self.auth_info)
            else:
                success = False
        except Exception:
            success = False

        if not success:
            self.auth_info = api.login(
                self.config.wyze_credentials.email,
                self.config.wyze_credentials.password,
            )
            db.set_credentials(self.db, self.auth_info)

            self.account_info = wyzecam.api.get_user_info(self.auth_info)

        assert self.auth_info is not None
        self.cameras = api.get_camera_list(self.auth_info)

        if self.config.cameras is not None:
            self.cameras = [
                c for c in self.cameras if c.mac in self.config.cameras
            ]

    def configure_server(self):
        self.server.set_address(self.config.rtsp_server.host)
        self.server.set_service(str(self.config.rtsp_server.port))

    def init_iotc(self):
        self.iotc = WyzeIOTC(max_num_av_channels=len(self.cameras))
        self.iotc.initialize()

        signal.signal(signal.SIGINT, self.shutdown)

    def camera_statuses(self, title="Connecting to cameras..."):
        if self.mux is None:
            return

        table = Table()
        table.title = title
        table.add_column("Camera MAC")
        table.add_column("Camera Nickname")
        table.add_column("Camera P2P Type")
        table.add_column("Camera IP")
        table.add_column("Mux Status")
        table.add_column("Session State")
        table.add_column("Error")

        for camera in self.cameras:
            status = self.mux.get_status(camera.mac)
            listener = self.mux.get_listener(camera.mac)
            session = listener.session
            try:
                session_info: Optional[SInfoStruct] = session.session_check()
            except (tutk.TutkError, AssertionError):
                session_info = None
            table.add_row(
                f"{camera.mac}",
                f"{camera.nickname}",
                f"{camera.p2p_type} : {session_info.mode if session_info else 'n/a'}",
                f"{session_info.remote_ip.decode('ascii')}"
                if session_info
                else f"[{camera.ip}]",
                f"{status.name}",
                f"{session.state.name}",
                f"{listener.error}",
            )
        return table

    def connect_to_cameras(self):
        if not self.iotc:
            return
        if not self.account_info:
            return

        self.mux = WyzeIOTCVideoMux(self.iotc, self.account_info, self.cameras)
        self.mux.start()
        with Live(self.camera_statuses(), refresh_per_second=4) as live:
            while not self.mux.is_all_connected():
                time.sleep(0.1)
                if self.is_shutting_down:
                    break
                live.update(self.camera_statuses())

    def configure_mount_points(self):
        if not self.iotc:
            return
        if not self.mux:
            return
        m = self.server.get_mount_points()
        f = WyzeCameraMediaFactory(self.iotc, self.mux, self.cameras)
        f.set_shared(True)
        for camera in self.cameras:
            path = f"/{camera.mac.lower()}"
            m.add_factory(path, f)
            print(
                f"{camera.nickname}: rtsp://{self.config.rtsp_server.host}:{self.config.rtsp_server.port}{path}"
            )

    def attach_to_main_loop(self):
        self.server.attach(None)
        print(f"Listening on port: {self.server.get_bound_port()}")


if __name__ == "__main__":
    conf = config.load_config()

    if conf:
        s = GstServer(conf)
        print("running server")
        s.startup()
        s.attach_to_main_loop()
        loop.run()
    else:
        print("missing config.yml")
