#! /usr/bin/env python3

"""Make lookup tables for the LOUDS trie
from input file
"""

import os
import sys
import io
import gc
import argparse
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
    threshold=int(os.environ.get("ASKUR_MEMORY_THRESHOLD", "60"))
)  # Watchdog to monitor system memory usage during build process
A: alphabet.Alphabet | None = alphabet.Alphabet


@dataclass(slots=True)
class Node:
    """A node in the trie."""

    leaf_indices: tuple[int] = None
    letters: dict[int, "Node"] = None
    single_index: int = None

    @property
    def has_children(self) -> bool:
        """Check if the node has any children."""
        return self.letters is not None

    @property
    def end(self) -> bool:
        """Check if the node is an end/leaf node (end of word)."""
        return self.leaf_indices is not None or self.single_index is not None

    def get_child(self, key: int) -> "Node":
        """Get the child node for a given key.
        If the child node does not exist, create it.
        """
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

    def __init__(self, collection_name="", field_separator=";") -> None:
        """Creates a new trie with associated files.
        Writes the trie structure to disk in LOUDS format along with
        the head child array (HC), select array (S), end of word array (EOW),
        index array (INDEX), and short text array (SHORT_TEXT).

        usage:
            trie = Trie()
            trie.make_frozen_data()
        Args:
            collection_name: The name of the collection to create.
            field_separator: The field separator used in the input data.
        """

        self._index = []  # the counter array (the number of words that have been added to the trie)
        self._short_text = []  # the short text array (the words in the trie)
        self.collection_name: str = collection_name
        self.field_separator = field_separator
        self.super_block_size: int = 0
        self.frozen_folder: str = ""
        self.index_byte_len: int = 0
        self.total_words: int = 0
        self._bw_byte_size: int = 0  # the byte size used for storing  index values when travesing backwards through the trie

        # The alphabet used in the trie.
        self.alphabet = A()

        # Set the method to be called when memory is low.
        # This method should handle the cleanup of build files or any other necessary actions before exiting.
        WD.set_clear_build_method(self.remove_build_files)

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

        self.frozen_folder: Path = Path(data_folder) / self.collection_name
        if not self.frozen_folder.exists():
            self.frozen_folder.mkdir(parents=True, exist_ok=True)

        self.select_bits_filename = Path(self.frozen_folder) / "s_bits.bin"
        self.trie_file = Path(self.frozen_folder) / "trie"

        self.index_bits_filename = Path(self.frozen_folder) / "index_bits.bin"
        self.hc_bits_filename = Path(self.frozen_folder) / "hc_bits.bin"

        # self.value_bits_filename = os.path.join(self.frozen_folder, "eow_bits.bin")
        self.value_bits_filename = Path(self.frozen_folder) / "eow_bits.bin"

        self.short_text_bits_filename = Path(self.frozen_folder) / "short_text_bits.bin"

        # end of word super block file
        self.eow_sb = Path(self.frozen_folder) / "eow_sb.bin"

        # hc superblock
        self.hc_sb_file = Path(self.frozen_folder) / "hc_sb.bin"

        # select superblock
        self.s_sb_file = Path(self.frozen_folder) / "s_sb.bin"

        self.data_file = Path(self.frozen_folder) / "data.bin"

        self.s_chr_file = Path(self.frozen_folder) / "s_chr.bin"

        self.hc_to_chr_file = Path(self.frozen_folder) / "hc_to_chr.bin"

        # ensure files are empty
        for p in [
            self.s_sb_file,
            self.hc_sb_file,
            self.eow_sb,
            self.value_bits_filename,
            self.hc_bits_filename,
            self.trie_file,
            self.select_bits_filename,
            self.index_bits_filename,
            self.short_text_bits_filename,
            self.short_text_bits_filename.with_suffix(".length"),
            self.trie_file.with_suffix(".alphabet"),
            self.s_chr_file,
            self.hc_to_chr_file,
        ]:
            # clear the file if it exists
            if os.path.exists(p):
                os.remove(p)

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
        """Returns a generator that yields the data values in
        the same order as the indices in the trie."""

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
            index = data_values[w_value]
            key = self.alphabet.convert_str_to_bytes(w_key)
            self._add(key, index, root)
            self.total_words += 1

        WD.clear_label()
        WD.print_label(" Writing to disk...")
        self.level_order_tree([root])

        # return tuple-generator(data_values) to save memory, instead of creating a list of all data values in memory
        return (k.encode("utf-8") for k in data_values)

    def write_frozen_data(self, data_values_gen: tuple[bytes, None, None]) -> None:
        """Write the LOUDS, HC, SELECT, INDEX, VALUE, INDEX_VALUE and SHORT_TEXT arrays to disk.
        Args:            data_values_gen: A generator that yields the data values in the same order as the indices in the trie.
        Returns: None
        """
        self.super_block_size = self.write_select_to_superblock()

        self.write_hc_to_superblock()

        self.write_eow_to_superblock()

        bytes_per_indexblock: int = self.write_short_text_to_file(data_values_gen)
        return bytes_per_indexblock

    def merge_data_files(self, bytes_per_indexblock: int) -> None:
        """
        Merge the temporary files into the final data file
        """
        with io.open(self.trie_file.with_suffix(".alphabet"), "wb") as f:
            f.write(bytearray(self.alphabet.get_used_sorted))
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
        header_bytes[ma.NR_WORDS.value] = int.to_bytes(
            self.total_words, bytes_per_info, "big"
        )
        header_bytes[ma.BW_BYTE_SIZE.value] = int.to_bytes(
            self._bw_byte_size, bytes_per_info, "big"
        )

        # calculate the next data offset for the start of the data section.
        next_data_offset: int = (len(ma)) * bytes_per_info

        header_bytes[ma.HC_TO_CHR.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.hc_to_chr_file)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.SELECT_FROM_CHR.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.s_chr_file)

        next_data_offset = os.path.getsize(self.data_file)

        header_bytes[ma.ALPHABET.value] = int.to_bytes(
            next_data_offset, bytes_per_info, "big"
        )
        self.merge_files(self.data_file, self.trie_file.with_suffix(".alphabet"))

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
        self.merge_files(
            self.data_file, self.short_text_bits_filename.with_suffix(".length")
        )

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

    def sorted_trie_range(self, node: Node) -> list[int]:
        """Get the sorted range of letters in the trie node.
        so that we always traverse the trie in alphabetical order.
        Args:
            node: The trie node.
        """
        if node.letters is None:
            return []
        return sorted(node.letters.keys())

    def level_order_tree(self, root: list[Node]) -> None:
        """Level out trie.
        Traverse the trie in level order and write to the _trie, _hc,
        _select, _is_eow and _index arrays.
        and write the arrays to disk in chunks to minimize memory usage.
        """
        stack: list[Node] = root
        child_nodes: list[Node] = []
        first: str = "1"
        eow: str = ""
        eow_list: list[int] = []
        sel = ""
        sel_list: list[int] = []
        hc = ""
        hc_list: list[int] = []
        trie: list[int] = []
        with (
            open(self.value_bits_filename, "wb") as fe,
            open(self.trie_file, "wb") as ft,
            open(self.hc_bits_filename, "wb") as fhc,
            open(self.select_bits_filename, "wb") as fs,
            open(self.index_bits_filename, "wb") as f_index,
        ):
            while stack:
                for node in stack:
                    first = "1"
                    for w_key in self.sorted_trie_range(node):
                        trie.append(self.alphabet.inv_alphabet.get(w_key))
                        if len(trie) >= 1024:
                            ft.write(
                                b"".join([int.to_bytes(val, 1, "big") for val in trie])
                            )
                            trie.clear()
                        sel += first
                        first = "0"
                        hc += "1" if node.letters[w_key].has_children else "0"
                        eow += "1" if node.letters[w_key].end else "0"

                        if node.letters[w_key].end:
                            self._index.append(node.letters[w_key].get_indices())

                        child_nodes.append(node.letters[w_key])

                        if len(eow) == 8:
                            eow_list.append(int(eow, 2))
                            sel_list.append(int(sel, 2))
                            hc_list.append(int(hc, 2))
                            eow = ""
                            sel = ""
                            hc = ""
                        if len(eow_list) >= 1024:
                            fe.write(
                                b"".join(
                                    [int.to_bytes(val, 1, "big") for val in eow_list]
                                )
                            )
                            eow_list.clear()
                            fs.write(
                                b"".join(
                                    [int.to_bytes(val, 1, "big") for val in sel_list]
                                )
                            )
                            sel_list.clear()
                            fhc.write(
                                b"".join(
                                    [int.to_bytes(val, 1, "big") for val in hc_list]
                                )
                            )
                            hc_list.clear()
                stack = child_nodes[:]
                child_nodes.clear()
            if len(eow) > 0:
                eow = eow.ljust(8, "0")  # Pad with zeros to make it 8 bits
                eow_list.append(int(eow, 2))
                hc = hc.ljust(8, "0")  # Pad with zeros to make it 8 bits
                hc_list.append(int(hc, 2))
                sel = sel.ljust(8, "0")  # Pad with zeros to make it 8 bits
                sel_list.append(int(sel, 2))
            fs.write(b"".join([int.to_bytes(val, 1, "big") for val in sel_list]))
            fe.write(b"".join([int.to_bytes(val, 1, "big") for val in eow_list]))
            fhc.write(b"".join([int.to_bytes(val, 1, "big") for val in hc_list]))
            ft.write(b"".join([int.to_bytes(val, 1, "big") for val in trie]))

    def write_eow_to_superblock(self) -> None:
        """sum of "1"-bits in a block of 32 bits to a file."""

        bitsum: int = 0
        n: int = 0
        buffer: list[int] = []
        bits_in_block: int = 32
        bytes_in_block: int = 4
        # TODO : calculate bits_in_block and bytes_in_block based on size of self._is_eow to save space/speed up search
        with io.open(self.value_bits_filename, "rb") as few:
            while True:
                chunk = few.read(1024)
                if not chunk:
                    break
                for b in chunk:
                    for bit in range(8):
                        n += 1
                        if (b >> (7 - bit)) & 1:
                            bitsum += 1
                        if n == bits_in_block:
                            buffer.append(bitsum)
                            n = 0
                        if len(buffer) >= 1024:
                            with io.open(self.eow_sb, "ab") as fb:
                                for val in buffer:
                                    fb.write(val.to_bytes(bytes_in_block, "big"))
                            buffer.clear()
        # write remaining buffer to file
        if buffer:
            with io.open(self.eow_sb, "ab") as fb:
                for val in buffer:
                    fb.write(val.to_bytes(bytes_in_block, "big"))
            buffer.clear()

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
        byte_len = m.ceil(
            total_short_len.bit_length() / 8
        )  # minimum number of bytes needed to represent total_short_len

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
                with io.open(
                    self.short_text_bits_filename.with_suffix(".length"), "ab"
                ) as fb:
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
            with io.open(
                self.short_text_bits_filename.with_suffix(".length"), "ab"
            ) as fb:
                for item in text_lengths:
                    fb.write(item.to_bytes(2, "big"))

        return byte_len

    def write_hc_to_superblock(self):
        """Writing to hc-superblock file"""

        nr_bytes: int = 4
        buffer: bytearray = bytearray()
        bitsum: int = 0
        index: int = 0
        hc_to_chr_buffer: bytes = b""
        nr_chr_bits: int = 0
        total_index: int = 0

        chr_bit_number: int = self._bw_byte_size * 8 # usually 24 bits

        with io.open(self.hc_bits_filename, "rb") as fhc:
            while True:
                chunk = fhc.read(1024)
                if not chunk:
                    break
                for b in chunk:
                    for bit in range(8):
                        index += 1
                        total_index += 1
                        if (b >> (7 - bit)) & 1:
                            bitsum += 1
                            nr_chr_bits += 1
                        if index == self.super_block_size:
                            byte_value = bitsum.to_bytes(nr_bytes, "big")
                            buffer.extend(byte_value)
                            index = 0
                            if len(buffer) >= 1024:
                                with io.open(self.hc_sb_file, "ab") as fb:
                                    fb.write(buffer)
                                buffer.clear()
                        if nr_chr_bits == chr_bit_number:
                            hc_to_chr_buffer += total_index.to_bytes(
                                self._bw_byte_size, "big"
                            )
                            nr_chr_bits = 0
                            if len(hc_to_chr_buffer) >= 1024:
                                with io.open(self.hc_to_chr_file, "ab") as fb:
                                    fb.write(hc_to_chr_buffer)
                                hc_to_chr_buffer = b""

        if index > 0:
            byte_value = bitsum.to_bytes(nr_bytes, "big")
            buffer.extend(byte_value)
        if len(buffer) > 0:
            with io.open(self.hc_sb_file, "ab") as fb:
                fb.write(buffer)
        if len(hc_to_chr_buffer) > 0:
            with io.open(self.hc_to_chr_file, "ab") as fb:
                fb.write(hc_to_chr_buffer)

    def write_select_to_superblock(self) -> int:
        """Write the select superblock to a file.
        returns the block size used in bits for the select superblock and hc superblock.

        return block_size: int
        """
        # block size in bits has to be a multiple of 8
        block_size: int = (
            m.ceil(m.log2(os.path.getsize(self.select_bits_filename)) / 2) // 8 * 8
        )
        block_size = max(8, block_size)

        # biggest number in hc_to_chr_buffer is the length of the hc_bits_filename
        max_integer: int = os.path.getsize(self.hc_bits_filename) * 8
        # calculate minimum number of bytes needed to store max_integer
        num_bytes_sel: int = (max_integer.bit_length() + 7) // 8
        self._bw_byte_size = num_bytes_sel

        bitsum: int = 0
        nr_bytes: int = 4
        buffer = bytearray()
        n: int = 0
        s_chr_buffer = b""
        total_bitsum: int = 0
        nt = 0

        with io.open(self.select_bits_filename, "rb") as fs:
            while True:
                chunk = fs.read(1024)
                if not chunk:
                    break
                for b in chunk:
                    total_bitsum += b.bit_count()
                    nt += 1
                    if nt == num_bytes_sel:
                        s_chr_buffer += total_bitsum.to_bytes(num_bytes_sel, "big")
                        nt = 0
                        if len(s_chr_buffer) >= 1024:
                            with io.open(self.s_chr_file, "ab") as f:
                                f.write(s_chr_buffer)
                            s_chr_buffer = b""

                    if bitsum + b.bit_count() < block_size:
                        bitsum += b.bit_count()
                        n += 8
                        continue

                    for bit in range(8):
                        if (b >> (7 - bit)) & 1:
                            bitsum += 1
                        if bitsum == block_size:
                            buffer.extend(n.to_bytes(nr_bytes, "big"))
                            bitsum = 0
                            if len(buffer) >= 1024:
                                with io.open(self.s_sb_file, "ab") as f:
                                    f.write(buffer)
                                buffer.clear()
                        n += 1

        if bitsum > 0:
            buffer.extend(n.to_bytes(nr_bytes, "big"))
        if len(buffer) > 0:
            with io.open(self.s_sb_file, "ab") as f:
                f.write(buffer)

        if len(s_chr_buffer) > 0:
            with io.open(self.s_chr_file, "ab") as f:
                f.write(s_chr_buffer)

        return block_size

    def merge_files(self, master_file: str, temp_file: str) -> None:
        """Merge two files into one."""
        if not Path(temp_file).exists():
            return
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
            self.trie_file.with_suffix(".alphabet"),
            self.short_text_bits_filename.with_suffix(".length"),
            self.s_chr_file,
            self.hc_to_chr_file,
        ]:
            if Path(file).exists():
                Path(file).unlink()  # Remove the file if it exists
        if remove_datafile:
            data_file_path = Path(self.data_file)
            if data_file_path.exists():
                data_file_path.unlink()  # Remove the data file if it exists
                # remove the frozen folder if it's empty
                if not any(Path(self.frozen_folder).iterdir()):
                    os.rmdir(self.frozen_folder)


def main():
    """Load text from a file (or stdin).
    The input should contain text lines in the format "<key><separator><value>" or just "<key>".
    The separator can be specified with the -F option (default is ';').
    Creates LOUDS trie from the input text and write the trie and associated
    lookup tables to disk in the specified collection folder.
    """

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
        "--field-separator",
        "-F",
        type=str,
        default=";",
        help="Field separator (default: ';')",
    )

    args: argparse.Namespace = arg_parser.parse_args()
    txt: str = args.file
    field_separator: str = args.field_separator or ";"

    if txt is None or (txt.name == "<stdin>" and sys.stdin.isatty()):
        print("\n" + "*" * 5 + " No input data provided. Exiting.")
        arg_parser.print_help()
        sys.exit(1)

    if args.collection is not None:
        trie = Trie(
            collection_name=args.collection,
            field_separator=field_separator,
        )
        trie.make_frozen_data(txt, statusbar=True)

    gc.collect()  # Force garbage collection to free up memory after build process

    if args.collection is None:
        arg_parser.print_help()


if __name__ == "__main__":
    main()
