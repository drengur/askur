import argparse
import os
import sys
from typing import Any
import hashlib
from askur.config import Config

Config()  # Initialize the global CONFIG variable


def collections(sort_by: str = "name", descending: bool = False) -> list[dict]:
    import datetime as dt
    from askur.search import Search as S

    sort_columns = {
        "name": "name",
        "date": "date",
        "size": "entry_size",
        "count": "entry_count",
    }
    sort_by = sort_columns.get(sort_by.lower(), "name")
    rows: list[dict[str, Any]] = []
    data_folder = os.environ["ASKUR_DATA_FOLDER"]
    total_size: int = 0
    has_suffix: bool = False
    
    if not os.path.exists(data_folder):
        return []
    
    for entry in sorted(os.listdir(data_folder) or []):
        # get size of folder
        search_instance = S(collection=entry)
        count = search_instance.count_collection_items
        has_suffix = search_instance.has_suffix_index
        search_instance.close()  # Close the search instance to free resources

        entry_size = 0
        for file in os.listdir(os.path.join(data_folder, entry)):
            entry_size += os.path.getsize(os.path.join(data_folder, entry, file))
            date_created = os.path.getctime(os.path.join(data_folder, entry))
            md5sum = hashlib.md5()
            with open(os.path.join(data_folder, entry, file), "rb") as f:
                while chunk := f.read(1024):
                    md5sum.update(chunk)
            md5sum = md5sum.hexdigest()
        total_size += entry_size
        size = (
            f"{entry_size / 1_000_000:.2f} MB"
            if entry_size > 1_000_000
            else f"{entry_size / 1_000:.2f} KB"
        )
        rows.append(
            {
                "name": entry,
                "size": size,
                "count": f"{count:_}",
                "created": dt.datetime.fromtimestamp(date_created).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "entry_size": entry_size,
                "date": date_created,
                "entry_count": count,
                "suffix": "R" if has_suffix else "_",
                "md5sum": md5sum,
            }
        )
    if not rows:
        return []

    rows = sorted(rows, key=lambda x: x[sort_by], reverse=descending)
    for col in ["entry_size", "entry_count"]:
        for row in rows:
            row.pop(col, None)

    return {
        "collections": rows,
        "total_size": total_size,
        "data_folder": data_folder,
    }


def list_collections(sort_by: str = "name", descending: bool = False) -> None:
    """Lists all collections in the data folder with their size and creation date. 
    Sorts by name, date, number of items or size depending on the sort_by argument.
    arguments:
        sort_by: str, either 'name', 'date', 'size' or 'count'. Default is 'name'.
        descending: bool, whether to sort in descending order. Default is False.
    """
    import sys

    sort_by = sort_by.lower()
    if sort_by not in ["name", "date", "size", "count"]:
        sort_by = "name"

    if sys.argv and len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="List Askur collections")
        parser.add_argument(
            "-s",
            "--sort_by",
            type=str,
            choices=["name", "date", "size", "count"],
            default="name",
            help="Sort collections by 'name', 'date', 'size' or 'count' (default: 'name')",
        )
        parser.add_argument(
            "-d",
            "--descending",
            action="store_true",
            help="Sort collections in descending order (default: ascending)",
            default=False,
        )
        args = parser.parse_args()
        sort_by = args.sort_by
        sort_descending = args.descending
    else:
        sort_descending = False

    collection_infos = collections(sort_by=sort_by, descending=sort_descending)
    if not collection_infos:
        print("No collections found.\nCheck your ASKUR_DATA_FOLDER environment variable.")
        return
    
    data_folder = collection_infos.get("data_folder")
    total_size = collection_infos.get("total_size")
    rows = collection_infos.get("collections")

    if not rows:
        print(f"No collections found in the data folder '{data_folder}'.")
        return
    
    col_0_width = len(str(len(rows))) + 2
    col_1_width = max(len(coll["name"]) for coll in rows) + 6
    col_2_width = max(len(coll["size"]) for coll in rows) + 6
    col_3_width = max(len(coll["count"]) for coll in rows) + 2
    col_4_width = max(len(coll["suffix"]) for coll in rows) + 2
    col_5_width = max(len(coll["created"]) for coll in rows) + 2
    col_6_width = max(len(coll["md5sum"]) for coll in rows) + 2
    

    print(f"\nCollections in {data_folder}:")
    print(
        f"{'n':>{col_0_width}} {'Name':<{col_1_width}} {'Size':>{col_2_width}} {'Items':>{col_3_width}}   {'S':<{col_4_width}} {'Created':<{col_5_width}} {'MD5':<{col_6_width}}"
    )
    print("-" * (col_0_width + col_1_width + col_2_width + col_3_width + col_4_width + col_5_width + col_6_width + 4))
    for n, coll in enumerate(rows):
        print(
            f"{n+1:>{col_0_width}} {coll['name']:<{col_1_width}} {coll['size']:>{col_2_width}} {coll['count']:>{col_3_width}}   {coll['suffix']:<{col_4_width}} {coll['created']:<{col_5_width}} {coll['md5sum']:<{col_6_width}}"
        )
        
    print("-" * (col_0_width + col_1_width + col_2_width + col_3_width + col_4_width + col_5_width + col_6_width + 4))
    print(
        f"{'Total':<{col_0_width + col_1_width}}  {(total_size / 1_000_000):>{col_2_width - 3}.2f} MB\n"
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
        print(
            f"Input file '{input_file}' not found. Use absolute path or check the file name and try again."
        )
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
        parser = argparse.ArgumentParser(
            description="Lookup in an Askur collection by ID"
        )
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
    Config().list_variables()
