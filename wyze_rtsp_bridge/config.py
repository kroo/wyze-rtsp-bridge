import pathlib
from typing import Optional, List

import pydantic
import yaml


class WyzeRtspBridgeConfig(pydantic.BaseModel):
    host: str = '0.0.0.0'
    port: int = 8554


class WyzeCredentialConfig(pydantic.BaseModel):
    email: str
    password: str


class Config(pydantic.BaseModel):
    wyze_credentials: WyzeCredentialConfig
    rtsp_server: WyzeRtspBridgeConfig = WyzeRtspBridgeConfig()
    db_path: str = str(pathlib.Path("~/.wyzecam/wyze_rtsp_bridge.db").expanduser())
    cameras: Optional[List[str]] = None


_project_root = pathlib.Path(__file__).parent.parent


def load_config(file: pathlib.Path = _project_root / 'config.yml') -> Config:
    return Config.parse_obj(yaml.load(open(file), Loader=yaml.SafeLoader))
