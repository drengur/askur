# Askur

A memory-mapped binary tree implementation for ultra-fast key-value lookup using LOUDS (Level-Order Unary Degree Sequence) trie representation with wildcard support.

## Features

- **Ultra-fast search**: Memory-mapped binary files for zero-copy access
- **Wildcard support**: `*` (any sequence) and `_` (single character) wildcards
- **Fuzzy matching**: Levenshtein distance search
- **Dual implementation**: Python fallback with Cython optimization
- **Unicode support**: Full UTF-8 character encoding
- **Reversed indexing**: Suffix search capabilities

## Installation

### From PyPI (when published)
```bash
pip install askur
```

### From Source
```bash
git clone https://github.com/drengur/askur.git
cd askur
pip install .
```

### Development Installation
```bash
git clone https://github.com/drengur/askur.git
cd askur
pip install -e ".[dev]"
```

## Quick Start

### Creating a Collection
```bash
# Input format: "word;value\n" 
echo -e "hello;greeting\nworld;earth\nhello*;wildcard" > data.txt
uv run askur.build -f data.txt -C my_collection
# reading from stdin:
cat textfile | uv run askur.build -C my_collection

```

### Searching
```bash
# Command line
askur-search -c my_collection -w "hel*"

# Or directly
python -m askur.search -c my_collection -w "hel*"
```

### Programmatic Usage
```python
from askur.search import Search

# Create search instance
s = Search("my_collection", limit=100)

# Search with wildcards
results = s.search("hel*")
print(results)

# Fuzzy search
s.set_levenshtein(True)
similar = s.search("helo")  # Finds "hello"
```

## Performance

Askur is optimized for:
- **Memory efficiency**: Memory-mapped files avoid loading data into RAM
- **Search speed**: LOUDS encoding enables O(1) operations
- **Scalability**: Handles millions of entries efficiently

## License

MIT License - see [LICENSE](LICENSE) file.