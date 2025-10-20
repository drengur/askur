


def list_collections() -> list[dict]:
    import os
    import datetime as dt
    from . import config
    colls = []
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    for entry in sorted(os.listdir(data_folder) or []):
        # get size of folder
        entry_size = 0
        for file in os.listdir(os.path.join(data_folder, entry)):
            entry_size += os.path.getsize(os.path.join(data_folder, entry, file))
            date_created = os.path.getctime(os.path.join(data_folder, entry))
        size = f"{entry_size/1_000_000:.2f} MB" if entry_size > 1_000_000 else f"{entry_size/1_000:.2f} KB"
        colls.append({'name':entry, 'size':size, 'created':dt.datetime.fromtimestamp(date_created).strftime("%Y-%m-%d %H:%M:%S")})
    return colls
