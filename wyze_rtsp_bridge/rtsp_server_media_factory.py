import ctypes
import functools
import random
import sys
import time
from typing import Tuple, List, Dict

from wyzecam import WyzeIOTC, WyzeCamera
from wyzecam.tutk import tutk

from glib_init import GstRtspServer, Gst
from wyze_rtsp_bridge.iotc_video_mux import WyzeIOTCVideoMux, WyzeIOTCVideoListener


class WyzeCameraMediaContext(ctypes.Structure):
    _fields_ = [
        ('timestamp', ctypes.c_int64),
        ('media_info_id', ctypes.c_int64),
        ('mac', ctypes.c_char * 12),
        ('need_data', ctypes.c_bool)
    ]


def build_gst_buffer(frame: bytes, frame_info: tutk.FrameInfoStruct,
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


def get_frame_size(frame_info: tutk.FrameInfoStruct) -> Tuple[int, int]:
    if frame_info.frame_size == tutk.FRAME_SIZE_1080P:
        return 1920, 1080
    elif frame_info.frame_size == tutk.FRAME_SIZE_360P:
        return 640, 360
    return 640, 360


def get_frame_rate(frame_info: tutk.FrameInfoStruct) -> int:
    if frame_info.framerate > 0:
        return int(frame_info.framerate)
    return 15


def get_codec(frame_info: tutk.FrameInfoStruct) -> str:
    if frame_info.codec_id == 78:
        return 'h264'
    if frame_info.codec_id == 80:
        return 'h265'
    assert False


class WyzeCameraMediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, iotc: WyzeIOTC, mux: WyzeIOTCVideoMux, cameras: List[WyzeCamera]):
        GstRtspServer.RTSPMediaFactory.__init__(self)
        self.iotc: WyzeIOTC = iotc
        self.mux = mux
        self.cameras: List[WyzeCamera] = cameras
        self.last_frame_infos: Dict[str, tutk.FrameInfoStruct] = {}
        self.factory_id = random.randint(0, sys.maxsize)

    def has_data(self, appsrc, ctx, listener: WyzeIOTCVideoListener):
        if ctx.need_data:
            self.send_data(appsrc, ctx)

    def send_data(self, appsrc, ctx):
        mac = appsrc.mac
        for frame, frame_info in self.mux.read_all(mac, self.factory_id, maxitems=10):
            last_frame_info = self.last_frame_infos.get(mac) or self.mux.get_sample_frame_info(mac)
            assert last_frame_info
            buf = build_gst_buffer(frame, frame_info, last_frame_info, ctx)

            retval = appsrc.emit("push-buffer", buf)
            if retval != Gst.FlowReturn.OK:
                print(f"push returned {retval}, expected {Gst.FlowReturn.OK}")

            self.last_frame_infos[mac] = frame_info

    def enough_data(self, apprc, ctx):
        ctx.need_data = False
        print("enough data")

    def need_data(self, appsrc, unused_length, ctx):
        self.send_data(appsrc, ctx)
        ctx.need_data = True
        print("need data")

    def do_create_element(self, url):
        print(f"Create stream: {url.abspath}")
        mac = url.abspath[1:]

        frame_info = self.mux.get_sample_frame_info(mac)
        assert frame_info
        if frame_info.codec_id == 78:
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
        last_frame_info = self.mux.get_sample_frame_info(appsrc.mac)
        assert last_frame_info

        width, height = get_frame_size(last_frame_info)
        framerate = get_frame_rate(last_frame_info)
        codec = get_codec(last_frame_info)
        caps = f"video/x-{codec}," \
               f"width={width},height={height}," \
               f"framerate={framerate}/1," \
               f"stream-format=byte-stream,alignment=au"
        appsrc.set_property('caps', Gst.caps_from_string(caps))

        ctx = WyzeCameraMediaContext()
        ctx.media_info_id = random.randint(0, sys.maxsize)
        ctx.mac = appsrc.mac.encode("ascii")

        callback = functools.partial(self.has_data, appsrc, ctx)
        self.mux.subscribe(appsrc.mac, self.factory_id, callback)

        appsrc.connect("need-data", self.need_data, ctx)
        appsrc.connect("enough-data", self.enough_data, ctx)
        rtsp_media.connect("new-stream", self.do_new_stream, ctx)
        rtsp_media.connect("new-state", self.do_new_state, ctx)
        rtsp_media.connect("removed-stream", self.do_removed_stream, ctx)

    def do_disconnect(self, *args):
        print(f"disconnect: {args}")

    def do_new_stream(self, *args):
        print(f"new stream: {args}")

    def do_new_state(self, rtsp_media, state, ctx):
        elem = rtsp_media.get_element()
        appsrc = elem.get_by_name_recurse_up("mysrc")

        print(f"new state: {state} for mac {str(ctx.mac)}")
        if state == 4:
            callback = functools.partial(self.has_data, appsrc, ctx)
            self.mux.subscribe(ctx.mac.decode('ascii'), self.factory_id, callback)
        elif state == 1:
            self.mux.unsubscribe(ctx.mac.decode('ascii'), self.factory_id)

    def do_removed_stream(self, *args):
        print(f"removed stream: {args}")
