#! /usr/bin/env python3

"""Make lookup tables for the trie.
Virkar eins og make_bin_trie, nema að það er bara
listi yfir orð id og ekkert annað.
"""

import io
import os
import argparse
import math as m
import config


ARG_PARSER = argparse.ArgumentParser(description="Make lookup tables for the trie.")
# ARG_PARSER.add_argument("--filename", "-f", type=str, help="The filename to read from.")
ARG_PARSER.add_argument(
    "--collection", "-C", type=str, help="The name of the collection to create."
)
ARG_PARSER.add_argument("--file", "-f", type=str, help="File to read from.")
ARG_PARSER.add_argument("-i", type=str, help="Case insensitive")
ARG_PARSER.add_argument(
    "--reversed", "-R", action="store_true", help="Make reversed index"
)
ARG_PARSER.add_argument(
    "-F", type=str, default=";", help="Field separator (default: ';')"
)


class Node:
    __slots__ = ["index", "letters"]

    def __init__(self):
        self.index = None  # Only create list when needed
        self.letters = None  # Only create dict when needed

    @property
    def has_children(self):
        return self.letters is not None

    @property
    def end(self):
        # Is this node an end/leaf node? (end of word)
        return self.index is not None

    def get_child(self, key):
        if self.letters is None:
            self.letters = {}
        if key not in self.letters:
            self.letters[key] = Node()
        return self.letters[key]

    def add_index(self, idx):
        """Add an index to the end/leaf node.
        Leaf nodes can have multiple indices.
        """
        if self.index is None:
            self.index = []
        if idx in self.index:
            return
        self.index.append(idx)


class Alphabet:
    # None printable characters:
    # 129 (0x81)
    # 141 (0x8D)
    # 143 (0x8F)
    # 144 (0x90)
    # 157 (0x9D)
    multibyte_char = 129
    reversed_char = 143  # This is a character that is not in the alphabet
    reversed_index = False

    def __init__(self, reversed=False):
        assert os.getenv("ASKUR_ALPHABET") is not None, (
            "ALPHABET environment variable is not set."
        )

        self._alphabet = {ord(c): n for n, c in enumerate(os.getenv("ASKUR_ALPHABET"))}
        self._alphabet.setdefault(self.multibyte_char, len(self._alphabet))
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

    def convert(self, word: str) -> bytearray:
        """Convert a word to a list of alphabet indices.
        If a character is not in the alphabet, it is added to the alphabet.
        If a character is a multibyte character, it is converted to 5 bytes.
        """
        res = bytearray()
        for c in word:
            if ord(c) > 255:
                bits = bin(ord(c))[2:].rjust(32, "0")
                res.append(Alphabet.multibyte_char)
                for i in range(0, 32, 8):
                    num = int(bits[i : i + 8], 2)
                    self.add(num)
                    res.append(num)
                    if num not in self._used_alphabet:
                        self._used_alphabet.append(num)
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


class Trie:
    """A trie."""

    def __init__(self, collection_name=None, reversed=False):
        """Create a new trie and associated files.
        usage:
            trie = Trie()
            trie.make_frozen_data()
        """

        self._trie = bytearray()  # the LOUDS representation of the trie
        self._hc = []  # the head child array (1 if the node has a child, 0 otherwise)
        self._select = []  # the select array (the index of the node in the LOUDS array)
        self._is_eow = []  # the value array (is the end of the word)
        self._index = []  # the counter array (the number of words that have been added to the trie)
        self._short_text = []  # the short text array (the words in the trie)
        self.collection_name = collection_name
        self.reversed = reversed  # make reversed index if True

        # The alphabet order used in the trie.
        self.alphabet = Alphabet(reversed)

        # Check for environment variable first, then fall back to config file
        data_folder = os.environ.get("ASKUR_DATA_FOLDER")

        assert data_folder is not None, "DATA_FOLDER environment variable is not set."
        assert collection_name is not None, "Collection name is not set.\ Exiting."
        frozen_folder = os.path.join(data_folder, self.collection_name)
        if not os.path.exists(frozen_folder):
            os.makedirs(frozen_folder, exist_ok=True)

        self.select_bits_filename = os.path.join(frozen_folder, "s_bits.bin")

        self.trie_file = os.path.join(frozen_folder, "trie")

        self.index_bits_filename = os.path.join(frozen_folder, "index_bits.bin")
        self.hc_bits_filename = os.path.join(frozen_folder, "hc_bits.bin")

        self.value_bits_filename = os.path.join(frozen_folder, "eow_bits.bin")

        self.short_text_bits_filename = os.path.join(
            frozen_folder, "short_text_bits.bin"
        )

        # end of word super block file
        self.eow_sb = os.path.join(frozen_folder, "eow_sb.bin")

        # hc superblock
        self.hc_sb_file = os.path.join(frozen_folder, "hc_sb.bin")

        # select superblock
        self.s_sb_file = os.path.join(frozen_folder, "s_sb.bin")

        # the root node of the trie
        self.root = Node()

    def make_frozen_data(self, filename=None):
        """Make the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays."""

        nr_lines_in_file = sum(1 for line in open(filename))
        print(f" Reading from file {filename}. Number of lines: {nr_lines_in_file}")
        data_values = {}
        index = 0
        line_nr = 0

        for word_key, word_value in self.read_from_file(filename):
            line_nr += 1
            if line_nr % 1000 == 0:
                print(f"Reading {line_nr / nr_lines_in_file * 100:.2f}%", end="\r")
            if word_key.startswith("#") or word_key.startswith("\n"):
                continue
            if not word_key:
                continue

            key = self.alphabet.convert(word_key)
            if word_value not in data_values:
                index = len(data_values)
                data_values.setdefault(word_value, index)
            else:
                index = data_values[word_value]
            self._add(key, index)
            if self.reversed:
                # If reversed, we add the word in reverse order
                key.reverse()
                key.insert(0, self.alphabet.reversed_char)
                self._add(key, index)

        print(" 1/7 - Writing to disk...", end="\r")
        self.level_order_tree([self.root], self.alphabet.inv_alphabet)
        print(" 2/7 - Writing to disk...", end="\r")
        self.write_tree_to_file()

        print(" 3/7 - Writing to disk...", end="\r")
        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_sums_to_file(self.eow_sb)

        print(" 4/7 - Writing to disk...", end="\r")
        self.write_hc_to_file(self.hc_bits_filename)
        self.hc_to_lookup()

        print(" 5/7 - Writing to disk...", end="\r")
        self.write_select_to_file(self.select_bits_filename)
        self.select_to_lookup()

        print(" 6/7 - Writing to disk...", end="\r")
        self.write_short_text_to_file(data_values)

        print(" 7/7 - Writing to disk...", end="\r")
        with io.open(self.trie_file + ".alphabet", "wb") as f:
            f.write(self.alphabet.get_used)

    def read_from_file(self, filename):
        """Read a file line by line."""
        file = io.open(filename, "r", encoding="utf-8")
        for line in file:
            if not line.strip():
                continue
            word_key = line.split(";", 1)[0].strip()
            word_value = (
                None if len(line.split(";")) == 1 else line.split(";", 1)[1].strip()
            )
            assert word_value is not None
            yield word_key, word_value
        file.close()

    def _add(self, word: list, index_id: int):
        """Add a word to the trie."""
        node = self.root
        for ch in word:
            node = node.get_child(self.alphabet.get_alphabet_index(ch))
        node.add_index(index_id)

    def level_order_tree(self, nodes, inv_alphabet):
        """Level out trie.
        Traverse the trie in level order and write to the _trie, _hc,
        _select, _is_eow and _index arrays.
        """
        if len(nodes) == 0:
            return
        child_nodes = []
        for node in nodes:
            first = 1
            for w_key in sorted(node.letters and node.letters.keys() or []):
                self._trie.append(inv_alphabet.get(w_key))
                self._select.append(first)
                first = 0
                self._hc.append(1 if node.letters[w_key].has_children else 0)
                if node.letters[w_key].end:
                    self._is_eow.append(1)
                    self._index.append(node.letters[w_key].index)
                else:
                    self._is_eow.append(0)
                child_nodes.append(node.letters[w_key])
        self.level_order_tree(child_nodes, inv_alphabet)

    def generate_data(self, big_string):
        """Generate data from a big string in chunks to minimize memory usage.
        This function is a placeholder for generating data.
        """
        i = 0
        chunk_size = 1024
        while i < len(big_string):
            yield big_string[i : i + chunk_size]
            i += chunk_size

    def write_tree_to_file(self):
        """Write level ordered trie to a file."""
        io.open(self.trie_file, "w").close()
        with io.open(self.trie_file, "ab") as f:
            for chunk in self.generate_data(self._trie):
                f.write(chunk)
            f.close()

    def write_hc_to_file(self, filename):
        """Write the head child array to a file."""
        io.open(filename, "w").close()

        buffer = bytearray()  # Buffer to hold bytes before Writing to disk
        i = 0
        extra_bits = len(self._hc) % 8
        if extra_bits > 0:
            for _ in range(8 - extra_bits):
                self._hc.append(0)  # Pad with zeros to make it a multiple of 8 bits
        while i < len(self._hc):
            buffer.append(int("".join([str(c) for c in self._hc[i : i + 8]]), 2))
            i += 8
            if len(buffer) >= 10240:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()  # Clear the buffer to free memory
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)
                f.close()

    def write_select_to_file(self, filename):
        """Write the select array to a file."""
        io.open(filename, "w").close()

        # Það þarf að bæta við 1 í enda á select fylkinu til að geta staðsett síðasta bókstafinn í trie-skránni
        # Að öðrum kosti finnst ekki verður select útreikningurinn óendanlegur
        self._select.append(1)  # Pad with 1 to make it a multiple
        buffer = bytearray()  # Buffer to hold bytes before Writing to disk
        i = 0
        extra_bits = len(self._select) % 8
        if extra_bits > 0:
            for _ in range(8 - extra_bits):
                self._select.append(0)  # Pad with zeros to make it a multiple of 8 bits
        while i < len(self._select):
            buffer.append(int("".join([str(c) for c in self._select[i : i + 8]]), 2))
            i += 8
            if len(buffer) >= 10240:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)
                f.close()

    def write_eow_values_to_file(self, filename):
        """Write the value array to a file."""
        io.open(filename, "w").close()

        buffer = bytearray()  # Buffer to hold bytes before Writing to disk
        i = 0
        extra_bits = len(self._is_eow) % 8
        if extra_bits > 0:
            for _ in range(8 - extra_bits):
                self._is_eow.append(0)  # Pad with zeros to make it a multiple of 8 bits
        # self._is_eow.append([0] * (8 - extra_bits) if extra_bits > 0 else 0)
        while i < len(self._is_eow):
            buffer.append(int("".join([str(c) for c in self._is_eow[i : i + 8]]), 2))
            i += 8
            if len(buffer) >= 10240:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()
        # add remaining bits
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)
                f.close()

    def write_eow_sums_to_file(self, filename):
        # bits in block = 32
        # sum of "1"-bits in a block of 32 bits
        io.open(filename, "w").close()

        sum = 0
        i = 0
        buffer = []
        bits_in_block = 32
        # Hérns er mögulegt að minnka bits_in_block
        for byte in range(0, len(self._is_eow)):
            sum += 1 if self._is_eow[byte] > 0 else 0
            i += 1
            if i == bits_in_block:
                i = 0
                buffer.append(sum)
                if len(buffer) >= 10240:
                    with io.open(filename, "ab") as f:
                        f.write(
                            self.bit_bytes_to_bits(
                                "".join(
                                    [
                                        bin(item)[2:].rjust(bits_in_block, "0")
                                        for item in buffer
                                    ]
                                )
                            )
                        )
                    buffer.clear()
        if sum:
            buffer.append(sum)
            with io.open(filename, "ab") as f:
                f.write(
                    self.bit_bytes_to_bits(
                        "".join(
                            [bin(item)[2:].rjust(bits_in_block, "0") for item in buffer]
                        )
                    )
                )
                f.close()

    def write_short_text_to_file(self, data_values):
        """Write the short text array to a file."""
        io.open(self.short_text_bits_filename, "w").close()
        io.open(self.index_bits_filename, "w").close()

        # Hérna snúum við data_values svo að röðin sé lykill og lykill sé value
        # Þetta er gert til að matcha staðsetningu self._index í Trie við data_values
        # invert the dictionary:
        # data_values = {v: self.modify_word(k) for k, v in data_values.items()}
        data_values = {v: self.alphabet.convert(k) for k, v in data_values.items()}

        total_sum = 0
        max_tmp_short_text = 0

        for _, value in data_values.items():
            total_sum += len(value)
            max_tmp_short_text = max(max_tmp_short_text, len(value))

        # byte_length er hægt að nota til að skipta út fyrir 32-bita lengdina
        nr_bytes_in_index_block = (
            len(bin(total_sum)[2:]) // 8 + (1 if len(bin(total_sum)[2:]) % 8 else 0) + 1
        )
        nr_bits_in_index_block = nr_bytes_in_index_block * 8  # 32

        # athuga lengd á tmp_short_text, s.s. spurning hvort að það séu mörg gildi fyrir sama key-index
        max_text_len = 0
        for idxs in self._index:
            text_len = 0
            for idx in idxs:
                text_len += len(data_values[idx]) + 1
            max_text_len = max(max_text_len, text_len)
        if max_text_len > 0:
            nr_bytes_in_value_block = len(bin(max_text_len)[2:]) // 8 + (
                1 if len(bin(max_text_len)[2:]) % 8 else 0
            )
            nr_bits_in_value_block = nr_bytes_in_value_block * 8

        with io.open(self.index_bits_filename, "ab") as f:
            f.write(
                self.bit_bytes_to_bits(
                    bin(nr_bytes_in_index_block)[2:].rjust(8, "0")
                    + bin(nr_bytes_in_value_block)[2:].rjust(8, "0")
                )
            )
            f.close()
        short_texts = []
        sum_index = 0
        tmp_indices = []
        indices = {}
        for idxs in self._index:
            multi_text = []
            for idx in idxs:
                if len(idxs) == 1:
                    if idx not in indices:
                        short_texts.append(data_values[idx])
                        value = bin(sum_index)[2:].rjust(
                            nr_bits_in_index_block, "0"
                        ) + bin(len(data_values[idx]))[2:].rjust(
                            nr_bits_in_value_block, "0"
                        )
                        indices[idx] = value
                        tmp_indices.append(value)
                        sum_index += len(data_values[idx])

                    else:
                        tmp_indices.append(indices[idx])
                else:
                    multi_text.append(data_values[idx])
            if len(multi_text) > 1:
                tmp_txt = []
                for mtx in multi_text:
                    if len(tmp_txt) == 0:
                        tmp_txt = mtx.copy()
                    else:
                        tmp_txt.append(141)  # separator between words/sentences
                        tmp_txt += mtx.copy()
                idx_n = len(data_values)
                short_texts.append(tmp_txt)

                value = bin(sum_index)[2:].rjust(nr_bits_in_index_block, "0") + bin(
                    len(tmp_txt)
                )[2:].rjust(nr_bits_in_value_block, "0")
                indices[idx_n] = []  # value
                tmp_indices.append(value)
                sum_index += len(tmp_txt)

            if len(short_texts) >= 10240:
                with io.open(self.short_text_bits_filename, "ab") as f:
                    for item in short_texts:
                        f.write(item)
                    f.close()
                short_texts.clear()

            if len(tmp_indices) >= 10240:
                with io.open(self.index_bits_filename, "ab") as f:
                    f.write(
                        self.bit_bytes_to_bits("".join([txt for txt in tmp_indices]))
                    )
                    f.close()
                tmp_indices.clear()

        if len(tmp_indices) > 0:
            with io.open(self.index_bits_filename, "ab") as f:
                f.write(self.bit_bytes_to_bits("".join([txt for txt in tmp_indices])))
                f.close()

        if len(short_texts) > 0:
            with io.open(self.short_text_bits_filename, "ab") as f:
                for item in short_texts:
                    f.write(item)
                f.close()

    def to_bytearray(self, s_bytes):
        """Convert chr to ord(chr)."""
        buffer = bytearray()
        for _, c in enumerate(s_bytes):
            buffer.append(ord(c))
        return buffer

    def bit_bytes_to_bits(self, s_bytes):
        """Convert ones and zeros from select and range series to bytes.
        s_bytes contain only 0 and 1, but are stored as bytes on the disk.
        We are converting the ones and zeros to bytes to compress their size.
        example '000000010000001001000001' -> bytearray(b'\x01\x02\x41')
        Thus reducing the size by a factor of 8.
        """
        buffer = bytearray()
        i = 0
        if len(s_bytes) % 8 != 0:
            s_bytes = s_bytes + "0" * (8 - len(s_bytes) % 8)
        while i < len(s_bytes):
            buffer.append(int(s_bytes[i : i + 8].ljust(8, "0"), 2))
            i += 8
        return buffer

    def hc_to_lookup(self):
        # Writing to hc-superblock
        bib = 8
        block_size = (round(m.ceil(m.log2(len(self._hc)) / 2) + 5, -1) // bib) * bib

        # bit lengd getur verið (len(bin(self._hc)) // 8 + 1 (byte)) * 8  í stað föstu tölunnar 32
        # það ætti að spara í það minnsta 1 byte fyrir hvert 32 bita block
        # sama er hægt að gera fyrir select_lookup
        io.open(self.hc_sb_file, "w").close()

        res = bytearray()
        bitsum = 0
        index = 0
        for i, val in enumerate(self._hc):
            bitsum += val
            index += 1
            if index == block_size:
                bits = bin(bitsum)[2:].rjust(32, "0")
                for j in range(0, len(bits), 8):
                    res.append(int(bits[j : j + 8], 2))
                index = 0
                if len(res) >= 1024:
                    with io.open(self.hc_sb_file, "ab") as f:
                        f.write(res)
                        f.close()
                    res.clear()
        if index > 0:
            bits = bin(bitsum)[2:].rjust(32, "0")
            for j in range(0, len(bits), 8):
                res.append(int(bits[j : j + 8], 2))
        if len(res) > 0:
            with io.open(self.hc_sb_file, "ab") as f:
                f.write(res)
                f.close()

    def select_to_lookup(self):
        io.open(self.s_sb_file, "w").close()

        bib = 8
        bits = ""
        block_size = (round(m.ceil(m.log2(len(self._select)) / 2) + 5, -1) // bib) * bib
        bitsum = 0
        res = bytearray()
        res.append(block_size)
        for i, val in enumerate(self._select):
            bitsum += val
            if bitsum == block_size:
                bits = bin(i)[2:].rjust(32, "0")
                for j in range(0, len(bits), 8):
                    res.append(int(bits[j : j + 8], 2))
                bitsum = 0
                if len(res) >= 1024:
                    with io.open(self.s_sb_file, "ab") as f:
                        f.write(res)
                        f.close()
                    res.clear()
                    bits = ""

        if bitsum > 0:
            bits = bin(i)[2:].rjust(32, "0")
            for j in range(0, len(bits), 8):
                res.append(int(bits[j : j + 8], 2))
        if len(res) > 0:
            with io.open(self.s_sb_file, "ab") as f:
                f.write(res)
                f.close()

    def __str__(self):
        return str(self.root)


def make_trie(filename, collection, reversed=False):
    """Load a tree from a file.
    The file should contain one word per line along with the word id.
    Saving the trie and associated data to files in frozen folder.
    """
    trie = Trie(collection, reversed=reversed)
    trie.make_frozen_data(filename=filename)


if __name__ == "__main__":
    args = ARG_PARSER.parse_args()

    if args.file is not None and args.collection is not None:
        make_trie(
            filename=args.file, collection=args.collection, reversed=args.reversed
        )
    else:
        ARG_PARSER.print_help()
