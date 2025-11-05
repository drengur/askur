import os


class Alphabet:
    
    reversed_char = 143  # This is a character that is not in the alphabet
    reversed_index = False
    RES_SEPARATOR = 141 # separator between results for multiple results in the lookup

    def __init__(self, reversed=False):
        assert os.getenv("ASKUR_ALPHABET") is not None, (
            "ALPHABET environment variable is not set."
        )

        self._alphabet = {ord(c): n for n, c in enumerate(os.getenv("ASKUR_ALPHABET"))}
        self._alphabet.setdefault(self.reversed_char, len(self._alphabet))

        self._used_alphabet = []  # used alphabet is empty at the start and gets filled as words are added
        self.reversed_index = reversed

    @property
    def alphabet(self):
        return self._alphabet

    def add(self, key):
        if isinstance(key, str):
            key = ord(key)
        self._alphabet.setdefault(key, len(self._alphabet))

    def get_alphabet_index(self, key: int):
        return self._alphabet.get(key)

    @property
    def inv_alphabet(self):
        """Inverse alphabet. v is the index, k is the character.
        example: {0: 'a', 1: 'b', ...}
        """
        return {v: k for k, v in self._alphabet.items()}

    def convert_int_to_str(query) -> str:
        """
        converts list of integers to text
        multibyte chars are begin with number 2 to 4
        """
        text_array = []
        i = 0
        while i < len(query):
            if query[i] <= 4:
                unicode_bytes = query[i + 1 : i + 1 + query[i]]
                bits = [bin(b)[2:].rjust(8, "0") for b in unicode_bytes]
                try:
                    unicode_val = int("".join(bits), 2)
                    char_str = chr(unicode_val)
                    text_array.append(char_str)
                except (ValueError, OverflowError):
                    text_array.append('?')  # fallback for invalid unicode
                i = 1 + i + query[i]
                continue
            text_array.append(chr(query[i]))
            i += 1
        return "".join(text_array)

    def convert(self, word: str) -> bytearray:
        """Convert a word to a list of alphabet chars to bytes.
        If a character is not in the alphabet, it is added to the end of it.
        If a character is a multibyte character, it is converted to multiple single bytes.
        """
        if word == "\\":
            word = word + "\\"  # to handle single escape character
        if word.endswith("\\") and not word.endswith("\\\\"):
            word = word + "\\"  # to handle escape character at end of word
        res = bytearray()
        for _, c in enumerate(word):
            if ord(c) > 255:
                ny_bits = bin(ord(c))[2:]
                nr_bytes = len(ny_bits) // 8 + (1 if len(ny_bits) % 8 != 0 else 0)
                ny_bits = bin(ord(c))[2:].rjust(nr_bytes * 8, "0")

                res.append(nr_bytes)
                self.add(nr_bytes)
                for i in range(0, nr_bytes * 8, 8):
                    num = int(ny_bits[i : i + 8].rjust(8, "0"), 2)
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
    def used_alphabet(self) -> list:
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
