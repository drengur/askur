#! /usr/bin/env python3

"""Make lookup tables for the LOUDS trie
from input file
"""

import os
import sys
import io
from pathlib import Path
import math as m
from dataclasses import dataclass
from askur.config import Config
from askur import alphabet
from askur import watchdog
from askur.map_infos import MapAddressInfo as ma

# initialization of global variables
# Config is initialized at the start of the build process and contains the configuration
# for the build process, such as the alphabet and data folder.
Config()  # Initialize the global CONFIG variable

WD = watchdog.Watchdog(
    threshold=int(os.environ.get("ASKUR_MEMORY_THRESHOLD", "5"))
)  # Watchdog to monitor system memory usage during build process
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

        with io.open(self.s_sb_file, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.hc_sb_file, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.eow_sb, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.value_bits_filename, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.hc_bits_filename, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.trie_file, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.select_bits_filename, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.index_bits_filename, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(self.short_text_bits_filename, encoding="utf-8", mode="w") as f:
            f.close()
        with io.open(
            self.short_text_bits_filename + ".length", encoding="utf-8", mode="w"
        ) as f:
            f.close()
        with io.open(self.trie_file + ".alphabet", encoding="utf-8", mode="w") as f:
            f.close()

    def make_frozen_data(self, input_data: str, statusbar=False) -> int:
        """Make the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays from the input data.
        Args:
            input_data: The input data as a string.
        Returns: int
        """
        res: int = 0
        try:
            WD.start(
                statusbar
            )  # Start the watchdog to monitor system memory usage during the build process
            data_values_gen: tuple[bytes] = self.make_trie(input_data)
            bytes_per_indexblock: int = self.write_frozen_data(data_values_gen)
            self.merge_data_files(bytes_per_indexblock)
        except (KeyboardInterrupt, SystemExit):
            self.remove_build_files(True)
            res = -1
            print("Build process interrupted. Exiting gracefully.")
        except Exception as e:
            self.remove_build_files(True)
            res = -1
            print(f"An error occurred during the build process: {e}")
        finally:
            WD.stop()
        return res

    def make_trie(self, input_data: str) -> tuple[bytes]:
        """Returns a generator that yields the data values in the same order as the indices in the trie."""

        # clear the data file if it exists
        with io.open(self.data_file, encoding="utf-8", mode="w") as f:
            f.close()
        data_values: dict[str, int] = {}
        index: int = -1
        key: bytes = b""
        next_index: int = -1
        root = Node()
        for w_key, w_value in self.read_from_input(input_data):
            if w_value not in data_values:
                next_index += 1
                data_values[w_value] = next_index
                index = next_index
            else:
                index = data_values[w_value]
            key = self.alphabet.convert_str_to_bytes(w_key)
            self._add(key, index, root)

        WD.clear_label()
        WD.print_label(" Writing to disk...")
        self.level_order_tree([root])

        # return tuple-generator(data_values) to save memory, instead of creating a list of all data values in memory
        return (k.encode("utf-8") for k in data_values.keys())

    def write_frozen_data(self, data_values_gen: tuple[bytes, None, None]) -> None:
        """Write the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays to disk.
        Args:            data_values_gen: A generator that yields the data values in the same order as the indices in the trie.
        Returns: None
        """
        self.write_tree_to_file()

        self.write_select_to_file(self.select_bits_filename)
        self.super_block_size = self.write_select_to_superblock()

        self.write_hc_to_file(self.hc_bits_filename)
        self.write_hc_to_superblock()

        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_to_superblock(self.eow_sb)

        bytes_per_indexblock: int = self.write_short_text_to_file(data_values_gen)
        return bytes_per_indexblock

    def merge_data_files(self, bytes_per_indexblock: int) -> None:
        """
        Merge the temporary files into the final data file
        """

        with io.open(self.trie_file + ".alphabet", "wb") as f:
            f.write(self.alphabet.get_used)
        WD.clear_label()

        bytes_per_info: int = 4
        # initialize data_file with all the info cells
        with io.open(self.data_file, "wb") as f:
            for item in ma:
                f.write(int.to_bytes(0, bytes_per_info, "big"))

        header_bytes = [int.to_bytes(0, bytes_per_info, "big") for _ in range(len(ma))]

        header_bytes[ma.BYTES_PR_INFO_CELL.value] = int.to_bytes(
            bytes_per_info, bytes_per_info, "big"
        )

        header_bytes[ma.BITS_PR_SB.value] = int.to_bytes(
            self.super_block_size, bytes_per_info, "big"
        )

        header_bytes[ma.BYTES_PR_INDEX_BLOCK.value] = int.to_bytes(
            bytes_per_indexblock, bytes_per_info, "big"
        )

        # calculate the next data offset for the start of the data section.
        next_data_offset: int = (len(ma) - 1) * bytes_per_info

        header_bytes[ma.ALPHABET.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.trie_file + ".alphabet")

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.TRIE.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.trie_file)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.SELECT.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.select_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.SELECT_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.s_sb_file)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.HC.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.hc_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.HC_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.hc_sb_file)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.EOW.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.value_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.EOW_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.eow_sb)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.INDEX_VALUE.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.index_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.INDEX_VALUE_LENGTH.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.short_text_bits_filename + ".length")

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.SHORT_TEXT.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.short_text_bits_filename)

        with io.open(self.data_file, "rb+") as f:
            for item in ma:
                if header_bytes[item.value] is not None:
                    f.seek(item.value * bytes_per_info)
                    f.write(header_bytes[item.value])

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
        key: str = ""
        value: str = ""

        if input_data is not sys.stdin:
            with io.open(input_data.name, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
        else:
            if sys.stdin.isatty():
                print("No input data provided. Exiting.")
                sys.exit(1)
        with (
            io.open(input_data.name, "r", encoding="utf-8")
            if input_data is not sys.stdin
            else sys.stdin as f
        ):
            for line in f:
                line_nr += 1
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if nr_cols == 0:
                    nr_cols = line.count(self.field_separator) + 1

                key, value = self.split_line(line.strip())
                if nr_cols == 2 and value == "" or nr_cols == 1 and value != "":
                    print(
                        f"\n{'*' * 50}\n  Unexpected value: {key}: {value}, line {line_nr}\n  Exiting\n{'*' * 50}"
                    )
                    sys.exit(1)
                if key == "":
                    print(
                        f"\n{'*' * 50}\n  Missing key in line {line_nr}\n  Exiting\n{'*' * 50}"
                    )
                    sys.exit(1)
                if line_count > 0 and line_nr % 1000 == 0:
                    WD.print_label(
                        f"  {line_nr / line_count * 100:.1f}% of lines processed"
                    )

                yield key, value or "1"

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

    def write_hc_to_file(self, filename: str) -> None:
        """Write the head child array to a file."""
        buffer: bytearray = bytearray()  # Buffer to hold bytes before Writing to disk
        i: int = 0

        nr_extra_bits: int = len(self._hc) % 8
        self._hc.extend([0 for _ in range(8 - nr_extra_bits)])

        while i < len(self._hc):
            buffer.append(int("".join([str(c) for c in self._hc[i : i + 8]]), 2))
            i += 8
            if len(buffer) >= 1024:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()  # Clear the buffer to free memory
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)

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
            if len(buffer) >= 1024:
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
            if len(buffer) >= 1024:
                with io.open(filename, "ab") as f:
                    f.write(buffer)
                buffer.clear()

        # add remaining bits
        if len(buffer) > 0:
            with io.open(filename, "ab") as f:
                f.write(buffer)

    def write_eow_to_superblock(self, filename: str) -> None:
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
                if len(buffer) >= 1024:
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
            return 4  # if there is only one short text, we can use 4 bytes to store the index value

        # total length of all short texts
        total_short_len: int = sum(len(value) for value in data_values)

        # byte_length is minimum number of bytes needed to represent total_short_len
        byte_len: int = len(bin(total_short_len)[2:]) // 8 + (
            1 if len(bin(total_short_len)[2:]) % 8 else 0
        )

        short_texts: list[bytes] = []
        sum_index: int = 0

        # short_text_index has same length and index reference as self._index
        # it points to the correct position of the resulting text value (the reusult)
        short_text_index: list[bytes] = []
        indices: dict[str, bytes] = {}
        text_lengths: list[int] = []
        tmp_txt: bytes = b""

        for _, idxs in enumerate(self._index):
            tmp_txt = A.UNIT_SEPARATOR.join([data_values[idx] for idx in idxs])
            idxs.sort()  # sort to make sure indexes are unique
            idxs_str = "_".join([str(i) for i in idxs])

            text_lengths.append(len(tmp_txt))
            if idxs_str not in indices:
                indices[idxs_str] = sum_index.to_bytes(byte_len, "big")
                short_texts.append(tmp_txt)
                sum_index += text_lengths[-1]
            short_text_index.append(indices[idxs_str])

            if len(short_texts) >= 1024:
                with io.open(self.short_text_bits_filename, "ab") as fb:
                    for item in short_texts:
                        fb.write(item)
                short_texts.clear()

            if len(short_text_index) >= 1024:
                with io.open(self.index_bits_filename, "ab") as fb:
                    fb.write(b"".join(short_text_index))
                short_text_index.clear()

            if len(text_lengths) >= 1024:
                with io.open(self.short_text_bits_filename + ".length", "ab") as fb:
                    for item in text_lengths:
                        fb.write(item.to_bytes(2, "big"))
                text_lengths.clear()

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

        if len(text_lengths) > 0:
            with io.open(self.short_text_bits_filename + ".length", "ab") as fb:
                for item in text_lengths:
                    fb.write(item.to_bytes(2, "big"))

        return byte_len

    def write_hc_to_superblock(self):
        """Writing to hc-superblock file"""

        nr_bytes: int = 4
        buffer: bytearray = bytearray()
        bitsum: int = 0
        index: int = 0
        for _, val in enumerate(self._hc):
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

    def write_select_to_superblock(self) -> int:
        """Write the select superblock to a file.
        returns the block size used in bits for the select superblock and hc superblock.

        return block_size: int
        """
        # block size in bits has to be a multiple of 8
        block_size: int = m.ceil(m.log2(len(self._select)) / 2) // 8 * 8
        block_size = max(8, block_size)

        bitsum: int = 0
        nr_bytes: int = 4
        buffer = bytearray()
        for i, val in enumerate(self._select):
            bitsum += val
            if bitsum == block_size:
                sb_bytes = i.to_bytes(nr_bytes, "big")
                buffer.extend(sb_bytes)
                bitsum = 0
                if len(buffer) >= 1024:
                    with io.open(self.s_sb_file, "ab") as f:
                        f.write(buffer)
                    buffer.clear()

        if bitsum > 0:
            sb_bytes = (len(self._select) - 1).to_bytes(nr_bytes, "big")
            buffer.extend(sb_bytes)

        if buffer:
            with io.open(self.s_sb_file, "ab") as f:
                f.write(buffer)
        return block_size

    def make_reversed(self, statusbar=True) -> None:
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
        """Make a reversed/suffix trie from the original data."""

        self.super_block_size: int = 0
        index_byte_len: int = 0
        short_text_len: int = 0
        root: Node = Node()
        key: bytes = b""
        w_key: bytes = b""
        value: int | None = None

        with io.open(self.data_file, "rb") as f_data:
            file_slice: bytes = f_data.read(len(ma) * 4)
            index_byte_len = int.from_bytes(
                file_slice[ma.address(ma.BYTES_PR_INDEX_BLOCK)], "big"
            )
            self.super_block_size = int.from_bytes(
                file_slice[ma.address(ma.BITS_PR_SB)], "big"
            )

        from askur.search import Search

        with Search(collection=self.collection_name) as search:
            # All entries in the trie
            short_text_len = search.value_size
            for item in search.exists("*"):
                key = list(item.keys())[0][::-1]  # reverse the key
                w_key = self.alphabet.convert_str_to_bytes(key)
                value = None if short_text_len == 0 else list(item.values())[0]
                self._add(w_key, value, root)

        self.level_order_tree([root])

        # Translate self._index to short text indices used in the original trie
        with io.open(self.index_bits_filename, "wb") as f_index:
            f_index.write(
                b"".join(
                    [idx[0].to_bytes(index_byte_len, "big") for idx in self._index]
                )
            )

        self.write_tree_to_file()

        self.write_select_to_file(self.select_bits_filename)
        self.write_select_to_superblock()

        self.write_eow_values_to_file(self.value_bits_filename)
        self.write_eow_to_superblock(self.eow_sb)

        self.write_hc_to_file(self.hc_bits_filename)
        self.write_hc_to_superblock()

        bytes_per_info: int = 4
        header_data: list[bytes] = [None for _ in range(len(ma))]

        # merge reversed files into data file
        next_data_offset: int = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_TRIE.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.trie_file)

        # select
        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_SELECT.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.select_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_SELECT_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.s_sb_file)

        # hc files
        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_HC.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.hc_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_HC_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.hc_sb_file)

        # eow files
        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_EOW.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.value_bits_filename)

        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_EOW_SB.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.eow_sb)

        # index bits file
        next_data_offset = os.path.getsize(self.data_file)
        header_data[ma.SUFFIX_INDEX_VALUE.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.index_bits_filename)

        with io.open(self.data_file, "rb+") as f:
            for i in range(len(ma)):
                if header_data[i] is not None:
                    f.seek(i * bytes_per_info)
                    f.write(header_data[i])

        self.remove_build_files()

    def merge_files(self, master_file: str, temp_file: str) -> None:
        """Merge two files into one."""
        with io.open(master_file, "ab") as f_master:
            with io.open(temp_file, "rb") as f_temp:
                while True:
                    chunk = f_temp.read(1024)
                    if not chunk:
                        break
                    f_master.write(chunk)

    def remove_build_files(self, remove_datafile=False) -> None:
        """Remove temporary files."""
        for file in [
            self.trie_file,
            self.select_bits_filename,
            self.s_sb_file,
            self.hc_bits_filename,
            self.hc_sb_file,
            self.value_bits_filename,
            self.eow_sb,
            self.index_bits_filename,
            self.short_text_bits_filename,
            self.trie_file + ".alphabet",
            self.short_text_bits_filename + ".length",
        ]:
            if Path(file).exists():
                os.remove(file)
        if remove_datafile:
            data_file_path = Path(self.data_file)
            if data_file_path.exists():
                data_file_path.unlink()  # Remove the data file if it exists
                os.rmdir(self.frozen_folder)


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

    if txt is None or (txt.name == "<stdin>" and sys.stdin.isatty()):
        print("\n" + "*" * 5 + " No input data provided. Exiting.")
        arg_parser.print_help()
        sys.exit(1)

    if args.collection is not None:
        trie = Trie(
            collection_name=args.collection,
            reversed=False,
            field_separator=field_separator,
        )
        res_build: int = trie.make_frozen_data(txt, statusbar=True)

    if res_build == 0 and args.reversed and args.collection:
        trie = Trie(
            collection_name=args.collection,
            reversed=True,
            field_separator=field_separator,
        )
        trie.make_reversed()
    gc.collect()  # Force garbage collection to free up memory after build process

    if args.collection is None:
        arg_parser.print_help()


if __name__ == "__main__":
    main()
