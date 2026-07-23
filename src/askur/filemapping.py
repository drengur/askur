import os
import mmap
from dataclasses import dataclass
from askur.alphabet import Alphabet
from askur.config import Config

Config()  # initialize config environment variables
A = Alphabet()


@dataclass(frozen=True)
class Section:
    start: int
    end: int


class Mapping:
    def __init__(self, collection: str) -> None:
        self._file: str = ""
        self._mmap: mmap.mmap = None
        self._view: memoryview = None

        self._trie: bytes = b""

        self._s_bits: bytes = b""
        self._s_superblocks: bytes = b""

        self._hc_bitarray: bytes = b""
        self._hc_super_blocks: bytes = b""

        self._eow_bits: bytes = b""
        self._eow_sb: bytes = b""

        self._index_bits: bytes = b""
        self._index_values_length: bytes = b""

        self.short_text_len: int = 0
        self.bits_in_superblock: int = 0
        self.collection: str = collection

        # pointers to the starts of the sections
        self._trie_start: int = 0
        self._trie_end: int = 0

        self._select_start: int = 0
        self._select_end: int = 0

        self._select_superblock_start: int = 0
        self._select_superblock_end: int = 0

        self._hc_start: int = 0
        self._hc_end: int = 0

        self._hc_superblock_start: int = 0
        self._hc_superblock_end: int = 0

        self._eow_start: int = 0
        self._eow_end: int = 0

        self._eow_superblock_start: int = 0
        self._eow_superblock_end: int = 0

        self._index_start: int = 0
        self._index_end: int = 0

        self._alphabet_index_start: int = 0
        self._alphabet_index_end: int = 0

        self._short_text_start: int = 0
        self._short_text_end: int = 0

        self.alphabet: bytes = b""
        self.check_if_key_exists: bool = False  # are we only checking if key exists?
        self._reversed_lookup: bool = False  # are we looking up suffixes?
        self._has_reversed_index: bool = False  # does the index have reversed entries?

        self.nr_bytes_in_index_block: int = 0

        self._reversed_trie: bytes = b""

        self._reversed_s_bits: bytes = b""
        self._reversed_s_superblocks: bytes = b""
        self._reversed_hc_bits: bytes = b""
        self._reversed_hc_super_blocks: bytes = b""

        self._reversed_eow_bits: bytes = b""
        self._reversed_eow_sb: bytes = b""

        self._short_text: bytes = b""

        # pointers to the starts of the reversed sections
        self._reversed_trie_start: int = 0
        self._reversed_trie_end: int = 0

        self._reversed_select_start: int = 0
        self._reversed_select_end: int = 0

        self._reversed_select_superblock_start: int = 0
        self._reversed_select_superblock_end: int = 0

        self._reversed_hc_start: int = 0
        self._reversed_hc_end: int = 0

        self._reversed_hc_superblock_start: int = 0
        self._reversed_hc_superblock_end: int = 0

        self._reversed_eow_start: int = 0
        self._reversed_eow_end: int = 0

        self._reversed_eow_superblock_start: int = 0
        self._reversed_eow_superblock_end: int = 0

        self._load_files()

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        """Ensure that the mmap and file are closed when the object is destroyed
        to avoid memory leaks and file locks"""
        self.close()

    def _load_files(self):
        # Check for environment variable first, then fall back to config file
        data_folder = os.environ.get("ASKUR_DATA_FOLDER")
        if data_folder is None:
            print(
                "DATA_FOLDER environment variable is not set. Please update config.py."
            )
            import sys

            sys.exit(1)

        frozen_folder = os.path.join(data_folder, self.collection)

        if not os.path.exists(frozen_folder):
            import sys
            from askur.__init__ import list_collections

            print(f"\n  '{self.collection}' collection does not exist!")
            list_collections()
            sys.exit(1)

        data_filename = os.path.join(frozen_folder, "data.bin")
        self._file = open(data_filename, "rb")
        self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._view = memoryview(self._mmap)

        self.bits_in_superblock = int.from_bytes(self._mmap[4:8], byteorder="big")
        self.nr_bytes_in_index_block = int.from_bytes(self._mmap[8:12], byteorder="big")

        alphabet_start = int.from_bytes(self._mmap[12:16], byteorder="big")
        alphabet_end = int.from_bytes(self._mmap[16:20], byteorder="big")
        self._trie_start = alphabet_end
        self._trie_end = int.from_bytes(self._mmap[20:24], byteorder="big")

        self._select_start = self._trie_end
        self._select_end = int.from_bytes(self._mmap[24:28], byteorder="big")

        self._select_superblock_start = self._select_end
        self._select_superblock_end = int.from_bytes(self._mmap[28:32], byteorder="big")

        self._hc_start = self._select_superblock_end
        self._hc_end = int.from_bytes(self._mmap[32:36], byteorder="big")

        self._hc_superblock_start = self._hc_end
        self._hc_superblock_end = int.from_bytes(self._mmap[36:40], byteorder="big")

        self._eow_start = self._hc_superblock_end
        self._eow_end = int.from_bytes(self._mmap[40:44], byteorder="big")

        self._eow_superblock_start = self._eow_end
        self._eow_superblock_end = int.from_bytes(self._mmap[44:48], byteorder="big")

        self._index_value_start = self._eow_superblock_end
        self._index_value_end = int.from_bytes(self._mmap[48:52], byteorder="big")

        self._index_values_length_start = self._index_value_end
        self._index_values_length_end = int.from_bytes(
            self._mmap[52:56], byteorder="big"
        )

        self._short_text_start = self._index_values_length_end

        self._reversed_trie_start = int.from_bytes(self._mmap[60:64], byteorder="big")
        self._reversed_trie_end = int.from_bytes(self._mmap[64:68], byteorder="big")

        self._reversed_select_start = self._reversed_trie_end
        self._reversed_select_end = int.from_bytes(self._mmap[68:72], byteorder="big")

        self._reversed_select_superblock_start = self._reversed_select_end
        self._reversed_select_superblock_end = int.from_bytes(
            self._mmap[72:76], byteorder="big"
        )

        self._reversed_hc_start = self._reversed_select_superblock_end
        self._reversed_hc_end = int.from_bytes(self._mmap[76:80], byteorder="big")

        self._reversed_hc_superblock_start = self._reversed_hc_end
        self._reversed_hc_superblock_end = int.from_bytes(
            self._mmap[80:84], byteorder="big"
        )
        self._reversed_eow_start = self._reversed_hc_superblock_end
        self._reversed_eow_end = int.from_bytes(self._mmap[84:88], byteorder="big")

        self._reversed_eow_superblock_start = self._reversed_eow_end
        self._reversed_eow_superblock_end = int.from_bytes(
            self._mmap[88:92], byteorder="big"
        )

        self._reversed_index_start = self._reversed_eow_superblock_end
        self._reversed_index_end = int.from_bytes(self._mmap[92:96], byteorder="big")

        self._alphabet = Section(alphabet_start, alphabet_end)

        self._short_text_end = (
            self._reversed_trie_start if self._reversed_trie_start > 0 else None
        )
        self._translate_index_bits = Section(
            self._reversed_index_start, self._reversed_index_end
        )

        self._has_reversed_index = self._reversed_trie_end > self._reversed_trie_start
        self.do_reversed_lookup(False)  # initialize the sections for normal lookup

    def section_slice(
        self, section: Section, start: int, end: int | None = None
    ) -> bytes:
        abs_start = section.start + start
        abs_end = section.end if end is None else section.start + end
        return self._view[abs_start:abs_end]

    def section_bytes(self, section: Section, index: int) -> int:
        return self._view[section.start + index]

    def section_find(
        self, section: Section, needle: bytes, start: int, end: int
    ) -> int:
        pos = self._mmap.find(needle, section.start + start, section.start + end)
        return -1 if pos < 0 else pos - section.start

    def has_reversed_index(self) -> bool:
        """Returns True if the index is reversed"""
        return self._has_reversed_index

    def do_reversed_lookup(self, reversed_lookup: bool) -> bool:
        """Returns True if the index is reversed and we are doing reversed lookup"""
        self._reversed_lookup = reversed_lookup and self.has_reversed_index()
        if not self._reversed_lookup:
            self._trie = Section(self._trie_start, self._trie_end)
            self._s_bits = Section(self._select_start, self._select_end)
            self._s_superblocks = Section(
                self._select_superblock_start, self._select_superblock_end
            )
            self._hc_bits = Section(self._hc_start, self._hc_end)
            self._hc_super_blocks = Section(
                self._hc_superblock_start, self._hc_superblock_end
            )
            self._eow_bits = Section(self._eow_start, self._eow_end)
            self._eow_sb = Section(self._eow_superblock_start, self._eow_superblock_end)

            self._index_bits = Section(self._index_value_start, self._index_value_end)
            self._index_values_length = Section(
                self._index_values_length_start, self._index_values_length_end
            )
            self._short_text = Section(self._short_text_start, self._short_text_end)
        else:
            self._trie = Section(self._reversed_trie_start, self._reversed_trie_end)
            self._s_bits = Section(
                self._reversed_select_start, self._reversed_select_end
            )
            self._s_superblocks = Section(
                self._reversed_select_superblock_start,
                self._reversed_select_superblock_end,
            )
            self._hc_bits = Section(self._reversed_hc_start, self._reversed_hc_end)
            self._hc_super_blocks = Section(
                self._reversed_hc_superblock_start, self._reversed_hc_superblock_end
            )
            self._eow_bits = Section(self._reversed_eow_start, self._reversed_eow_end)
            self._eow_sb = Section(
                self._reversed_eow_superblock_start, self._reversed_eow_superblock_end
            )
        return self._reversed_lookup

    def set_check_key_exists(self, check_key_exists: bool) -> bool:
        """Returns True if the key exists in the index"""
        self.check_if_key_exists = check_key_exists
        return check_key_exists

    def calculate_select(self, sum_ones_wanted: int) -> list[int, int]:
        # There are 32 bits/4 bytes in each superblock
        """Returns the index of the first "1" bit in the select array that is equal to sum_ones_wanted
        and the index of the next "1" bit in the select array that is equal to sum_ones_wanted + 1
        """
        res_start_index: int = None
        r_start: int = 7
        superblock_start: int = sum_ones_wanted // self.bits_in_superblock
        start_index: int = 0
        start_byte: int = 0
        extra_bits: int = 0
        start_sum: int = 0
        start_select: int = sum_ones_wanted
        end_select: int = sum_ones_wanted + 1

        if superblock_start > 0:
            start_index = (
                int.from_bytes(
                    self.section_slice(
                        self._s_superblocks,
                        (superblock_start - 1) * 4,
                        (superblock_start - 1) * 4 + 4,
                    ),
                    byteorder="big",
                    signed=False,
                )
            ) + 1
            start_byte = start_index // 8
            extra_bits = start_index % 8
            start_sum = self.bits_in_superblock * superblock_start
        total_sum: int = start_sum
        loop_index: int = start_index

        if start_sum == sum_ones_wanted:
            res_start_index = start_index - 1

        value: int = 0
        end_byte: int = start_byte
        while total_sum < end_select:
            start_byte = end_byte
            end_byte = start_byte + 16
            for value in self.section_slice(self._s_bits, start_byte, end_byte):
                if not value:
                    loop_index += 8
                    continue
                if extra_bits > 0:
                    r_start = 7 - extra_bits
                    extra_bits = 0
                for i in range(r_start, -1, -1):
                    if value & (1 << i):
                        total_sum += 1
                        if not res_start_index and total_sum == start_select:
                            res_start_index = loop_index
                        if total_sum == end_select:
                            return [res_start_index, loop_index]
                    loop_index += 1
                r_start = 7

    def calculate_hc(self, end_request_index: int) -> int:
        """what is the total number of "1" bits in hc_bits from 0 to end_request_index?
        Returns the total sum (number) of "1" bits in hc_bits from 0 to end_request_index
        """
        bits_in_byte: int = 8
        superblock_start: int = end_request_index // self.bits_in_superblock
        start_block: int = 0
        index: int = 0
        bitsum: int = 0
        superblock_bytes: bytes = b""
        if superblock_start > 0:
            start_block = superblock_start * self.bits_in_superblock // bits_in_byte
            superblock_bytes: bytes = self.section_slice(
                self._hc_super_blocks,
                (superblock_start - 1) * 4,
                (superblock_start - 1) * 4 + 4,
            )
            bitsum = int.from_bytes(
                superblock_bytes,
                byteorder="big",
                signed=False,
            )
            index = superblock_start * self.bits_in_superblock
        end_block: int = start_block + self.bits_in_superblock // bits_in_byte + 1
        # we have already calculated the sum from 0 to start_block -1
        # now we need the sum from start_block to end_request_index
        for value in self.section_slice(self._hc_bits, start_block, end_block):
            if not value:
                index += 8
                continue
            for i in range(7, -1, -1):
                if value & (1 << i):
                    bitsum += 1
                    if index == end_request_index:
                        return bitsum
                index += 1
                if index > end_request_index:
                    return 0
        return 0  # no heads/childen found, return 0

    def has_child(self, index: int) -> bool:
        """Returns True if node has child = '1'"""
        value: int = (
            self.section_bytes(self._hc_bits, 0)
            if index < 9
            else self.section_bytes(self._hc_bits, index // 8)
        )
        return value & (1 << (7 - index % 8)) > 0

    def get_trie_range(self, start: int, end: int) -> list[int]:
        """Returns the range of letters (bytes) in the mmaped trie"""
        return list(self.section_slice(self._trie, start, end))

    def get_trie_index_of(self, start: int, end: int, letter: int) -> int:
        """Returns the index of the of letter in the given range of the mmap"""
        # print([f"{i}:{chr(c)}={c}" for i, c in enumerate   (self.section_slice(self._trie, start, end))])
        chr_index: int = self.section_find(self._trie, bytes([letter]), start, end)
        return -1 if chr_index < 0 else chr_index - start

    def get_index(self, index_value: int) -> list[int, int]:
        """Skilar gildi í index sem segir til hvar í short text
        er að finna niðurstöðuna sem á að skila til baka
        Skilar einnig lengd textans sem á að skila
        """
        start_idx: int = index_value * self.nr_bytes_in_index_block
        end_idx: int = start_idx + self.nr_bytes_in_index_block
        # short_text index:
        sh_index: int = int.from_bytes(
            self.section_slice(self._index_bits, start_idx, end_idx),
            byteorder="big",
            signed=False,
        )
        # short_text length:
        sh_len: int = int.from_bytes(
            self.section_slice(
                self._index_values_length, index_value * 2, index_value * 2 + 2
            ),
            byteorder="big",
            signed=False,
        )
        return [sh_index, sh_len]

    def is_end_of_word(self, index: int) -> bool:
        """
        Returns True if is end of word, else False
        """
        start_byte: int = index // 8
        extra_bits: int = index % 8
        return (
            self.section_bytes(self._eow_bits, start_byte) & (1 << (7 - extra_bits)) > 0
        )

    def get_value_bits_sum(self, index: int) -> int:
        """
        eow_superblock has 4 byte in each block
        Each block in eow_superblock stores the number of "1" bits at the beginning of the next block in eow_bits
        """
        # superblock start index:
        sb_start_index: int = max(0, index // 32) * 4 - 4
        sb_end_index: int = sb_start_index + 4

        # superblock bytes:
        sb_start_bytes: bytes = self.section_slice(
            self._eow_sb, sb_start_index, sb_end_index
        )
        # nr of "1" bits before the start of the current superblock:
        nr_ones_before: int = (
            0
            if index < 32
            else int.from_bytes(sb_start_bytes, byteorder="big", signed=False)
        )
        # number of bits to read in the current eow_bits block:
        nr_rest_bits: int = index - sb_end_index * 8

        eow_bytes = self.section_slice(self._eow_bits, sb_end_index, sb_end_index + 4)
        nr_ones: int = self.eow_index(nr_rest_bits, eow_bytes)

        return nr_ones + nr_ones_before - 1

    def eow_index(self, end_index: int, value_bytes: bytes) -> int:
        """Returns the index of the last "1" bit in the given bytes"""
        bits: int = 0
        index: int = 0
        i: int = 0
        for value in value_bytes:
            if not value:
                index += 8
                continue
            for i in range(7, -1, -1):
                bits += (value >> i) & 1
                if index == end_index:
                    return bits
                index += 1
        return bits

    def get_result(self, value_index: int) -> list[str]:
        """Returns result of the query"""
        value_sum: int = self.get_value_bits_sum(value_index)
        if self._has_reversed_index and self._reversed_lookup:
            value_sum = value_sum * self.nr_bytes_in_index_block
            value_sum = int.from_bytes(
                self.section_slice(
                    self._translate_index_bits,
                    value_sum,
                    value_sum + self.nr_bytes_in_index_block,
                ),
                byteorder="big",
                signed=False,
            )
        if self.check_if_key_exists:
            return [value_sum]
        index_value, text_len = self.get_index(value_sum)

        return self.get_short_text(index_value, text_len)

    def get_by_id(self, id: int) -> list[str]:
        """id is the value_sum from the method get_result()"""

        index_value, text_len = self.get_index(id)
        return self.get_short_text(index_value, text_len)

    def get_short_text(self, index: int, text_len: int) -> list[str]:
        """Returns the short text"""
        res: bytes = bytes(
            self.section_slice(self._short_text, index, index + text_len)
        )
        text_array: list[bytes] = (
            res.split(A.UNIT_SEPARATOR) if A.UNIT_SEPARATOR in res else [res]
        )
        return sorted([txt.decode("utf-8") for txt in text_array])

    def close(self):
        """Closes the mmap and file"""
        if self._view:
            self._view.release()
        if self._mmap:
            self._mmap.close()
        if self._file:
            self._file.close()
