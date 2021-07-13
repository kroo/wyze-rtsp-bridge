import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import GLib, GObject, Gst, GstApp, GstRtspServer

loop = GLib.MainLoop()
Gst.init(None)

__all__ = ["GLib", "GObject", "Gst", "GstApp", "GstRtspServer", "loop"]
