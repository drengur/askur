"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    alphabet: str = os.getenv("ASKUR_ALPHABET", None)
    data_folder: str = os.getenv("ASKUR_DATA_FOLDER", None)
    config_env_file: str = None

    def __post_init__(self):
        if self.data_folder and self.alphabet:
            return
        self.data_folder, self.config_env_file = self.get_default_folders()
        self.load_from_env_file()
        self.alphabet = os.getenv("ASKUR_ALPHABET", self.get_default_alphabet())

    def __str__(self):
        return f"alphabet={self.alphabet},\n data_folder={self.data_folder}),\n config_env_file={self.config_env_file})"

    def __repr__(self):
        return self.__str__()

    def get_default_alphabet(self) -> str:
        return "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -"

    def get_default_folders(self) -> list[str]:
        if os.name == "nt":
            base_dir: str = os.getenv(
                "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
            )
            data_dir: str = os.path.join(base_dir, "askur", "data")
            config_env_file: str = os.path.join(base_dir, "askur", "config.env")
            return data_dir, config_env_file
        else:
            data_dir: str = os.path.join(
                str(Path.home()), ".local", "share", "askur", "data"
            )
            config_env_file: str = os.path.join(
                str(Path.home()), ".config", "askur", "config.env"
            )
            return data_dir, config_env_file

    def pre_create_config_file(self, path: str) -> None:
        if os.path.exists(path):
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(f"ASKUR_ALPHABET={self.get_default_alphabet()}\n")
            f.write(f"ASKUR_DATA_FOLDER={self.get_default_folders()[0]}\n")

    def load_from_env_file(self) -> None:
        if self.config_env_file is None:
            return
        line:str = ""
        key_value:list[str] = []
        key:str = ""
        value:str = ""
        
        if not os.path.exists(self.config_env_file):
            self.pre_create_config_file(self.config_env_file)

        with open(self.config_env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key_value = line.split("=", 1)
                if len(key_value) != 2:
                    continue
                key, value = key_value
                os.environ.setdefault(key, value)

        if not os.environ.get("ASKUR_ALPHABET"):
            os.environ["ASKUR_ALPHABET"] = self.get_default_alphabet()
        if not os.environ.get("ASKUR_DATA_FOLDER"):
            os.environ["ASKUR_DATA_FOLDER"] = self.get_default_folders()[0]
