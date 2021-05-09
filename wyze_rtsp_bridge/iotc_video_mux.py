import enum
import queue
import threading
import time
import warnings
from queue import Queue
from threading import Thread
from typing import List, Dict, Tuple

from wyzecam import WyzeIOTC, WyzeCamera, WyzeIOTCSession, WyzeAccount
from wyzecam.tutk import tutk
from wyzecam.tutk.tutk import FrameInfoStruct


class WyzeIOTCVideoMux:
    """
    Handles recieving of video data from mutliple camera sessions,
    and publishing of video data to subscribers.
    """

    def __init__(self, iotc: WyzeIOTC, account: WyzeAccount, cameras: List[WyzeCamera]):
        self.iotc = iotc
        self.account = account
        self.cameras = cameras
        self.listeners: Dict[str, WyzeIOTCVideoListener] = {}

    def start(self):
        for camera in self.cameras:
            self.listeners[camera.mac] = WyzeIOTCVideoListener(
                self.iotc.connect_and_auth(self.account, camera), camera)

    def subscribe(self, mac, subscriber_id):
        self.listeners[mac].subscribe(subscriber_id)

    def unsubscribe(self, mac, subscriber_id):
        self.listeners[mac].subscribe(subscriber_id)

    def read_all(self, mac, subscriber_id):
        self.listeners[mac].read_all(subscriber_id)


class WyzeIOTCVideoListenerState(enum.Enum):
    DISCONNECTED = 0
    """Not yet connected.  Call WyzeIOTCVideoMux.start() to start listener threads"""

    CONNECTED = 1
    """Connected, but no listeners added"""

    STREAMING_REQUESTED = 2
    """Streaming will start soon"""

    STREAMING = 3
    """Currently streaming to at least 1 active listener"""

    PAUSE_REQUESTED = 4
    """Streaming will pause soon"""

    PAUSED = 5
    """Streaming has paused"""


LISTENER_SLEEP_INTERVAL = 0.1


class WyzeIOTCVideoListener(Thread):
    """A separate thread"""

    def __init__(self, session: WyzeIOTCSession, camera: WyzeCamera, max_queue_size=10_000):
        super(WyzeIOTCVideoListener, self).__init__()
        self.session = session
        self.camera = camera
        self.subscribers: Dict[int, Queue[Tuple[bytes, FrameInfoStruct]]] = {}
        self._state = WyzeIOTCVideoListenerState.DISCONNECTED
        self.state_lock: threading.Lock = threading.Lock()
        self.max_queue_size = max_queue_size

    @property
    def state(self):
        with self.state_lock:
            return self._state

    @state.setter
    def state(self, new_state):
        with self.state_lock:
            print(f"Video for camera {self.camera.mac} is now {self._state}")
            self._state = new_state

    def run(self) -> None:
        self.state = WyzeIOTCVideoListenerState.DISCONNECTED
        with self.session:
            try:
                with self.state_lock:
                    if self._state == WyzeIOTCVideoListenerState.DISCONNECTED:
                        self._state = WyzeIOTCVideoListenerState.CONNECTED
                    if len(self.subscribers) > 0:
                        self._state = WyzeIOTCVideoListenerState.STREAMING_REQUESTED
                while True:
                    if self.state == WyzeIOTCVideoListenerState.STREAMING_REQUESTED:
                        self.stream_until_paused()
                    else:
                        time.sleep(LISTENER_SLEEP_INTERVAL)
            finally:
                self.state = WyzeIOTCVideoListenerState.DISCONNECTED

    def stream_until_paused(self):
        assert self.state == WyzeIOTCVideoListenerState.STREAMING_REQUESTED

        self.state = WyzeIOTCVideoListenerState.STREAMING
        for data in self.session.recv_video_data():
            for subscriber_id, subscriber in list(self.subscribers.items()):
                try:
                    subscriber.put_nowait(data)
                except queue.Full:
                    warnings.warn(
                        f"Subscriber {subscriber_id} has hit the max queue size; "
                        f"either fell behind or stopped listening")
                    self.unsubscribe(subscriber_id)
            if self.state == WyzeIOTCVideoListenerState.PAUSE_REQUESTED:
                self.state = WyzeIOTCVideoListenerState.PAUSED
                return

    def subscribe(self, subscriber_id) -> None:
        with self.state_lock:
            if subscriber_id in self.subscribers:
                warnings.warn(f"Double-subscribed to camera {self.camera.mac} with subscriber_id {subscriber_id}")
                return

            self.subscribers[subscriber_id] = queue.Queue(maxsize=self.max_queue_size)
            if len(self.subscribers) > 0 and self._state in [WyzeIOTCVideoListenerState.CONNECTED,
                                                             WyzeIOTCVideoListenerState.PAUSED]:
                self._state = WyzeIOTCVideoListenerState.STREAMING_REQUESTED

    def unsubscribe(self, subscriber_id: int) -> None:
        with self.state_lock:
            if subscriber_id not in self.subscribers:
                warnings.warn(f"Double-unsubscribed to camera {self.camera.mac} with subscriber_id {subscriber_id}")
                return

            del self.subscribers[subscriber_id]
            if len(self.subscribers) == 0 and self._state in [WyzeIOTCVideoListenerState.STREAMING]:
                self._state = WyzeIOTCVideoListenerState.PAUSE_REQUESTED

    def read_all(self, subscriber_id: int) -> List[Tuple[bytes, tutk.FrameInfoStruct]]:
        items = []
        while True:
            try:
                items.append(self.subscribers[subscriber_id].get_nowait())
            except queue.Empty:
                break

        return items
