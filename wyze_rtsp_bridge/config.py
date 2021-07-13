import typing
from typing import List, Optional

import json
import os
import pathlib
import textwrap

import pydantic
import yaml


class WyzeRtspBridgeConfig(pydantic.BaseModel):
    host: pydantic.IPvAnyInterface = pydantic.Field(
        default="127.0.0.1",
        description="The IP address or hostname to start the rtsp server from",
    )

    port: pydantic.PositiveInt = pydantic.Field(
        default=8554, description="The port number to start the rtsp server on"
    )


class WyzeCredentialConfig(pydantic.BaseModel):
    email: typing.Union[
        pydantic.EmailStr, typing.Literal["<REQUIRED>"]
    ] = pydantic.Field(
        description="Email address to log into your wyze account"
    )
    password: str = pydantic.Field(description="Password of your wyze account")


class Config(pydantic.BaseModel):
    wyze_credentials: WyzeCredentialConfig
    rtsp_server: WyzeRtspBridgeConfig = WyzeRtspBridgeConfig()
    db_path: pydantic.FilePath = pathlib.Path(
        "~/.wyzecam/wyze_rtsp_bridge.db"
    ).expanduser()
    cameras: Optional[List[str]] = pydantic.Field(
        description="Use 'cameras' to specify a list of camera MAC addresses to expose.  Use this option to "
        "filter the cameras exposed by the bridge (a good idea for low-resource "
        "systems like Raspberry Pis, if you have a lot of cameras).",
        example=["2CABCDEF1234", "..."],
    )


_project_root = pathlib.Path(__file__).parent.parent
_config_root = pathlib.Path("~/.wyzecam/").expanduser()
_config_filename = "wyze_rtsp_bridge_config.yml"


def load_config(file: Optional[pathlib.Path] = None) -> Optional[Config]:
    if not file or not file.exists():
        if (_project_root / _config_filename).exists():
            file = _project_root / _config_filename
        elif (_config_root / _config_filename).exists():
            file = _config_root / _config_filename
        else:
            return None
    config = Config.parse_obj(yaml.load(open(file), Loader=yaml.SafeLoader))
    return config


def make_default_config(
    obj: typing.Type[pydantic.BaseModel] = Config, indent: int = 0
) -> str:
    result = []
    istr = " " * indent
    for name, field in obj.__fields__.items():
        description = field.field_info.description
        kind = field.type_
        # noinspection PyUnresolvedReferences
        if type(kind) == typing._UnionGenericAlias:  # type: ignore
            # noinspection PyUnresolvedReferences
            kind = kind.__args__[0]
        if issubclass(kind, pydantic.BaseModel):
            if description is not None:
                result.append(textwrap.indent(f"# {description}", istr))
            if field.required and not field.default:
                result.append(textwrap.indent(f"{name}:", istr))
            else:
                result.append(textwrap.indent(f"# {name}:", istr))
            result.append(make_default_config(kind, indent=indent + 2))
            result.append("")
        else:
            example_val = field.field_info.extra.get("example")
            if field.required and not field.default:
                result.append(textwrap.indent(f"{name}: <REQUIRED>", istr))
            elif field.required and field.default:
                result.append(textwrap.indent(f"{name}: {field.default}", istr))
            elif not field.required and field.default:
                result.append(
                    textwrap.indent(f"# {name}: {field.default}", istr)
                )
            elif not field.required and example_val:
                result.append(
                    textwrap.indent(
                        f"# For example, {name}:" f" {json.dumps(example_val)}",
                        istr,
                    )
                )

            if description is not None and len(textwrap.wrap(description)) == 1:
                result[-1] += f"  # {description}"
            elif description:
                result.insert(-1, "")
                result.insert(
                    -1,
                    textwrap.indent(
                        "\n".join(textwrap.wrap(description)), istr + "# "
                    ),
                )

    result.append("")
    return "\n".join(result)


def create_config():
    os.makedirs(_config_root, exist_ok=True)
    with open(_config_root / _config_filename, "w+") as f:
        f.write(make_default_config())
