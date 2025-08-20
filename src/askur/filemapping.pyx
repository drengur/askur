# distutils: language = c++
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: profile=False

import io
import os
import mmap

cdef class Mapping:
    # C-level attributes for maximum speed
    cdef public object _trie
    cdef public object _hc_bitarray
    cdef public object _s_bits
    cdef public object _eow_bits
    cdef public int short_text_len
    cdef public object _s_lookup_blocks
    cdef public object _s_superblocks
    cdef public object _hc_super_blocks
    cdef public object _hc_lookup_blocks
    cdef public int bits_in_superblock
    cdef public str collection
    cdef public object _eow_sb
    cdef public int nr_bytes_in_index_block
    cdef public int nr_bytes_in_value_block
    cdef public object alphabet
    cdef public bint reversed
    cdef public bint check_if_key_exists
    cdef public object _index_bits
    cdef public object _short_text

    def __init__(self, collection: str) -> None:
        self.short_text_len = 0
        self.bits_in_superblock = 0
        self.collection = collection
        self.nr_bytes_in_index_block = 0
        self.nr_bytes_in_value_block = 0
        self.alphabet = bytearray()
        self.reversed = False
        self.check_if_key_exists = False
        self._load_files()

    def _load_files(self):
        cdef dict confs = {}
        cdef str line, key, value
        cdef str DATA_FOLDER, frozen_folder
        
        with open("askur.conf", "r") as f:
            for line in f:
                if line.startswith("#") or line.startswith("\n"):
                    continue
                if "=" not in line:
                    print(f"Error: in line {line}.\n  No '=' found.\n  Please add missing '=' and try again. \n Exiting.")
                    return -1
                parts = line.split("=", 1)
                confs[parts[0].strip()] = parts[1].strip()
        
        DATA_FOLDER = confs.get("DATA_FOLDER")
        if DATA_FOLDER is None:
            print(f"Error: No DATA_FOLDER found.\n  Please add missing DATA_FOLDER and try again. \n Exiting.")
            return -1

        frozen_folder = os.path.join(DATA_FOLDER, self.collection)
        if not os.path.exists(frozen_folder):
            existing_collections = os.listdir(DATA_FOLDER)
            raise FileNotFoundError(f"{self.collection} collection does not exist!\n Existing collections are: {existing_collections}")

        # File paths
        cdef str SELECT_BITS_FILE = os.path.join(frozen_folder, "s_bits.bin")
        cdef str HC_BITS_FILE = os.path.join(frozen_folder, "hc_bits.bin")
        cdef str HC_SB_BIN = os.path.join(frozen_folder, "hc_sb.bin")
        cdef str S_SB_BIN = os.path.join(frozen_folder, "s_sb.bin")
        cdef str TRIE_FILE = os.path.join(frozen_folder, "trie")
        cdef str EOW_BITS_FILE = os.path.join(frozen_folder, "eow_bits.bin")
        cdef str EOW_BITS_SUMMARY_FILE = os.path.join(frozen_folder, "eow_sb.bin")
        cdef str INDEX_BITS_FILE = os.path.join(frozen_folder, "index_bits.bin")
        cdef str SHORT_TEXT_BITS_FILE = os.path.join(frozen_folder, "short_text_bits.bin")
        cdef str ALPHABET_FILE = os.path.join(frozen_folder, "trie.alphabet")

        # Load files without pointer caching
        with io.open(S_SB_BIN, "rb") as f_s_superblocks:
            self._s_superblocks = mmap.mmap(f_s_superblocks.fileno(), 0, access=mmap.ACCESS_READ)
            self.bits_in_superblock = self._s_superblocks[0]
            self._s_superblocks = self._s_superblocks[1:]

        with io.open(TRIE_FILE, "rb") as f_trie:
            self._trie = mmap.mmap(f_trie.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(HC_BITS_FILE, "rb") as f_hc_bitarray:
            self._hc_bitarray = mmap.mmap(f_hc_bitarray.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(HC_SB_BIN, "rb") as f_hc_super_blocks:
            self._hc_super_blocks = mmap.mmap(f_hc_super_blocks.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(SELECT_BITS_FILE, "rb") as f_select_bits:
            self._s_bits = mmap.mmap(f_select_bits.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(EOW_BITS_FILE, "rb") as f_value_bits:
            self._eow_bits = mmap.mmap(f_value_bits.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(EOW_BITS_SUMMARY_FILE, "rb") as f_eow_bits_summary:
            self._eow_sb = mmap.mmap(f_eow_bits_summary.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(INDEX_BITS_FILE, "rb") as f_index_bits:
            self._index_bits = mmap.mmap(f_index_bits.fileno(), 0, access=mmap.ACCESS_READ)
            self.nr_bytes_in_index_block = self._index_bits[0]
            self.nr_bytes_in_value_block = self._index_bits[1]
            self._index_bits = self._index_bits[2:]

        with io.open(SHORT_TEXT_BITS_FILE, "rb") as f_short_text:
            self._short_text = mmap.mmap(f_short_text.fileno(), 0, access=mmap.ACCESS_READ)

        with io.open(ALPHABET_FILE, "rb") as f_alphabet:
            self.alphabet = mmap.mmap(f_alphabet.fileno(), 0, access=mmap.ACCESS_READ)

        # Check if reversed
        if len(self.alphabet) > 0 and self.alphabet[0] == 0x8f:
            self.reversed = True

    cpdef bint is_reversed(self):
        """Returns True if the index is reversed"""
        return self.reversed
    
    cpdef bint set_check_key_exists(self, bint check_key_exists):
        """Returns True if the key exists in the index"""
        self.check_if_key_exists = check_key_exists
        return self.check_if_key_exists

    cpdef list calculate_select(self, int sum_ones_wanted):
        """Calculate select range - using mmap objects directly for safety"""
        cdef int res_end_index = -1  
        cdef int res_start_index = -1
        cdef int r_start = 7
        cdef int superblock_start = sum_ones_wanted // self.bits_in_superblock
        cdef int start_index = 0
        cdef int start_byte = 0
        cdef int extra_bits = 0
        cdef int start_sum = 0
        cdef int total_sum, loop_index
        cdef int byte_val
        cdef int i

        if superblock_start > 0:
            # Use original mmap access for superblock data
            superblock_bytes = self._s_superblocks[(superblock_start - 1) * 4:(superblock_start - 1) * 4 + 4]
            start_index = int.from_bytes(superblock_bytes, byteorder="big", signed=False) + 1
            start_byte = start_index // 8
            extra_bits = start_index % 8
            start_sum = self.bits_in_superblock * superblock_start

        total_sum = start_sum
        loop_index = start_index

        if start_sum == sum_ones_wanted:
            res_start_index = start_index - 1

        # Main loop - exactly like original Python version
        while total_sum < sum_ones_wanted + 1:
            # Get byte using original mmap access
            byte_val = self._s_bits[start_byte]
            
            if not byte_val:
                start_byte += 1
                loop_index += 8
                continue

            if extra_bits > 0:
                r_start = 7 - extra_bits
                extra_bits = 0
            
            for i in range(r_start, -1, -1):
                if byte_val & (1 << i):
                    total_sum += 1
                    if total_sum == sum_ones_wanted and res_start_index == -1:
                        res_start_index = loop_index
                    if total_sum == sum_ones_wanted + 1 and res_end_index == -1:
                        res_end_index = loop_index
                        break
                loop_index += 1
            
            r_start = 7
            start_byte += 1

        return [res_start_index, res_end_index]

    cpdef int calculate_hc(self, int end_request_index):
        """Calculate head count - using safe mmap access"""
        cdef int bits_in_byte = 8
        cdef int superblock_start = end_request_index // self.bits_in_superblock
        cdef int bitsum = 0
        cdef int index = 0
        cdef int i, j
        cdef int byte_val
        cdef int start_block, end_block

        if superblock_start == 0:
            index = 0
            end_block = self.bits_in_superblock // bits_in_byte + 1
            for byte_idx in range(end_block):
                if byte_idx >= len(self._hc_bitarray):
                    break
                byte_val = self._hc_bitarray[byte_idx]
                if not byte_val:
                    index += 8
                    continue
                for i in range(7, -1, -1):
                    if byte_val & (1 << i):
                        bitsum += 1
                        if index == end_request_index:
                            return bitsum
                    index += 1
        else:
            # Get sum from superblock using safe mmap access
            superblock_bytes = self._hc_super_blocks[(superblock_start - 1) * 4:(superblock_start - 1) * 4 + 4]
            bitsum = int.from_bytes(superblock_bytes, byteorder="big", signed=False)

        # Calculate remaining bits
        start_block = superblock_start * self.bits_in_superblock // bits_in_byte
        end_block = start_block + self.bits_in_superblock // bits_in_byte + 1
        index = superblock_start * self.bits_in_superblock

        for i in range(start_block, min(end_block, len(self._hc_bitarray))):
            byte_val = self._hc_bitarray[i]
            if not byte_val:
                index += 8
                continue
            
            for j in range(7, -1, -1):
                if byte_val & (1 << j):
                    bitsum += 1
                    if index == end_request_index:
                        return bitsum
                index += 1

        return bitsum

    cpdef bint has_child(self, int index):
        """Check if node has child using safe mmap access"""
        cdef int byte_idx = index // 8
        cdef int bit_pos = 7 - (index % 8)
        if byte_idx >= len(self._hc_bitarray):
            return False
        cdef int byte_val = self._hc_bitarray[byte_idx]
        return (byte_val & (1 << bit_pos)) > 0

    cpdef bytes get_trie_range(self, int start, int end):
        """Returns the byte range from trie"""
        return self._trie[start:end]

    cpdef int get_trie_index_of(self, int start, int end, unsigned char letter):
        """Search for letter in trie range using safe mmap access"""
        cdef bytes trie_slice = self._trie[start:end]
        return trie_slice.find(letter)

    cpdef list get_index(self, int index_value):
        """Get index using safe mmap access"""
        cdef int start_idx, end_idx, start_len, end_len
        cdef int index_val, len_value

        if index_value == 0:
            start_idx = 0
        else:
            start_idx = index_value * (self.nr_bytes_in_index_block + self.nr_bytes_in_value_block)
        
        end_idx = start_idx + self.nr_bytes_in_index_block
        start_len = end_idx
        end_len = start_len + self.nr_bytes_in_value_block

        # Use safe mmap access
        index_bytes = self._index_bits[start_idx:end_idx]
        len_bytes = self._index_bits[start_len:end_len]
        
        index_val = int.from_bytes(index_bytes, byteorder="big", signed=False)
        len_value = int.from_bytes(len_bytes, byteorder="big", signed=False)
        
        return [index_val, len_value]

    cpdef int is_end_of_word(self, int index):
        """Check end of word using safe mmap access"""
        cdef int start_byte = index // 8
        cdef int extra_bits = index % 8
        
        if start_byte >= len(self._eow_bits):
            return 0
            
        cdef int byte_val = self._eow_bits[start_byte]
        cdef str bits = bin(byte_val)[2:].rjust(8, "0")
        return int(bits[extra_bits:extra_bits + 1])

    cpdef int get_value_bits_sum(self, int index):
        """Get value bits sum using safe mmap access"""
        cdef int s_start = (index // 32 - 1) * 4
        cdef int s_end = s_start + 4
        
        # Use safe mmap access for summary data
        start_bytes = self._eow_sb[s_start:s_start + 4]
        end_bytes = self._eow_sb[s_end:s_end + 4]
        
        cdef int start_index = int.from_bytes(start_bytes, byteorder="big", signed=False)
        cdef int end_index = int.from_bytes(end_bytes, byteorder="big", signed=False)

        if end_index == start_index:
            return start_index

        cdef int extra_bits = index - s_end * 8 + 1
        cdef int i, j
        cdef int byte_val

        # Process value bits safely
        value_bits = self._eow_bits[s_end:s_end + 4]
        for i in range(len(value_bits)):
            byte_val = value_bits[i]
            if not byte_val and extra_bits > 8:
                extra_bits -= 8
                continue
            
            for j in range(7, -1, -1):
                if extra_bits > 0:
                    extra_bits -= 1
                    if byte_val & (1 << j):
                        start_index += 1
                else:
                    return start_index - 1
        
        return start_index - 1

    cpdef list get_result(self, int value_index, bint reversed=False):
        """Returns result of the query"""
        if self.check_if_key_exists:
            return ["1"]
        
        cdef int value_sum = self.get_value_bits_sum(value_index)
        cdef list index_data = self.get_index(value_sum)
        cdef int index_value = index_data[0]
        cdef int text_len = index_data[1]
        return self.get_short_text(index_value, text_len)

    cpdef list get_short_text(self, int index, int text_len):
        """Get short text using safe mmap access"""
        cdef list text_arr = []
        cdef list short_texts = []
        cdef int i = 0
        cdef int current_byte
        cdef int unicode_val
        cdef str char_str

        # Get the result slice safely
        res = self._short_text[index:index + text_len]

        while i < len(res):
            current_byte = res[i]
            
            if current_byte == 141:  # new line of result
                if text_arr:
                    short_texts.append("".join(text_arr))
                    text_arr = []
                i += 1
                continue
            
            if current_byte == 129:  # special character indicating a 4-byte character
                if i + 4 < len(res):
                    # Get 4 bytes safely
                    unicode_bytes = res[i + 1:i + 5]
                    bits = [bin(b)[2:].rjust(8, "0") for b in unicode_bytes]
                    try:
                        unicode_val = int("".join(bits), 2)
                        char_str = chr(unicode_val)
                        text_arr.append(char_str)
                    except (ValueError, OverflowError):
                        text_arr.append('?')  # fallback for invalid unicode
                    i += 5
                else:
                    i += 1
                continue
            
            text_arr.append(chr(current_byte))
            i += 1

        if text_arr:
            short_texts.append("".join(text_arr))
        
        short_texts.sort()
        return short_texts