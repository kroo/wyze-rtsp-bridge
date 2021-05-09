import enum
import queue
import threading
import time
import traceback
import warnings
from queue import Queue
from threading import Thread
from typing import List, Dict, Tuple, Optional, Callable

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
        for camera in self.cameras:
            thread = WyzeIOTCVideoListener(self.iotc.connect_and_auth(self.account, camera), camera)
            self.listeners[camera.mac.lower()] = thread
            thread.add_state_change_listener(self.print_state_change)

    def get_listener(self, mac) -> 'WyzeIOTCVideoListener':
        return self.listeners[mac.lower()]

    def start(self):
        for thread in self.listeners.values():
            thread.start()

    def stop(self, block=True):
        for thread in self.listeners.values():
            thread.disconnect()
            if block:
                thread.join()

    def subscribe(self, mac: str, subscriber_id: int,
                  callback: Optional[Callable[['WyzeIOTCVideoListener'], None]] = None) -> None:
        self.get_listener(mac).subscribe(subscriber_id, callback=callback)

    def unsubscribe(self, mac: str, subscriber_id: int) -> None:
        self.get_listener(mac).unsubscribe(subscriber_id)

    def read_all(self, mac: str, subscriber_id: int, maxitems: Optional[int] = None) -> List[
        Tuple[bytes, FrameInfoStruct]]:
        return self.get_listener(mac).read_all(subscriber_id, maxitems=maxitems)

    def get_sample_frame_info(self, mac: str) -> Optional[FrameInfoStruct]:
        return self.get_listener(mac).example_frame_info

    def get_status(self, mac: str) -> 'WyzeIOTCVideoListenerState':
        return self.get_listener(mac).state

    def is_all_connected(self) -> bool:
        return all(listener.state > WyzeIOTCVideoListenerState.CONNECTING
                   for listener in self.listeners.values())

    def is_any_connected(self) -> bool:
        return any(
            listener.state not in [WyzeIOTCVideoListenerState.DISCONNECTED, WyzeIOTCVideoListenerState.FATAL_ERROR]
            for listener in self.listeners.values())

    def wait_for_all_connected(self, debug=False):
        while not self.is_all_connected():
            if debug:
                for mac, listener in self.listeners.items():
                    print(f"{mac} {listener.state}")

            time.sleep(0.1)

    def print_state_change(self, listener, new_state):
        print(f"{listener.camera.mac} -> {new_state.name}")
        if new_state == WyzeIOTCVideoListenerState.FATAL_ERROR:
            print(f"\tError: {listener.error}")


class WyzeIOTCVideoListenerState(enum.IntEnum):
    DISCONNECTED = 0
    """Not yet connected.  Call WyzeIOTCVideoMux.start() to start listener threads"""

    CONNECTING = 1
    """Not yet connected.  Call WyzeIOTCVideoMux.start() to start listener threads"""

    CONNECTED = 2
    """Connected, but no listeners added"""

    STREAMING_REQUESTED = 3
    """Streaming will start soon"""

    STREAMING = 4
    """Currently streaming to at least 1 active listener"""

    PAUSE_REQUESTED = 5
    """Streaming will pause soon"""

    PAUSED = 6
    """Streaming has paused"""

    DISCONNECT_REQUESTED = 7
    """Will disconnect soon"""

    FATAL_ERROR = 8
    """Unrecoverable error; see listener.error"""


LISTENER_SLEEP_INTERVAL = 0.5


class WyzeIOTCVideoListener(Thread):
    """A separate thread"""

    def __init__(self, session: WyzeIOTCSession, camera: WyzeCamera, max_queue_size: int = 10_000) -> None:
        super(WyzeIOTCVideoListener, self).__init__(daemon=True)
        self.session: WyzeIOTCSession = session
        self.camera: WyzeCamera = camera
        self.subscribers: Dict[int, Queue[Tuple[bytes, FrameInfoStruct]]] = {}
        self._state = WyzeIOTCVideoListenerState.DISCONNECTED
        self.state_lock: threading.RLock = threading.RLock()
        self.max_queue_size: int = max_queue_size
        self.example_frame_info: Optional[FrameInfoStruct] = None
        self.state_change_listeners: List[Callable[['WyzeIOTCVideoListener', WyzeIOTCVideoListenerState], None]] = []
        self.error: Optional[Exception] = None
        self.data_available_listeners: Dict[
            int, Callable[['WyzeIOTCVideoListener'], None]] = {}

    def add_state_change_listener(self,
                                  listener: Callable[
                                      ['WyzeIOTCVideoListener', WyzeIOTCVideoListenerState], None]) -> None:
        self.state_change_listeners.append(listener)

    @property
    def state(self) -> WyzeIOTCVideoListenerState:
        with self.state_lock:
            return self._state

    @state.setter
    def state(self, new_state: WyzeIOTCVideoListenerState) -> None:
        with self.state_lock:
            self._state = new_state
            for listener in self.state_change_listeners:
                listener(self, new_state)

    def transition_state(self,
                         condition: Callable[[WyzeIOTCVideoListenerState], bool],
                         new_state: WyzeIOTCVideoListenerState) -> None:

        with self.state_lock:
            if condition(self._state):
                self._state = new_state
                for listener in self.state_change_listeners:
                    listener(self, new_state)

    def run(self) -> None:
        while True:
            self.connect_and_start_streaming()
            if self.state == WyzeIOTCVideoListenerState.DISCONNECTED:
                break
            time.sleep(5)

    def connect_and_start_streaming(self):
        self.state = WyzeIOTCVideoListenerState.CONNECTING
        try:
            with self.session:
                # read one frame, and safe the frame info data for later use
                _, self.example_frame_info = next(self.session.recv_video_data())

                self.transition_state(
                    lambda old: old == WyzeIOTCVideoListenerState.DISCONNECTED,
                    WyzeIOTCVideoListenerState.CONNECTED)
                self.state = WyzeIOTCVideoListenerState.STREAMING_REQUESTED
                while True:
                    if self.state == WyzeIOTCVideoListenerState.STREAMING_REQUESTED:
                        self._stream_until_paused()
                    elif self.state == WyzeIOTCVideoListenerState.DISCONNECT_REQUESTED:
                        break
                    else:
                        time.sleep(LISTENER_SLEEP_INTERVAL)
        except tutk.TutkError as e:
            traceback.print_exc()
            self.error = e
            self.state = WyzeIOTCVideoListenerState.FATAL_ERROR
        self.transition_state(lambda old: old == WyzeIOTCVideoListenerState.DISCONNECT_REQUESTED,
                              WyzeIOTCVideoListenerState.DISCONNECTED)

    def _stream_until_paused(self):
        assert self.state == WyzeIOTCVideoListenerState.STREAMING_REQUESTED

        self.state = WyzeIOTCVideoListenerState.STREAMING
        for data in self.session.recv_video_data():
            for subscriber_id, subscriber in list(self.subscribers.items()):
                self._try_add_data(data, subscriber_id)
            if self.state == WyzeIOTCVideoListenerState.PAUSE_REQUESTED:
                self.state = WyzeIOTCVideoListenerState.PAUSED
                return
            if self.state == WyzeIOTCVideoListenerState.DISCONNECT_REQUESTED:
                return

    def _try_add_data(self, data, subscriber_id):
        try:
            self.subscribers[subscriber_id].put_nowait(data)
            if subscriber_id in self.data_available_listeners:
                self.data_available_listeners[subscriber_id](self)
        except queue.Full:
            warnings.warn(
                f"Subscriber {subscriber_id} has hit the max queue size; "
                f"either fell behind or stopped listening")
            self.unsubscribe(subscriber_id)

    def subscribe(self, subscriber_id: int,
                  callback: Optional[Callable[['WyzeIOTCVideoListener'], None]] = None) -> None:
        if subscriber_id in self.subscribers:
            warnings.warn(f"Double-subscribed to camera {self.camera.mac} with subscriber_id {subscriber_id}")
            return

        self.subscribers[subscriber_id] = queue.Queue(maxsize=self.max_queue_size)
        if callback:
            self.data_available_listeners[subscriber_id] = callback

    def unsubscribe(self, subscriber_id: int) -> None:
        if subscriber_id not in self.subscribers:
            warnings.warn(f"Double-unsubscribed to camera {self.camera.mac} with subscriber_id {subscriber_id}")
            return

        del self.subscribers[subscriber_id]
        if subscriber_id in self.data_available_listeners:
            del self.data_available_listeners[subscriber_id]

    def read_all(self, subscriber_id: int, maxitems: Optional[int] = None) -> List[Tuple[bytes, tutk.FrameInfoStruct]]:
        items: List[Tuple[bytes, tutk.FrameInfoStruct]] = []
        while True:
            try:
                if maxitems is not None and len(items) >= maxitems:
                    break
                q = self.subscribers[subscriber_id]
                items.append(q.get_nowait())
                q.task_done()
            except queue.Empty:
                break

        return items

    def disconnect(self):
        if self.state in [WyzeIOTCVideoListenerState.DISCONNECTED,
                          WyzeIOTCVideoListenerState.FATAL_ERROR]:
            return
        self.state = WyzeIOTCVideoListenerState.DISCONNECT_REQUESTED
