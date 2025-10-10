"""
Using environment var tables for configuration settings.for data folder path.

"""

import os
# Use this variable to set arbitrary data folder path.
_askur_data_folder = ""

if not os.getenv("ASKUR_DATA_FOLDER", _askur_data_folder):
    if os.name in ["posix", "mac"]:
        home_dir = os.path.expanduser("~")
        home_dir = os.path.abspath(home_dir)
        if not os.path.exists(
            os.path.join(home_dir, ".local", "share", "askur", "data")
        ):
            os.makedirs(os.path.join(home_dir, ".local", "share", "askur", "data"))
        os.environ["ASKUR_DATA_FOLDER"] = os.path.join(
            home_dir, ".local", "share", "askur", "data"
        )
    elif os.name == "nt" and os.getenv("APPDATA"):
        appdata_dir = os.getenv("APPDATA")
        if not os.path.exists(os.path.join(appdata_dir, "askur", "data")):
            os.makedirs(os.path.join(appdata_dir, "askur", "data"))
        os.environ["ASKUR_DATA_FOLDER"] = os.path.join(appdata_dir, "askur", "data")
    else:
        if not os.path.exists(os.path.dirname(__file__) + "/data"):
            os.makedirs(os.path.dirname(__file__) + "/data")
        os.environ["ASKUR_DATA_FOLDER"] = os.path.dirname(__file__) + "/data"
