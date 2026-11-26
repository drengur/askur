[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-390/)

# Askur

A memory-mapped binary tree implementation for ultra-fast key-value lookup using LOUDS (Level-Order Unary Degree Sequence) trie representation with wildcard support.

## Features

- **Ultra-fast search**: Memory-mapped binary files for zero-copy access
- **Wildcard support**: `*` (any sequence) and `_` (single character) wildcards
- **Fuzzy matching**: Levenshtein distance search
- **Case Insensitive**: Search both upper and lowercase letters in same search: 
- **Unicode support**: UTF-8 character encoding (max 4 byte chars)

## Installation

### From ~~PyPI~~ and Github
```bash
uv pip install askur (NOT AVAILABLE)
uv pip install git+https://github.com/drengur/askur.git
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

# building package
uv build
uv pip install dist/<file-distribution-name>.whl
or
uv pip install dist/<file-distribution-name>.tar.gz
```

## Quick Start

### Command Line Usage
```python
# Build a collection:
# The build procedure sorts the input while building the data
askur-build -C <collection_name:str> -f <path-to-file> (-F <column_separator:str>)
# -F determes where to split the input lines into key and value (default is ";")

# or reading from stdin...
cat <path_to_file> | askur-build -C <collection_name>

# Building a collection can be memory demanding. Default memory upper limit is 60% of system total memory.
# When building from command line the memory threshold can be set using the ASKUR_MEMORY_THRESHOLD environment variable.
# Example usage from command line:
ASKUR_MEMORY_THRESHOLD=70 askur-build -C<collection_name> -f <file_name>

# build example:
echo -e "hello;greeting\nworld;earth\nhello*;wildcard" > data.txt
askur-build -C test_collection -f data.txt -F";"

# searching:
askur-search -c <collection:str> -q "<key:str>" [-l <limit:int>] [-e] [-z] [-i] [--asc] [--desc]
# -l = limits output (limit = 0 is no limit)
# -e = check if key exists (=True)
# -z = fuzzy match word (levenshtein distance =1) (=True)
# i = case insensitive search (=True)
# --asc = sort result ascending
# --desc  = sort result descending

# get value by index (example index = 10):
askur-get_id -c <collection_name:str> --id 10

# rename a collection:
askur-rename -o <old_name:str> -n <new_name:str>

# remove a collection
askur-remove <collectin_name:str>

# list all available collections:
askur-list_collections
askur-list_collections [--sort_by (name, date or size)]

# list Configs:
askur-list_config

```

### Programmatic Usage
```python
# Building Collection:
import askur
res:int = askur.build_collection(<collection_name:str>, <path_to_file>
# res = 0 if success, else -1

# Examples of searching a collection...
from askur import search
# choose the collection to search:
s = search.Search(<collection_name:str>)

# The result from the search returns a generator
# To get the results, loop through the search result:
for item in s.search('query'):
    print(item)

# to limit the output to n-number (0 = unlimited) of lines:
s.limit = n

# to search case insensitive:
s.case_insensetive = True

# check if key exists (faster search)
# if exists = True the search returns the word index
s.exists = True

# get the value associated with index value
# find the result based on the word index value.
# set query parameter to empty string.
s.id = <index:int>
result = s.search('')


# Find similar words
# returns all words with levenshtein distance one.
# When using fuzzy_match wildcards can't be used
s.fuzzy_match = True

# general search method:
for item in S.search('word'): print(item);

# Use wildcards in the search:
results = s.search('*w_rd*')
# Wildcards can be escaped with backslash (\)
results = s.search('hello\*')

# get the result in ascending- or descending order:
s.sort_ascending = True
# or
s.sort_descending = True

# To format the output:
# there are three output formats: 'json', 'list' and 'none'
# none is the default (dict)
s.output_format='<format>'

# Release the memory mapped object when done:
s.close()

# Or use the search as a context manager with automatic cleanup:
with Search(
    collection=collection,
    limit=0,
    case_insensitive=False,
    fuzzy_match=False,
    exists=False,
    sort_ascending=False,
    sort_descending=False,
    id=-1,
    output_json=False,
    output_list=False,
) as s: 
    for item in s.search(query):
        print(item)


```


## Performance

Askur is optimized for:
- **Memory efficiency**: Memory-mapped files avoid loading data into RAM
- **Search speed**: LOUDS encoding enables O(1) operations
- **Scalability**: Handles millions of entries efficiently

## License

MIT License - see [LICENSE](LICENSE) file.
