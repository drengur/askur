# Askur

A memory-mapped binary tree implementation for ultra-fast key-value lookup using LOUDS (Level-Order Unary Degree Sequence) trie representation with wildcard support.

## Features

- **Ultra-fast search**: Memory-mapped binary files for zero-copy access
- **Wildcard support**: `*` (any sequence) and `_` (single character) wildcards
- **Fuzzy matching**: Levenshtein distance search
- **Case Insensetive**: Search both upper and lowercase letters in same search: 
- **Unicode support**: UTF-8 character encoding (max 4 byte chars)
- **Reversed indexing**: Suffix search capabilities

## Installation

### From PyPI
```bash
uv pip install askur
```

### From Source
```bash
git clone https://github.com/drengur/askur.git
cd askur
uv pip install .
```

### Development Installation
```bash
git clone https://github.com/drengur/askur.git
cd askur
uv pip install -e ".[dev]"
```

## Quick Start

### Command Line Usage
```python
# Build a collection:
# The build procedure sorts the input while building the data
askur-build -C <collection_name:str> -f <path-to-file> (-F <column_separator:str>) (-R)
# -R is used to make reversed trie index
# -F determes where to split the input lines into key and value (default is ";")
# Reversed index is reversed sorted


# OR reading from stdin...
cat <path_to_file> | askur-build -C <collection_name> 

# Build Example:
echo -e "hello;greeting\nworld;earth\nhello*;wildcard" > data.txt
askur-build -C test_collection -f data.txt -F";" -R

# Searching:
askur-search -c <collection:str> -q <key:str> [-l <limit:int>] [-e] [-z] [-i]
# -l = limits output (limit = 0 is no limit)
# -e = check if key exists (=True)
# -z = fuzzy search (levenshtein distance =1) (=True)
# i = case insensetive search (=True)

# get value by index (example index = 10):
askur-get_id -c <collection_name:str> --id 10

# Rename Collection:
askur-rename -o <old_name:str> -n <new_name:str>

#Remove Collection
askur-remove <collectin_name:str>

# List All Available Collections:
askur-list_collections
askur-list_collections [--sort_by (name, date or size)]

# List Configs:
askur-list_config

```

### Programmatic Usage
```python
# Building Collection:
import askur
res:int = askur.build_collection(<collection_name:str>, <path_to_file>, <reversed_index:bool>)
# res = 0 if success, else -1

# Examples of Searching Collection...
from askur import search
# choose the collection to search:
S = search(<collection_name:str>)

# to limit the output to n-number of lines:
S.limit=n

# to search case insensetive:
S.case_insensetive = True

# check if key exists (faster search)
# returns the key and index value {<key:str>: <index:int>}
S.exists('key')

# get the value associated whith index value
S.get_by_id(<index:int>)

# Find similar keys
# returns all keys with levenshtein distance one.
S.fuzzy_find('key')

# general search method:
S.lookup('key')

# Use wildcards in the search:
S.lookup('*k_ey*')
# Wildcards can be escaped with backslash (\)
S.lookup('hello\*')

# All search methods (except get_by_id )
# returns a generator. To print the results from a search method do:
for item in S.lookup('key'):
    print(item)

```

## Performance

Askur is optimized for:
- **Memory efficiency**: Memory-mapped files avoid loading data into RAM
- **Search speed**: LOUDS encoding enables O(1) operations
- **Scalability**: Handles millions of entries efficiently

## License

MIT License - see [LICENSE](LICENSE) file.