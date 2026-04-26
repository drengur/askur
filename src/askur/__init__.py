import os
import sys
from askur.config import Config

Config()  # initialize config environment variables


def list_collections() -> list[dict]:
    import datetime as dt

    colls = []
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    for entry in sorted(os.listdir(data_folder) or []):
        # get size of folder
        entry_size = 0
        for file in os.listdir(os.path.join(data_folder, entry)):
            entry_size += os.path.getsize(os.path.join(data_folder, entry, file))
            date_created = os.path.getctime(os.path.join(data_folder, entry))
        size = (
            f"{entry_size / 1_000_000:.2f} MB"
            if entry_size > 1_000_000
            else f"{entry_size / 1_000:.2f} KB"
        )
        colls.append(
            {
                "name": entry,
                "size": size,
                "created": dt.datetime.fromtimestamp(date_created).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
    return colls


def print_collections():
    colls = list_collections()
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    print(f"Collections in {data_folder}:")
    print(f"{'Collection':<20} {'Size':<10} {'Created':<20}")
    print("-" * 50)
    total_size = 0
    for coll in colls:
        size_str = coll["size"]
        if "MB" in size_str:
            total_size += float(size_str.replace(" MB", "")) * 1_000_000
        elif "KB" in size_str:
            total_size += float(size_str.replace(" KB", "")) * 1_000
        print(f"{coll['name']:<20} {coll['size']:<10} {coll['created']:<20}")
    print("-" * 50)
    print(f"{'Total':<20} {total_size / 1_000_000:.2f} MB")


def build_collection(
    collection_name: str, input_file: str, reversed=False, field_separator=";"
) -> None:
    import askur.build

    print(f"Building collection '{collection_name}' from '{input_file}'...")
    trie = askur.build.Trie(
        collection_name=collection_name,
        reversed=reversed,
        field_separator=field_separator,
    )
    trie.make_frozen_data(input_data=input_file)

    if not reversed:
        print(f"Built collection '{collection_name}' from '{input_file}'")

    print(f"Building reversed collection '{collection_name}' from '{input_file}'...")
    trie = askur.build.Trie(
        collection_name=collection_name,
        reversed=True,
        field_separator=field_separator,
    )
    trie.make_reversed()
    print(f"Built reversed collection '{collection_name}' from '{input_file}'")


def remove_collection(collection_name: str=None) -> None:
    if collection_name is None:
        if len(sys.argv) < 2:
            print("Please provide a collection name to remove.")
            return
        collection_name = sys.argv[1]
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    file_name = os.path.join(data_folder, collection_name,"data.bin")
    if os.path.exists(file_name):
        os.remove(file_name)
        os.rmdir(os.path.join(data_folder, collection_name))
        print(f"Deleted collection '{collection_name}'")
    else:
        print(f"Collection '{collection_name}' does not exist")

def print_configuration() -> None:
    config = Config()
    print("Current configuration:")
    print(f"Data folder: {config.data_folder}")
    print(f"Default alphabet: {config.alphabet}")
