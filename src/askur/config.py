"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
import platform
from pathlib import Path

# Use this variable to set arbitrary data folder path.
# User absolute path only.
_askur_data_folder = ""

if _askur_data_folder:
    if not os.path.exists(_askur_data_folder):
        os.makedirs(_askur_data_folder, exist_ok=True)
    os.environ["ASKUR_DATA_FOLDER"] = _askur_data_folder
elif platform.system() == "Windows":
    base_dir = os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    if not os.path.exists(os.path.join(base_dir, "askur", "data")):
        os.makedirs(os.path.join(base_dir, "askur", "data"))
    os.environ["ASKUR_DATA_FOLDER"] = os.path.join(base_dir, "askur", "data")
else:
    home_dir = str(Path.home())
    if not os.path.exists(os.path.join(home_dir, ".local", "share", "askur", "data")):
        os.makedirs(os.path.join(home_dir, ".local", "share", "askur", "data"))
    os.environ["ASKUR_DATA_FOLDER"] = os.path.join(
        Path.home(), ".local", "share", "askur", "data"
    )
