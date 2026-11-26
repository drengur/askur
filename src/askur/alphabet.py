import os
import sys


class Alphabet:
    """
    Class representing an alphabet for the trie structure.
    Alphabet consists of characters defined in the ASKUR_ALPHABET environment variable
    plus characters added dynamically through the add method.
    It also keeps track of the used characters in the alphabet.

    Multibyte characters are handled by representing them with a
    leading byte indicating the number of following bytes:
    "💊" <=> [00000011 00000001 11110100 10001010] <=> [3 1 244 138]
    """

    UNDERSCORE = ord("_")
    WILDCARD = ord("*")
    BACKSLASH = ord("\\")
    UNIT_SEPARATOR = b"\x1f"  # int = 31, unit separator between results for multiple results in the lookup result (short_text)

    def __init__(self) -> None:
        if os.getenv("ASKUR_ALPHABET") is None:
            raise EnvironmentError("ALPHABET environment variable is not set.")

        self._alphabet: dict[int, int] = {
            ord(c): n for n, c in enumerate(os.getenv("ASKUR_ALPHABET"))
        }
        self._used_alphabet: list[int] = []

    @property
    def alphabet(self) -> dict[int, int]:
        """Return the current alphabet mapping."""
        return self._alphabet

    def add(self, w_key: int | str | bytes) -> None:
        """Add a key to the alphabet if it doesn't already exist."""
        key: int
        if isinstance(w_key, str):
            key = ord(w_key)
        elif isinstance(w_key, bytes):
            key = int.from_bytes(w_key, byteorder="big")
        else:
            key = w_key
        self._alphabet.setdefault(key, len(self._alphabet))

    def get_alphabet_index(self, key: int) -> int | None:
        """Return the alphabet index for the given key, or None if not found."""
        return self._alphabet.get(key)

    @property
    def inv_alphabet(self) -> dict[int, int]:
        """Inverse alphabet. v is the index, k is the character.
        example: {0: 97, 1: 98, ...}
        """
        return {v: k for k, v in self._alphabet.items()}

    @staticmethod
    def convert_bytes_to_str(query: list[bytes]) -> str:
        """
        converts list of bytes to text
        multibyte chars begin with number 2 to 4, indicating how many bytes follow
        single byte chars are represented by their ascii/unicode value directly
        """
        text_array: list[str] = []
        i: int = 0
        while i < len(query):
            if query[i] <= 4:
                multi_bytes_char: list[bytes] = query[i + 1 : i + 1 + query[i]]
                try:
                    int_value: int = int.from_bytes(bytearray(multi_bytes_char), "big")
                    text_array.append(chr(int_value))
                except (ValueError, OverflowError):
                    text_array.append("?")  # fallback for invalid unicode
                i = 1 + i + query[i]
                continue
            text_array.append(chr(query[i]))
            i += 1
        return "".join(text_array)

    def convert_str_to_bytes(self, word: str) -> bytearray:
        """Convert a word to a list of alphabet chars to bytes.
        If a character is not in the alphabet, it is added to the end of it.
        If a character is a multibyte character, it is converted to multiple single bytes.
        """
        if word == "\\":
            word = word + "\\"  # to handle single escape character
        if word.endswith("\\") and not word.endswith("\\\\"):
            word = word + "\\"  # to handle escape character at end of word
        res = bytearray()
        nr_bytes: int
        for _, c in enumerate(word):
            if ord(c) > 255:
                nr_bytes = (ord(c).bit_length() + 7) // 8
                res.append(nr_bytes)
                if nr_bytes not in self._used_alphabet:
                    self._used_alphabet.append(nr_bytes)
                byte_values = ord(c).to_bytes(nr_bytes, byteorder="big")
                res.extend([b for b in byte_values])
                self.add(nr_bytes)
                [self.add(b) for b in byte_values]
                continue
            if ord(c) not in self._alphabet:
                self.add(c)
            if ord(c) not in self._used_alphabet:
                self._used_alphabet.append(ord(c))
            res.extend(ord(c).to_bytes(1, byteorder="big"))
        return res

    @property
    def used_alphabet(self) -> list[int]:
        """Return the used letters in the alphabet."""
        return self.get_used

    @property
    def get_used(self) -> bytearray:
        """Return the used letters in the alphabet as a bytearray."""
        return [c for c in self._used_alphabet]

    @property
    def get_used_sorted(self) -> list[int]:
        """Return the used letters in the alphabet sorted."""
        res = []
        for _, c in enumerate(self._alphabet):
            if c in self._used_alphabet:
                res.append(c)
        return res

    def case_folding(self, char: int) -> int:
        """Convert character to lower case if it's upper case and vice versa."""
        if char in (247, 215):
            return char
        if 65 <= char <= 90 or 192 <= char <= 222:
            return char + 32
        if 97 <= char <= 122 or 224 <= char <= 254:
            return char - 32
        return char
