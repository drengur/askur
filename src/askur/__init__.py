import argparse
import os
import sys
from askur.config import Config

Config()  # initialize config environment variables


def collections(sort_by: str = "name") -> list[dict]:
    import datetime as dt

    colls = []
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    if not os.path.exists(data_folder):
        return []
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
    if sort_by == "date":
        return sorted(colls, key=lambda x: x["created"], reverse=True)
    elif sort_by == "size":
        return sorted(colls, key=lambda x: x["size"], reverse=True)

    return sorted(colls, key=lambda x: x["name"])


def list_collections(sort_by: str = "name") -> None:
    """Lists all collections in the data folder with their size and creation date. Sorts by name, date or size depending on the sort_by argument.
    arguments:
        sort_by: str, either 'name', 'date' or 'size'. Default is 'name'.
    """
    import sys

    if sort_by not in ["name", "date", "size"]:
        print(f"Invalid sort_by value '{sort_by}'. Defaulting to 'name'.")
        sort_by = "name"

    if sys.argv and len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="List Askur collections")
        parser.add_argument(
            "-s",
            "--sort_by",
            type=str,
            choices=["name", "date", "size"],
            default="name",
            help="Sort collections by 'name', 'date' or 'size'",
        )
        args = parser.parse_args()
        sort_by = args.sort_by

    colls = collections(sort_by=sort_by)
    if not colls:
        print(f"Data folder '{os.environ['ASKUR_DATA_FOLDER']}' does not exist. Please check your configuration and try again.")
        return

    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    col_1_width = max(len(coll["name"]) for coll in colls) + 6
    col_2_width = max(len(coll["size"]) for coll in colls) + 6
    col_3_width = max(len(coll["created"]) for coll in colls) + 2

    print(f"\nCollections in {data_folder}:")
    print(
        f"{'Collection':<{col_1_width}} {'Size':>{col_2_width}}   {'Created':<{col_3_width}}"
    )
    print("-" * (col_1_width + col_2_width + col_3_width))
    total_size = 0
    for coll in colls:
        size_str = coll["size"]
        if "MB" in size_str:
            total_size += float(size_str.replace(" MB", "")) * 1_000_000
        elif "KB" in size_str:
            total_size += float(size_str.replace(" KB", "")) * 1_000
        print(
            f"{coll['name']:<{col_1_width}} {coll['size']:>{col_2_width}}   {coll['created']:<{col_3_width}}"
        )
    print("-" * (col_1_width + col_2_width + col_3_width))
    print(
        f"{'Total':<{col_1_width}} {(total_size / 1_000_000):>{col_2_width - 3}.2f} MB\n"
    )


def build_collection(
    collection_name: str, input_file: str, reversed=False, field_separator=";"
) -> int:
    import gc

    trie = None
    try:
        file = open(input_file, "r", encoding="utf-8")
        import askur.build

        trie = askur.build.Trie(
            collection_name=collection_name,
            reversed=False,
            field_separator=field_separator,
        )
        trie.make_frozen_data(input_data=file)

        if reversed:
            trie = askur.build.Trie(
                collection_name=collection_name,
                reversed=True,
                field_separator=field_separator,
            )
            trie.make_reversed()
    except FileNotFoundError:
        print(f"Input file '{input_file}' not found. Use absolute path or check the file name and try again.")
        return -1
    finally:
        if "file" in dir():
            file.close()
        del trie
        gc.collect()
    return 0

def get_id(
    collection_name: str = None,
    id: int = None,
) -> list[str]:

    if collection_name is None or id is None:
        parser = argparse.ArgumentParser(description="Lookup in an Askur collection by ID")
        parser.add_argument(
            "-c", "--collection_name", type=str, help="Name of the collection"
        )
        parser.add_argument("--id", type=int, help="ID to lookup")
        args = parser.parse_args()

        collection_name = args.collection_name
        id = args.id
    if collection_name is None or id is None:
        print("Please provide both collection name and ID.")
        return ""

    import askur.search as search_module

    S = search_module.Search(collection=collection_name)
    result = S.get_by_id(id)
    return result

def remove_collection(collection_name: str = None) -> None:
    if collection_name is None:
        if len(sys.argv) < 2:
            print("Please provide a collection name to remove.")
            return
        collection_name = sys.argv[1]
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    file_name = os.path.join(data_folder, collection_name, "data.bin")
    if os.path.exists(file_name):
        file_size = os.path.getsize(file_name)
        os.remove(file_name)
        os.rmdir(os.path.join(data_folder, collection_name))
        print(
            f"Deleted collection '{collection_name}', size: {file_size / 1_000_000:.2f} MB"
        )
    else:
        print(f"Collection '{collection_name}' does not exist. Nothing removed.")


def rename_collection(old_name: str = None, new_name: str = None) -> None:
    if old_name is None or new_name is None:
        parser = argparse.ArgumentParser(description="Rename an Askur collection")
        parser.add_argument(
            "-o", "--old_name", type=str, help="Current name of the collection"
        )
        parser.add_argument(
            "-n", "--new_name", type=str, help="New name of the collection"
        )
        args = parser.parse_args()
        old_name = args.old_name
        new_name = args.new_name

    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    old_path = os.path.join(data_folder, old_name)
    new_path = os.path.join(data_folder, new_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        print(f"Renamed collection '{old_name}' to '{new_name}'")
    else:
        print(f"Collection '{old_name}' does not exist or '{new_name}' already exists")


def list_configuration() -> None:
    config = Config()
    col1_width = max(len(key) for key in config.__dict__.keys()) + 2
    col2_width = max(len(str(value)) for value in config.__dict__.values()) + 2
    print("Current configuration:")
    for key, value in config.__dict__.items():
        print(f"{key:<{col1_width}}: {str(value):<{col2_width}}")
