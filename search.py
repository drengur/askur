#!/usr/bin/env python3
import sys
import re
import time
import argparse


from filemapping import Mapping

# from filemapping_cy import Mapping
# M = Mapping()
arg_parser = argparse.ArgumentParser(
    description="Search for word in a collection of words."
)
arg_parser.add_argument("-c", type=str, help="The collection to search in.")
arg_parser.add_argument(
    "-w",
    type=str,
    help="""The word(s) to search for. Use * for wildcard, _ for any char.\n
    Space separates list of words. Ex: "word1 word2 word3\n" escape wildcard with "\\".""",
)
arg_parser.add_argument("-l", type=int, help="Limit number of results.", default=0)
arg_parser.add_argument(
    "-r",
    action="store_true",
    help="Use Levenshtein distance to find similar words.",
)


class Search:
    """Search for words in the LOUDS trie."""

    def __init__(self, collection, limit=0) -> None:
        self.mmap = Mapping(collection)
        self.use_levenstein = False
        self.limit = limit  # 0 means no limit
        self._results = []

    def add_result(self, result):
        """Add a result to the search results."""

        if self.limit > 0 and len(self._results) >= self.limit:
            return
        if result not in self._results:
            self._results.append(result)

    def results(self):
        """Return the results of the search."""
        return self._results

    def result_as_list(self):
        """Return the results of the search as a string."""
        res = []
        for items in self.results():
            if isinstance(items, str):
                res.append(items)
            elif isinstance(items, list):
                for item in items:
                    res.append(item)
            elif isinstance(items, dict):
                for key, value in items.items():
                    res.append(f"{key}: {value}")
            else:
                res.append(str(items))
        res.sort() if res else []
        return res

    def clear_results(self):
        """Clear the search results."""
        self._results = []

    def search_completed(self) -> bool:
        """Check if the search is completed."""
        if self.limit > 0 and len(self._results) >= self.limit:
            return True
        return False

    def levhenshtein_find(self, query):
        """Method to find similar words to the query
        Levenshtein distance of 1 is used to find similar words
        """
        if (
            query[0] is None
            or 95 in query[0]  # "_" wildcard
            or 42 in query[0]  # "*" wildcard
        ):
            # If there are wildcards in the query, we cannot use Levenshtein distance
            return
        s_index = 1  # Start from the root of the trie
        i_word = query[0].copy()
        base_len = len(i_word)
        for n in range(base_len):
            for i_letter in [
                ord(c) for c in self.mmap.alphabet if ord(c) not in (42, 95)
            ]:
                if self.search_completed():
                    return
                new_word = i_word.copy()
                new_word[n] = i_letter
                query[0] = new_word
                self._search(query, s_index)

    def _wildcard_search(self, s_index, start_part, word_parts, end_part) -> None:
        """Search for a word in the trie with wildcards (*)."""
        if self.search_completed():
            return

        # Hér er verið að athuga hvort að bókstarnir sem koma á undan stjörnunni (*)
        # séu sjálfstætt orð (is_eow)
        if start_part and start_part[-1] == 42 and not word_parts and not end_part:
            self._search([start_part[:-1], None, None], s_index)

        s_start, s_end = self.mmap.calculate_select(s_index)

        for idx, letter in enumerate(self.mmap.get_trie_range(s_start, s_end)):
            next_start_part = (
                start_part[:-1].copy()
                if start_part and start_part[-1] == 42
                else start_part.copy()
            )
            next_start_part.append(int(letter))

            next_end_part = None if not end_part else next_start_part[-len(end_part) :]
            end_part_match = self._matches_pattern_sequence(next_end_part, [end_part])
            word_parts_match = self._matches_pattern_sequence(
                next_start_part, word_parts
            )
            # Check if we can match any of the patterns in word_parts sequentially
            if (
                end_part_match
                and word_parts_match
                and self.mmap.is_end_of_word(s_start + idx)
            ):
                result = self.mmap.get_result(s_start + idx)
                self.add_result(result)
            # If we have a match, continue searching
            if self.mmap.has_child(s_start + idx):
                nr_hc = self.mmap.calculate_hc(s_start + idx)
                self._wildcard_search(nr_hc + 1, next_start_part, word_parts, end_part)

    def _matches_pattern_sequence(self, word_part, word_parts) -> bool:
        """
        Check if word_part contains ALL patterns from word_parts in sequential order.

        Args:
            word_part: Current accumulated letters as list of integers
            word_parts: List of patterns, e.g. [[s,t],[a,k],[r,a]] for "st*ak*ra"

        Returns:
            bool: True if ALL patterns are found in their relative order

        Example:
            word_part = [s,t,u,v,a,k,w,x,r,a,z]
            word_parts = [[s,t],[a,k],[r,a]]
            Returns True because "st" appears first, then "ak", then "ra"
        """
        if word_parts is None or word_part is None:
            return True

        word_len = len(word_part)
        search_start = 0

        # MUST match ALL patterns in the given order
        for pattern in word_parts:
            pattern_len = len(pattern)
            pattern_found = False

            # Search for this pattern starting from where the last pattern ended
            for i in range(search_start, word_len - pattern_len + 1):
                match = True
                for j in range(pattern_len):
                    # 95 represents wildcard character '_'
                    if pattern[j] != 95 and pattern[j] != word_part[i + j]:
                        match = False
                        break

                if match:
                    # Pattern found! Next pattern must start after this one
                    search_start = i + pattern_len
                    pattern_found = True
                    break

            # If ANY pattern is not found, the whole sequence fails
            if not pattern_found:
                return False

        # Only returns True if ALL patterns were found in order
        return True

    def _underscore_search(self, s_index, query, start) -> None:
        """Search for a word in the trie from a given index."""
        s_start, s_end = self.mmap.calculate_select(s_index)
        chr_range = self.mmap.get_trie_range(s_start, s_end)
        next_query = [[], query[1], query[2]]
        for i_letter in chr_range:
            if i_letter == 95 or i_letter == 42:  # "_" or "*"
                continue
            if self.search_completed():
                return
            next_query[0] = [i_letter] + query[0][start + 1 :].copy()
            self._search(next_query, s_index)

    def _search(self, query, s_index) -> None:
        # print(f"Searching for: {query}, s_index: {s_index}")
        chr_index = -1
        if self.search_completed():
            return
        for n, i_letter in enumerate(query[0]):
            if i_letter == 42:  # "*"
                self._wildcard_search(s_index, query[0], query[1], query[2])
                return
            if i_letter == 95:  # "_"
                self._underscore_search(s_index, query, n)
                return
            s_start, s_end = self.mmap.calculate_select(s_index)
            chr_index = self.mmap.get_trie_index_of(s_start, s_end, i_letter)
            # No such letter in the trie, so we can return
            if chr_index == -1:
                return

            if n < len(query[0]) - 1:
                nr_hc = self.mmap.calculate_hc(s_start + chr_index)
                # No child, so we can return and get the results
                if nr_hc is None:
                    # if we are at the end of the query and the last letter is a wildcard
                    # and we have perhaps a complete word at this point
                    if n == len(query[0]) - 2 and query[0][-1] == 42:
                        self._wildcard_search(s_index, query[0], query[1], query[2])
                    return
                s_index = nr_hc + 1

        end_of_word = self.mmap.is_end_of_word(s_start + chr_index)
        if end_of_word == 1:
            result = self.mmap.get_result(s_start + chr_index)
            word = "".join([chr(c) for c in query[0]])
            self.add_result({word: result})

    def search(self, query) -> str:
        # print("Searching for:", query)
        if self.use_levenstein:
            """Using Levenshtein distance to find similar words."""
            if query is None or query[0] is None:
                print("Invalid query for Levenshtein search.")
                return []
            self.levhenshtein_find(query)
        elif query[0] is None:
            """Using wildcards in start of query:"""
            self._wildcard_search(1, [], query[1], query[2])  # "*"
        else:
            """Using no wildcards in start of query:"""
            self._search(query, 1)
        return self.result_as_list()

    def prepare_query(self, query):
        """Modify the query to be used in the search."""
        if query.count("*") > 1:
            query = re.sub(r"\*+", "*", query)

        res = []
        for c in query:
            if ord(c) > 255:
                res.append(129)  # start of 4(5) byte char
                bits = bin(ord(c))[2:].rjust(32, "0")
                for i in range(0, 32, 8):
                    res.append(int(bits[i : i + 8], 2))
            else:
                res.append(ord(c))

        if 42 in res:  # 42 is the ASCII code for '*'
            sublist = []
            starts_with = None
            middle_part = []
            ends_with = None
            # split at first 42
            index = res.index(42)
            if index > 0:
                starts_with = res[: index + 1]
            # Split at the last occurrence of 42
            last_index = len(res) - 1 - res[::-1].index(42)
            ends_with = res[last_index + 1 :]
            if not ends_with:
                ends_with = None

            parts = res[index + 1 : last_index]
            res = res[index + 1 :]
            for i, item in enumerate(parts):
                if item == 42:
                    middle_part.append(sublist)
                    sublist = []
                else:
                    sublist.append(item)
            if sublist:
                middle_part.append(sublist)
            else:
                middle_part = None

            return [starts_with, middle_part, ends_with]

        if res == []:
            return None
        return [res, None, None]


if __name__ == "__main__":
    args = arg_parser.parse_args()
    COLLECTION = args.c
    QUERY = args.w
    LIMIT = args.l if args.l > 0 else 0
    LEVENSHTEIN_QUERY = args.r
    if COLLECTION is None or QUERY is None:
        print("Usage: python3 search.py -c <collection> -w <word1,word2,word3>")
        sys.exit(1)
    if QUERY.startswith("*") and not QUERY.endswith("*"):
        QUERY = QUERY[::-1]  # remove leading * if present
        COLLECTION = (
            "__" + COLLECTION
        )  # prepend __ to collection name for reversed search

    SEARCH_RESULTS = []
    S = Search(COLLECTION, LIMIT)
    # S.reversed_query = False
    START_TIME = time.time()
    queries = QUERY.split(" ")

    for QUERY in queries:
        modified_query = S.prepare_query(QUERY)
        if modified_query is None:
            print("Query is empty or invalid.")
            sys.exit(1)
        if LEVENSHTEIN_QUERY:
            S.use_levenstein = True
        else:
            S.use_levenstein = False
        SEARCH_RESULTS.append(S.search(modified_query))

    END_TIME = time.time()
    print("\n".join("\n".join(res) for res in SEARCH_RESULTS))
    print(f"Rows: {len(SEARCH_RESULTS[0])}")
    print(f"Tími: {1000 * (END_TIME - START_TIME):f} ms")
    if len(SEARCH_RESULTS[0]) > 1:
        print(
            f"Time: {1000 * (END_TIME - START_TIME) / len(SEARCH_RESULTS[0]):f} ms/query"
        )
    else:
        print(f"Time: {1000 * (END_TIME - START_TIME):f} ms")
    print(f"fjöldi niðurstaða: {len(SEARCH_RESULTS[0])}")
