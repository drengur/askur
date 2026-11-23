from typing import Iterator
import copy
from askur.alphabet import Alphabet

alpha = Alphabet()


class ScanNode:
    """Class to keep track of traversal state within a scan query
    while traversing the trie."""

    item: dict = None

    def __init__(self, query: dict):

        self.query = query
        self.items = []
        self.scan_query_start: int = 0

    def __str__(self):
        return "Not implemented"

    def copy(self) -> "ScanNode":
        """Return a deep copy of the current ScanNode."""
        return copy.deepcopy(self)

    @property
    def start_at_end(self) -> bool:
        """Return whether the start_at_end flag is set.
        Meaning that the query does not end with a wildcard or underscore"""
        return self.query.get("start_at_end", False)

    @property
    def start_at_zero(self) -> bool:
        """Return whether the start_at_zero flag is set.
        Meaning that the query does not start with a wildcard or underscore"""
        return self.query.get("start_at_zero", False)

    def copy_items(self) -> list[dict]:
        """Return a copy of the items list."""
        return copy.deepcopy(self.items) if self.items else []

    def add_item(self, item) -> "ScanNode":
        """Add the item to the items list and update the item attribute."""
        self.items.append(item)
        return self

    def clear_items(self) -> "ScanNode":
        """Remove all items from the items list."""
        self.items = []
        return self

    def update_last_item(self, item) -> "ScanNode":
        """Update the last item in the items list with the given item."""
        if self.items:
            self.items[-1].update(item)
        return self

    def next_hc(self):
        """Return the next hc (head count value) based on the last item in the items list."""
        return self.items[-1].get("hc") + 1 if self.items else None

    @property
    def scan_query(self) -> list[dict]:
        """Return the sub-query items list."""
        return self.query.get("scan_query") if self.query else []

    def suffix(self) -> list[dict]:
        """Return the suffix items list."""
        return self.query.get("suffix") if self.query else []

    def end_letter(self) -> list[int]:
        """Return the end_letter items list."""
        return self.query.get("end_letter") if self.query else []

    def start_letters(self) -> list[dict]:
        """Return the start_letters items list."""
        return self.query.get("start_letters") if self.query else []

    def prefix(self) -> list[dict]:
        """Return the prefix items list."""
        return self.query.get("prefix") if self.query else []

    def prefix_end(self) -> list[dict]:
        """Return the end_prefix items list."""
        return self.query.get("prefix_end") if self.query else []

    @property
    def prefix_end_len(self) -> int:
        """Return the length of the prefix_end items list."""
        return 0 if not self.prefix_end() else len(self.prefix_end())

    @property
    def prefix_len(self) -> int:
        """Return the length of the prefix items list."""
        return 0 if not self.prefix() else len([p for p in self.prefix() for p in p])

    @property
    def suffix_len(self) -> int:
        """Return the length of the suffix items list."""
        return 0 if not self.suffix() else len([s for s in self.suffix() for s in s])

    @property
    def end_letter_len(self) -> int:
        """Return the length of the end_letter items list."""
        return 0 if not self.end_letter() else len(self.end_letter())

    @property
    def start_letters_len(self) -> int:
        """Return the length of the start_letters items list."""
        return 0 if not self.start_letters() else len(self.start_letters())

    @property
    def query_start_letter(self) -> int:
        """Return the start letter of the scan query."""
        return (
            self.query.get("scan_query")[0]
            if self.query and self.query.get("scan_query")
            else None
        )

    @property
    def scan_query_length(self) -> int:
        """Return the length of the scan_query items list."""
        return 0 if not self.scan_query else len(self.scan_query)


class Scanner:
    """
    Scanner class for scanning a trie data structure using a prepared query.

    Attributes:
        mmap: Memory-mapped trie structure.
        search: Search object to store and manage search results.
        query: Prepared query for scanning the trie.
    """

    def __init__(self, qb_instance, search_instance):
        self.mmap = search_instance.mmap
        self.search = search_instance
        self.query = qb_instance.query
        self.case_insensitive = qb_instance.case_insensitive
        self.limit = qb_instance.limit

    def search_completed(self) -> bool:
        """Check if the search is completed."""
        return self.search.search_completed()

    def add_result(self, item: dict):
        """Add a result to the search results using the search class
        Args:
            item (dict): The item representing the word to be added to the search results.
        Returns:
            The result of adding the item to the search results.
        """
        word = "".join([chr(chr_info["key"]) for chr_info in item])
        value = self.mmap.get_result(item[-1]["chr_index"])
        return self.search.add_result({word: value})

    def _find_next_index(self, start_index: int, letter: int) -> int:
        """Find the next index of the given letter in the trie starting from start_index."""
        return self.mmap.scan_trie(start_index, letter)

    def start_scan(self) -> Iterator[dict[str, list[str]]]:
        """Start scanning the trie from the beginning."""

        scan_node = ScanNode(self.query)
        start_letter: int = scan_node.query_start_letter
        start_letters: list[int] = [start_letter]

        if self.case_insensitive:
            start_letters = sorted(
                [start_letter]
                if alpha.case_folding(start_letter) == start_letter
                else [start_letter, alpha.case_folding(start_letter)]
            )

        for letter in start_letters:
            yield from self._scan(scan_node, letter)

    def _scan(
        self, scan_node: ScanNode, start_letter: int
    ) -> Iterator[dict[str, list[str]]]:
        """Scan the trie for the given query pattern to minimize search space.

        This method attempts to locate the starting index of the sub_query in the trie
        and iteratively finds the subsequent characters to narrow down the search space.

        Yields:
            dict[str, list[str]]: A dictionary containing character
            indices and their positions in the trie.
        """
        next_index: int = 0  # Initialize the next index to start scanning from
        rest_of_scan_query = scan_node.scan_query[1:]
        rest_len = len(rest_of_scan_query)

        chr_index: int = -1
        is_done: bool = False
        while not is_done:
            # 0: we find the next index of the start letter in the trie
            if scan_node.start_at_zero:
                # We stop scanning because we only need to scan from the start letter (s_start=0)
                is_done = True
            chr_index = self._find_next_index(next_index, start_letter)
            if chr_index < 0:
                break
            next_index = chr_index + 1
            nr_hc = self.mmap.calculate_hc(chr_index)
            if nr_hc <= 0 < rest_len:
                continue
            sel = self.mmap.calculate_select_from_index(chr_index)
            scan_node.clear_items()
            item = {
                "chr_index": chr_index,
                "s_start": sel["s_start"],
                "s_end": sel["s_end"],
                "key": start_letter,
                "hc": nr_hc,
            }
            scan_node.add_item(item)

            scan_node.scan_query_start = sel["s_start"]

            if rest_of_scan_query:
                # 1: we start by searching for the rest of the sub_query in the trie
                # from the current scan node
                yield from self._search_trie(scan_node, rest_of_scan_query)
            else:
                yield from self._traverse_edges_of_query(scan_node, [item])

    def _traverse_edges_of_query(
        self, scan_node: ScanNode, item: list[dict]
    ) -> Iterator[dict[str, int]]:
        """Traverse the edges (prefixes and suffixes)
        of the query results starting from the given item
        when the actual scanning is done."""

        if scan_node.prefix_end_len > 0:
            query = scan_node.query.get("prefix_end")
            scan_node.query["prefix_end"] = None
            yield from self.traverse_prefix_end(scan_node, item, query)
            return
        yield from self._traverse_forward(scan_node, item)

    def _search_trie(
        self,
        scan_node: ScanNode,
        query: list[int],
    ) -> Iterator[dict[str, int]]:
        """Search the trie for the given pattern starting from start_index."""
        hc = scan_node.next_hc()
        s_start, s_end = self.mmap.calculate_select(hc)

        i_letter = query[0]  # the letter we are currently seeking
        letter_range = self.mmap.get_trie_range(
            s_start, s_end
        )  # all letters available in the trie node range

        if i_letter != alpha.UNDERSCORE and i_letter not in letter_range:
            # No matching letters
            if not self.case_insensitive:
                return
            if alpha.case_folding(i_letter) not in letter_range:
                return

        if (
            self.case_insensitive
            and i_letter not in letter_range
            and i_letter != alpha.UNDERSCORE
        ):
            cf_letter = alpha.case_folding(i_letter)
            if cf_letter not in letter_range:
                return

        if i_letter == alpha.UNDERSCORE:
            # If the current letter is an underscore, we consider all letters in the range
            i_letters = letter_range
        else:
            i_letters = [i_letter] if i_letter in letter_range else []
            if self.case_insensitive:
                cf_letter = alpha.case_folding(
                    i_letter
                )  # case folded version of the letter
                if cf_letter != i_letter and cf_letter in letter_range:
                    i_letters.append(cf_letter)
        first_iter_item = True
        for i, letter in enumerate(i_letters):
            chr_idx = i if i_letter == alpha.UNDERSCORE else letter_range.index(letter)
            nr_hc = self.mmap.calculate_hc(s_start + chr_idx)
            if nr_hc <= 0 and len(query) > 1:
                # this word ends prematurely
                continue
            node = {
                "chr_index": chr_idx + s_start,
                "s_start": s_start,
                "s_end": s_end,
                "key": letter,
                "hc": nr_hc,
            }
            if first_iter_item:
                scan_node.add_item(node)
                first_iter_item = False
            else:
                scan_node.update_last_item(node)

            if len(query) > 1:
                yield from self._search_trie(copy.deepcopy(scan_node), query[1:][:])
            else:
                yield from self._traverse_edges_of_query(
                    scan_node, copy.deepcopy(scan_node.items)
                )

    def _check_suffix_prefix(
        self, scan_node: ScanNode, nodes: list[dict], direction: str
    ):
        """Check if the item (the word represented by the item) matches the given suffix or prefix.

        Args:
            scan_node (ScanNode): The current scan node containing the suffix and end letter information.
            nodes (list[dict]): The nodes representing the word.
            direction (str): The direction of traversal, either "fw" for forward or "bw" for backward.
        Returns:
            bool: True if the item matches the suffix or prefix, False otherwise.
        """
        # i_word represents the word extracted from the item and is the
        # part of the word that will be checked against the suffix or prefix.
        # for forward direction, the suffix and end letter will be checked against the end of i_word.
        # for backward direction, the prefix will be checked against the start of i_word.
        pattern: list[int | list[int]] = None
        i_word: list[int] = []
        if direction == "fw":
            # the resulting i_word will be checked against the suffix and end letter.
            # thus we remove the part of the word prior to the scan_query
            i_word = [chr_info["key"] for chr_info in nodes]
            suffix_word_start = 0
            for c in nodes:
                if c.get("s_start") == scan_node.scan_query_start:
                    break
                suffix_word_start += 1
            i_word = i_word[suffix_word_start + len(scan_node.scan_query) :][:]

            if scan_node.suffix_len + scan_node.end_letter_len > len(i_word):
                # suffix/prefix + end_letter is longer than the word,
                # returning False because it cannot match
                return False

            if scan_node.end_letter():
                # match every character of the end_letter against the end of the i_word
                for i in range(scan_node.end_letter_len, 0, -1):
                    if scan_node.end_letter()[-i] == alpha.UNDERSCORE:
                        continue
                    if self.case_insensitive and scan_node.end_letter()[-i] not in (
                        alpha.case_folding(i_word[-i]),
                        i_word[-i],
                    ):
                        return False
                    if (
                        not self.case_insensitive
                        and i_word[-i] != scan_node.end_letter()[-i]
                    ):
                        return False
                # remove the matched end_letter from the end of i_word before pattern matching
                i_word = i_word[: -scan_node.end_letter_len]
            pattern = scan_node.suffix()

        if direction == "bw":
            if scan_node.start_at_zero:
                # If there is nothing to check before the scan_query, any word is acceptable.
                return True

            if scan_node.scan_query_start == 0 and (
                scan_node.prefix_len > 0
                or scan_node.prefix_end_len > 0
                or scan_node.start_letters_len > 0
            ):
                # we are at the start of the word and there can be no prefix
                return False
            # i_word will be constructed from the start of the item to the start of the scan_query.
            # This loop iterates over the item and constructs i_word until it reaches the start of the scan_query.
            # but because we could have added a prefix_end to the start of the scan_query, we need to account
            # for it when constructing i_word.
            for c in nodes:
                if c.get("s_start") == scan_node.scan_query_start:
                    break
                i_word.append(c.get("key"))

            if scan_node.prefix_end():
                if len(i_word) < scan_node.prefix_end_len:
                    return False
                if (
                    scan_node.prefix_len == 0
                    and scan_node.start_letters_len == 0
                    and scan_node.start_at_zero is True
                    and len(i_word) > scan_node.prefix_end_len
                ):
                    return False
                for c in range(1, scan_node.prefix_end_len + 1):
                    if scan_node.prefix_end()[-c] == alpha.UNDERSCORE:
                        continue
                    if self.case_insensitive and i_word[-c] not in (
                        alpha.case_folding(scan_node.prefix_end()[-c]),
                        scan_node.prefix_end()[-c],
                    ):
                        return False
                    if (
                        not self.case_insensitive
                        and i_word[-c] != scan_node.prefix_end()[-c]
                    ):
                        return False
                # remove the matched prefix_end from the end of i_word
                i_word = i_word[: -scan_node.prefix_end_len]
            if scan_node.start_letters():
                if len(scan_node.start_letters()) > len(i_word):
                    # start_letters is longer than the remaining i_word, cannot match
                    return False

                for i, c in enumerate(scan_node.start_letters()):
                    if c == alpha.UNDERSCORE:
                        continue
                    if not self.case_insensitive and i_word[i] != c:
                        return False
                    if self.case_insensitive and i_word[i] not in (
                        alpha.case_folding(c),
                        c,
                    ):
                        return False
                i_word = i_word[i + 1 :] if i_word else []

            if scan_node.prefix_len > len(i_word):
                return False
            pattern = scan_node.prefix()
        return self._matches_pattern_sequence(i_word, pattern)

    def _traverse_forward(self, scan_node: "ScanNode", item: list[dict], loop_depth=0):
        """Traverse the trie forward starting from the given scans
        and returning all possible completions."""

        if scan_node.start_at_end:
            if self.mmap.is_end_of_word(item[-1]["chr_index"]):
                yield from self._traverse_backwards(scan_node, copy.deepcopy(item))
            # If the forward scan node is empty
            # we have already yielded all possible completions for this branch, so we return.
            return
        chr_index = item[-1]["chr_index"]
        if loop_depth == 0 and self.mmap.is_end_of_word(chr_index):
            if self._check_suffix_prefix(scan_node, item, "fw"):
                yield from self._traverse_backwards(scan_node, copy.deepcopy(item))

        hc = self.mmap.calculate_hc(chr_index)
        if hc == 0:
            # No further nodes to traverse, returning from this branch of the trie.
            return

        s_start, s_end = self.mmap.calculate_select(hc + 1)

        chr_range = self.mmap.get_trie_range(s_start, s_end)

        for idx, i_letter in enumerate(chr_range):
            hc = self.mmap.calculate_hc(s_start + idx)
            node = {
                "s_start": s_start,
                "s_end": s_end,
                "chr_index": s_start + idx,
                "key": i_letter,
                "hc": hc,
            }
            if idx == 0:
                item.append(node)
            else:
                item.pop()
                item.append(node)

            if self.mmap.is_end_of_word(s_start + idx):
                if self._check_suffix_prefix(scan_node, item, "fw"):
                    yield from self._traverse_backwards(scan_node, copy.deepcopy(item))
            if hc:
                yield from self._traverse_forward(
                    scan_node, copy.deepcopy(item), loop_depth=loop_depth + 1
                )

    def traverse_prefix_end(
        self, scan_node: "ScanNode", item: list[dict], prefix_query: list[int]
    ):
        """Traverse the trie to find the end of a prefix."""

        start = item[0]["chr_index"]
        s = self.mmap.calculate_select_from_index(start)

        hc = s["hc"] - 1
        chr_index = self.mmap.calculate_chr_from_hc(hc)
        if chr_index < 0:
            return

        s = self.mmap.calculate_select_from_index(chr_index)
        i_letter = self.mmap.get_trie_range(s.get("s_start"), s.get("s_end"))[
            chr_index - s.get("s_start")
        ]

        if i_letter != prefix_query[-1] and prefix_query[-1] != alpha.UNDERSCORE:
            return

        item.insert(
            0,
            {
                "s_start": s.get("s_start"),
                "s_end": s.get("s_end"),
                "chr_index": chr_index,
                "key": i_letter,
                "hc": hc,
            },
        )

        if len(prefix_query) > 1:
            # loop until the prefix is fully traversed
            yield from self.traverse_prefix_end(scan_node, item, prefix_query[:-1][:])
        else:
            yield from self._traverse_forward(scan_node, item, loop_depth=0)

    def _traverse_backwards(self, scan_node: "ScanNode", item: list[dict]):
        """Traverse the trie backwards to get the whole word.
        Starting from the given scans
        and ending at the root of the trie."""
        if self.search.search_completed():
            return

        if scan_node.start_at_zero:
            # If the backward scan node is empty,
            # there are no letters to traverse backwards.
            res = self.add_result(item)
            if res:
                yield res
            return

        if item[0].get("s_start") == 0:
            # we have reached the root of the trie
            if self._check_suffix_prefix(scan_node, item, "bw"):
                res = self.add_result(item)
                if res:
                    yield res
            return

        start = item[0]["chr_index"]
        s = self.mmap.calculate_select_from_index(start)

        while True:
            hc = s["hc"] - 1
            chr_index = self.mmap.calculate_chr_from_hc(hc)
            s = self.mmap.calculate_select_from_index(chr_index)

            item.insert(
                0,
                {
                    "s_start": s["s_start"],
                    "s_end": s["s_end"],
                    "chr_index": chr_index,
                    "key": s["key"],
                    "hc": hc,
                },
            )

            if s["s_start"] == 0:
                if self._check_suffix_prefix(scan_node, item, "bw"):
                    res = self.add_result(item)
                    if res:
                        yield res
                break
        return

    def _matches_pattern_sequence(self, word_part, patterns) -> bool:
        """
        Check if word_part contains ALL patterns from patterns in sequential order.

        Args:
            word_part: Current accumulated letters as list of integers
            patterns: List of patterns, e.g. [[s,t],[a,k],[r,a]] for "st*ak*ra"

        Returns:
            bool: True if ALL patterns are found in their relative order

        Example:
            word_part = [s,t,u,v,a,k,w,x,r,a,z]
            patterns = [[s,t],[a,k],[r,a]]
            Returns True because "st" appears first, then "ak", then "ra"
        """
        if not patterns or not word_part:
            return True

        word_len: int = len(word_part)
        search_start: int = 0
        # MUST match ALL patterns in the given order
        for pattern in patterns:
            pattern_len = len(pattern)
            pattern_matches = False
            # Search for this pattern starting from where the last pattern ended
            for i in range(search_start, word_len - pattern_len + 1):
                chr_match = True
                for j in range(pattern_len):
                    if pattern[j] == alpha.UNDERSCORE:
                        # Underscore matches any character, so we skip this position
                        continue
                    current_char = word_part[i + j]
                    pattern_chars = (
                        [pattern[j]]
                        if not self.case_insensitive
                        else [pattern[j], alpha.case_folding(pattern[j])]
                    )
                    if current_char not in pattern_chars:
                        chr_match = False
                        break
                if chr_match:
                    # Pattern found! Next pattern must start after this one
                    search_start = i + pattern_len
                    pattern_matches = True
                    break

            # If ANY pattern is not found, the whole sequence fails
            if not pattern_matches:
                return False

        # Only returns True if ALL patterns were found in order
        return True
