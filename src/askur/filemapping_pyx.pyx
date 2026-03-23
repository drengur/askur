# distutils: language = c++
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: profile=False
import io
import os
import mmap
import alphabet
A = alphabet.Alphabet()

cdef class Mapping:
    # C-level attributes for maximum speed
    cdef public bytes _trie
    
    cdef public bytes _s_bits
    cdef public bytes _s_superblocks

    cdef public bytes _hc_bitarray
    cdef public bytes _hc_super_blocks

    cdef public bytes _eow_bits
    cdef public bytes _eow_sb

    cdef public bytes _index_bits
    cdef public bytes _index_values_length
    
    # cdef public int short_text_len
    cdef public int bits_in_superblock
    cdef public str collection

    # pointers for start of the sections
    cdef public int _triet_start 
    cdef public int _select_start
    cdef public int _select_superblock_start
    cdef public int _hc_start
    cdef public int _hc_superblock_start
    cdef public int _eow_start
    cdef public int _eow_superblock_start
    cdef public int _index_start
    cdef public int alphabet_index_start

    cdef public bytes alphabet
    cdef public bint _has_reversed_index  # does the index have reversed entries?
    cdef public bint _reversed_lookup  # are we looking up reversed entries?
    cdef public bint check_if_key_exists  # are we only checking if key exists?
    # cdef public bytes _data

    cdef public int nr_bytes_in_index_block

    cdef public bytes _reversed_trie

    cdef public bytes _reversed_s_bits
    cdef public bytes _reversed_s_superblocks
    cdef public bytes _reversed_hc_bits
    cdef public bytes _reversed_hc_super_blocks

    cdef public bytes _reversed_eow_bits
    cdef public bytes _reversed_eow_sb

    cdef public bytes _reversed_index_bits
    cdef public bytes _translate_index_bits

    cdef public bytes _short_text

    # pointers to the starts of the reversed sections
    cdef public int _reversed_trie_start

    cdef public int _reversed_select_start
    cdef public int _reversed_select_superblock_start
    cdef public int _reversed_hc_start
    cdef public int _reversed_hc_superblock_start

    cdef public int _reversed_eow_start
    cdef public int _reversed_eow_superblock_start

    # cdef public int _reversed_index_start

    # lookup tables in use for index lookups or reverse index lookups
    cdef public  bytes _lookup_trie_list

    cdef public bytes _lookup_s_bits_list
    cdef public bytes _lookup_s_superblocks_list
    cdef public bytes _lookup_hc_bits_list
    cdef public bytes _lookup_hc_super_blocks_list

    cdef public bytes _lookup_eow_bits_list
    cdef public bytes _lookup_eow_sb_list

    cdef public bytes _lookup_index_bits_list


    def __init__(self, collection: str) -> None:
        # self.short_text_len = 0
        self.bits_in_superblock = 0
        self.collection = collection
        self.nr_bytes_in_index_block = 0
        self.check_if_key_exists = False
        self._reversed_lookup = False
        self._has_reversed_index = False
        self._load_files()

    cdef void _load_files(self):
        cdef int alphabet_start, trie_start
        cdef int select_bits_start, select_superblock_start
        cdef int hc_start, hc_superblock_start
        
        cdef int eow_bytes_start, eow_superblock_start
        cdef int index_value_start, short_text_start
        cdef int reversed_trie_start, reversed_select_start
        cdef int reversed_select_superblock_start, reversed_hc_start
        cdef int reversed_hc_superblock_start, reversed_eow_start
        cdef int reversed_eow_superblock_start, reversed_index_start
        cdef object data 
        cdef str data_filename
        
        # Check for environment variable first, then fall back to config file
        # Use Python-level variables to avoid unsafe C derivatives
        data_folder = os.environ.get('ASKUR_DATA_FOLDER')
        frozen_folder = os.path.join(data_folder, self.collection)
            
        if not os.path.exists(frozen_folder):
            data_parent = data_folder if os.path.isabs(data_folder) else os.path.join(os.path.dirname(__file__), data_folder)
            if os.path.exists(data_parent):
                existing_collections = os.listdir(data_parent)
            else:
                existing_collections = ["No data directory found"]
            raise FileNotFoundError(f"{self.collection} collection does not exist!\n Existing collections are: {existing_collections}\n Data folder: {data_parent}")

        # File paths
        data_filename = os.path.join(frozen_folder, "data.bin")    
        
        # Load files without pointer caching
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
            # reversed_index_start = index_value_start

            self.alphabet = data[alphabet_start:trie_start]
            self._trie = data[trie_start:select_bits_start]

            self._s_bits = data[select_bits_start:select_superblock_start]
            self._s_superblocks = data[select_superblock_start:hc_start]

            self._hc_bitarray = data[hc_start:hc_superblock_start]
            self._hc_super_blocks = data[hc_superblock_start:eow_bytes_start]

            self._eow_bits = data[eow_bytes_start:eow_superblock_start]
            self._eow_sb = data[eow_superblock_start:index_value_start]

            self._index_bits = data[index_value_start:short_text_start]
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
            self._translate_index_bits = data[reversed_index_start:]

            self._has_reversed_index = reversed_trie_start > 0 
            # and reversed_select_start > reversed_trie_start

            self._lookup_trie_list = self._trie
            self._lookup_s_bits_list = self._s_bits
            self._lookup_s_superblocks_list = self._s_superblocks
            self._lookup_hc_bits_list = self._hc_bitarray
            self._lookup_hc_super_blocks_list = self._hc_super_blocks
            self._lookup_eow_bits_list = self._eow_bits
            self._lookup_eow_sb_list = self._eow_sb
            self._lookup_index_bits_list = self._index_bits
            self._lookup_index_values_length_list = self._index_values_length

    cpdef bint has_reversed_index(self):
        """Returns True if the index is reversed"""
        return self._has_reversed_index
    
    cpdef bint do_reversed_lookup(self, bool reversed_lookup):
        self._reversed_lookup = reversed_lookup and self._has_reversed_index
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
            superblock_bytes = self._lookup_s_superblocks_list[(superblock_start - 1) * 4:(superblock_start - 1) * 4 + 4]
            start_index = int.from_bytes(superblock_bytes, byteorder="big", signed=False) + 1
            start_byte = start_index // 8
            extra_bits = start_index % 8
            start_sum = self.bits_in_superblock * superblock_start

        total_sum = start_sum
        loop_index = start_index

        if start_sum == sum_ones_wanted:
            res_start_index = start_index - 1

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
        cdef int start_block = 0
        cdef int end_block = 0
        cdef bytes superblock_bytes

        if superblock_start > 0:
            start_block = superblock_start * self.bits_in_superblock // bits_in_byte
            superblock_bytes = self._lookup_hc_super_blocks_list[
                (superblock_start - 1) * 4 : (superblock_start - 1) * 4 + 4
            ]
            bitsum = int.from_bytes(
                superblock_bytes,
                byteorder="big",
                signed=False,
            )
            index = superblock_start * self.bits_in_superblock
        end_block = start_block + self.bits_in_superblock // bits_in_byte + 1
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


    cpdef bint has_child(self, int index):
        """Check if node has child using safe mmap access"""
        cdef int byte_idx = index // 8
        cdef int bit_pos = 7 - (index % 8)
        if byte_idx >= len(self._lookup_hc_bits_list):
            return False
        cdef int byte_val = self._lookup_hc_bits_list[byte_idx]
        return (byte_val & (1 << bit_pos)) > 0

    cpdef bytes get_trie_range(self, int start, int end):
        """Returns the byte range from trie"""
        return self._lookup_trie_list[start:end]

    cpdef int get_trie_index_of(self, int start, int end, unsigned char letter):
        """Search for letter in trie range using safe mmap access"""
        cdef bytes trie_slice = self._lookup_trie_list[start:end]
        return trie_slice.find(letter)

    cpdef list get_index(self, int index_value):
        """Get index using safe mmap access"""
        cdef int start_idx, end_idx
        cdef int sh_index, sh_len

        start_idx = index_value * self.nr_bytes_in_index_block
        end_idx = start_idx + self.nr_bytes_in_index_block

        sh_index = int.from_bytes(
            self._lookup_index_bits_list[start_idx:end_idx],
            byteorder="big",
            signed=False,
        )
        sh_len = int.from_bytes(
            self._lookup_index_values_length_list[
                index_value * 2 : index_value * 2 + 2
            ],
            byteorder="big",
            signed=False,
        )
        return [sh_index, sh_len]

    cpdef int is_end_of_word(self, int index):
        """Check end of word using safe mmap access"""
        cdef int start_byte = index // 8
        cdef int extra_bits = index % 8
        
        if start_byte >= len(self._lookup_eow_bits_list):
            return 0
            
        if self._lookup_eow_bits_list[start_byte : start_byte + 1][0] & (1 << (7 - extra_bits)):
            return 1
        return 0


    cpdef int get_value_bits_sum(self, int index):
        """Get value bits sum using safe mmap access"""
        cdef int s_start = (index // 32 - 1) * 4
        cdef int s_end = s_start + 4
        cdef bytes start_bytes, end_bytes
        cdef bytes value_bits
        cdef int start_index, end_index, extra_bits, i, j, byte_val
        
        s_start = (index // 32 - 1) * 4
        s_end = s_start + 4
        start_bytes = self._lookup_eow_sb_list[s_start:s_end]
        start_index = int.from_bytes(start_bytes, byteorder="big", signed=False)

        end_bytes = self._lookup_eow_sb_list[s_end : s_end + 4]
        end_index = int.from_bytes(end_bytes, byteorder="big", signed=False)

        if end_index == start_index:
            return start_index

        extra_bits = index - s_end * 8 + 1
        value_bytes = self._lookup_eow_bits_list[s_end : s_end + 4]
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

    cpdef list get_result(self, int value_index, bint reversed=False):
        """Returns result of the query"""
        cdef int value_sum, index_value, text_len
        cdef list index_data

        value_sum = self.get_value_bits_sum(value_index)

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

        if self._has_reversed_index and self._reversed_lookup:
            value_sum = value_sum * self.nr_bytes_in_index_block
            value_sum = int.from_bytes(
                self._translate_index_bits[
                    value_sum : value_sum + self.nr_bytes_in_index_block
                ],
                byteorder="big",
                signed=False,
            )

        index_data = self.get_index(value_sum)
        index_value = index_data[0]
        text_len = index_data[1]
        return self.get_short_text(index_value, text_len)

    cpdef list get_short_text(self, int index, int text_len):
        """Get short text using safe mmap access"""
        cdef list text_array = []
        cdef int i = 0
        cdef bytes unicodes = b""
        cdef bytes res = b""

        res = self._short_text[index : index + text_len]
        while i < len(res):
            if res[i] == A.RES_SEPARATOR:
                text_array.append(A.convert_bytes_to_str(unicodes))
                unicodes = b""
            else:
                unicodes += bytes([res[i]])
            i += 1
        if len(unicodes) > 0:
            text_array.append(A.convert_bytes_to_str(unicodes))
        text_array.sort()
        return text_array

