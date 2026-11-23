#!/usr/bin/env python3

import sys
import json

from typing import Iterator
from askur.filemapping import Mapping
from askur.config import Config
from askur.alphabet import Alphabet

# from askur.scan import Scanner
from askur.query_builder import QueryBuilder as qb
# from askur.lookup import Lookup


Config()  # Initialize the global CONFIG variable
A = Alphabet()

UNDERSCORE = 95
WILDCARD = 42


class Search:
    """Search for words in the LOUDS trie."""

    def __init__(
        self,
        collection: str,
        limit: int = 0,
        case_insensitive: bool = False,
        use_levenshtein: bool = False,
        exists: bool = False,
        sort_ascending: bool = False,
        sort_descending: bool = False,
        id: int = -1,
        output_json: bool = False,
        output_list: bool = False,
    ) -> None:
        assert isinstance(collection, str) and collection, (
            "Collection name must be a non-empty string."
        )
        assert isinstance(limit, int) and limit >= 0, (
            "Limit must be a non-negative integer."
        )
        assert isinstance(case_insensitive, bool), "case_insensitive must be a boolean."
        assert isinstance(use_levenshtein, bool), "use_levenshtein must be a boolean."
        assert collection, "Collection name must be provided."
        assert (output_json and output_list) is False, (
            "Cannot set both output_json and output_list to True."
        )

        self.mmap = Mapping(collection)
        self._levenshtein = use_levenshtein
        self._limit = limit  # 0 means no limit
        self._case_insensitive = case_insensitive
        self._collection_name = collection
        self._nr_results = 0
        self._reversed = False
        self._levenshtein_query = None
        self._exists = self._set_check_if_key_exists(exists)  # check if key exists mode

        self._sort_ascending = sort_ascending
        self._sort_descending = sort_descending
        self._id = id
        self._output_json = output_json
        self._output_list = output_list

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        """Exit the runtime context related to this object."""
        self.close()

    def _set_check_if_key_exists(self, value: bool):
        self.mmap.check_if_key_exists = value
        return self.mmap.check_if_key_exists

    def add_result(self, value) -> dict[str, list[str] | int] | None:
        self._nr_results += 1

        key: str
        if self._levenshtein:
            key = list(value.keys())[0]
            if key == self._levenshtein_query:
                self._nr_results -= 1  # Don't count the original query word as a result
                return None  # Skip the original query word in fuzzy search results
        if self._exists:
            val: list[str] | int = (
                0
                if not value.values() or not list(value.values())[0]
                else list(value.values())[0][0]
            )
        else:
            val: list[str] = list(value.values())[0]
        key = list(value.keys())[0]
        return {key: val}

    def format_output(self, value) -> str:
        """Format the output based on the current output settings."""
        if not value:
            return ""
        key = list(value.keys())[0]
        val = value[key]

        if self._output_list:
            return self.results_as_list(key, val)
        if self._output_json:
            return self.result_as_json(key, val)
        return f"{key}: {val}"

    def results_as_list(self, key: str, value: dict[str, list[str] | int]):
        """Convert the search result to a list format."""

        if isinstance(value, list):
            value_str = ", ".join(value)
        if isinstance(value, dict):
            value_str = ", ".join(f"{k}: {v}" for k, v in value.items())

        return f"{key}: {value_str}"

    def result_as_json(self, key: str, value: dict[str, list[str] | int]) -> str:
        """Convert the search result to a JSON string."""
        return json.dumps({key: value}, ensure_ascii=False)

    def search_completed(self) -> bool:
        """Check if the search is completed."""
        if self._sort_ascending or self._sort_descending:
            return False

        return self._limit > 0 and self._nr_results >= self._limit

    @property
    def count_collection_items(self) -> int:
        """Return the number of items in the collection."""
        return self.mmap.count_items()

    @property
    def start_letters(self) -> list[int]:
        """Return the first letters of all keys in the collection."""
        return self.mmap.get_start_letters()

    @property
    def alphabet(self) -> dict[int, int]:
        """Return the alphabet used in the collection."""
        return self.mmap.get_alphabet()


    def search(
        self, query_string: str
    ) -> Iterator[dict[str, list[str]] | dict[str, int]]:
        """Search for a word in the trie."""

        qb_instance = qb(
            query_string,
            limit=self._limit,
            case_insensitive=self._case_insensitive,
            use_levenshtein=self._levenshtein,
            key_exists=self._exists,
            id=self._id,
        )
        # print(qb_instance)

        if qb_instance.query_type == "scan":
            from askur.scan import Scanner

            scanner = Scanner(qb_instance, self)
            if self._sort_ascending or self._sort_descending:
                yield from self.sorted_results(scanner.start_scan)
            else:
                yield from [self.format_output(item) for item in scanner.start_scan()]
            return

        from askur.lookup import Lookup

        lookup = Lookup(self, qb_instance)
        if self._sort_ascending or self._sort_descending:
            yield from self.sorted_results(lookup.lookup)
        else:
            yield from [self.format_output(item) for item in lookup.lookup()]

    def sorted_results(self, method) -> Iterator[dict[str, list[str]] | dict[str, int]]:
        """Return the search results sorted by key."""
        results = list(method())

        if not results:
            return iter([])

        # returns a single item if the id is specified
        if self._id > -1:
            return iter([self.format_output(res) for res in results])

        def key_func(item):
            return [self.alphabet.index(c) for c in next(iter(item)).casefold()]

        if self._sort_descending:
            results = sorted(
                results,
                key=key_func,
                reverse=True,
            )
        elif self._sort_ascending:
            results = sorted(
                results,
                key=key_func,
            )

        if self._limit > 0:
            return iter([self.format_output(res) for res in results[: self._limit]])
        return iter([self.format_output(res) for res in results])

    def close(self):
        """Close the memory-mapped file."""
        if self.mmap:
            self.mmap.close()


def main():
    """Main entry point for the askur-search CLI command."""
    import argparse
    import signal

    # Handle SIGPIPE for proper pipe behavior (Unix/Linux)
    # Allows silent exit when piping to commands like 'head'
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    arg_parser = argparse.ArgumentParser(
        description="Search for a key in a collection of key-value pairs stored in a LOUDS trie."
    )
    arg_parser.add_argument(
        "-c", type=str, required=True, help="The collection to search in."
    )
    arg_parser.add_argument(
        "-q",
        type=str,
        help="The word (query) to search for. Use * for wildcard, _ for any char.",
    )
    arg_parser.add_argument("-l", type=int, help="Limit number of results.", default=0)
    arg_parser.add_argument(
        "-z",
        action="store_true",
        help="Use fuzzy-search (levenshtein distance 1) to find similar words.",
    )
    arg_parser.add_argument(
        "-i",
        "--insensitive",
        action="store_true",
        help="Use case insensitive search.",
    )
    arg_parser.add_argument(
        "-e",
        "--exists",
        action="store_true",
        help="Check if the word exists in the collection.",
    )
    arg_parser.add_argument(
        "--id",
        type=int,
        default=-1,
        help="Return the search results by ID.",
    )
    arg_parser.add_argument("--asc", action="store_true", help="Sort ascending")
    arg_parser.add_argument("--desc", action="store_true", help="Sort descending")
    arg_parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format."
    )
    arg_parser.add_argument(
        "--list", action="store_true", help="Output results as a list."
    )

    args = arg_parser.parse_args()

    collection = args.c
    query = args.q
    limit = args.l if args.l > 0 else 0
    fuzzy_search = args.z
    case_insensitive = args.insensitive
    exists = args.exists
    id = args.id if args.id > -1 else -1
    sort_ascending = args.asc
    sort_descending = args.desc

    with Search(
        collection=collection,
        limit=limit,
        case_insensitive=case_insensitive,
        use_levenshtein=fuzzy_search,
        exists=exists,
        sort_ascending=sort_ascending,
        sort_descending=sort_descending,
        id=id,
        output_json=args.json,
        output_list=args.list,
    ) as s:
        try:
            for item in s.search(query):
                print(item)
        except BrokenPipeError:
            # Silently exit when pipe is closed (e.g., by 'head')
            s.close()
            sys.exit(0)


if __name__ == "__main__":
    main()
