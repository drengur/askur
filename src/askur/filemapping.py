import os
import mmap
from dataclasses import dataclass
from askur.alphabet import Alphabet
from askur.config import Config
from askur.map_infos import MapAddressInfo as ma

Config()  # Initialize the global CONFIG variable
A = Alphabet()


@dataclass(frozen=True)
class Section:
    """Represents a section of the memory-mapped file."""

    start: int
    end: int


class Mapping:
    """Class for memory-mapped file access and manipulation."""

    BYTE_LOOKUP_DICT = {i: i.bit_count() for i in range(256)}

    def __init__(self, collection: str) -> None:
        self._file: str = ""
        self._mmap: mmap.mmap = None
        self._view: memoryview = None

        self._trie: Section = None

        self._s_bits: Section = None
        self._s_superblocks: Section = None

        self._hc_bits: Section = None
        self._hc_super_blocks: Section = None

        self._eow_bits: Section = None
        self._eow_sb: Section = None

        self._index_bits: Section = None
        self._index_values_length: Section = None

        self.bits_in_superblock: int = 0
        self.collection: str = collection

        self._short_text: Section = None
        self.alphabet: Section = None

        self._check_if_key_exists: bool = False  # are we only checking if key exists?
        self._reversed_lookup: bool = False  # are we looking up suffixes?
        self._has_reversed_index: bool = False  # does the index have reversed entries?

        self.nr_bytes_in_index_block: int = 0
        self.max_index_value: int = 0  # number of (items -1)  in the short text index, used to calculate the number of items in the collection

        self._reversed_trie: Section = None
        self._reversed_s_bits: Section = None
        self._reversed_s_superblocks: Section = None

        self._reversed_hc_bits: Section = None
        self._reversed_hc_super_blocks: Section = None

        self._reversed_eow_bits: Section = None
        self._reversed_eow_sb: Section = None

        self._load_files()

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        """Ensure that the mmap and file are closed when the object is destroyed
        to avoid memory leaks and file locks"""
        self.close()

    def map_section(self, map_address: int) -> Section:
        """Convert a section slice dictionary to a Section based on the given slice."""
        section_slices = ma.value_slices(map_address)

        start = int.from_bytes(self._mmap[section_slices["start"]], byteorder="big")
        end = int.from_bytes(self._mmap[section_slices["end"]], byteorder="big")
        if end == 0 and start > 0:
            end = self._mmap.size()  # happens when the section is at the end of the file, usually the short text section, which is the last section in the file

        return Section(
            start=start,
            end=end,
        )

    def _load_files(self):
        # Check for environment variable first, then fall back to config file
        data_folder = os.environ.get("ASKUR_DATA_FOLDER")
        assert data_folder is not None, (
            "ASKUR_DATA_FOLDER environment variable is not set. Please update config.py."
        )

        frozen_folder = os.path.join(data_folder, self.collection)
        assert os.path.exists(frozen_folder), (
            f"'{self.collection}' collection does not exist! \nPlease list available collections (askur-list_collections)\nor check the ASKUR_DATA_FOLDER directory: {data_folder}"
        )

        data_filename = os.path.join(frozen_folder, "data.bin")

        self._file = open(data_filename, "rb")
        self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._view = memoryview(self._mmap)

        self.bits_in_superblock = int.from_bytes(
            self._mmap[ma.address(ma.BITS_PR_SB)], byteorder="big"
        )

        self.nr_bytes_in_index_block = int.from_bytes(
            self._mmap[ma.address(ma.BYTES_PR_INDEX_BLOCK)], byteorder="big"
        )

        self.alphabet = self.map_section(ma.ALPHABET)

        self._trie = self.map_section(ma.TRIE)

        self._s_bits = self.map_section(ma.SELECT)
        self._s_superblocks = self.map_section(ma.SELECT_SB)

        self._hc_bits = self.map_section(ma.HC)
        self._hc_super_blocks = self.map_section(ma.HC_SB)

        self._eow_bits = self.map_section(ma.EOW)
        self._eow_sb = self.map_section(ma.EOW_SB)

        self._index_bits = self.map_section(ma.INDEX_VALUE)
        self._index_values_length = self.map_section(ma.INDEX_VALUE_LENGTH)

        self._short_text = self.map_section(ma.SHORT_TEXT)

        # translate_index_bits is used to translate the
        # index value to the corresponding index in the reversed index
        self._translate_index_bits = self.map_section(ma.SUFFIX_INDEX_VALUE)

        # how many items are in the trie (max_index is equivalent to row count):
        self.max_index_value = (
            self._index_values_length.end - self._index_values_length.start
        ) // 2 - 1

        # initialize reversed lookup if the index has a suffix trie section
        # and we are doing a reversed lookup (suffix search)
        self.do_reversed_lookup(False)

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

        # If there is a suffix trie section, then we have a reversed index. If not, we don't.
        suffix_trie_section = self.map_section(ma.SUFFIX_TRIE)
        self._has_reversed_index = suffix_trie_section.end > suffix_trie_section.start
        self._reversed_lookup = reversed_lookup and self._has_reversed_index

        if self._reversed_lookup:
            # use the reversed sections for lookup
            self._trie = self.map_section(ma.SUFFIX_TRIE)
            self._s_bits = self.map_section(ma.SUFFIX_SELECT)
            self._s_superblocks = self.map_section(ma.SUFFIX_SELECT_SB)
            self._hc_bits = self.map_section(ma.SUFFIX_HC)
            self._hc_super_blocks = self.map_section(ma.SUFFIX_HC_SB)
            self._eow_bits = self.map_section(ma.SUFFIX_EOW)
            self._eow_sb = self.map_section(ma.SUFFIX_EOW_SB)

        return self._reversed_lookup

    @property
    def check_if_key_exists(self) -> bool:
        """Returns True if the search is in 'exists' mode,
        where we only check if the key (the word) exists without returning the value.
        """
        return self._check_if_key_exists

    @check_if_key_exists.setter
    def check_if_key_exists(self, value: bool):
        self._check_if_key_exists = value

    def count_items(self) -> int:
        """Returns the number of items in the index"""
        return self.max_index_value + 1

    def value_size(self) -> int:
        """Returns true size of the short text (the resulting value)"""
        return self._short_text.end - self._short_text.start

    def calculate_select(self, sum_ones_wanted: int) -> list[int, int]:
        # There are 32 bits/4 bytes in each superblock
        """Returns the index of the first "1" bit in the select array that is equal to sum_ones_wanted
        and the index of the next "1" bit in the select array that is equal to sum_ones_wanted + 1
        """
        res_start_index: int = None
        r_start: int = 7  # the bit position in the byte to start searching from, 7 is the leftmost bit
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
            r_start = 7 - extra_bits
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
                bit_count = self.BYTE_LOOKUP_DICT.get(value, 0)
                if not value or r_start == 7 and total_sum + bit_count < start_select:
                    total_sum += bit_count
                    loop_index += 8
                    continue

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
            superblock_bytes = self.section_slice(
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

    def get_value_bits_sum(self, trie_index_value: int) -> int:
        """
        eow_superblock has 4 byte in each block
        Each block in eow_sb stores the number of "1" bits at the beginning of the next block in eow_bits
        """
        # superblock start index
        sb_start_index: int = trie_index_value // 32 * 4 - 4
        sb_end_index: int = sb_start_index + 4

        # superblock bytes
        sb_start_bytes: bytes = (
            0
            if trie_index_value < 32
            else self.section_slice(self._eow_sb, sb_start_index, sb_end_index)
        )

        # nr of "1" bits before the start of the current superblock:
        nr_ones_before: int = (
            0
            if trie_index_value < 32
            else int.from_bytes(sb_start_bytes, byteorder="big", signed=False)
        )
        # number of bits to read in the current eow_bits block:
        nr_rest_bits: int = trie_index_value - sb_end_index * 8

        eow_bytes = self.section_slice(self._eow_bits, sb_end_index, sb_end_index + 4)
        nr_ones: int = self.eow_index(nr_rest_bits, eow_bytes)
        return nr_ones + nr_ones_before - 1

    def eow_index(self, end_index: int, value_bytes: bytes) -> int:
        """Returns the index of the last "1" bit in the given bytes"""
        bitsum: int = 0
        index: int = 0
        i: int = 0

        for value in value_bytes:
            if not value or index + 8 < end_index:
                bitsum += self.BYTE_LOOKUP_DICT.get(value, 0)
                index += 8
                continue
            for i in range(7, -1, -1):
                bitsum += (value >> i) & 1
                if index == end_index:
                    return bitsum
                index += 1
        return bitsum

    def translate_index(self, index_value: int) -> int:
        """Translate the index value to the corresponding index in the reversed index"""
        start_idx: int = index_value * self.nr_bytes_in_index_block
        end_idx: int = start_idx + self.nr_bytes_in_index_block

        # short_text index:
        translated_index: int = int.from_bytes(
            self.section_slice(self._translate_index_bits, start_idx, end_idx),
            byteorder="big",
            signed=False,
        )
        return translated_index

    def get_result(self, trie_index_value: int) -> list[str]:
        """Returns result of the query"""
        eow_index_value: int = self.get_value_bits_sum(trie_index_value)

        if self._reversed_lookup:
            eow_index_value = self.translate_index(eow_index_value)
        return self.get_by_id(eow_index_value)

    def get_by_id(self, value_index_id: int) -> list[str]:
        """id is the value_sum from the method get_result()"""

        if value_index_id < 0 or value_index_id > self.max_index_value:
            return []
        if self._check_if_key_exists:
            return [value_index_id]

        index_value, text_len = self.get_index(value_index_id)
        return {value_index_id: self.get_short_text(index_value, text_len)}

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
