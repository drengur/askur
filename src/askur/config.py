"""
Using environment var tables for configuration settingsfor data folder path.
To override the default path, set the ASKUR_DATA_FOLDER environment variable
to your desired path before importing this module.
"""

import os
import platform
from pathlib import Path

# Use this variable to set arbitrary data folder path.
_askur_data_folder = ""

if _askur_data_folder:
    os.environ["ASKUR_DATA_FOLDER"] = _askur_data_folder
elif platform.system() == "Windows":
    base_dir = os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    os.environ["ASKUR_DATA_FOLDER"] = os.path.join(base_dir, "askur", "data")
else:
    os.environ["ASKUR_DATA_FOLDER"] = os.path.join(
        Path.home(), ".local", "share", "askur", "data"
    )
