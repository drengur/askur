# Askur Distribution Guide

## Distribution Methods

### 1. **Local Development Installation** ✅

For immediate local development and testing:

```bash
# From project root
pip install --user --force-reinstall dist/askur-0.1.0-cp310-cp310-linux_x86_64.whl
```

### 2. **Build Distribution Packages**

Create distributable packages:

```bash
# Install build dependencies
pip install build twine

# Build source distribution and wheel
python -m build

# This creates:
# - dist/askur-0.1.0.tar.gz (source distribution)
# - dist/askur-0.1.0-cp310-cp310-linux_x86_64.whl (compiled wheel)
```

### 3. **Install from Built Packages**

```bash
# Install from wheel (recommended - faster)
pip install dist/askur-0.1.0-cp310-cp310-linux_x86_64.whl

# Or install from source distribution
pip install dist/askur-0.1.0.tar.gz
```

### 4. **Publish to PyPI** 🚀

When ready to share publicly:

```bash
# First, test on Test PyPI
python -m twine upload --repository testpypi dist/*

# Then upload to real PyPI
python -m twine upload dist/*
```

After publishing, users can install with:
```bash
pip install askur
```

### 5. **GitHub Releases**

Create a release on GitHub and attach the distribution files:
- Upload `askur-0.1.0.tar.gz` 
- Upload `askur-0.1.0-cp310-cp310-linux_x86_64.whl`

Users can then install directly from GitHub:
```bash
pip install https://github.com/drengur/askur/releases/download/v0.1.0/askur-0.1.0-cp310-cp310-linux_x86_64.whl
```

## Installation Verification

After installation, verify it works:

```bash
# Test Python import
python -c "import askur; print('Success!')"

# Test CLI command
askur-search --help

# Test with a collection (if you have data)
askur-search -c test -w "hello*"
```

## Development Installation

For development with live changes:

```bash
# Unfortunately, editable installs don't work with your current setup
# due to system restrictions. Use regular installation and rebuild when needed:

python -m build
pip install --user --force-reinstall dist/askur-0.1.0-cp310-cp310-linux_x86_64.whl
```

## Building for Different Platforms

To create wheels for multiple platforms:

```bash
# Install cibuildwheel for cross-platform builds
pip install cibuildwheel

# Build wheels for multiple platforms
cibuildwheel --platform linux
```

## Package Contents

Your built package includes:
- ✅ Python source code (`*.py`)
- ✅ Cython source (`*.pyx`) 
- ✅ Compiled Cython extension (`*.so`)
- ✅ CLI entry point (`askur-search` command)

## Troubleshooting

**Permission Errors**: Use `--user` flag for user-level installation

**Cython Compilation Issues**: Ensure you have:
- `gcc` compiler installed
- Python development headers: `sudo apt-get install python3-dev`

**Import Errors**: Check that the package is installed correctly:
```bash
pip list | grep askur
```