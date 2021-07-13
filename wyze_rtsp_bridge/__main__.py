# type: ignore[attr-defined]
import os
import pathlib
import sys
from enum import Enum

import typer
from rich.console import Console
from wyze_rtsp_bridge import __version__, config
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
        "-v",
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Prints the version of the wyze-rtsp-bridge package.",
    ),
    cameras: str = typer.Option(
        None,
        "-c",
        "--cameras",
        help="A list of camera MAC addresses to expose.  Use this option to filter the cameras exposed by the bridge "
        "(a good idea for low-resource systems like Raspberry Pis, if you have a lot of cameras).",
    ),
    port: int = typer.Option(8554, "-p", "--port"),
    config_file: str = typer.Option(
        "~/.config/wyze_rtsp_bridge/config.yml",
        "-c",
        "--config",
        help="The path to the configuration file for wyze-rtsp-bridge",
    ),
    create_config: bool = typer.Option(
        False,
        "--create-config",
        help="Creates a config file at ~/.wyzecam/config.yml",
    ),
):
    """Starts a server that translates local wyze camera video streams to rtsp."""

    if create_config is True:
        config.create_config()
        console.print("Wrote example config to ~/.wyzecam/config.yml")
        sys.exit(0)

    conf = config.load_config(pathlib.Path(config_file) if config_file else None)

    if conf is None:
        console.print(
            "Config file not found, please run wyze-rtsp-bridge --create-config"
        )
        sys.exit(-1)

    if cameras is not None:
        conf.cameras = cameras.split(",")

    if port is not None:
        conf.rtsp_server.port = port

    if "WYZE_EMAIL" in os.environ:
        conf.wyze_credentials.email = os.environ["WYZE_EMAIL"]
    if "WYZE_PASSWORD" in os.environ:
        conf.wyze_credentials.password = os.environ["WYZE_PASSWORD"]

    s = GstServer(conf)
    s.startup()
    s.attach_to_main_loop()
    loop.run()


if __name__ == "__main__":
    typer.run(main)
