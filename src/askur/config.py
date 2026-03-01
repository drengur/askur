"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
from pathlib import Path

os.environ.setdefault("ASKUR_ALPHABET", "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -")

if os.name == "nt":
    base_dir = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    data_dir = os.path.join(base_dir, "askur", "data")
    os.environ.setdefault("ASKUR_DATA_FOLDER", data_dir)
else:
    data_dir = os.path.join(str(Path.home()), ".local", "share", "askur", "data")
    os.environ.setdefault("ASKUR_DATA_FOLDER", data_dir)

