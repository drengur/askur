from enum import Enum, unique


"""
    Enum class representing different types of map address information.
    Each member of the enum corresponds to a specific type of information that can be stored in a map.
    Each value, or cell is 4 byte long, and the enum values are used to calculate the starting index 
    of each section in the mapped info.
"""


@unique
class MapAddressInfo(Enum):
    BYTES_PR_INFO_CELL = 0
    BITS_PR_SB = 1
    BYTES_PR_INDEX_BLOCK = 2
    NR_WORDS = 3
    BW_BYTE_SIZE = 4
    VOID_3 = 5
    VOID_4 = 6
    VOID_5 = 7
    VOID_6 = 8
    VOID_7 = 9
    VOID_8 = 10
    HC_TO_CHR = 11
    SELECT_FROM_CHR = 12
    ALPHABET = 13
    TRIE = 14
    SELECT = 15
    SELECT_SB = 16
    HC = 17
    HC_SB = 18
    EOW = 19
    EOW_SB = 20
    INDEX_VALUE = 21
    INDEX_VALUE_LENGTH = 22
    SHORT_TEXT = 23

    @classmethod
    def value_slices(cls, info_name) -> dict[str, slice]:
        """
        Return a slice object for the given info_name,
        which can be used to access the corresponding section of the mapped info.
        All info cells are 4 bytes long

        Example usage:
        TRIE starts at index 4 * 4 = 16 and ends at index (4 + 1) * 4 = 20
        TRIE end is the start of the next section.
        So:
        TRIE.start has the address [16:20] in the memory map
        TRIE.end has the address [20:24].
        TRIE data = mmap[TRIE.start:TRIE.end], when finally mapped.
        """
        start_cell: int = cls(info_name).value * 4
        end_cell = start_cell + 8 if cls(info_name).value < len(cls) - 1 else 0
        return {
            "start": slice(start_cell, start_cell + 4),
            "end": slice(start_cell + 4, end_cell),
        }

    @classmethod
    def address(cls, info_name) -> slice:
        """
        Return the starting address of the given info_name.
        All values are 4 bytes long.
        """
        start_cell: int = cls(info_name).value * 4
        return slice(start_cell, start_cell + 4)
