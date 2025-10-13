"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
import platform
from pathlib import Path

# Default alphabet (sort order) if not set in environment variable.
_alphabet = "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -"
if not os.getenv("ASKUR_ALPHABET"):
    os.environ["ASKUR_ALPHABET"] = _alphabet

# Use this variable to set arbitrary data folder path.
_askur_data_folder = os.getenv("ASKUR_DATA_FOLDER", "")

if _askur_data_folder:
    if not os.path.exists(_askur_data_folder):
        os.makedirs(_askur_data_folder, exist_ok=True)
    os.environ["ASKUR_DATA_FOLDER"] = _askur_data_folder
elif platform.system() == "Windows":
    base_dir = os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    data_dir = os.path.join(base_dir, "askur", "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    os.environ["ASKUR_DATA_FOLDER"] = data_dir
else:
    home_dir = str(Path.home())
    data_dir = os.path.join(home_dir, ".local", "share", "askur", "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    os.environ["ASKUR_DATA_FOLDER"] = data_dir
