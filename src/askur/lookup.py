
from typing import Iterator
from askur.config import Config
from askur.alphabet import Alphabet

Config()  # Initialize the global CONFIG variable
alpha = Alphabet()


class Lookup:
    """Lookup words in the LOUDS trie."""

    def __init__(
        self,
        search_instance,
        query_builder_instance,
    ) -> None:
        self._search = search_instance
        self.mmap = search_instance.mmap
        self._fuzzy_match = query_builder_instance.query.get("fuzzy_match", False)
        self._limit = query_builder_instance.query.get("limit", 0)
        self._case_insensitive = query_builder_instance.query.get(
            "case_insensitive", False
        )
        self._query_type = query_builder_instance.query.get("type", "")
        self._collection_name = search_instance._collection_name
        self._nr_results = 0
        self._query = query_builder_instance.query["query"]
        self._min_word_length = query_builder_instance.query.get("min_length", 0)
        self._max_word_length = query_builder_instance.query.get("max_length", 0)
        if self._fuzzy_match:
            search_instance._fuzzy_find_query = query_builder_instance.query[
                "original_query"
            ]
        self._id = query_builder_instance.query.get("id", 0)


    def _fuzzy_search(self, query: list) -> None:
        """Method to find similar words
        Levenshtein distance of 1 is used to find similar words
        Case folding is applied to find similar words in case insensitive search

        WORD can be transformed into another word by:
        - add a letter
        - remove a letter
        - replace a letter
        """

        for i in range(len(query) + 1):
            # add letter between every letter in the word
            # beginning and end as well
            new_word = query[:]
            new_word.insert(i, alpha.UNDERSCORE)
            yield from self._lookup(new_word, s_index=1)

        # replace the letter at position n with i_letter
        for n in range(len(query)):
            new_word = query[:]
            new_word[n] = alpha.UNDERSCORE
            yield from self._lookup(new_word, s_index=1)

        # remove the letter at position n
        for n in range(len(query)) if len(query) > 1 else []:
            new_word = query[:]
            del new_word[n]
            yield from self._lookup(new_word, s_index=1)

    def _wildcard_search(self) -> Iterator[dict[str, list[str]]]:
        min_length = (
            self._min_word_length - 1
        )  # subtract 1 to save calculation time in wildcard search
        max_length = self._max_word_length
        return self._wildcard_find(
            min_length, max_length, s_index=1, start=0, accumulated=[]
        )

    def _wildcard_find(
        self,
        min_length: int,
        max_length: int,
        s_index: int,
        start: int = 0,
        accumulated: list[int] = None,
    ) -> Iterator[dict[str, list[str]]]:
        """Search for a word in the trie using pure wildcard (*)"""

        next_query = accumulated[:] if accumulated else []

        if start >= max_length and max_length > 0:
            # If the current length exceeds the maximum allowed length, stop the search.
            return

        # Determine if we should check for end-of-word at this position.
        check_if_eow: bool = min_length < 0 or start >= min_length

        s_start, s_end = self.mmap.calculate_select(s_index)

        for idx, i_letter in enumerate(self.mmap.get_trie_range(s_start, s_end)):
            if i_letter in (alpha.UNDERSCORE, alpha.WILDCARD):
                i_letter *= -1

            if check_if_eow and self.mmap.is_end_of_word(s_start + idx):
                res = self._search.add_result(
                    {
                        self._query_to_string(
                            next_query + [i_letter]
                        ): self.mmap.get_result(s_start + idx)
                    }
                )
                if res:
                    yield res
            if self._search.search_completed():
                return

            nr_hc = self.mmap.calculate_hc(s_start + idx)
            if nr_hc > 0:
                yield from self._wildcard_find(
                    min_length,
                    max_length,
                    s_index=nr_hc + 1,
                    start=start + 1,
                    accumulated=next_query + [i_letter],
                )

    def _underscore_search(
        self, s_index, query, start
    ) -> Iterator[dict[str, list[str]]]:
        """
        Search for a word in the trie from a given index.
        This method handles the underscore wildcard "_" which matches any single character.
        Args:
            s_index (int): The index of the current node in the trie.
            query (list[list[int]]): The query being searched for, represented as a list of lists of character codes.
            start (int): The starting position in the query to search from.

        Yields:
            dict[str, list[str]]: A dictionary containing the search results for the current query.
        """
        s_start, s_end = self.mmap.calculate_select(s_index)
        chr_range = self.mmap.get_trie_range(s_start, s_end)
        next_query = query[:]
        word_length = len(query) - 1
        for n, i_letter in enumerate(chr_range):
            if i_letter in (alpha.UNDERSCORE, alpha.WILDCARD):
                i_letter *= -1  # Escape the character

            if start < word_length and self.mmap.calculate_hc(s_start + n) == 0:
                # if this is not the last character in the query
                # and the character has no head count, skip it
                continue
            next_query[start] = i_letter

            yield from self._lookup(next_query, s_index, start)

    def _case_insensitive_search(
        self,
        query,
        s_index: int = 1,
        start: int = 0,
        accumulated_word: list[int] = [],
    ) -> Iterator[dict[str, list[str]] | dict[str, int]]:

        s_start, s_end = self.mmap.calculate_select(s_index)
        chr_range = self.mmap.get_trie_range(s_start, s_end)
        word_len = len(query) - 1
        i_letter = query[start]
        i_letters: list[int] = [i_letter]
        if i_letter == alpha.UNDERSCORE:
            chr_indices = [i for i, _ in enumerate(chr_range)]
        else:
            if alpha.case_folding(i_letter) != i_letter:
                i_letters.append(alpha.case_folding(i_letter))
            chr_indices = [chr_range.index(i) for i in chr_range if i in i_letters]

        for chr_index in chr_indices:
            nr_hc = self.mmap.calculate_hc(s_start + chr_index)
            if start == word_len:
                if self.mmap.is_end_of_word(s_start + chr_index):
                    result = self.mmap.get_result(s_start + chr_index)
                    word = self._query_to_string(
                        accumulated_word[:] + [chr_range[chr_index]]
                    )
                    res = self._search.add_result({word: result})
                    if res:
                        yield res
            if nr_hc == 0:
                continue
            if start >= word_len:
                continue

            yield from self._case_insensitive_search(
                query,
                nr_hc + 1,
                start + 1,
                accumulated_word[:] + [chr_range[chr_index]],
            )

    def _lookup(
        self, query: list[int], s_index: int, start: int = 0
    ) -> Iterator[dict[str, list[str]] | dict[str, int]]:
        if self._search.search_completed():
            return
        chr_index: int = -1
        word_length: int = len(query[start:]) - 1
        for n, i_letter in enumerate(query[start:]):
            if i_letter == alpha.UNDERSCORE:
                yield from self._underscore_search(s_index, query, start + n)
                return

            letter = i_letter if i_letter >= 0 else -i_letter
            s_start, s_end = self.mmap.calculate_select(s_index)
            chr_index = self.mmap.get_trie_index_of(s_start, s_end, letter)
            if chr_index == -1:
                # No such letter in the trie range, so we can return
                return
            nr_hc = self.mmap.calculate_hc(s_start + chr_index)
            if nr_hc == 0 and n < word_length:
                # no solution remaining for this path, return early
                return
            s_index = nr_hc + 1

        if self.mmap.is_end_of_word(s_start + chr_index):
            result = self.mmap.get_result(s_start + chr_index)
            word = self._query_to_string(query)
            res = self._search.add_result({word: result})
            if res:
                yield res

    def _query_to_string(self, query) -> str:
        """Convert a query list of integers (ASCII values) back to text."""
        if query is None:
            return ""
        if len(query) > 1 and query[-1] == alpha.WILDCARD:
            # Remove the wildcard from the end of the query, because it is not part of the word
            query = query[:-1][:]

        # Convert negative (escaped) ASCII values back to their original characters
        query = [val if val >= 0 else -val for val in query]
        return alpha.convert_bytes_to_str(query)

    def _get_by_id(self, id: int) -> dict[str, list[str]] | dict[str, int]:
        """Implement the method to get a word by its ID."""
        return self.mmap.get_by_id(id)

    def lookup(self) -> Iterator[dict[str, list[str]] | dict[str, int]]:
        """Lookup a word in the trie."""

        if self._query_type == "wildcard":
            yield from self._wildcard_search()
            return
        if self._query_type == "id":
            yield self._get_by_id(self._id)
            return
        if self._fuzzy_match:
            yield from self._fuzzy_search(self._query)
            return
        if self._case_insensitive:
            yield from self._case_insensitive_search(
                self._query, s_index=1, start=0, accumulated_word=[]
            )
            return
        yield from self._lookup(self._query, 1)
