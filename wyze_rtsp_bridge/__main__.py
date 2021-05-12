# type: ignore[attr-defined]

from enum import Enum

import typer
from rich.console import Console

from wyze_rtsp_bridge import __version__, rtsp_server, config
from wyze_rtsp_bridge.glib_init import loop
from wyze_rtsp_bridge.rtsp_server import GstServer


class Color(str, Enum):
    white = "white"
    red = "red"
    cyan = "cyan"
    magenta = "magenta"
    yellow = "yellow"
    green = "green"


app = typer.Typer(
    name="wyze-rtsp-bridge",
    help="A server that transcodes wyze native video streams to rtsp",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    """Prints the version of the package."""
    if value:
        console.print(
            f"[yellow]wyze-rtsp-bridge[/] version: [bold blue]{__version__}[/]"
        )
        raise typer.Exit()


@app.command(name="")
def main(

    version: bool = typer.Option(
        None,
        "-v", "--version",
        callback=version_callback,
        is_eager=True,
        help="Prints the version of the wyze-rtsp-bridge package.",
    ),

    cameras: str = None,

    port: int = 8554
):
    """Prints a greeting for a giving name."""

    conf = config.load_config()
    if cameras is not None:
        conf.cameras = cameras.split(",")
    if port is not None:
        conf.rtsp_server.port = port
    s = GstServer(conf)
    s.startup()
    s.attach_to_main_loop()
    loop.run()


if __name__ == "__main__":
    typer.run(main)
