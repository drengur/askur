#! /usr/bin/env python3

"""Make lookup tables for the trie.
Virkar eins og make_bin_trie, nema að það er bara
listi yfir orð id og ekkert annað.
"""

import io
import os
import argparse
import math as m


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
    """A node in a tree."""

    def __init__(self):
        self.end = False
        self.index = []
        self.letters = {}
        self.has_children = False


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
        self.reversed = reversed
        
        # The alphabet order used in the trie.
        alphabet = "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -"
        # self.alphabet = {}
        self.used_alphabet = []  # used alphabet is empty at the start and gets filled as words are added
        self.prepare_alphabet(alphabet)

        confs = {}
        with open("askur.conf", "r") as f:
            for line in f:
                if line.startswith("#") or line.startswith("\n"):
                    continue
                if "=" not in line:
                    print(
                        f"Error: in line {line}.\n  No '=' found.\n  Please add missing '=' and try again. \n Exiting."
                    )
                    return
                confs[line.split("=")[0].strip()] = line.split("=")[1].strip()
        DATA_FOLDER = confs.get("DATA_FOLDER")
        if DATA_FOLDER is None:
            print(
                f"Error: in line {line}.\n  No DATA_FOLDER found.\n  Please add missing DATA_FOLDER and try again. \n Exiting."
            )
            return

        # save the trie data to files
        # if collection_name is not None:
        if collection_name is None:
            print("No collection name provided. \n  Exiting.")
            return

        this_folder = os.path.dirname(os.path.abspath(__file__))

        FROZEN_FOLDER = os.path.join(this_folder, DATA_FOLDER, collection_name)

        os.makedirs(FROZEN_FOLDER, exist_ok=True)

        self.select_bits_filename = os.path.join(FROZEN_FOLDER, "s_bits.bin")

        self.trie_file = os.path.join(FROZEN_FOLDER, "trie")

        self.index_bits_filename = os.path.join(FROZEN_FOLDER, "index_bits.bin")
        self.hc_bits_filename = os.path.join(FROZEN_FOLDER, "hc_bits.bin")

        self.value_bits_filename = os.path.join(FROZEN_FOLDER, "eow_bits.bin")

        self.short_text_bits_filename = os.path.join(
            FROZEN_FOLDER, "short_text_bits.bin"
        )

        # end of word super block file
        self.eow_sb = os.path.join(FROZEN_FOLDER, "eow_sb.bin")

        # hc superblock
        self.hc_sb_file = os.path.join(FROZEN_FOLDER, "hc_sb.bin")
        # select superblock
        self.s_sb_file = os.path.join(FROZEN_FOLDER, "s_sb.bin")

        self.root = Node()  # the root node of the

    def prepare_alphabet(self, init_alphabet):
        """Prepare the alphabet for the trie."""
        if not isinstance(init_alphabet, str) and not isinstance(init_alphabet, list):
            raise ValueError("Alphabet must be a string or a list of characters.", type(init_alphabet), init_alphabet)

        self.alphabet = {ord(item): n for n, item in enumerate(init_alphabet)}
        self.used_alphabet = []  # used alphabet is empty at the start
        multibyte_char = 129
        reversed_char = 143  # This is a character that is not in the alphabet
        self.alphabet.setdefault(multibyte_char, len(self.alphabet))
        if self.reversed:
            self.alphabet.setdefault(reversed_char, len(self.alphabet))
            self.used_alphabet.append(reversed_char)

    # @property
    # def alphabet(self):
    #     return self.alphabet()

    # @alphabet.setter
    # def alphabet(self, alphabet):
    #     self.prepare_alphabet(alphabet)

    def make_frozen_data(self, filename=None):
        """Make the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays."""

        print(f" Reading from file {filename}")
        nr_lines_in_file = sum(1 for line in open(filename))
        print(f" Number of lines in file: {nr_lines_in_file}")

        data_values = {}
        index = 0
        line_nr = 0

        for line in self.read_from_file(filename):
            line_nr += 1
            if line_nr % 1000 == 0:
                print(f"Reading {line_nr / nr_lines_in_file * 100:.2f}%", end="\r")
            line_split = line.strip().split(";", 1)
            word_key = line_split[0].strip()
            if word_key.startswith("#") or word_key.startswith("\n"):
                continue
            if not word_key:
                continue
            word_value = None if len(line_split) == 1 else line_split[1].strip()
            if word_value is None:
                print(
                    f"Error: in line {line_nr}, key:'{word_key}'.\n  No value.\n  Please add missing values and try again. \n Exiting."
                )
                return
            key = self.modify_word(word_key)

            if word_value not in data_values:
                index = len(data_values)
                # Use setdefault to avoid storing duplicate values and save memory
                data_values.setdefault(word_value, index)
            else:
                index = data_values[word_value]
            self._add(key, index)
            if self.reversed:
                # If reversed, we add the word in reverse order
                key.reverse()
                key.insert(0, 143)
                self._add(key, index)

        self.inv_alphabet = {v: k for k, v in self.alphabet.items()}

        print(" 1/7 - Writing to file...", end="\r")
        self.level_order_tree([self.root])
        print(" 2/7 - Writing to file...", end="\r")
        self.write_tree_to_file()
        del self._trie

        print(" 3/7 - Writing to file...", end="\r")
        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_sums_to_file(self.eow_sb)

        print(" 4/7 - Writing to file...", end="\r")
        self.write_hc_to_file(self.hc_bits_filename)
        self.hc_to_lookup()

        print(" 5/7 - Writing to file...", end="\r")
        self.write_select_to_file(self.select_bits_filename)
        self.select_to_lookup()

        print(" 6/7 - Writing to file...", end="\r")
        # inverting data_values so that the key is the value and the value is the key
        inv_data_values = {v: self.modify_word(k) for k, v in data_values.items()}
        self.write_short_text_to_file(inv_data_values)

        print(" 7/7 - Writing to file...", end="\r")
        alphabet_bytes = bytearray()
        for k in self.used_alphabet:
            # if k in self.used_alphabet:
            alphabet_bytes.append(k)
        with io.open(self.trie_file + ".alphabet", "wb") as f:
            f.write(alphabet_bytes)

    def read_from_file(self, filename):
        """Read a file line by line."""
        file = io.open(filename, "r", encoding="utf-8")
        for line in file:
            yield line
        file.close()

    def modify_word(self, word):
        res = bytearray()
        for c in word:
            if ord(c) not in self.used_alphabet:
                self.used_alphabet.append(ord(c))

            if ord(c) not in self.alphabet.keys():
                # update the alphabet with the new character
                idx = len(self.alphabet)
                self.alphabet.setdefault(ord(c), idx)

            if ord(c) > 255:
                bits = bin(ord(c))[2:].rjust(32, "0")
                res.append(129)
                for i in range(0, 32, 8):
                    num = int(bits[i : i + 8], 2)
                    res.append(num)
                    if num not in self.alphabet.keys():
                        idx = len(self.alphabet)
                        self.alphabet.setdefault(num, idx)
            else:
                res.append(ord(c))
        return res

    def _add(self, word, index_id):
        """Add a word to the trie."""
        node = self.root
        for i, ch in enumerate(word):
            idx = self.alphabet.get(ch)
            if node.letters.get(idx):
                node = node.letters[idx]
            else:
                node.letters[idx] = Node()
                node = node.letters[idx]
            if i < len(word) - 1:
                node.has_children = True
        if index_id not in node.index:
            node.index.append(index_id)
        node.end = True

    def level_order_tree(self, nodes):
        """Level out trie.
        Traverse the trie in level order and write to the _trie, _hc,
        _select, _is_eow and _index arrays.
        """
        if len(nodes) == 0:
            return
        child_nodes = []
        for node in nodes:
            first = 1
            for letter_key in sorted(node.letters.keys()):
                self._trie.append(self.inv_alphabet.get(letter_key))
                self._select.append(first)
                first = 0
                self._hc.append(1 if node.letters[letter_key].has_children else 0)
                if node.letters[letter_key].end:
                    self._is_eow.append(1)
                    self._index.append(node.letters[letter_key].index)
                else:
                    self._is_eow.append(0)
                child_nodes.append(node.letters[letter_key])
        self.level_order_tree(child_nodes)

    def generate_data(self, big_string):
        """Generate data from a big string in chunks to mimize memory usage."""
        # This function is a placeholder for generating data.
        i = 0
        chunk_size = 1024
        while i < len(big_string):
            yield big_string[i : i + chunk_size]
            i += chunk_size

    def write_tree_to_file(self):
        """Write level ordered trie to a file."""
        with io.open(self.trie_file, "w") as f:
            f.write("")
            f.close()
        with io.open(self.trie_file, "ab") as f:
            for chunk in self.generate_data(self._trie):
                f.write(chunk)
            f.close()

    def write_hc_to_file(self, filename):
        """Write the head child array to a file."""
        with io.open(filename, "w") as f:
            f.write("")
            f.close()

        buffer = bytearray()  # Buffer to hold bytes before writing to file
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
        with io.open(filename, "w") as f:
            f.write("")
            f.close()
        # Það þarf að bæta við 1 í enda á select fylkinu til að geta staðsett síðasta bókstafinn í trie-skránni
        # Að öðrum kosti finnst ekki verður select útreikningurinn óendanlegur
        self._select.append(1)  # Pad with 1 to make it a multiple
        buffer = bytearray()  # Buffer to hold bytes before writing to file
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
        with io.open(filename, "w") as f:
            f.write("")
            f.close()

        buffer = bytearray()  # Buffer to hold bytes before writing to file
        i = 0
        extra_bits = len(self._is_eow) % 8
        if extra_bits > 0:
            for _ in range(8 - extra_bits):
                self._is_eow.append(0)  # Pad with zeros to make it a multiple of 8 bits
        while i < len(self._is_eow):
            buffer.append(int("".join([str(c) for c in self._is_eow[i : i + 8]]), 2))
            i += 8
            if len(buffer) >= 10240:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()  # Clear the buffer to free memory
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)
                f.close()

    def write_eow_sums_to_file(self, filename):
        # bits in block = 32
        # sum of "1"-bits in a block of 32 bits
        with io.open(filename, "w") as f:
            f.write("")

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

    def write_short_text_to_file(self, inv_data_values):
        """Write the short text array to a file."""
        with io.open(self.short_text_bits_filename, "w", encoding="utf-8") as f:
            f.write("")
            f.close()

        with io.open(self.index_bits_filename, "w") as f:
            f.write("")
            f.close()

        # Hérna snúum við data_values svo að röðin sé lykill og lykill sé value
        # Þetta er gert til að matcha staðsetningu self._index í Trie við data_values
        # inv_data_values = {}
        total_sum = 0
        max_tmp_short_text = 0

        for _, value in inv_data_values.items():
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
                text_len += len(inv_data_values[idx]) + 1
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
                        short_texts.append(inv_data_values[idx])
                        value = bin(sum_index)[2:].rjust(
                            nr_bits_in_index_block, "0"
                        ) + bin(len(inv_data_values[idx]))[2:].rjust(
                            nr_bits_in_value_block, "0"
                        )
                        indices[idx] = value
                        tmp_indices.append(value)
                        sum_index += len(inv_data_values[idx])

                    else:
                        tmp_indices.append(indices[idx])
                else:
                    multi_text.append(inv_data_values[idx])
            if len(multi_text) > 1:
                tmp_txt = []
                for mtx in multi_text:
                    if len(tmp_txt) == 0:
                        tmp_txt = mtx.copy()
                    else:
                        tmp_txt.append(141)  # separator between words/sentences
                        tmp_txt += mtx.copy()
                idx_n = len(inv_data_values)
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
        """Convert bytes from select and range directory (files) to bits.
        files contain only 0 and 1, but are stored as bytes in the file.
        Now we need to convert  the 'bit-bytes' to bits to compress their size.
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
        with io.open(self.hc_sb_file, "w") as f:
            f.write("")
            f.close()

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
        with io.open(self.s_sb_file, "w") as f:
            f.write("")
            f.close()

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
