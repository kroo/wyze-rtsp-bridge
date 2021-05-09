import ctypes
import random
import sys
from typing import Optional, Iterator, Tuple, List, Dict

import wyzecam
from wyzecam import WyzeIOTC, WyzeCamera, WyzeIOTCSession, WyzeAccount
from wyzecam.tutk import tutk

from glib_init import GstRtspServer, Gst


class WyzeCameraMediaContext(ctypes.Structure):
    _fields_ = [
        ('timestamp', ctypes.c_int64),
        ('media_info_id', ctypes.c_int64)
    ]


class WyzeCameraMediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, iotc: WyzeIOTC, account: WyzeAccount, cameras: List[WyzeCamera]):
        GstRtspServer.RTSPMediaFactory.__init__(self)
        self.iotc: WyzeIOTC = iotc
        self.account: WyzeAccount = account
        self.cameras: List[WyzeCamera] = cameras
        self.sessions: Dict[str, WyzeIOTCSession] = {}
        self.videostreams: Dict[str, Iterator[Tuple[Optional[bytes], tutk.FrameInfoStruct]]] = {}
        self.last_frame_infos: Dict[str, tutk.FrameInfoStruct] = {}

    def init_session(self, mac):
        camera = [c for c in self.cameras if c.mac.lower() == mac][0]
        session = wyzecam.WyzeIOTCSession(self.iotc.tutk_platform_lib, self.account, camera,
                                          frame_size=tutk.FRAME_SIZE_1080P)
        print(f"Connecting to wyze camera {camera.nickname}")
        session._connect()
        print("Connected; authenticating")
        session._auth()
        print("Authenticated.  Starting video stream")

        videostream = session.recv_video_data()
        last_frame, last_frame_info = next(videostream)

        self.sessions[mac] = session
        self.videostreams[mac] = videostream
        self.last_frame_infos[mac] = last_frame_info

    def need_data(self, appsrc, unused_length, ctx):
        mac = appsrc.mac
        assert self.videostreams[mac]

        frame, frame_info = next(self.videostreams[mac])
        buf = self.build_gst_buffer(frame, frame_info, self.last_frame_infos[mac], ctx)

        retval = appsrc.emit("push-buffer", buf)
        if retval != Gst.FlowReturn.OK:
            print(f"push returned {retval}, expected {Gst.FlowReturn.OK}")

        self.last_frame_infos[mac] = frame_info

    def build_gst_buffer(self, frame: bytes, frame_info: tutk.FrameInfoStruct,
                         last_frame_info: tutk.FrameInfoStruct,
                         ctx: WyzeCameraMediaContext) -> Gst.Buffer:
        buf = Gst.Buffer.new_wrapped(frame)
        ts_s = Gst.util_uint64_scale_int(frame_info.timestamp, Gst.SECOND, 1)
        ts_ms = Gst.util_uint64_scale_int(frame_info.timestamp_ms, Gst.USECOND, 1)
        l_ts_s = Gst.util_uint64_scale_int(last_frame_info.timestamp, Gst.SECOND, 1)
        l_ts_ms = Gst.util_uint64_scale_int(last_frame_info.timestamp_ms, Gst.USECOND, 1)
        timestamp = ts_s + ts_ms
        last_timestamp = l_ts_s + l_ts_ms
        duration_calced = timestamp - last_timestamp
        timestamp = ctx.timestamp
        ctx.timestamp += duration_calced
        buf.pts = timestamp
        buf.duration = duration_calced
        return buf

    def get_frame_size(self, frame_info: tutk.FrameInfoStruct) -> Tuple[int, int]:
        if frame_info.frame_size == tutk.FRAME_SIZE_1080P:
            return 1920, 1080
        elif frame_info.frame_size == tutk.FRAME_SIZE_360P:
            return 640, 360
        return 640, 360

    def get_frame_rate(self, frame_info: tutk.FrameInfoStruct) -> int:
        if frame_info.framerate > 0:
            return int(frame_info.framerate)
        return 15

    def get_codec(self, frame_info: tutk.FrameInfoStruct) -> str:
        if frame_info.codec_id == 78:
            return 'h264'
        if frame_info.codec_id == 80:
            return 'h265'
        assert False

    def do_create_element(self, url):
        print(f"Create stream: {url.abspath}")
        mac = url.abspath[1:]
        if mac not in self.sessions:
            self.init_session(mac)

        assert mac in self.last_frame_infos
        if self.last_frame_infos[mac].codec_id == 78:
            pipeline_str = f"( appsrc name=mysrc ! rtph264pay name=pay0 pt=96 )"
        else:
            pipeline_str = f"( appsrc name=mysrc ! rtph265pay name=pay0 pt=96 )"
        launch = Gst.parse_launch(pipeline_str)
        appsrc = launch.get_by_name_recurse_up("mysrc")
        appsrc.mac = mac
        return launch

    def do_media_configure(self, rtsp_media):

        elem = rtsp_media.get_element()
        appsrc = elem.get_by_name_recurse_up("mysrc")
        Gst.util_set_object_arg(appsrc, 'format', 'time')
        print("media configure for camera ", appsrc.mac)
        assert appsrc.mac in self.last_frame_infos
        last_frame_info = self.last_frame_infos[appsrc.mac]

        width, height = self.get_frame_size(last_frame_info)
        framerate = self.get_frame_rate(last_frame_info)
        codec = self.get_codec(last_frame_info)
        caps = f"video/x-{codec}," \
               f"width={width},height={height}," \
               f"framerate={framerate}/1," \
               f"stream-format=byte-stream,alignment=au"
        appsrc.set_property('caps', Gst.caps_from_string(caps))

        ctx = WyzeCameraMediaContext()
        ctx.media_info_id = random.randint(0, sys.maxsize)
        appsrc.connect("need-data", self.need_data, ctx)
        rtsp_media.connect("new-stream", self.do_new_stream, ctx)
        rtsp_media.connect("new-state", self.do_new_state, ctx)
        rtsp_media.connect("removed-stream", self.do_removed_stream, ctx)

    def do_disconnect(self, *args):
        print(f"disconnect: {args}")

    def do_new_stream(self, *args):
        print(f"new stream: {args}")

    def do_new_state(self, *args):
        print(f"new state: {args}")

    def do_removed_stream(self, *args):
        print(f"removed stream: {args}")
