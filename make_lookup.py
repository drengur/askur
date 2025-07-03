#! /usr/bin/env python3

"""Make lookup tables for the trie.
Virkar eins og make_bin_trie, nema að það er bara
listi yfir orð id og ekkert annað.
"""

import io
# import sys

# import sys
import os
import argparse
import math as m

# import threading
# from multiprocessing import Process
# import configparser


ARG_PARSER = argparse.ArgumentParser(description="Make lookup tables for the trie.")
ARG_PARSER.add_argument("--filename", "-f", type=str, help="The filename to read from.")
ARG_PARSER.add_argument(
    "--collection", "-c", type=str, help="The name of the collection to create."
)


class Node:
    """A node in a tree."""

    FORWARD_WORD = 1
    REVERSE_WORD = 2
    BOTH_WAY = 3

    def __init__(self, alphabet=None):
        self.end = False
        self.value_ids = []
        self.index = []
        self.alphabet = bytearray()
        if alphabet is None:
            alphabet = "123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -"
        for item in alphabet:
            self.alphabet.append(ord(item))
        self.alphabet.append(129)

        self.letters = [None] * len(self.alphabet)
        self.has_children = False
        self.fw = 0
        self.bw = 0
        self.letters = [None] * len(self.alphabet)


class Trie:
    """A trie."""

    def __init__(self, collection_name=None):
        """Create a new trie and associated files.
        usage:
            trie = Trie()
            trie.make_frozen_data()
        """
        # p = configparser.ConfigParser()
        # p.read("config.ini")

        self._trie = bytearray()  # the LOUDS representation of the trie
        self._hc = []  # the head child array (1 if the node has a child, 0 otherwise)
        self._select = []  # the select array (the index of the node in the LOUDS array)
        self._is_eow = []  # the value array (is the end of the word)
        self._index = []  # the counter array (the number of words that have been added to the trie)
        self._short_text = []  # the short text array (the words in the trie)
        self._data_values = {}
        self._fat_value = []
        self.collection_name = collection_name
        self.alphabet = Node().alphabet  # the alphabet used in the trie

        confs = {}
        with open("trie.conf", "r") as f:
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

        self.root = Node()  # the root node of the trie

    def make_frozen_data(self, filename=None):
        """Make the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays."""

        # if filename is None:
        #     filename = self.trie_data_file
        print(f"1 - Reading from file {filename}, \n making trie...")
        nr_lines_in_file = sum(1 for line in open(filename))
        print(f"Number of lines in file: {nr_lines_in_file}")

        self._data_values = {}
        index = 0
        line_nr = 0
        fw = 1  # forward direction
        # bw = 2  # backward direction
        is_reverse = self.collection_name.startswith("__")

        print(f"Is reverse: {is_reverse}")

        for line in self.read_from_file(filename):
            line_nr += 1
            if line_nr % 1000 == 0:
                print(f"Reading {line_nr / nr_lines_in_file * 100:.2f}%", end="\r")
            line_split = line.strip().split(";", 1)
            word_key = line_split[0].strip()
            if word_key.startswith("#") or word_key.startswith("\n"):
                continue
            if not word_key:
                print(f" No key found in line {line_nr}.\n Skipping line.")
                continue
            word_value = None if len(line_split) == 1 else line_split[1].strip()
            if word_value is None:
                print(
                    f"Error: in line {line_nr}, key:'{word_key}'.\n  No value.\n  Please add missing values and try again. \n Exiting."
                )
                return
            if is_reverse:
                key = self.modify_word(word_key[::-1])
            else:
                key = self.modify_word(word_key)
            if word_value not in self._data_values:
                index = len(self._data_values)
                # Use setdefault to avoid storing duplicate values and save memory
                self._data_values.setdefault(word_value, index)
            else:
                index = self._data_values[word_value]
            self._add(key, index, fw)

            for c in key:
                if c > 255:
                    continue
                if c not in self.alphabet:
                    self.alphabet.append(c)

        print("\n ")
        print("writing do disk...")

        print("2 - Making binary tree (trie)")
        self.make_tree()
        self.write_tree_to_file(self.trie_file, "wb")
        del self._trie

        print("2a - Processing eow values")
        self.write_eow_values_to_file(self.value_bits_filename, "wb")

        # print("2b -make value_bits_sum_file")
        self.write_eow_sums_to_file(self.eow_sb)

        print("3 - Process HC")
        self.write_hc_to_file(self.hc_bits_filename)
        self.hc_to_lookup()

        self.write_select_to_file(self.select_bits_filename)
        self.select_to_lookup()

        print("5 - Process SHORT_TEXT")
        with io.open(self.short_text_bits_filename, "w", encoding="utf-8") as f:
            f.write("")
        self.write_short_text_to_file(self.short_text_bits_filename, "wb")

        print("6 - write alphabet to file")
        with io.open(self.trie_file + ".alphabet", "wb") as f:
            f.write(self.alphabet)

    def read_from_file(self, filename):
        """Read a file line by line."""
        file = io.open(filename, "r", encoding="utf-8")
        for line in file:
            yield line
        file.close()

    def modify_word(self, word):
        res = bytearray()
        for c in word:
            if ord(c) > 255:
                bits = bin(ord(c))[2:].rjust(32, "0")
                res.append(129)
                for i in range(0, 32, 8):
                    res.append(int(bits[i : i + 8], 2))
            else:
                res.append(ord(c))
        return res

    def _add(self, word, index_id, direction=1):
        """Add a word to the trie."""
        node = self.root
        for i, ch in enumerate(word):
            node.has_children = True
            if ch not in node.alphabet:
                node.alphabet.append(ch)
            idx = node.alphabet.index(ch)
            while len(node.letters) <= idx:
                node.letters.append(None)
            if node.letters[idx] is None:
                node.letters[idx] = Node()
                if i < len(word) - 1:
                    node.letters[idx].has_children = True
                node.letters[idx].ord = ch
            node = node.letters[idx]

        node.end = True
        if direction == 1:
            node.fw = 1
        else:
            node.bw = 2
        if index_id not in node.index:
            node.index.append(index_id)

    def make_tree(self, node=None):
        """the level out trie."""
        self._to_tree([self.root])

    def _to_tree(self, nodes):
        if len(nodes) == 0:
            return
        child_nodes = []
        for node in nodes:
            first = 1
            for letter in node.letters:
                if letter is None:
                    continue
                self._trie.append(letter.ord)
                self._select.append(first)
                first = 0
                self._hc.append(1 if letter.has_children else 0)
                if letter.end:
                    self._is_eow.append(1)
                    self._fat_value.append(bin(letter.fw + letter.bw)[2:].rjust(2, "0"))
                    self._index.append(letter.index)
                else:
                    self._is_eow.append(0)
                    self._fat_value.append("00")
                child_nodes.append(letter)
        self._to_tree(child_nodes)

    def write_tree_to_file(self, filename, write_method="wb"):
        """Write the LOUDS representation of the trie to a file."""
        with io.open(filename, write_method) as f:
            f.write(self._trie)
            f.close()

    def get_hc(self):
        """Return the head child array."""
        return "".join(str(hc) for hc in self._hc) + "0" * (8 - len(self._hc) % 8)

    def write_hc_to_file(self, filename):
        """Write the head child array to a file."""
        with io.open(filename, "bw") as f:
            f.write(self.bit_bytes_to_bits(self.get_hc()))
            f.close()

    def get_select(self) -> str:
        """Return the select array."""
        return "".join(str(s) for s in self._select) + "1" * (8 - len(self._select) % 8)

    def write_select_to_file(self, filename):
        """Write the select array to a file."""
        with io.open(filename, "bw") as f:
            f.write(self.bit_bytes_to_bits(self.get_select()))
            f.close()

    def write_eow_values_to_file(self, filename, write_method="wb"):
        """Write the value array to a file."""
        with io.open(filename, write_method) as f:
            f.write(self.bit_bytes_to_bits(self.get_eow_values()))
            f.close()

        with io.open(self.value_bits_filename + ".fat", "wb") as f:
            f.write(self.bit_bytes_to_bits(self.get_fat_values()))
            f.close()

    def get_eow_values(self):
        """Return the value array (is_end_of_word)."""
        if not self._is_eow:
            return ""
        return "".join(
            [
                "1" if (c == Node.BOTH_WAY or c == Node.FORWARD_WORD) else "0"
                for c in self._is_eow
            ]
        )

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


    def write_short_text_to_file(self, filename, write_method="ab"):
        """Write the short text array to a file."""

        # Hérna snúum við data_values svo að röðin sé lykill og lykill sé value
        # Þetta er gert til að matcha staðsetningu self._index í Trie við data_values
        tmp_short_text = {}
        total_sum = 0
        max_tmp_short_text = 0
        for n, item in enumerate(self._data_values):
            modified_item = self.modify_word(item)
            tmp_short_text[n] = modified_item

            total_sum += len(modified_item)
            if len(modified_item) > max_tmp_short_text:
                max_tmp_short_text = len(modified_item)

        # byte_length er hægt að nota til að skipta út fyrir 32-bita lengdina
        nr_bytes_in_index_block = (
            len(bin(total_sum)[2:]) // 8 + (1 if len(bin(total_sum)[2:]) % 8 else 0) + 1
        )
        # nr_bytes_in_value_block er hægt að nota til að skipta út fyrir 16 bita lengdina
        nr_bytes_in_value_block = len(bin(max_tmp_short_text)[2:]) // 8 + (
            1 if len(bin(max_tmp_short_text)[2:]) % 8 else 0
        )

        nr_bits_in_index_block = nr_bytes_in_index_block * 8  # 32
        # nr_bits_in_value_block = nr_bytes_in_value_block * 8  # 16

        # athuga lengd á tmp_short_text, s.s. spurning hvort að það séu mörg gildi fyrir sama key-index
        max_text_len = 0
        for idxs in self._index:
            if len(idxs) > 1:
                text_len = 0
                for idx in idxs:
                    text_len += len(tmp_short_text[idx]) + 1
                if text_len > max_text_len:
                    max_text_len = text_len
        if max_text_len > 0:
            nr_bytes_in_value_block = len(bin(max_text_len)[2:]) // 8 + (
                1 if len(bin(max_text_len)[2:]) % 8 else 0
            )
            nr_bits_in_value_block = nr_bytes_in_value_block * 8

        n = 0
        short_texts = []
        sum_index = 0
        tmp_indices = []
        indices = {}
        for idxs in self._index:
            multi_text = []
            for idx in idxs:
                if len(idxs) == 1:
                    if idx not in indices:
                        short_texts.append(tmp_short_text[idx])
                        value = bin(sum_index)[2:].rjust(
                            nr_bits_in_index_block, "0"
                        ) + bin(len(tmp_short_text[idx]))[2:].rjust(
                            nr_bits_in_value_block, "0"
                        )
                        indices[idx] = value
                        tmp_indices.append(value)
                        sum_index += len(tmp_short_text[idx])

                    else:
                        tmp_indices.append(indices[idx])
                else:
                    multi_text.append(tmp_short_text[idx])
            if len(multi_text) > 1:
                tmp_txt = []
                for mtx in multi_text:
                    if len(tmp_txt) == 0:
                        tmp_txt = mtx.copy()
                    else:
                        tmp_txt.append(141)
                        tmp_txt += mtx.copy()
                idx_n = len(tmp_short_text)
                short_texts.append(tmp_txt)
                value = bin(sum_index)[2:].rjust(nr_bits_in_index_block, "0") + bin(
                    len(tmp_txt)
                )[2:].rjust(nr_bits_in_value_block, "0")
                indices[idx_n] = []  # value
                tmp_indices.append(value)
                sum_index += len(tmp_txt)

        with io.open(self.index_bits_filename, "wb") as f:
            f.write(
                self.bit_bytes_to_bits(
                    bin(nr_bytes_in_index_block)[2:].rjust(8, "0")
                    + bin(nr_bytes_in_value_block)[2:].rjust(8, "0")
                    + "".join([txt for txt in tmp_indices])
                )
            )
            f.close()

        with io.open(filename, "wb") as f:
            for item in short_texts:
                f.write(item)
            f.close()

    def get_fat_values(self):
        return "".join([val for val in self._fat_value])

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
            # s_bytes = s_bytes.ljust(len(s_bytes) + (8 - len(s_bytes) % 8), "0")
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
        res = bytearray()
        bitsum = 0
        index = 0
        max_value = 0
        for i, val in enumerate(self._hc):
            bitsum += val
            index += 1
            if index == block_size:
                bits = bin(bitsum)[2:].rjust(32, "0")
                for j in range(0, len(bits), 8):
                    res.append(int(bits[j : j + 8], 2))
                index = 0
        if bitsum > 0:
            max_value = max(max_value, bitsum)
            bits = bin(bitsum)[2:].rjust(32, "0")
            for j in range(0, len(bits), 8):
                res.append(int(bits[j : j + 8], 2))
        with io.open(self.hc_sb_file, "wb") as f:
            f.write(res)
            f.close()

    def select_to_lookup(self):
        bib = 8
        block_size = (round(m.ceil(m.log2(len(self._select)) / 2) + 5, -1) // bib) * bib
        bitsum = 0
        res = bytearray()
        res.append(block_size)
        max_val = 0
        for i, val in enumerate(self._select):
            bitsum += val
            if bitsum == block_size:
                bits = bin(i)[2:].rjust(32, "0")
                max_val = max(max_val, i)
                for j in range(0, len(bits), 8):
                    res.append(int(bits[j : j + 8], 2))
                bitsum = 0
        if bitsum > 0:
            bits = bin(i)[2:].rjust(32, "0")
            for j in range(0, len(bits), 8):
                res.append(int(bits[j : j + 8], 2))
        with io.open(self.s_sb_file, "wb") as f:
            f.write(res)
            f.close()

    def __str__(self):
        return str(self.root)


def make_trie(filename, collection):
    """Load a tree from a file.
    The file should contain one word per line along with the word id.
    Saving the trie and associated data to files in frozen folder.
    """
    trie = Trie(collection)
    trie.make_frozen_data(filename)


if __name__ == "__main__":
    args = ARG_PARSER.parse_args()
    if args.filename is not None and args.collection is not None:
        make_trie(filename=args.filename, collection=args.collection)
        make_trie(filename=args.filename, collection="__" + args.collection)
    else:
        ARG_PARSER.print_help()
