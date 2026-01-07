#!/usr/bin/env python3
import os
import argparse


A_DEVELOPMENT = os.getenv("ASKUR_DEVELOPEMENT", "0") == "1"

if A_DEVELOPMENT:
    import config
    import alphabet
    from filemapping_py import Mapping

    A = alphabet.Alphabet()
else:
    from . import config
    from . import alphabet as alphabet

    A = alphabet.Alphabet()

    try:
        from .filemapping import Mapping
    except ImportError:
        from .filemapping_py import Mapping


arg_parser = argparse.ArgumentParser(
    description="Search for a key in a collection of key-value pairs stored in a LOUDS trie."
)
arg_parser.add_argument("-c", type=str, help="The collection to search in.")
arg_parser.add_argument(
    "-w",
    type=str,
    help="The word to search for. Use * for wildcard, _ for any char.",
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

class Search:
    """Search for words in the LOUDS trie."""
    def __init__(
        self,
        collection,
        limit=0,
        case_insensitive=False,
        use_levenshtein=False,
    ) -> None:
        self.mmap = Mapping(collection)
        self._levenshtein = use_levenshtein
        self._limit = limit  # 0 means no limit
        self._reversed_char = 143  # ASCII code for start of reversed word
        self._case_insensitive = case_insensitive
        self._collection_name = collection
        self._nr_results = 0

    @property
    def check_if_key_exists(self):
        return self.mmap.check_if_key_exists

    @check_if_key_exists.setter
    def check_if_key_exists(self, value: bool):
        self.mmap.set_check_key_exists(value)

    def _add_result(self, value) -> None:
        if self._limit > 0 and self._nr_results >= self._limit:
            return None
        self._nr_results += 1
        if self.reversed:
            # If the search is reversed, we need to reverse the result
            # and remove the first character (143)
            value = {k[::-1][:-1]: v for k, v in value.items()}
        if self.check_if_key_exists:
            # If we are only checking for existance of keys.
            # The result is a single integer value (ID)
            value = {k: v[0] for k, v in value.items() if v is not None}
        return value

    def search_completed(self) -> bool:
        """Check if the search is completed."""
        return self._limit > 0 and self._nr_results >= self._limit or False

    def case_folding(self, char: int) -> int:
        """Convert character to lower case if it's upper case and vice versa."""
        if (char >= 65 and char <= 90) or (char >= 192 and char <= 222):
            return char + 32
        if (char >= 97 and char <= 122) or (char >= 224 and char <= 254):
            return char - 32
        return char

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def limit(self) -> int:
        return self._limit

    @limit.setter
    def limit(self, value: int):
        self._limit = value

    @property
    def levenshtein(self) -> bool:
        return self._levenshtein

    @levenshtein.setter
    def levenshtein(self, use_levenshtein: bool):
        """Set whether to use Levenshtein distance for the search."""
        self._levenshtein = use_levenshtein

    @property
    def reversed(self) -> bool:
        """return  whether to search in reversed order."""
        return self._reversed and self.mmap.is_reversed()

    @reversed.setter
    def reversed(self, reversed: bool):
        """Set whether to search in reversed order."""
        self._reversed = reversed and self.mmap.is_reversed()

    @property
    def case_insensitive(self) -> bool:
        return self._case_insensitive

    @case_insensitive.setter
    def case_insensitive(self, value: bool):
        self._case_insensitive = value

    def levenshtein_find(self, query):
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
            if ord(c)
            not in (
                42,
                95,
                self._reversed_char,
            )
        ]

        for i_letter in alphabet:
            # add letter between every letter in the word
            # beginning and end as well
            for n in range(len(query[0]) + 1):
                new_word = query[0][:]
                new_word.insert(n, i_letter)
                yield from self._search([new_word, None, None], s_index=1)

        # replace the letter at position n with i_letter
        for n in range(len(query[0])):
            for i_letter in alphabet:
                new_word = query[0][:]
                new_word[n] = i_letter
                yield from self._search([new_word, None, None], s_index=1)

    def _wildcard_search(self, s_index, query, original_start_part=None) -> None:
        """Search for a word in the trie with wildcards (*) in the query."""
        if self.search_completed():
            return
        start_part = query[0]
        middle_parts = query[1]
        end_part = query[2]
        s_start, s_end = self.mmap.calculate_select(s_index)
        next_start_part = (
            start_part[:-1][:]
            if start_part and start_part[-1] == 42
            else start_part[:]
            if start_part
            else []
        )
        for idx, i_letter in enumerate(self.mmap.get_trie_range(s_start, s_end)):
            if i_letter == self._reversed_char:
                continue
            if i_letter == 95 or i_letter == 42:  # "_" or "*"
                i_letter *= -1

            next_start_part.append(i_letter)
            next_end_part = None if not end_part else next_start_part[-len(end_part) :]
            # pattern_to_match = [end_part] þegar verið er að athuga hvort að orðið endi á vissan hátt.
            end_part_match = self._matches_pattern_sequence(next_end_part, [end_part])

            # það sem er að gerast er að byrjunarhlutinn er að stækka án þess að tekið sé í burtu
            # sjálf byrjunin, sem á ekki að matcha við
            if not original_start_part:
                original_start_part = next_start_part[:-1][:]

            pattern_to_match = (
                next_start_part[len(original_start_part) :]
                if original_start_part
                else next_start_part
            )
            word_parts_match = end_part_match and self._matches_pattern_sequence(
                pattern_to_match, middle_parts
            )

            # Check if we can match any of the patterns in word_parts sequentially
            if word_parts_match and self.mmap.is_end_of_word(s_start + idx):
                result = self.mmap.get_result(s_start + idx)
                word = self._query_to_string(next_start_part)
                if len(query) > 3:
                    word = self._query_to_string(query[3]) + word

                res = self._add_result({word: result})
                if res is not None:
                    yield res
                else:
                    return

            # If we have a match, continue searching
            # bitsum is nr_children (nr_hc)
            bitsum = self.mmap.calculate_hc(s_start + idx)
            if bitsum > 0:
                yield from self._wildcard_search(
                    bitsum + 1,
                    [
                        next_start_part,
                        middle_parts,
                        end_part,
                        query[3] if len(query) > 3 else None,
                    ],
                    original_start_part,
                )
            next_start_part.pop()

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
                    if self.case_insensitive:
                        # Case insensitive comparison
                        if (
                            pattern[j] != 95
                            and pattern[j] != word_part[i + j]
                            and pattern[j] != self.case_folding(word_part[i + j])
                        ):
                            match = False
                            break
                    else:
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
            next_query[0] = [i_letter] + query[0][start + 1 :][:]
            yield from self._search(next_query, s_index)

    def _case_insensitive_search(self, query, s_index, start=0) -> None:
        """
        Search for a word in the trie from a given index.
        This method handles case insensitive search by checking both upper and lower case letters.
        """
        if start >= len(query[0]):
            return

        if len(query) == 3:
            query.append([])
        chr_range = []
        next_query = [[], query[1], query[2], query[3]]
        s_start, s_end = self.mmap.calculate_select(s_index)
        range = self.mmap.get_trie_range(s_start, s_end)
        i_letter = query[0][start]
        i_fold_letter = self.case_folding(i_letter)
        if range.find(i_letter) >= 0:
            chr_range.append(i_letter)
        if i_letter != i_fold_letter and range.find(i_fold_letter) >= 0:
            chr_range.append(i_fold_letter)
        if chr_range == [] and i_letter == 95:  #  "_"
            chr_range = range

        for nr, ic_letter in enumerate(chr_range):
            chr_index = range.find(ic_letter)
            nr_hc = self.mmap.calculate_hc(s_start + chr_index)

            if start == len(query[0]) - 1 and self.mmap.is_end_of_word(
                s_start + chr_index
            ):
                result = self.mmap.get_result(s_start + chr_index)
                word = self._query_to_string(query[0][:][0:start]) + chr(ic_letter)
                if len(query) > 3:
                    word = self._query_to_string(query[3]) + word

                result = self._add_result({word: result})
                if result is not None:
                    yield result
                else:
                    return

                if nr < len(chr_range) - 1:
                    continue
                else:
                    break

            if self.search_completed():
                return
            s_index_next = nr_hc + 1

            next_query[0] = query[0][:]
            next_query[0][start] = ic_letter

            next_query2 = [None, query[1], query[2]]
            next_query2[0] = query[0][:][start:]
            next_query2[0][0] = ic_letter
            if len(query) > 3:
                next_query2.append(query[3] + query[0][:][0:start])
            else:
                next_query2.append(query[0][:][0:start])

            if next_query2[0][-1] == 42 and len(next_query2[0]) == 2:
                yield from self._search(next_query2, s_index)
            if nr_hc > 0:
                yield from self._case_insensitive_search(
                    next_query, s_index_next, start + 1
                )

    def _search(self, query, s_index) -> None:
        chr_index = -1
        if self.search_completed():
            return
        for n, i_letter in enumerate(query[0]):
            if i_letter == 42:  # "*"
                yield from self._wildcard_search(s_index, query)
                return
            if i_letter == 95:  # "_"
                yield from self._underscore_search(s_index, query, n)
                return
            if i_letter < 0:  # Negative ASCII value means escaped character
                i_letter *= -1

            s_start, s_end = self.mmap.calculate_select(s_index)
            chr_index = self.mmap.get_trie_index_of(s_start, s_end, i_letter)
            # No such letter in the trie interval, so we can return
            if chr_index == -1:
                return

            if n < len(query[0]) - 1:
                nr_hc = self.mmap.calculate_hc(s_start + chr_index)
                if nr_hc == 0:
                    if n == len(query[0]) - 2 and query[0][-1] == 42:
                        if query[1] is None and query[2] is None:
                            break
                    # We can return here without result, because we have nothing more to search for
                    return

                # if we are at the end of the query and the last letter is a wildcard
                # and we have perhaps a complete word at this point, even if there are no more letters
                # in the query, we can still get a possible result
                if (
                    n == len(query[0]) - 2
                    and query[0][-1] == 42
                    and not query[1]
                    and not query[2]
                ):
                    end_of_word = self.mmap.is_end_of_word(s_start + chr_index)
                    if end_of_word == 1:
                        result = self.mmap.get_result(s_start + chr_index)
                        word = self._query_to_string(query[0])
                        if (
                            len(query) > 3
                        ):  # If there is a prefix in the query from underscore search
                            word = self._query_to_string(query[3]) + word

                        res = self._add_result({word: result})
                        if res is not None:
                            yield res
                        else:
                            return

                s_index = nr_hc + 1
        end_of_word = self.mmap.is_end_of_word(s_start + chr_index)

        if end_of_word == 1:
            result = self.mmap.get_result(s_start + chr_index)
            word = self._query_to_string(query[0])
            if (
                len(query) > 3
            ):  # If there is a prefix in the query from underscore search
                word = self._query_to_string(query[3]) + word

            res = self._add_result({word: result})
            if res is not None:
                yield res
            else:
                return

    def _query_to_string(self, query) -> str:
        """Convert a query list of ASCII values back to a string."""
        if query is None:
            return ""
        if len(query) > 1 and query[-1] == 42:
            query = query[:-1][:]
        for i, val in enumerate(query):
            if val < 0:
                query[i] *= -1
        return A.convert_bytes_to_str(query)

    def fuzzy_search(self, query, result_format="dict"):
        """Fuzzy search for a word in the trie.
        This method uses Levenshtein distance to find similar words.
        """
        self.levenshtein = True
        return self.search(query)

    def exists(self, query) -> list[str]:
        """
        For faster search results.
        Check if a word exists in the collection.
        This method does not return the value associated with the word,
        it only checks if the word exists.
        returns list of words.
        """
        self.check_if_key_exists = True
        return self.search(query)

        # self.check_if_key_exists = False

        # return self.results

    def get_by_id(self, id) -> str:
        # Implement the method to get a word by its ID
        res = self.mmap.get_by_id(id)
        return res

    def search(self, query) -> str:
        modified_query = self._prepare_query(query)
        # self.clear_results()
        self.reversed = modified_query[0] is not None and modified_query[0][0] == 143

        if self.levenshtein:
            """Using Levenshtein distance to find similar words."""
            if (
                modified_query is None
                or modified_query[0] is None
                or modified_query[1] is not None
                or modified_query[2] is not None
            ):
                print("Invalid query for fuzzy search.")
                return

            yield from self.levenshtein_find(modified_query)
            self.levenshtein = False
        elif self.case_insensitive and modified_query[0] is not None:
            """Using case insensitive search."""
            yield from self._case_insensitive_search(modified_query, 1)
            self.case_insensitive = False
        elif modified_query[0] is None:
            """Using wildcards in start of query:"""
            yield from self._wildcard_search(1, modified_query)
        else:
            """Using no wildcards in start of query:"""
            yield from self._search(modified_query, 1)
            if self.check_if_key_exists:
                self.check_if_key_exists = False

    def _prepare_query(self, query):
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
                multi_bytes = A.convert_str_to_bytes(c)
                for b in multi_bytes:
                    res.append(int(b))
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


def main():
    """Main entry point for the askur-search CLI command."""
    args = arg_parser.parse_args()
    COLLECTION = args.c
    QUERY = args.w
    LIMIT = args.l if args.l > 0 else 0
    FUZZY_SEARCH = args.z
    CASE_INSENSITIVE = args.insensitive

    assert COLLECTION is not None, "Collection 'c' is required."
    assert QUERY is not None, "query/word 'w' is required."

    S = Search(
        collection=COLLECTION,
        limit=LIMIT,
        case_insensitive=CASE_INSENSITIVE,
        use_levenshtein=FUZZY_SEARCH,
    )
    return S.search(QUERY)


if __name__ == "__main__":
    for item in main():
        print(item)
