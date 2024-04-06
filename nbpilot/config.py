import json
from pathlib import Path


config = None


def load_config():
    global config
    if config is None:
        path = Path(__file__)
        config_file_path = path.parent.parent / "config/config.json"
        with open(config_file_path, encoding="utf-8") as fi:
            config = json.load(fi)

    return config
