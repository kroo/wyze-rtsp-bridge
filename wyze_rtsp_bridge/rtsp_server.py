import traceback
from typing import Optional, List

import wyzecam
from wyzecam import api, api_models
from wyzecam.iotc import WyzeIOTC

from glib_init import loop, GstRtspServer
from wyze_rtsp_bridge import config
from wyze_rtsp_bridge.db import db
from wyze_rtsp_bridge.db.db import WyzeRtspDatabase
from wyze_rtsp_bridge.rtsp_server_media_factory import WyzeCameraMediaFactory


class GstServer:
    def __init__(self, conf: config.Config):
        self.server = GstRtspServer.RTSPServer()
        self.db = WyzeRtspDatabase(conf)
        self.config: config.Config = conf
        self.iotc: Optional[WyzeIOTC] = None
        self.auth_info: Optional[api_models.WyzeCredential] = None
        self.account_info: Optional[api_models.WyzeAccount] = None
        self.cameras: List[api_models.WyzeCamera] = []

    def startup(self):
        self.init_db()
        self.authenticate_with_wyze()
        self.configure_server()
        self.init_iotc()
        self.configure_mount_points()

    def init_iotc(self):
        self.iotc = WyzeIOTC(max_num_av_channels=len(self.cameras))
        self.iotc.initialize()

    def init_db(self):
        self.db.open()

    def authenticate_with_wyze(self):
        success = True
        self.auth_info = db.get_credentials(self.db)
        try:
            if self.auth_info:
                self.account_info = wyzecam.api.get_user_info(self.auth_info)
            else:
                success = False
        except:
            traceback.print_exc()
            success = False

        if not success:
            self.auth_info = api.login(
                self.config.wyze_credentials.email,
                self.config.wyze_credentials.password)
            db.set_credentials(self.db, self.auth_info)

            self.account_info = wyzecam.api.get_user_info(self.auth_info)

        assert self.auth_info is not None
        self.cameras = api.get_camera_list(self.auth_info)

    def configure_server(self):
        self.server.set_address(self.config.rtsp_server.host)
        self.server.set_service(str(self.config.rtsp_server.port))

    def configure_mount_points(self):
        m = self.server.get_mount_points()
        f = WyzeCameraMediaFactory(self.iotc, self.account_info, self.cameras)
        for camera in self.cameras:
            f.set_shared(True)
            path = f"/{camera.mac.lower()}"
            m.add_factory(path, f)
            print(f"added factory: {path} for camera {camera.nickname}")

    def attach_to_main_loop(self):
        self.server.attach(None)
        print(f"Listening on port: {self.server.get_bound_port()}")


if __name__ == '__main__':
    conf = config.load_config()
    s = GstServer(conf)
    print("running server")
    s.startup()
    s.attach_to_main_loop()
    loop.run()
