import os
import sys

class Alphabet:
    reversed_char = 143  # This is a character that is not in the alphabet.
    # It indicates the beginning of a reversed index as first character in the reversed index.
    reversed_index = False
    RES_SEPARATOR = 141  # separator between results for multiple results in the lookup result (short_text)

    def __init__(self, reversed=False) -> None:
        if os.getenv("ASKUR_ALPHABET") is None:
            raise EnvironmentError("ALPHABET environment variable is not set.")
            sys.exit(1)

        self._alphabet: dict[int, int] = {
            ord(c): n for n, c in enumerate(os.getenv("ASKUR_ALPHABET"))
        }
        self._alphabet.setdefault(self.reversed_char, len(self._alphabet))

        self._used_alphabet: list[
            dict[int, int]
        ] = []  # used alphabet is empty at the start and gets filled as words are added

        # Are we using a reversed index?
        self.reversed_index: bool = reversed

    @property
    def alphabet(self) -> dict[int, int]:
        return self._alphabet

    def add(self, key) -> None:
        if isinstance(key, str):
            key: int = ord(key)
        self._alphabet.setdefault(key, len(self._alphabet))

    def get_alphabet_index(self, key: int) -> int | None:
        return self._alphabet.get(key)

    @property
    def inv_alphabet(self) -> dict[int, int]:
        """Inverse alphabet. v is the index, k is the character.
        example: {0: 97, 1: 98, ...}
        """
        return {v: k for k, v in self._alphabet.items()}

    @staticmethod
    def convert_int_to_str(query: list[int]) -> str:
        """
        converts list of integers to text
        multibyte chars begin with number 2 to 4, indicating how many bytes follow
        single byte chars are represented by their ascii/unicode value directly
        """
        text_array: list[str] = []
        i: int = 0
        bits: list[str]
        while i < len(query):
            if query[i] <= 4:
                unicode_bytes: list[int] = query[i + 1 : i + 1 + query[i]]
                bits = [bin(b)[2:].rjust(8, "0") for b in unicode_bytes]
                try:
                    unicode_val = int("".join(bits), 2)
                    text_array.append(chr(unicode_val))
                except (ValueError, OverflowError):
                    text_array.append("?")  # fallback for invalid unicode
                i = 1 + i + query[i]
                continue
            text_array.append(chr(query[i]))
            i += 1
        return "".join(text_array)

    @staticmethod
    def convert(word: str) -> bytearray:
        """Convert a word to a list of alphabet chars to bytes.
        If a character is not in the alphabet, it is added to the end of it.
        If a character is a multibyte character, it is converted to multiple single bytes.
        """
        if word == "\\":
            word = word + "\\"  # to handle single escape character
        if word.endswith("\\") and not word.endswith("\\\\"):
            word = word + "\\"  # to handle escape character at end of word
        res = bytearray()
        num: int = 0
        ny_bits: str
        nr_bytes: int
        for _, c in enumerate(word):
            if ord(c) > 255:
                ny_bits = bin(ord(c))[2:]
                ny_bits = ny_bits.rjust(
                    ((len(ny_bits) + 7) // 8) * 8, "0"
                )  # pad to full bytes
                nr_bytes = len(ny_bits) // 8

                res.append(nr_bytes)
                self.add(nr_bytes)
                for i in range(0, nr_bytes * 8, 8):
                    num = int(ny_bits[i : i + 8], 2)
                    self.add(num)
                    res.append(num)
                continue

            if ord(c) not in self._alphabet:
                self.add(c)
            res.append(ord(c))
            if ord(c) not in self._used_alphabet:
                self._used_alphabet.append(ord(c))
        return res

    @property
    def used_alphabet(self) -> list[dict[int, int]]:
        """Return the used letters in the alphabet."""
        return self._used_alphabet

    @property
    def get_used(self) -> bytearray:
        """Return the used letters in the alphabet as a bytearray."""
        alphabet_bytes = bytearray()
        if self.reversed_index:
            alphabet_bytes.append(self.reversed_char)
        for k in self._alphabet.keys():
            if k in self._used_alphabet and k not in alphabet_bytes:
                alphabet_bytes.append(k)
        return alphabet_bytes
