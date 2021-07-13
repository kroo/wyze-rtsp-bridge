import yaml
from wyze_rtsp_bridge import config


def test_make_default_config():
    result = config.make_default_config()

    print()
    print("--- Start ---")
    print(result)
    print("--- End ---")
    print()

    assert len(result) > 0
    yaml_parsed = yaml.load(result, Loader=yaml.SafeLoader)
    assert yaml_parsed is not None
    pydantic_parsed = config.Config.parse_obj(yaml_parsed)
    assert pydantic_parsed is not None
