#!/usr/bin/env python3
import sys

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

    def __init__(self, collection, limit=0, use_levenshtein=False) -> None:
        self.mmap = Mapping(collection)
        self.use_levenstein = use_levenshtein
        self.limit = limit  # 0 means no limit
        self._results = []

    def add_result(self, result):
        """Add a result to the search results."""

        if self.limit > 0 and len(self._results) >= self.limit:
            return
        if result not in self._results:
            if self.reversed:
                # If the search is reversed, we need to reverse the result
                result = {k[::-1]: v for k, v in result.items()}
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
        # res.sort() if res else []
        return res

    def clear_results(self):
        """Clear the search results."""
        self._results = []

    def search_completed(self) -> bool:
        """Check if the search is completed."""
        if self.limit > 0 and len(self._results) >= self.limit:
            return True
        return False

    def set_levenshtein(self, use_levenshtein: bool):
        """Set whether to use Levenshtein distance for the search."""
        self.use_levenstein = use_levenshtein

    def set_reversed(self, reversed: bool):
        """Set whether to search in reversed order."""
        self.reversed = reversed and self.mmap.is_reversed()

    def levhenshtein_find(self, query):
        """Method to find similar words
        Levenshtein distance of 1 is used to find similar words
        """
        if (
            query[0] is None
            or 95 in query[0]  # "_" wildcard
            or 42 in query[0]  # "*" wildcard
        ):
            # If there are wildcards in the query, we cannot use Levenshtein distance
            return

        alphabet = [
            ord(c)
            for c in self.mmap.alphabet
            if ord(c) not in (42, 95, 143)  # 143 is reversed start
        ]
        base_word = query[0][:]  # copy list to avoid modifying the original query

        new_query = [None, None, None]
        for i_letter in alphabet:
            # add the letter at the start of the word
            new_query[0] = [i_letter] + base_word[:]
            self._search(new_query, s_index=1)

            # add the letter at the end of the word
            new_query[0] = base_word[:] + [i_letter]
            self._search(new_query, s_index=1)

        for n in range(len(base_word)):
            for i_letter in alphabet:
                # replace the letter at position n with i_letter
                new_word = base_word[:]
                new_word[n] = i_letter
                self._search([new_word, None, None], s_index=1)

    def _wildcard_search(self, s_index, start_part, word_parts, end_part) -> None:
        """Search for a word in the trie with wildcards (*) in the query."""
        if self.search_completed():
            return

        s_start, s_end = self.mmap.calculate_select(s_index)

        for idx, letter in enumerate(self.mmap.get_trie_range(s_start, s_end)):
            if letter == 143:
                continue
            if letter == 95 or letter == 42:  # "_" or "*"
                letter *= -1
            next_start_part = (
                start_part[:-1][:]
                if start_part and start_part[-1] == 42
                else start_part[:]
                if start_part
                else []
            )
            next_start_part.append(int(letter))

            next_end_part = None if not end_part else next_start_part[-len(end_part) :]
            end_part_match = self._matches_pattern_sequence(next_end_part, [end_part])
            word_parts_match = end_part_match and self._matches_pattern_sequence(
                next_start_part, word_parts
            )
            # Check if we can match any of the patterns in word_parts sequentially
            if word_parts_match and self.mmap.is_end_of_word(s_start + idx):
                result = self.mmap.get_result(s_start + idx)
                word = "".join([chr(c if c >= 0 else -1 * c) for c in next_start_part])
                self.add_result({word: result})
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
        """
        Search for a word in the trie from a given index.
        This method handles the underscore wildcard "_" which matches any single character.
        """
        s_start, s_end = self.mmap.calculate_select(s_index)
        chr_range = self.mmap.get_trie_range(s_start, s_end)
        next_query = [[], query[1], query[2]]
        if len(query) > 3:
            next_query.append(query[3] + query[0][0:start])
        else:
            next_query.append(query[0][0:start])

        for i_letter in chr_range:
            if i_letter == 95 or i_letter == 42:  # "_" or "*"
                i_letter *= -1  # Escape the character
                # continue
            if self.search_completed():
                return
            next_query[0] = [i_letter] + query[0][start + 1 :][:]
            self._search(next_query, s_index)

    def _search(self, query, s_index) -> None:
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
            if i_letter < 0:  # Negative ASCII value means escaped character
                i_letter = -1 * i_letter

            s_start, s_end = self.mmap.calculate_select(s_index)
            chr_index = self.mmap.get_trie_index_of(s_start, s_end, i_letter)
            # No such letter in the trie, so we can return
            if chr_index == -1:
                return

            if n < len(query[0]) - 1:
                nr_hc = self.mmap.calculate_hc(s_start + chr_index)
                # No child (nr_ch is None), so we can return or get the results, if any, if a wildcard is at the end
                if nr_hc is None:
                    # if we are (almost) at the end of the query and the last letter is a wildcard
                    # and we have perhaps a complete word at this point
                    if n == len(query[0]) - 2 and query[0][-1] == 42:
                        if query[1] is None and query[2] is None:
                            break
                    # We can return here without result, because we have nothing more to search for
                    return
                # if we are at the end of the query and the last letter is a wildcard
                # and we have perhaps a complete word at this point, even if there are no more letters
                # in the query, we can still get a possible result
                if n == len(query[0]) - 2 and query[0][-1] == 42:
                    end_of_word = self.mmap.is_end_of_word(s_start + chr_index)
                    if end_of_word == 1:
                        result = self.mmap.get_result(s_start + chr_index)
                        word = "".join(
                            [chr(c if c >= 0 else -1 * c) for c in query[0][:-1]]
                        )
                        if (
                            len(query) > 3
                        ):  # If there is a prefix in the query from underscore search
                            word = "".join([chr(c) for c in query[3]]) + word
                        self.add_result({word: result})

                s_index = nr_hc + 1
        end_of_word = self.mmap.is_end_of_word(s_start + chr_index)

        if end_of_word == 1:
            result = self.mmap.get_result(s_start + chr_index)
            word = "".join([chr(c if c >= 0 else -1 * c) for c in query[0]])
            if (
                len(query) > 3
            ):  # If there is a prefix in the query from underscore search
                word = "".join([chr(c) for c in query[3]]) + word
            self.add_result({word: result})

    def exists(self, query):
        """
        For faster search results.
        Check if a word exists in the collection.
        This method does not return the value associated with the word,
        it only checks if the word exists.
        """
        self.mmap.set_check_key_exists(True)
        self.search(query)
        self.mmap.set_check_key_exists(False)
        return self.result_as_list() if self.results() else ["0"]

    def search(self, query) -> str:
        modified_query = self.prepare_query(query)

        if modified_query is None:
            print("Query is empty or invalid.")
            sys.exit(1)
        self.clear_results()
        self.reversed = modified_query[0] is not None and modified_query[0][0] == 143

        if self.use_levenstein:
            """Using Levenshtein distance to find similar words."""
            if modified_query is None or modified_query[0] is None:
                print("Invalid query for Levenshtein search.")
                return []
            self.levhenshtein_find(modified_query)
        elif modified_query[0] is None:
            """Using wildcards in start of query:"""
            self._wildcard_search(1, [], modified_query[1], modified_query[2])
        else:
            """Using no wildcards in start of query:"""
            self._search(modified_query, 1)
        return self.result_as_list()

    def prepare_query(self, query):
        """Modify the query to be used in the search.
        This method handles wildcards, underscores, and character encoding.
        It returns a list with three parts and converts characters to their ASCII values:
        - starts_with: characters before the first wildcard (*)
        - middle_part: characters between the first and last wildcard (*)
        - ends_with: characters after the last wildcard (*)
        If there are no wildcards, it returns a list with the query as the first element and None for the other two.
        """
        res = []
        esc = False  # Escape character for wildcards '\'

        reversed_query = (
            self.mmap.is_reversed()
            and query.startswith("*")
            and not query.endswith("*")
            and len(query) > 1
        )
        if reversed_query:
            query = query[::-1]
            res.append(
                143
            )  # 143 is unused ASCII code, used to indicate start of reversed query

        for c in query:
            if ord(c) > 255:
                res.append(
                    129
                )  # 129 is unused ASCII code, used to indicate start of 4(5) byte char
                bits = bin(ord(c))[2:].rjust(32, "0")
                for i in range(0, 32, 8):
                    res.append(int(bits[i : i + 8], 2))
            else:
                if c == "\\" and not esc:
                    esc = True
                    continue
                if esc:
                    if c in ("*", "_"):
                        res.append(-1 * ord(c))
                    else:
                        res.append(ord(c))
                    esc = False
                    continue

                res.append(ord(c))

        if 42 in res:  # 42 is the ASCII code for '*'
            starts_with = (
                None  # Every character before the first 42 belong to the start
            )
            middle_part = []  # Every character between the first and last 42 belongs to the middle
            ends_with = None  # Every character after the last 42 belongs to the end
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
            sublist = []
            for _, item in enumerate(parts):
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
    # if QUERY.startswith("*") and not QUERY.endswith("*"):
    #     QUERY = QUERY[::-1]  # remove leading * if present
    #     COLLECTION = (
    #         "__" + COLLECTION
    #     )  # prepend __ to collection name for reversed search

    SEARCH_RESULTS = []
    S = Search(COLLECTION, LIMIT, use_levenshtein=LEVENSHTEIN_QUERY)

    START_TIME = time.time()

    for query in QUERY.split(" "):
        SEARCH_RESULTS.append(S.search(query))
        # SEARCH_RESULTS.append(S.exists(query))

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
