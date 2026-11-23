"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
from pathlib import Path


class Config:
    def __init__(self):
        self.env_variables: dict[str, str] = {}
        self.config_env_file: str = ""
        self.load_from_env_file()

    def list_variables(self):

        print("\nCurrent configuration variables:")
        print(f"Config file: {self.config_env_file}")
        print("-" * 50)
        for key, value in self.env_variables.items():
            if os.environ.get(key) is not None:
                print(f"{key}: {os.environ[key]}")
            else:
                print(f"{key}: {value}")
        print("-" * 50)

    def get_default_folders(self) -> list[str]:
        if os.name == "nt":
            base_dir: str = os.getenv(
                "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
            )
            data_dir: str = os.path.join(base_dir, "askur", "data")
            config_env_file: str = os.path.join(base_dir, "askur", "config.env")
        else:
            data_dir: str = os.path.join(
                str(Path.home()), ".local", "share", "askur", "data"
            )
            config_env_file: str = os.path.join(
                str(Path.home()), ".config", "askur", "config.env"
            )
        return data_dir, config_env_file

    def pre_create_config_file(self, path: str) -> None:
        """Pre-create the config.env file with default values if it does not exist."""
        if os.path.exists(path):
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for key, value in self.defaults().items():
                self.env_variables[key] = os.environ[key] = value
                f.write(f"{key}={value}\n")

    def load_from_env_file(self) -> None:
        """Load environment variables from the config.env file. If the file does not exist, create it with default values."""
        self.config_env_file: str = self.get_default_folders()[1]
        self.pre_create_config_file(self.config_env_file)
        key: str = ""
        value: str = ""

        with open(self.config_env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                [key, value] = line.split("=", 1)
                self.env_variables[key] = os.environ[key] = os.environ.get(
                    key, value or ""
                )

    def defaults(self) -> dict[str, str]:
        """Initialize environment variables."""
        return {
            "ASKUR_ALPHABET": "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -",  # default sort order for the alphabet
            "ASKUR_DATA_FOLDER": self.get_default_folders()[
                0
            ],  # default data folder path based on OS
            "ASKUR_MEMORY_THRESHOLD": "60",  # % system memory used before stopping the build process
        }
