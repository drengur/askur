from askur.alphabet import Alphabet

alpha = Alphabet()


class QueryBuilder:
    """A class to build and manage query dictionaries for the search process."""

    # Query types
    TYPE_BASIC = "basic"
    TYPE_WILDCARD = "wildcard"
    TYPE_SCAN = "scan"
    TYPE_ID = "id"

    query: dict = None
    _has_wildcard: bool = False
    _has_underscore: bool = False

    def __init__(
        self,
        query,
        case_insensitive: bool = False,
        fuzzy_match: bool = False,
        key_exists: bool = False,
        sorted_results: bool = False,
        id: int = -1,
    ):
        self.original_query = query
        self._fuzzy_match = fuzzy_match
        self._case_insensitive = case_insensitive
        self._has_wildcard = False
        self._has_underscore = False
        self._id = id

        self.query = {
            "type": "",
            "original_query": query,
            "query": None,
            "start_letters": None,
            "prefix": None,  # the part of letters between the wildcards before the scan_query
            "prefix_end": None,  # the word starts with this letter(s)
            "scan_query": None,  # the main part of the query between the prefix and suffix
            "suffix": None,  # the part of letters between the wildcards after the scan_query
            "end_letter": None,  # the word end with this letter(s)
            "start_at_end": False,  # Nothing to check before the scan_query
            "start_at_zero": False,  # Nothing to check after the scan_query
            "min_word_length": 0,  # Minimum length of the query result considering underscores and wildcards
            "max_word_length": 0,  # Maximum length of the query resultconsidering underscores and wildcards
            "case_insensitive": self._case_insensitive,
            "fuzzy_match": self._fuzzy_match,
            "key_exists": key_exists,
            "id": self._id,
        }

        # assert self._limit >= 0, "Limit must be a non-negative integer."
        assert isinstance(sorted_results, bool), "sorted_results must be a boolean."
        if query is None or query == "":
            assert self._id > -1, "ID must be greater than -1."
        if self._id > -1:
            assert query is None or query == "", (
                "Query must not be provided if ID is used."
            )

        san_query = self.sanitize_query()
        if self._id > -1:
            self.query["type"] = self.TYPE_ID
            return
        if self._is_clean_wildcard_query(san_query):
            self.prepare_wildcard_query(san_query)
        elif self._is_scan_query(san_query):
            self.prepare_query_for_scan(san_query)
        else:
            self.prepare_basic_query(san_query)

    def __str__(self) -> str:
        ret = [f"   {key}: {value}\n" for key, value in self.query.items()]
        return f"QueryBuilder:\n {''.join(ret)}"

    @property
    def query_type(self) -> bool:
        return self.query["type"]

    @property
    def _is_basic_query(self) -> bool:
        """Return whether the query can be treated as a normal query (without wildcards)."""
        return not self._has_wildcard and not self._has_underscore

    @property
    def case_insensitive(self) -> bool:
        """Return whether to use case insensitive search."""
        return self._case_insensitive

    @property
    def fuzzy_match(self) -> bool:
        """Return whether to use Levenshtein distance (of one) for the search."""
        return self._fuzzy_match

    def sanitize_query(self) -> dict[bytes, int]:
        """Return a sanitized query dictionary containing only the original query."""
        byte_query = (
            alpha.convert_str_to_bytes(self.original_query)
            if self.original_query is not None
            else b""
        )
        back_slashed = False
        sanitized_query = []
        for n, value in enumerate(byte_query):
            if value == alpha.BACKSLASH and back_slashed:
                back_slashed = False
            elif value == alpha.BACKSLASH:
                back_slashed = True
                continue
            if back_slashed and value in (alpha.WILDCARD, alpha.UNDERSCORE):
                value = -value
                back_slashed = False
            sanitized_query.append(value)

        self._has_wildcard = alpha.WILDCARD in sanitized_query
        self._has_underscore = alpha.UNDERSCORE in sanitized_query
        return sanitized_query

    def _is_scan_query(self, query) -> bool:
        """Return whether the query contains a wildcard character."""
        return self._has_wildcard and not self._is_clean_wildcard_query(query)

    def _is_clean_wildcard_query(self, query) -> bool:
        """Return wheter there are any non-wildcard and non-underscore characters."""
        if not [c for c in query if c != alpha.UNDERSCORE]:
            return False

        # check to see if we have clean wildcards and underscores:
        if [c for c in query if c not in (alpha.WILDCARD, alpha.UNDERSCORE)]:
            return False

        return True

    def prepare_wildcard_query(self, query) -> None:
        """Prepares the query as for wildcard search"""
        nr_underscores = query.count(alpha.UNDERSCORE)
        nr_wildcards = query.count(alpha.WILDCARD)

        self.query["min_length"] = nr_underscores
        self.query["max_length"] = 0 if nr_wildcards > 0 else nr_underscores
        self.query["type"] = self.TYPE_WILDCARD
        self.query["query"] = [alpha.WILDCARD]

    def prepare_basic_query(self, query: bytes) -> None:
        """Prepares the query as a basic query without wildcards."""
        self.query["type"] = self.TYPE_BASIC
        self.query["query"] = query

    def prepare_query_for_scan(self, query) -> dict:
        """Implement the logic to prepare the query for scanning the trie.
        Finding the longest contiguous sequence of non-wildcard and non-underscore
        characters to optimize the scanning process.
        Constructing a dictionary where each key represents a segment of the query
        for validation and scanning.

        query =
        |a V e r y V e r y so L o n g W o r d|
        |-1--|-2---|-3----|-4----|-5-----|-6-|
        1: start-letters
        2: prefix
        3: prefix_end
        4: scan_query
        5: suffix
        6: end_letters

        'prefix_end': If the prefix ends with an underscore,
            it should be separated from the prefix and treated separately as attached part of the scan_query.
        'suffix': If suffix starts with an underscore,
            the first part of it should be attached to the scan_query.
        'start-letters': If the query does not start with a wildcard,
            the start-letters segment should be the first element of the prefix and treaded separately.
        'end-letters': If the query does not end with a wildcard, the end-letter segment should be considered.
        """

        d_query = {}  # dictionary to store query segments
        tmp_underscores = []  # temporary list to store contiguous underscore characters
        tmp_wildcards = []  # temporary list to store contiguous wildcard characters
        tmp_ords = []  # temporary list to store contiguous non-wildcard and non-underscore characters
        idx = 0  # current segment index
        max_len = 0  # length of the longest contiguous segment
        max_len_idx = -1  # index of the longest contiguous segment

        # find the longest contiguous segment of non-wildcard and non-underscore characters
        for i, c in enumerate(query):
            if c == alpha.WILDCARD:
                tmp_wildcards.append(c)
                if tmp_underscores:
                    d_query[idx] = tmp_underscores[:]
                    tmp_underscores.clear()
                    idx += 1
                elif tmp_ords:
                    if max_len < len(tmp_ords):
                        max_len = len(tmp_ords)
                        max_len_idx = idx
                    d_query[idx] = tmp_ords[:]
                    tmp_ords.clear()
                    idx += 1
                continue
            if c == alpha.UNDERSCORE:
                tmp_underscores.append(c)
                if tmp_ords:
                    d_query[idx] = tmp_ords[:]
                    if max_len < len(tmp_ords):
                        max_len = len(tmp_ords)
                        max_len_idx = idx
                    tmp_ords.clear()
                    idx += 1
                elif tmp_wildcards:
                    d_query[idx] = tmp_wildcards[:]
                    tmp_wildcards.clear()
                    idx += 1
                continue
            if tmp_underscores:
                d_query[idx] = tmp_underscores[:]
                tmp_underscores.clear()
                idx += 1
            elif tmp_wildcards:
                d_query[idx] = tmp_wildcards[:]
                tmp_wildcards.clear()
                idx += 1
            tmp_ords.append(c)

        if tmp_ords:
            d_query[idx] = tmp_ords[:]
            if max_len < len(tmp_ords):
                max_len = len(tmp_ords)
                max_len_idx = idx
        if tmp_underscores:
            d_query[idx] = tmp_underscores[:]
        if tmp_wildcards:
            d_query[idx] = tmp_wildcards[:]

        # If the query does not start with a wildcard or underscore,
        # the first segment is considered the longest by default
        # if the longest segment is too short.
        # Searching through the first letter in the trie it gives (possibly) the fastest search results.
        if query[0] not in (alpha.WILDCARD, alpha.UNDERSCORE) and max_len < 3:
            max_len_idx = 0

        # prefixes and start-letters
        sub_query = d_query[max_len_idx] if max_len_idx != -1 else []
        prefix_queries = []
        prefix_end = []
        split = False
        for i in range(0, max_len_idx):
            if d_query[i] and d_query[i][0] == alpha.WILDCARD:
                split = True
                continue
            if d_query[i] and d_query[i][0] != alpha.WILDCARD and i < max_len_idx - 1:
                if not split and prefix_queries:
                    prefix_queries[-1].extend(d_query[i])
                else:
                    prefix_queries.append(d_query[i])
                split = False
            if (
                i == max_len_idx - 1
                and d_query[i]
                and d_query[i][0] == alpha.UNDERSCORE
            ):
                prefix_end = d_query[i]
                if not split and prefix_queries:
                    prefix_end = prefix_queries[-1] + prefix_end
                    prefix_queries.pop()
        if not prefix_queries:
            prefix_queries = None
        if not prefix_end:
            prefix_end = None

        start_letters = None
        if d_query[0] and d_query[0][0] != alpha.WILDCARD:
            start_letters = prefix_queries[0] if prefix_queries else None
            prefix_queries = prefix_queries[1:] if prefix_queries else None

        # suffix and end-letters
        suffix = []
        end_letter = []
        split = False
        for i in range(max_len_idx + 1, idx + 1):
            if d_query[i] and d_query[i][0] == alpha.WILDCARD:
                split = True
                continue
            if not split:
                sub_query.extend(d_query[i])
            else:
                suffix.append(d_query[i])

        if d_query[idx] and d_query[idx][0] != alpha.WILDCARD and suffix:
            suffix.pop()
            end_letter = d_query[idx]
            if not split and suffix:
                end_letter = suffix[-1] + end_letter
                suffix.pop()

        if not suffix:
            suffix = None
        if not end_letter:
            end_letter = None

        # Determine if the forward search is supposed to by empty
        # when checking the suffix part of the query
        # (is the end of the  word the same as the scan query?)
        start_at_end = False
        if end_letter is None and suffix is None and query[-1] != alpha.WILDCARD:
            start_at_end = True

        # is the beginning of the word the same as the scan query beginning?
        start_at_zero = False
        if prefix_end is None and prefix_queries is None and query[0] != alpha.WILDCARD:
            start_at_zero = True

        self.query["start_letters"] = start_letters
        self.query["prefix"] = prefix_queries or None
        self.query["prefix_end"] = prefix_end or None
        self.query["scan_query"] = sub_query
        self.query["suffix"] = suffix or None
        self.query["end_letter"] = end_letter
        self.query["start_at_end"] = start_at_end
        self.query["start_at_zero"] = start_at_zero
        self.query["type"] = self.TYPE_SCAN
        self.query["original_query"] = ""
