import io
import os

# import configparser
import mmap
import cython


class Mapping:
    def __init__(self, collection: str) -> None:
        self._trie: mmap.mmap
        self._hc_bitarray: mmap.mmap
        self._s_bits: mmap.mmap
        self._eow_bits: mmap.mmap
        self.short_text_len: int = 0
        self._s_lookup_blocks: mmap.mmap  # Type unknown, set to None
        self._s_superblocks: mmap.mmap
        self._hc_super_blocks: mmap.mmap
        self._hc_lookup_blocks: mmap.mmap  # Type unknown, set to None
        self.bits_in_superblock: int = 0
        self.collection: str = collection
        self._eow_sb: mmap.mmap
        self.nr_bytes_in_index_block: int = 0
        self.nr_bytes_in_value_block: int = 0
        self.alphabet: mmap.mmap | bytearray = bytearray()
        self.reversed: bool = False
        self.check_if_key_exists = False  #

        self._load_files()

    def _load_files(self):
        confs = {}
        config_file = os.path.join(os.path.dirname(__file__), "askur.conf")
        with open(config_file, "r") as f:
            for line in f:
                if line.startswith("#") or line.startswith("\n"):
                    continue
                if "=" not in line:
                    print(
                        f"Error: in line {line}.\n  No '=' found.\n  Please add missing '=' and try again. \n Exiting."
                    )
                    return -1
                confs[line.split("=")[0].strip()] = line.split("=")[1].strip()
        DATA_FOLDER = confs.get("DATA_FOLDER")
        if DATA_FOLDER is None:
            print(
                f"Error: in line {line}.\n  No DATA_FOLDER found.\n  Please add missing DATA_FOLDER and try again. \n Exiting."
            )
            return -1

        frozen_folder = os.path.join(
            os.path.dirname(__file__), DATA_FOLDER, self.collection
        )
        if not os.path.exists(frozen_folder):
            existing_collections = os.listdir(os.path.join(DATA_FOLDER))
            raise FileNotFoundError(
                f"{self.collection} collection does not exist!\n Existing collections are: {existing_collections}"
            )

        # SELECT FILE (bits)
        SELECT_BITS_FILE = os.path.join(frozen_folder, "s_bits.bin")
        # HEADCOUNt FILE (bits)
        HC_BITS_FILE = os.path.join(frozen_folder, "hc_bits.bin")

        # HC SUPERBLOCK FILE
        HC_SB_BIN = os.path.join(frozen_folder, "hc_sb.bin")
        # Select superblock file
        S_SB_BIN = os.path.join(frozen_folder, "s_sb.bin")
        # trie (Louds) file
        TRIE_FILE = os.path.join(frozen_folder, "trie")

        # end of word bits file (value bits)
        EOW_BITS_FILE = os.path.join(frozen_folder, "eow_bits.bin")

        # end of word bits summary file (super block file)
        EOW_BITS_SUMMARY_FILE = os.path.join(frozen_folder, "eow_sb.bin")

        # VALUE_BITS_FAT_FILE = os.path.join(frozen_folder, "eow_bits.bin" + ".fat")

        INDEX_BITS_FILE = os.path.join(frozen_folder, "index_bits.bin")

        SHORT_TEXT_BITS_FILE = os.path.join(frozen_folder, "short_text_bits.bin")
        ALPHABET_FILE = os.path.join(frozen_folder, "trie.alphabet")

        # SELECT SUPERBLOCK FILE
        with io.open(S_SB_BIN, "rb") as f_s_superblocks:
            self._s_superblocks = mmap.mmap(
                f_s_superblocks.fileno(), 0, access=mmap.ACCESS_READ
            )
            self.bits_in_superblock = self._s_superblocks[0]
            self._s_superblocks = self._s_superblocks[1:]

        with io.open(TRIE_FILE, "rb") as f_trie:
            self._trie = mmap.mmap(f_trie.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(HC_BITS_FILE, "rb") as f_hc_bitarray:
            self._hc_bitarray = mmap.mmap(
                f_hc_bitarray.fileno(), 0, access=mmap.ACCESS_READ
            )

        with io.open(HC_SB_BIN, "rb") as f_hc_super_blocks:
            self._hc_super_blocks = mmap.mmap(
                f_hc_super_blocks.fileno(), 0, access=mmap.ACCESS_READ
            )

        with io.open(SELECT_BITS_FILE, "rb") as f_select_bits:
            self._s_bits = mmap.mmap(f_select_bits.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(EOW_BITS_FILE, "rb") as f_value_bits:
            self._eow_bits = mmap.mmap(
                f_value_bits.fileno(), 0, access=mmap.ACCESS_READ
            )

        with io.open(
            EOW_BITS_SUMMARY_FILE, "r", encoding="utf-8"
        ) as f_eow_bits_summary:
            self._eow_sb = mmap.mmap(
                f_eow_bits_summary.fileno(), 0, access=mmap.ACCESS_READ
            )

        with io.open(INDEX_BITS_FILE, "rb") as f_index_bits:
            self._index_bits = mmap.mmap(
                f_index_bits.fileno(), 0, access=mmap.ACCESS_READ
            )
            self.nr_bytes_in_index_block = int.from_bytes(
                self._index_bits[0:1], byteorder="little", signed=False
            )
            self.nr_bytes_in_value_block = int.from_bytes(
                self._index_bits[1:2], byteorder="little", signed=False
            )
            self._index_bits = self._index_bits[2:]

        with io.open(SHORT_TEXT_BITS_FILE, "r", encoding="utf-8") as f_short_text:
            self._short_text = mmap.mmap(
                f_short_text.fileno(), 0, access=mmap.ACCESS_READ
            )
        with io.open(ALPHABET_FILE, "rb") as f_alphabet:
            self.alphabet = mmap.mmap(f_alphabet.fileno(), 0, access=mmap.ACCESS_READ)

        # Check if value 143 exists in self.alphabet (is it reversed?)
        if b"\x8f" == self.alphabet[0:1]:
            self.reversed = True

    def is_reversed(self) -> bool:
        """Returns True if the index is reversed"""
        return self.reversed

    def set_check_key_exists(self, check_key_exists: bool) -> bool:
        """Returns True if the key exists in the index"""
        self.check_if_key_exists = check_key_exists
        return self.check_if_key_exists

    def calculate_select(self, sum_ones_wanted: cython.int) -> list[int, int]:
        # There are 32 bits/4 bytes in each superblock

        res_end_index: cython.int = None
        res_start_index = cython.int = None
        r_start = cython.int = 7
        superblock_start = cython.int = sum_ones_wanted // self.bits_in_superblock
        start_index: cython.int = 0
        start_byte: cython.int = 0
        extra_bits: cython.int = 0
        start_sum: cython.int = 0

        if superblock_start > 0:
            start_index = (
                int.from_bytes(
                    self._s_superblocks[
                        (superblock_start - 1) * 4 : (superblock_start - 1) * 4 + 4
                    ],
                    byteorder="big",
                    signed=False,
                )
            ) + 1
            start_byte = start_index // 8
            extra_bits = start_index % 8
            start_sum = self.bits_in_superblock * superblock_start

        total_sum: cython.int = start_sum
        loop_index: cython.int = start_index

        if start_sum == sum_ones_wanted:
            res_start_index = start_index - 1

        byte: cython.int = 0
        i: cython.int = 0

        while total_sum < sum_ones_wanted + 1:
            for byte in self._s_bits[start_byte : start_byte + 1]:
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

    def calculate_hc(self, end_request_index) -> int:
        """Hver er heildar summan við end_request_index"""
        bits_in_byte = 8
        superblock_start = end_request_index // self.bits_in_superblock

        if superblock_start == 0:
            index = 0
            bitsum = 0
            end_block = self.bits_in_superblock // bits_in_byte + 1
            for byte in self._hc_bitarray[0:end_block]:
                if not byte:
                    index += 8
                    continue
                for i in range(7, -1, -1):
                    if byte & (1 << i):
                        bitsum += 1
                        if index == end_request_index:
                            return bitsum
                    index += 1
        else:
            bitsum = int(
                "".join(
                    [
                        bin(byte)[2:].rjust(8, "0")
                        for byte in self._hc_super_blocks[
                            (superblock_start - 1) * 4 : (superblock_start - 1) * 4 + 4
                        ]
                    ]
                ),
                2,
            )

        # það er búið að reikna summu frá 0 til start_block -1
        # þá vantar summuna frá start_block til end_request_index
        start_block = superblock_start * self.bits_in_superblock // bits_in_byte
        end_block = start_block + self.bits_in_superblock // bits_in_byte + 1
        index = superblock_start * self.bits_in_superblock
        for byte in self._hc_bitarray[start_block:end_block]:  # bytes:
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

    def has_child(self, index) -> bool:
        """Returns True if node has child = '1'"""
        byte = self._hc_bitarray[0] if index < 9 else self._hc_bitarray[index // 8]
        return byte & (1 << (7 - index % 8)) > 0

    def get_trie_range(self, start, end) -> list[int]:
        """Returns the letter (int of letter) in the given range or the range itself"""
        return self._trie[start:end]

    def get_trie_index_of(self, start, end, letter) -> int:
        """Returns the index of the of letter in the given range of the mmap"""
        return self._trie[start:end].find(letter)

    def get_index(self, index_value) -> int:
        """Skilar gildi í index sem segir til hvar í short text er að finna niðurstöðuna sem á að skila til baka
        Skilar einnig lengd textans sem á að skila
        """
        if index_value == 0:
            start_idx = 0
        else:
            # start_idx = index_value * 6 # 4 + 2 byte = 32 + 16 bitar
            start_idx = index_value * (
                self.nr_bytes_in_index_block + self.nr_bytes_in_value_block
            )
        end_idx = start_idx + self.nr_bytes_in_index_block

        start_len = end_idx
        end_len = start_len + self.nr_bytes_in_value_block

        index_val = int.from_bytes(
            self._index_bits[start_idx:end_idx],
            byteorder="big",
            signed=False,
        )
        len_value = int.from_bytes(
            self._index_bits[start_len:end_len],
            byteorder="big",
            signed=False,
        )
        return [index_val, len_value]

    def is_end_of_word(self, index) -> int:
        """
        Returns 1 if is end of word, else 0
        """

        start_byte = index // 8
        extra_bits = index % 8

        bits = bin(
            int.from_bytes(
                self._eow_bits[start_byte : start_byte + 1],
                byteorder="big",
                signed=False,
            )
        )[2:].rjust(8, "0")
        return int(bits[extra_bits : extra_bits + 1])

    def get_value_bits_sum(self, index) -> int:
        """
        Returns the sum of "0"  bits in the value bits
        Það eru 32 bitar í hverju boxi sem skiptist í 4 bæt (4*8 = 32)
        Þess vegna þarf að margfalda index með 4 til að fá réttu bætin sem við erum að leita í
        þessir 32 bitar í boxi geyma tölu á fjölda bita í byrjun boxins
        end_index er fjöldi bita í næsta boxi á eftir.
        """
        s_start = (index // 32 - 1) * 4
        s_end = s_start + 4
        start_bytes = self._eow_sb[s_start : s_start + 4]
        start_index = int.from_bytes(start_bytes, byteorder="big", signed=False)

        end_bytes = self._eow_sb[s_end : s_end + 4]
        end_index = int.from_bytes(end_bytes, byteorder="big", signed=False)

        if end_index == start_index:
            return start_index

        extra_bits = index - s_end * 8 + 1
        value_bits = self._eow_bits[s_end : s_end + 4]
        for byte in value_bits:
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

    def get_result(self, value_index, reversed=False) -> list[str]:
        """Returns result of the query"""

        # We know that the key exists at this point and the user
        # is only interested to know if it does exist.
        if self.check_if_key_exists:
            return ["1"]

        value_sum = self.get_value_bits_sum(value_index)
        index_value, text_len = self.get_index(value_sum)
        return self.get_short_text(index_value, text_len)

    def get_short_text(self, index, text_len) -> list[str]:
        """Returns the short text"""
        res = self._short_text[index : index + text_len]

        text_arr = []
        short_texts = []
        i = 0
        # Loop through the result bytes
        while i < len(res):
            if res[i] == 141:  # new line of result
                short_texts.append("".join(text_arr))
                text_arr = []
                i += 1
                continue
            if res[i] == 129:  # special character indicating a 4-byte character
                bits = [bin(res[i + 1])[2:].rjust(8, "0") for i in range(1, 5)]
                text_arr.append(chr(int("".join(bits), 2)))
                i += 5
                continue
            text_arr.append(chr(res[i]))
            i += 1

        if len(text_arr) > 0:
            short_texts.append("".join(text_arr))
            short_texts.sort()
        return short_texts
