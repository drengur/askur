# Askur Project Instructions

## Overview
Askur is a memory-mapped binary tree implementation for ultra-fast key-value lookup using LOUDS (Level-Order Unary Degree Sequence) trie representation. The core focus is performance-critical string search with wildcard support.

## Architecture

### Dual Implementation Strategy
- **Python fallback**: `filemapping_py.py` - Pure Python implementation for development/debugging
- **Cython optimized**: `filemapping.pyx` - Performance-critical production version
- **Selection logic**: `search.py` imports from Cython first, falls back to Python

### Binary Data Structure
The trie is serialized into multiple binary files in `data/{collection}/`:
- `trie` - LOUDS encoded trie structure  
- `s_bits.bin` / `s_sb.bin` - Select bit arrays and superblocks
- `hc_bits.bin` / `hc_sb.bin` - Head count bit arrays and superblocks
- `eow_bits.bin` / `eow_sb.bin` - End-of-word markers and superblocks
- `index_bits.bin` - Index mapping to short text
- `short_text_bits.bin` - Actual string values
- `trie.alphabet` - Character encoding mapping

### Key Components

#### Mapping Class (`filemapping_py.py` / `filemapping.pyx`)
Core data structure interface using memory-mapped files for zero-copy access:
```python
mmap = Mapping("collection_name")  # Loads all binary files
```

#### Search Class (`search.py`)
High-level search interface with wildcard support:
- `*` - matches any sequence of characters
- `_` - matches any single character  
- `\` - escapes wildcards
- Levenshtein distance search for fuzzy matching
- Reversed index support for suffix searches

#### Trie Builder (`make_lookup.py`)
Creates optimized binary representations from text input:
```bash
python make_lookup.py -f input.txt -C collection_name
```

## Special Encoding

### Multibyte Characters
- ASCII 129: Indicates start of 4-byte UTF-8 character
- ASCII 143: Indicates reversed search prefix  
- Characters >255 are encoded as 5 bytes: [129, byte1, byte2, byte3, byte4]

### Wildcard Processing
Query preprocessing splits on `*` wildcards into:
- `starts_with`: Characters before first `*`
- `middle_parts`: Character sequences between `*` wildcards
- `ends_with`: Characters after last `*`

## Development Workflows

### Building Cython Extension
```bash
# From project root
python setup.py.bak build_ext --inplace
```

### Creating Collections
```bash
# Input format: "word;value\n"
python src/askur/make_lookup.py -f data.txt -C collection_name
# Creates data/collection_name/ with all binary files
```

### Search Interface
```bash
# Command line
python src/askur/search.py -c collection_name -w "query*with*wildcards"

# Programmatic
from askur.search import Search
s = Search("collection_name", limit=100)
results = s.search("pattern*")
```

## Performance Considerations

### Memory Management
- Uses `mmap` for zero-copy file access
- Cython version uses `cdef` classes and typed variables
- Buffer management in `make_lookup.py` processes data in 10KB chunks

### Bit Operations
Intensive bit manipulation for LOUDS operations:
- `calculate_select()` - Find positions of 1-bits in select array
- `calculate_hc()` - Count 1-bits in head count array  
- Superblock optimization for O(1) bit counting

### Configuration
`conf.py`:
defines `DATA_FOLDER` path - update when changing data location.
and defines `ASKUR_ALPHABET` (sort order).

## Common Patterns

### Error Handling
```python
# Collection validation
```
Assert collection_name is not None, "Collection name is not set. Exiting."
```
# Alphabet validation
```
Assert alphabet is not None, "Alphabet is not set. Exiting."

### Result Processing
```python
# Convert results to consistent format
def result_as_list(self):
    res = []
    for items in self.results():
        if isinstance(items, dict):
            for key, value in items.items():
                res.append(f"{key}: {value}")
```

### Alphabet Management
The `Alphabet` class handles character encoding with special handling for multibyte characters and maintains `_used_alphabet` for space efficiency.

## Integration Points
- Collections are loaded via collection name string
- Data folder path and alphabet configurable in `config.py`
- Both Python and Cython versions expose identical interfaces
- Search results are always returned as lists of strings
