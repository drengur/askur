import io
import os
import mmap
from askur.alphabet import Alphabet
from askur.config import Config
Config()  # initialize config environment variables
A = Alphabet()


class Mapping:
    def __init__(self, collection: str) -> None:
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
        self._triet_start: int = 0
        self._select_start: int = 0
        self._select_superblock_start: int = 0
        self._hc_start: int = 0
        self._hc_superblock_start: int = 0
        self._eow_start: int = 0
        self._eow_superblock_start: int = 0
        self._index_start: int = 0
        self.alphabet_index_start: int = 0

        self.alphabet: bytes = b""
        self.check_if_key_exists: bool = False  # are we only checking if key exists?
        self._reversed_lookup: bool = False  # are we looking up reversed entries?
        self._has_reversed_index: bool = False  # does the index have reversed entries?

        self.nr_bytes_in_index_block: int = 0

        self._reversed_trie: bytes = b""

        self._reversed_s_bits: bytes = b""
        self._reversed_s_superblocks: bytes = b""
        self._reversed_hc_bits: bytes = b""
        self._reversed_hc_super_blocks: bytes = b""

        self._reversed_eow_bits: bytes = b""
        self._reversed_eow_sb: bytes = b""

        # self._reversed_index_bits: bytes = b""

        self._short_text: bytes = b""

        # pointers to the starts of the reversed sections
        self._reversed_trie_start: int = 0

        self._reversed_select_start: int = 0
        self._reversed_select_superblock_start: int = 0
        self._reversed_hc_start: int = 0
        self._reversed_hc_superblock_start: int = 0

        self._reversed_eow_start: int = 0
        self._reversed_eow_superblock_start: int = 0

        # self._reversed_index_start: int = 0

        # lookup tables in use for index lookups or reverse index lookups
        self._lookup_trie_list: bytes = b""

        self._lookup_s_bits_list: bytes = b""
        self._lookup_s_superblocks_list: bytes = b""
        self._lookup_hc_bits_list: bytes = b""
        self._lookup_hc_super_blocks_list: bytes = b""

        self._lookup_eow_bits_list: bytes = b""
        self._lookup_eow_sb_list: bytes = b""

        self._lookup_index_bits_list: bytes = b""
        self._lookup_index_values_length_list: bytes = b""

        # self._lookup_short_text_list: bytes = b""
        self._load_files()

    def _load_files(self):
        # Check for environment variable first, then fall back to config file
        data_folder = os.environ.get("ASKUR_DATA_FOLDER")
        assert data_folder is not None, (
            "DATA_FOLDER environment variable is not set. Please update config.py."
        )

        frozen_folder = os.path.join(data_folder, self.collection)
        if not os.path.exists(frozen_folder):
            available_collections = [
                name
                for name in os.listdir(data_folder)
                if os.path.isdir(os.path.join(data_folder, name))
            ]
            assert False, (
                f"{self.collection} collection does not exist!\n Existing collections are: {available_collections}"
            )

        data_filename = os.path.join(frozen_folder, "data.bin")

        with io.open(data_filename, "rb") as f_data:
            data = mmap.mmap(f_data.fileno(), 0, access=mmap.ACCESS_READ)
            self.bits_in_superblock = int.from_bytes(data[4:8], byteorder="big")
            self.nr_bytes_in_index_block = int.from_bytes(data[8:12], byteorder="big")

            alphabet_start = int.from_bytes(data[12:16], byteorder="big")

            trie_start = int.from_bytes(data[16:20], byteorder="big")

            select_bits_start = int.from_bytes(data[20:24], byteorder="big")
            select_superblock_start = int.from_bytes(data[24:28], byteorder="big")

            hc_start = int.from_bytes(data[28:32], byteorder="big")
            hc_superblock_start = int.from_bytes(data[32:36], byteorder="big")

            eow_bytes_start = int.from_bytes(data[36:40], byteorder="big")
            eow_superblock_start = int.from_bytes(data[40:44], byteorder="big")

            index_value_start = int.from_bytes(data[44:48], byteorder="big")
            index_values_length_start = int.from_bytes(data[48:52], byteorder="big")

            short_text_start = int.from_bytes(data[52:56], byteorder="big")

            reversed_trie_start = int.from_bytes(data[60:64], byteorder="big")
            reversed_select_start = int.from_bytes(data[64:68], byteorder="big")
            reversed_select_superblock_start = int.from_bytes(
                data[68:72], byteorder="big"
            )
            reversed_hc_start = int.from_bytes(data[72:76], byteorder="big")
            reversed_hc_superblock_start = int.from_bytes(data[76:80], byteorder="big")
            reversed_eow_start = int.from_bytes(data[80:84], byteorder="big")
            reversed_eow_superblock_start = int.from_bytes(data[84:88], byteorder="big")
            reversed_index_start = int.from_bytes(data[88:92], byteorder="big")

            self.alphabet = data[alphabet_start:trie_start]
            self._trie = data[trie_start:select_bits_start]

            self._s_bits = data[select_bits_start:select_superblock_start]
            self._s_superblocks = data[select_superblock_start:hc_start]

            self._hc_bitarray = data[hc_start:hc_superblock_start]
            self._hc_super_blocks = data[hc_superblock_start:eow_bytes_start]

            self._eow_bits = data[eow_bytes_start:eow_superblock_start]
            self._eow_sb = data[eow_superblock_start:index_value_start]

            self._index_bits = data[index_value_start:index_values_length_start]
            self._index_values_length = data[index_values_length_start:short_text_start]

            if reversed_trie_start > 0:
                self._short_text = data[short_text_start:reversed_trie_start]
            else:
                self._short_text = data[short_text_start:]

            self._reversed_trie = data[reversed_trie_start:reversed_select_start]
            # select bits
            self._reversed_s_bits = data[
                reversed_select_start:reversed_select_superblock_start
            ]
            self._reversed_s_superblocks = data[
                reversed_select_superblock_start:reversed_hc_start
            ]
            # hc bits
            self._reversed_hc_bits = data[
                reversed_hc_start:reversed_hc_superblock_start
            ]
            self._reversed_hc_super_blocks = data[
                reversed_hc_superblock_start:reversed_eow_start
            ]
            # eow bits
            self._reversed_eow_bits = data[
                reversed_eow_start:reversed_eow_superblock_start
            ]
            self._reversed_eow_sb = data[reversed_eow_superblock_start:]
            # index bits
            # ATT: We are not using reversed index bits, but translating the index values
            # back to normal index values
            # self._reversed_index_bits = self._index_bits
            self._translate_index_bits = data[reversed_index_start:]

            self._has_reversed_index = len(self._reversed_trie) > 0

            self._lookup_trie_list = self._trie
            self._lookup_s_bits_list = self._s_bits
            self._lookup_s_superblocks_list = self._s_superblocks
            self._lookup_hc_bits_list = self._hc_bitarray
            self._lookup_hc_super_blocks_list = self._hc_super_blocks
            self._lookup_eow_bits_list = self._eow_bits
            self._lookup_eow_sb_list = self._eow_sb
            self._lookup_index_bits_list = self._index_bits
            self._lookup_index_values_length_list = self._index_values_length

    def has_reversed_index(self) -> bool:
        """Returns True if the index is reversed"""
        return self._has_reversed_index

    def do_reversed_lookup(self, reversed_lookup: bool) -> bool:
        """Returns True if the index is reversed and we are doing reversed lookup"""
        self._reversed_lookup = reversed_lookup and self.has_reversed_index()
        if self._reversed_lookup:
            self._lookup_trie_list = self._reversed_trie
            self._lookup_s_bits_list = self._reversed_s_bits
            self._lookup_s_superblocks_list = self._reversed_s_superblocks
            self._lookup_hc_bits_list = self._reversed_hc_bits
            self._lookup_hc_super_blocks_list = self._reversed_hc_super_blocks
            self._lookup_eow_bits_list = self._reversed_eow_bits
            self._lookup_eow_sb_list = self._reversed_eow_sb
        else:
            self._lookup_trie_list = self._trie
            self._lookup_s_bits_list = self._s_bits
            self._lookup_s_superblocks_list = self._s_superblocks
            self._lookup_hc_bits_list = self._hc_bitarray
            self._lookup_hc_super_blocks_list = self._hc_super_blocks
            self._lookup_eow_bits_list = self._eow_bits
            self._lookup_eow_sb_list = self._eow_sb
        return self._reversed_lookup

    def set_check_key_exists(self, check_key_exists: bool) -> bool:
        """Returns True if the key exists in the index"""
        self.check_if_key_exists = check_key_exists
        return check_key_exists

    def calculate_select(self, sum_ones_wanted: int) -> list[int, int]:
        # There are 32 bits/4 bytes in each superblock

        res_end_index: int = None
        res_start_index: int = None
        r_start: int = 7
        superblock_start: int = sum_ones_wanted // self.bits_in_superblock
        start_index: int = 0
        start_byte: int = 0
        extra_bits: int = 0
        start_sum: int = 0

        if superblock_start > 0:
            start_index = (
                int.from_bytes(
                    self._lookup_s_superblocks_list[
                        (superblock_start - 1) * 4 : (superblock_start - 1) * 4 + 4
                    ],
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

        byte: int = 0
        i: int = 0

        while total_sum < sum_ones_wanted + 1:
            for byte in self._lookup_s_bits_list[start_byte : start_byte + 1]:
                if not byte:
                    start_byte += 1
                    loop_index += 8
                    continue

                if extra_bits > 0:
                    r_start = 7 - extra_bits
                    extra_bits = 0
                for i in range(r_start, -1, -1):
                    if byte & (1 << i):
                        total_sum += 1
                        if total_sum == sum_ones_wanted and res_start_index is None:
                            res_start_index = loop_index
                        if total_sum == sum_ones_wanted + 1 and res_end_index is None:
                            res_end_index = loop_index
                            break
                    loop_index += 1
                r_start = 7
                start_byte += 1
        return [res_start_index, res_end_index]

    def calculate_hc(self, end_request_index: int) -> int:
        """Hver er heildar summan við end_request_index"""
        bits_in_byte: int = 8
        superblock_start: int = end_request_index // self.bits_in_superblock
        start_block: int = 0
        index: int = 0
        bitsum: int = 0
        superblock_bytes: bytes = b""
        if superblock_start > 0:
            start_block = superblock_start * self.bits_in_superblock // bits_in_byte
            superblock_bytes: bytes = self._lookup_hc_super_blocks_list[
                (superblock_start - 1) * 4 : (superblock_start - 1) * 4 + 4
            ]
            bitsum = int.from_bytes(
                superblock_bytes,
                byteorder="big",
                signed=False,
            )
            index = superblock_start * self.bits_in_superblock
        end_block: int = start_block + self.bits_in_superblock // bits_in_byte + 1
        # það er búið að reikna summu frá 0 til start_block -1
        # þá vantar summuna frá start_block til end_request_index
        for byte in self._lookup_hc_bits_list[start_block:end_block]:  # bytes:
            if not byte:
                index += 8
                continue
            for i in range(7, -1, -1):
                if byte & (1 << i):
                    bitsum += 1
                    if index == end_request_index:
                        return bitsum
                index += 1
        return 0

    def has_child(self, index: int) -> bool:
        """Returns True if node has child = '1'"""
        byte: int = (
            self._lookup_hc_bits_list[0]
            if index < 9
            else self._lookup_hc_bits_list[index // 8]
        )
        return byte & (1 << (7 - index % 8)) > 0

    def get_trie_range(self, start: int, end: int) -> list[int]:
        """Returns the range of letters (bytes) in the mmaped trie """
        return self._lookup_trie_list[start:end]

    def get_trie_index_of(self, start: int, end: int, letter: int) -> int:
        """Returns the index of the of letter in the given range of the mmap"""
        return self._lookup_trie_list[start:end].find(letter)

    def get_index(self, index_value: int) -> list[int, int]:
        """Skilar gildi í index sem segir til hvar í short text
        er að finna niðurstöðuna sem á að skila til baka
        Skilar einnig lengd textans sem á að skila
        """

        start_idx: int = index_value * self.nr_bytes_in_index_block
        end_idx: int = start_idx + self.nr_bytes_in_index_block

        # short_text index:
        sh_index: int = int.from_bytes(
            self._lookup_index_bits_list[start_idx:end_idx],
            byteorder="big",
            signed=False,
        )
        # short_text length:
        sh_len: int = int.from_bytes(
            self._lookup_index_values_length_list[
                index_value * 2 : index_value * 2 + 2
            ],
            byteorder="big",
            signed=False,
        )

        return [sh_index, sh_len]

    def is_end_of_word(self, index: int) -> int:
        """
        Returns 1 if is end of word, else 0
        """

        start_byte: int = index // 8
        extra_bits: int = index % 8

        if self._lookup_eow_bits_list[start_byte : start_byte + 1][0] & (
            1 << (7 - extra_bits)
        ):
            return 1
        return 0

    def get_value_bits_sum(self, index: int) -> int:
        """
        Returns the sum of "0"  bits in the value bits
        Það eru 32 bitar í hverju boxi (= 4 bytes)
        Þess vegna þarf að margfalda index með 4 til að fá réttu bætin sem við erum að leita í
        þessir 32 bitar í superblock geyma tölu á fjölda bita í byrjun boxins
        end_index er fjöldi bita í byrjun á næsta boxi sem kemur á eftir.
        """
        s_start: int = (index // 32 - 1) * 4
        s_end: int = s_start + 4
        start_bytes: bytes = self._lookup_eow_sb_list[s_start:s_end]
        start_index: int = int.from_bytes(start_bytes, byteorder="big", signed=False)

        end_bytes: bytes = self._lookup_eow_sb_list[s_end : s_end + 4]
        end_index: int = int.from_bytes(end_bytes, byteorder="big", signed=False)

        if end_index == start_index:
            return start_index

        extra_bits: int = index - s_end * 8 + 1
        value_bytes: bytes = self._lookup_eow_bits_list[s_end : s_end + 4]
        for byte in value_bytes:
            if not byte and extra_bits > 8:
                extra_bits -= 8
                continue
            for i in range(7, -1, -1):
                if extra_bits > 0:
                    extra_bits -= 1
                    if byte & (1 << i):
                        start_index += 1
                else:
                    return start_index - 1
        return start_index - 1

    def get_result(self, value_index: int) -> list[str]:
        """Returns result of the query"""
        value_sum: int = self.get_value_bits_sum(value_index)
        if self._has_reversed_index and self._reversed_lookup:
            value_sum = value_sum * self.nr_bytes_in_index_block
            value_sum = int.from_bytes(
                self._translate_index_bits[
                    value_sum : value_sum + self.nr_bytes_in_index_block
                ],
                byteorder="big",
                signed=False,
            )
        if self.check_if_key_exists:
            return [value_sum]
        index_value, text_len = self.get_index(value_sum)
        return self.get_short_text(index_value, text_len)

    def get_by_id(self, id: int) -> list[str]:
        # id is the value_sum from the method get_result()
        index_value, text_len = self.get_index(id)
        return self.get_short_text(index_value, text_len)

    def get_short_text(self, index: int, text_len: int) -> list[str]:
        """Returns the short text"""
        res: bytes = self._short_text[index : index + text_len]
        unicodes: bytearray = bytearray()
        text_array: list[str] = []
        i: int = 0
        while i < len(res):
            if res[i] == A.RES_SEPARATOR:
                text_array.append(A.convert_bytes_to_str(unicodes))
                unicodes = bytearray()
            else:
                unicodes.append(res[i])
            i += 1
        if len(unicodes) > 0:
            text_array.append(A.convert_bytes_to_str(unicodes))
        return sorted(text_array)
