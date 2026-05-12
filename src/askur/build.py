#! /usr/bin/env python3

"""Make lookup tables for the LOUDS trie
from input file
"""

import os
import sys
import io
import math as m
from dataclasses import dataclass
from askur.config import Config
from askur import alphabet
from askur import watchdog

# initialization of global variables
# Config is initialized at the start of the build process and contains the configuration
# for the build process, such as the alphabet and data folder.
CONFIG: Config = Config()

WD = watchdog.Watchdog()  # Watchdog to monitor system memory usage during build process
A: alphabet.Alphabet | None = alphabet.Alphabet


@dataclass(slots=True)
class Node:
    leaf_indices: tuple[int] = None
    letters: dict[int, "Node"] = None
    single_index: int = None

    @property
    def has_children(self) -> bool:
        return self.letters is not None

    @property
    def end(self) -> bool:
        # Is this node an end/leaf node? (end of word)
        return self.leaf_indices is not None or self.single_index is not None

    def get_child(self, key: int) -> "Node":
        """Get the child node for a given key. If the child node does not exist, create it."""
        if self.letters is None:
            self.letters = {}
        if key not in self.letters:
            self.letters[key] = Node()
        return self.letters[key]

    def add_index(self, idx: int) -> None:
        """Add an index to the end/leaf node.
        Leaf nodes can have multiple indices.
        Using single_index for single index to save memory.
        Args:
            idx: The index to add.
        Returns: None
        """
        if self.leaf_indices is None and self.single_index is None:
            self.single_index = idx
            return
        if self.single_index is not None:
            if self.single_index == idx:
                return
            self.leaf_indices = (self.single_index, idx)
            self.single_index = None
            return
        if idx not in self.leaf_indices:
            self.leaf_indices = (*self.leaf_indices, idx)

    def get_indices(self) -> list[int]:
        """Get the indices of the end/leaf node."""
        if self.leaf_indices is not None:
            return list(self.leaf_indices)
        if self.single_index is not None:
            return [self.single_index]
        return []


class Trie:
    """A trie."""

    def __init__(self, collection_name="", reversed=False, field_separator=";") -> None:
        """Creates a new trie with associated files.
        Writes the trie structure to disk in LOUDS format along with
        the head child array (HC), select array (S), end of word array (EOW),
        index array (INDEX), and short text array (SHORT_TEXT).

        usage:
            trie = Trie()
            trie.make_frozen_data()
        Args:
            reversed: If True, create a reversed index.
            collection_name: The name of the collection to create.
            field_separator: The field separator used in the input data.
        """

        self._trie = bytearray()  # the LOUDS representation of the trie
        self._hc = []  # the head child array (1 if the node has a child, 0 otherwise)
        self._select = []  # the select array (the index of the node in the LOUDS array)
        self._is_eow = []  # the value array (is the end of the word)
        self._index = []  # the counter array (the number of words that have been added to the trie)
        self._short_text = []  # the short text array (the words in the trie)
        self.collection_name: str = collection_name
        self.reversed: bool = reversed  # make reversed index if True
        self.field_separator = field_separator
        self.super_block_size: int = 0
        self.frozen_folder: str = ""

        # The alphabet used in the trie.
        self.alphabet = A()

        # Check for environment variable first, then fall back to config file
        data_folder: str | None = os.environ.get("ASKUR_DATA_FOLDER")
        if data_folder is None:
            print("DATA_FOLDER environment variable is not set.")
            sys.exit(1)

        if collection_name == "":
            print("Collection name is not set.")
            sys.exit(1)
        if len(collection_name.split(" ")) > 1:
            print("Collection name can not contain spaces.")
            sys.exit(1)

        self.frozen_folder: str = os.path.join(data_folder, self.collection_name)
        if not os.path.exists(self.frozen_folder):
            os.makedirs(self.frozen_folder, exist_ok=True)

        self.select_bits_filename = os.path.join(self.frozen_folder, "s_bits.bin")
        self.trie_file = os.path.join(self.frozen_folder, "trie")

        self.index_bits_filename = os.path.join(self.frozen_folder, "index_bits.bin")
        self.hc_bits_filename = os.path.join(self.frozen_folder, "hc_bits.bin")

        self.value_bits_filename = os.path.join(self.frozen_folder, "eow_bits.bin")

        self.short_text_bits_filename = os.path.join(
            self.frozen_folder, "short_text_bits.bin"
        )

        # end of word super block file
        self.eow_sb = os.path.join(self.frozen_folder, "eow_sb.bin")

        # hc superblock
        self.hc_sb_file = os.path.join(self.frozen_folder, "hc_sb.bin")

        # select superblock
        self.s_sb_file = os.path.join(self.frozen_folder, "s_sb.bin")

        self.data_file = os.path.join(self.frozen_folder, "data.bin")

        io.open(self.s_sb_file, "w").close()
        io.open(self.hc_sb_file, "w").close()
        io.open(self.eow_sb, "w").close()

        io.open(self.value_bits_filename, "w").close()
        io.open(self.hc_bits_filename, "w").close()
        io.open(self.trie_file, "w").close()
        io.open(self.select_bits_filename, "w").close()
        io.open(self.index_bits_filename, "w").close()
        io.open(self.short_text_bits_filename, "w").close()
        io.open(self.short_text_bits_filename + ".length", "w").close()
        io.open(self.trie_file + ".alphabet", "w").close()

    def make_frozen_data(self, input_data: str, statusbar=False) -> None:
        """Make the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays from the input data.
        Args:
            input_data: The input data as a string.
        Returns: None
        """
        try:
            WD.start(statusbar)  # Start the watchdog to monitor system memory usage during the build process
            data_values_gen: tuple[bytes] = self.make_trie(input_data)
            bytes_per_indexblock: int = self.write_frozen_data(data_values_gen)
            self.merge_data_files(bytes_per_indexblock)
        except (KeyboardInterrupt, SystemExit):
            print("Build process interrupted. Exiting gracefully.")
        except Exception as e:
            print(f"An error occurred during the build process: {e}")
        finally:
            WD.stop()

    def make_trie(self, input_data: str) -> tuple[bytes]:
        """Returns a generator that yields the data values in the same order as the indices in the trie."""

        io.open(self.data_file, "w").close()

        data_values: dict[str, int] = {}
        index: int = -1
        key: bytes = None
        next_index: int = -1
        root = Node()
        for word_key, word_value in self.read_from_input(input_data):
            if word_value not in data_values:
                next_index += 1
                data_values[word_value] = next_index
                index = next_index
            else:
                index = data_values[word_value]
            key = self.alphabet.convert_str_to_bytes(word_key)
            self._add(key, index, root)

        WD.clear_label()
        WD.print_label(" Writing to disk...")
        self.level_order_tree([root])

        # return tuple-generator(data_values) to save memory, instead of creating a list of all data values in memory
        return (self.alphabet.convert_str_to_bytes(k) for k, _ in data_values.items())

    def write_frozen_data(self, data_values_gen: tuple[bytes, None, None]) -> None:
        """Write the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays to disk.
        Args:            data_values_gen: A generator that yields the data values in the same order as the indices in the trie.
        Returns: None
        """
        self.write_tree_to_file()

        self.write_select_to_file(self.select_bits_filename)
        self.super_block_size = self.select_to_superblock()

        self.write_hc_to_file(self.hc_bits_filename)
        self.hc_to_superblock()

        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_sums_to_file(self.eow_sb)

        bytes_per_indexblock: int = self.write_short_text_to_file(data_values_gen)
        return bytes_per_indexblock

    def merge_data_files(self, bytes_per_indexblock: int) -> None:
        """
        Merge the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT files into a single data file.
        The first 4 bytes of the data file will contain the number of bytes used for the index block (short text index).
        The next 4 bytes will contain the super block size used for the select superblock and hc superblock.
        The following 4 bytes will contain the number of bytes used for the index block (short text index).
        """

        with io.open(self.trie_file + ".alphabet", "wb") as f:
            f.write(self.alphabet.get_used)
        WD.clear_label()

        bytes_per_info: int = 4
        start_bytes = [int.to_bytes(0, bytes_per_info, "big") for _ in range(30)]
        start_bytes[0] = int.to_bytes(bytes_per_info, bytes_per_info, "big")
        start_bytes[1] = int.to_bytes(self.super_block_size, bytes_per_info, "big")
        start_bytes[2] = int.to_bytes(bytes_per_indexblock, bytes_per_info, "big")

        with io.open(self.data_file, "ab") as f:
            f.write(b"".join(start_bytes))

        next_start: list[int] = [os.path.getsize(self.data_file)]
        start_bytes[3] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.trie_file + ".alphabet")

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[4] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.trie_file)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[5] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.select_bits_filename)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[6] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.s_sb_file)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[7] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.hc_bits_filename)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[8] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.hc_sb_file)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[9] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.value_bits_filename)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[10] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.eow_sb)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[11] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.index_bits_filename)

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[12] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.short_text_bits_filename + ".length")

        next_start.append(os.path.getsize(self.data_file))
        start_bytes[13] = int.to_bytes(next_start[-1], bytes_per_info, "big")
        self.merge_files(self.data_file, self.short_text_bits_filename)

        # length of short text
        start_bytes[14] = int.to_bytes(
            os.path.getsize(self.short_text_bits_filename), bytes_per_info, "big"
        )

        with io.open(self.data_file, "rb+") as f:
            f.seek(0)
            f.write(b"".join(start_bytes))

        self.remove_build_files()

    def split_line(self, line: str) -> tuple[str, str]:
        """Split a line into key and value based on the field separator."""
        esc: bool = False
        key: str = ""
        value: str = ""
        for i, c in enumerate(line):
            if c == "\\":
                esc = not esc
                continue
            if c == self.field_separator and not esc:
                value = line[i + 1 :]
                break
            key += c
            esc = False

        return key, value

    def read_from_input(self, input_data: str) -> tuple[str, str]:
        """Read a file line by line."""
        nr_cols: int = 0
        line_nr: int = 0
        line_count: int = 0

        if input_data != sys.stdin:
            with io.open(input_data.name, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
        with (
            io.open(input_data.name, "r", encoding="utf-8")
            if input_data != sys.stdin
            else sys.stdin as f
        ):
            for line in f:
                line_nr += 1
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if nr_cols == 0:
                    nr_cols = line.count(self.field_separator) + 1

                word_key, word_value = self.split_line(line.strip())
                if nr_cols == 2 and word_value == "":
                    print(
                        f"\n{'*' * 50}\n  Missing word value for {word_key}: {word_value}, line {line_nr}\n  Exiting\n{'*' * 50}"
                    )
                    sys.exit(1)
                if nr_cols == 1 and word_value != "":
                    print(
                        f"\n{'*' * 50}\n  Unexpected word value for '{word_key}': {word_value}, line {line_nr}\n  Expected one column, got two.\n  Exiting \n{'*' * 50}"
                    )
                    sys.exit(1)
                if word_key == "":
                    print(
                        f"\n{'*' * 50}\n  Missing key in line {line_nr}\n  Exiting\n{'*' * 50}"
                    )
                    sys.exit(1)
                if line_count > 0 and line_nr % 1000 == 0:
                    WD.print_label(
                        f"  {line_nr / line_count * 100:.1f}% of lines processed"
                    )

                yield word_key, word_value or "1"

    def _add(self, word: bytearray, index_id: int, root: Node) -> None:
        """Add a word to the trie."""
        node: Node = root
        for ch in word:
            node = node.get_child(self.alphabet.get_alphabet_index(ch))
        node.add_index(index_id)

    def sorted_trie_range(self, node: Node) -> None:
        """Get the sorted range of letters in the trie node.
        so that we always traverse the trie in alphabetical order (unless reversed).
        Args:
            node: The trie node.
        """
        if node.letters is None:
            return []
        if self.reversed:
            return node.letters.keys()
        return sorted(node.letters.keys())

    def level_order_tree(self, root: list[Node]) -> None:
        """Level out trie.
        Traverse the trie in level order and write to the _trie, _hc,
        _select, _is_eow and _index arrays.
        """
        stack: Node = root
        child_nodes: list[Node] = []
        first: int = 1
        while stack:
            for node in stack:
                first = 1
                for w_key in self.sorted_trie_range(node):
                    self._trie.append(self.alphabet.inv_alphabet.get(w_key))
                    self._select.append(first)
                    first = 0
                    self._hc.append(1 if node.letters[w_key].has_children else 0)
                    if node.letters[w_key].end:
                        self._is_eow.append(1)
                        self._index.append(node.letters[w_key].get_indices())
                    else:
                        self._is_eow.append(0)
                    child_nodes.append(node.letters[w_key])
            stack = child_nodes[:]
            child_nodes.clear()

    def generate_data(self, big_string: bytearray) -> bytearray:
        """Generate data from a big string in chunks to minimize memory usage.
        This function is a placeholder for generating data.
        """
        i: int = 0
        chunk_size: int = 1024
        while i < len(big_string):
            yield big_string[i : i + chunk_size]
            i += chunk_size

    def write_tree_to_file(self) -> None:
        """Write level ordered trie to a file."""
        with io.open(self.trie_file, "ab") as f:
            for chunk in self.generate_data(self._trie):
                f.write(chunk)
            f.close()

    def write_hc_to_file(self, filename: str) -> None:
        """Write the head child array to a file."""
        buffer: bytearray = bytearray()  # Buffer to hold bytes before Writing to disk
        i: int = 0

        nr_extra_bits: int = len(self._hc) % 8
        self._hc.extend([0 for _ in range(8 - nr_extra_bits)])

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

    def write_select_to_file(self, filename: str) -> None:
        """Write the select array to a file."""

        self._select.append(1)  # Pad with 1 to mark end of last char range in trie
        buffer: bytearray = bytearray()  # Buffer to hold bytes before Writing to disk
        i: int = 0

        # Total lengt of select has to be a multiple of 8
        nr_extra_bits: int = len(self._select) % 8
        self._select.extend(0 for _ in range(8 - nr_extra_bits))

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

    def write_eow_values_to_file(self, filename: str) -> None:
        """Write the value array to a file."""
        buffer: bytearray = bytearray()  # Buffer to hold bytes before Writing to disk
        i: int = 0

        # Total lengt of is_eow has to be a multiple of 8
        nr_rest_bits: int = len(self._is_eow) % 8
        self._is_eow.extend([0 for _ in range(8 - nr_rest_bits)])

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

    def write_eow_sums_to_file(self, filename: str) -> None:
        """sum of "1"-bits in a block of 32 bits to a file."""

        bitsum: int = 0
        i: int = 0
        buffer: list[int] = []
        bits_in_block: int = 32
        bytes_in_block: int = 4
        # TODO : calculate bits_in_block and bytes_in_block based on size of self._is_eow to save space/speed up search
        for idx in range(0, len(self._is_eow)):
            bitsum += 1 if self._is_eow[idx] > 0 else 0
            i += 1
            if i == bits_in_block:
                i = 0
                buffer.append(bitsum)
                if len(buffer) >= 10240:
                    with io.open(filename, "ab") as fb:
                        for summa in buffer:
                            fb.write(summa.to_bytes(bytes_in_block, "big"))
                    buffer.clear()
        if bitsum:
            buffer.append(bitsum)
            with io.open(filename, "ab") as fb:
                for summa in buffer:
                    fb.write(summa.to_bytes(bytes_in_block, "big"))

    def write_short_text_to_file(self, data_values: tuple[bytes]) -> int:
        """Write the short text array to a file.
        Returns the index_byte length (block size) used to store the index values.
        """
        # from generator to tuple. to be able to do index search
        # and do calculations on the data_values
        data_values = tuple(data_values)

        if len(data_values) == 1:
            return 1

        # total length of all short texts
        total_short_len: int = sum(len(value) for value in data_values)

        # byte_length is minimum number of bytes needed to represent total_short_len
        byte_len: int = len(bin(total_short_len)[2:]) // 8 + (
            1 if len(bin(total_short_len)[2:]) % 8 else 0
        )

        short_texts: list[bytearray] = []
        sum_index: int = 0

        # short_text_index has same length and index reference as self._index
        # it points to the correct position of the resulting text value (the reusult)
        short_text_index: list[bytes] = []
        indices: dict[str, bytes] = {}
        short_text_values_length: list[int] = []

        for _, idxs in enumerate(self._index):
            multi_text = []
            for idx in idxs:
                if len(idxs) == 1:
                    if str(idx) not in indices:
                        byte_value = sum_index.to_bytes(byte_len, "big")
                        indices[str(idx)] = byte_value
                        short_text_index.append(byte_value)
                        short_texts.append(data_values[idx])
                        short_text_values_length.append(len(data_values[idx]))
                        sum_index += len(data_values[idx])
                    else:
                        short_text_values_length.append(len(data_values[idx]))
                        short_text_index.append(indices[str(idx)])
                else:
                    multi_text.append(data_values[idx])
            if len(multi_text) > 1:
                tmp_txt: bytearray = bytearray()
                for mtx in multi_text:
                    if len(tmp_txt) == 0:
                        tmp_txt = mtx[:]
                    else:
                        tmp_txt.append(141)
                        for c in mtx:
                            tmp_txt.append(c)
                idxs.sort()  # sort to make sure indexes are uniqe
                idxs_str = "_".join([str(i) for i in idxs])
                if idxs_str not in indices:
                    byte_value = sum_index.to_bytes(byte_len, "big")
                    indices[idxs_str] = byte_value
                    short_text_index.append(byte_value)
                    short_texts.append(tmp_txt)
                    short_text_values_length.append(len(tmp_txt))
                    sum_index += len(tmp_txt)
                else:
                    short_text_index.append(indices[idxs_str])
                    short_text_values_length.append(len(tmp_txt))
            if len(short_texts) >= 10240:
                with io.open(self.short_text_bits_filename, "ab") as fb:
                    for item in short_texts:
                        fb.write(item)
                short_texts.clear()

            if len(short_text_index) >= 10240:
                with io.open(self.index_bits_filename, "ab") as fb:
                    fb.write(b"".join(short_text_index))
                short_text_index.clear()

            if len(short_text_values_length) >= 10240:
                with io.open(self.short_text_bits_filename + ".length", "ab") as fb:
                    for item in short_text_values_length:
                        fb.write(item.to_bytes(2, "big"))
                short_text_values_length.clear()

        # don't forget to append the last sum_index,
        # othewise the last item in short text will have length of zero
        byte_value = sum_index.to_bytes(byte_len, "big")
        short_text_index.append(byte_value)
        with io.open(self.index_bits_filename, "ab") as fb:
            fb.write(b"".join(short_text_index))
        if len(short_texts) > 0:
            with io.open(self.short_text_bits_filename, "ab") as fb:
                for item in short_texts:
                    fb.write(item)

        if len(short_text_values_length) > 0:
            with io.open(self.short_text_bits_filename + ".length", "ab") as fb:
                for item in short_text_values_length:
                    fb.write(item.to_bytes(2, "big"))

        return byte_len

    def hc_to_superblock(self):
        """Writing to hc-superblock file"""

        nr_bytes: int = 4
        buffer: bytearray = bytearray()
        bitsum: int = 0
        index: int = 0
        for i, val in enumerate(self._hc):
            bitsum += val
            index += 1
            if index == self.super_block_size:
                byte_value = bitsum.to_bytes(nr_bytes, "big")
                buffer.extend(byte_value)
                index = 0

                if len(buffer) >= 1024:
                    with io.open(self.hc_sb_file, "ab") as fb:
                        fb.write(buffer)
                    buffer.clear()
        if index > 0:
            byte_value = bitsum.to_bytes(nr_bytes, "big")
            buffer.extend(byte_value)
        if len(buffer) > 0:
            with io.open(self.hc_sb_file, "ab") as fb:
                fb.write(buffer)

    def select_to_superblock(self) -> int:
        """Write the select superblock to a file.
        returns the block size used in bits for the select superblock and hc superblock.

        return block_size: int
        """
        # block size in bits has to be multiple of 8
        block_size: int = m.ceil(m.log2(len(self._select)) / 2) // 8 * 8
        block_size = max(8, block_size)

        bitsum: int = 0
        nr_bytes: int = 4
        buffer = bytearray()
        for i, val in enumerate(self._select):
            bitsum += val
            if bitsum == block_size:
                bytes = i.to_bytes(nr_bytes, "big")
                buffer.extend(bytes)
                bitsum = 0
                if len(buffer) >= 1024:
                    with io.open(self.s_sb_file, "ab") as f:
                        f.write(buffer)
                    buffer.clear()

        if bitsum > 0:
            bytes = i.to_bytes(nr_bytes, "big")
            buffer.extend(bytes)

        if buffer:
            with io.open(self.s_sb_file, "ab") as f:
                f.write(buffer)
        return block_size

    def make_reversed(self, statusbar=False) -> None:
        """Make a reversed trie from the original data."""
        try:
            WD.start(statusbar)
            WD.print_label(" Building reversed index...")
            self._make_reversed()
        except Exception as e:
            print(f"An error occurred during the build process: {e}")
        finally:
            WD.stop()


    def _make_reversed(self) -> None:
        """Make a reversed trie from the original data."""

        self.super_block_size = 0
        index_byte_len: int = 0
        short_text_len: int = 0
        root = Node()

        with io.open(self.data_file, "rb") as f_data:
            vals = f_data.read(1024)  # read first 1024 bytes
            self.super_block_size = int.from_bytes(vals[4:8], "big")
            index_byte_len = int.from_bytes(vals[8:12], "big")
            short_text_len = int.from_bytes(vals[52:56], "big")

        from askur.search import Search

        search: Search = Search(collection=self.collection_name)

        # All entries in the trie
        for items in search.exists("*"):
            for key, value in items.items():
                self._add(
                    self.alphabet.convert_str_to_bytes(key[::-1]), int(value), root
                )

        self.level_order_tree([root])

        # Translate self._index to short text indices used in the original trie
        if short_text_len > 0:
            with io.open(self.index_bits_filename, "wb") as f_index:
                f_index.write(
                    b"".join(
                        [i[0].to_bytes(index_byte_len, "big") for i in self._index]
                    )
                )

        self.write_tree_to_file()

        self.write_select_to_file(self.select_bits_filename)
        self.select_to_superblock()

        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_sums_to_file(self.eow_sb)

        self.write_hc_to_file(self.hc_bits_filename)
        self.hc_to_superblock()

        start_bytes: list[bytes] = []
        bytes_per_info: int = 4
        # merge reversed files into data file
        next_start: list[int] = [os.path.getsize(self.data_file)]
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.trie_file)
        # select
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.select_bits_filename)
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.s_sb_file)
        # hc files
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.hc_bits_filename)
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.hc_sb_file)
        # eow files
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.value_bits_filename)
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.eow_sb)
        # index bits file
        next_start.append(os.path.getsize(self.data_file))
        start_bytes.append(int.to_bytes(next_start[-1], bytes_per_info, "big"))
        self.merge_files(self.data_file, self.index_bits_filename)

        with io.open(self.data_file, "rb+") as f:
            start_index: int = 60
            for n in range(len(start_bytes)):
                f.seek(start_index + n * bytes_per_info)
                vals = start_bytes[n]
                f.write(vals)

        self.remove_build_files()
        WD.stop()

    def merge_files(self, master_file: str, temp_file: str) -> None:
        """Merge two files into one."""
        with io.open(master_file, "ab") as f_master:
            with io.open(temp_file, "rb") as f_temp:
                while True:
                    chunk = f_temp.read(10240)
                    if not chunk:
                        break
                    f_master.write(chunk)

    def remove_build_files(self) -> None:
        """Remove temporary files."""
        os.remove(self.trie_file)
        os.remove(self.select_bits_filename)
        os.remove(self.s_sb_file)
        os.remove(self.hc_bits_filename)
        os.remove(self.hc_sb_file)
        os.remove(self.value_bits_filename)
        os.remove(self.eow_sb)
        os.remove(self.index_bits_filename)
        os.remove(self.short_text_bits_filename)
        os.remove(self.trie_file + ".alphabet")
        os.remove(self.short_text_bits_filename + ".length")


def main():
    """Load text from a file (or stdin).
    The input should contain text lines in the format "<key><separator><value>" or just "<key>".
    The separator can be specified with the -F option (default is ';').
    Creates LOUDS trie from the input text and write the trie and associated
    lookup tables to disk in the specified collection folder.
    """
    import gc
    import argparse

    arg_parser = argparse.ArgumentParser(description="Make lookup tables for the trie.")

    arg_parser.add_argument(
        "--collection", "-C", type=str, help="The name of the collection to create."
    )
    arg_parser.add_argument(
        "--file",
        "-f",
        type=argparse.FileType("r", encoding="utf-8"),
        nargs="?",
        help="Input file (default: stdin).",
        default=sys.stdin,
    )
    arg_parser.add_argument(
        "--reversed", "-R", action="store_true", help="Make reversed index"
    )
    arg_parser.add_argument(
        "--field-separator",
        "-F",
        type=str,
        default=";",
        help="Field separator (default: ';')",
    )

    args = arg_parser.parse_args()
    txt = args.file
    field_separator = args.field_separator or ";"

    if txt is not None and args.collection is not None:
        trie = Trie(
            collection_name=args.collection,
            reversed=False,
            field_separator=field_separator,
        )
        trie.make_frozen_data(txt, statusbar=True)

    if args.reversed and args.collection:
        trie = Trie(
            collection_name=args.collection,
            reversed=True,
            field_separator=field_separator,
        )
        trie.make_reversed()
    gc.collect()  # Force garbage collection to free up memory after build process

    if args.collection is None or (txt is None and not args.reversed):
        arg_parser.print_help()


if __name__ == "__main__":
    main()
