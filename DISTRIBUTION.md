# Askur Distribution Guide

## Overview

This guide explains how to build and distribute the Askur package across multiple platforms using modern Python packaging tools. The build system uses `cibuildwheel` to create wheels for Linux, macOS, and Windows with compiled Cython extensions.

## Understanding Python Package Distribution

### What Are Wheels?
- **Wheels** (`.whl` files) are pre-compiled binary distributions
- They contain compiled C extensions, so users don't need compilers
- Platform-specific (e.g., `askur-0.1.0-cp310-cp310-linux_x86_64.whl`)
- Much faster to install than source distributions

### What Are Source Distributions (sdist)?
- **Source distributions** (`.tar.gz` files) contain raw source code
- Users must compile C extensions during installation
- Platform-independent but require compilers on user machines
- Slower to install but work as fallback

## Build System Architecture

### Core Components

1. **pyproject.toml**: Modern Python packaging configuration
2. **setup.py**: Handles Cython compilation with platform-specific optimizations
3. **cibuildwheel**: Creates wheels for multiple platforms automatically
4. **GitHub Actions**: Automates building and uploading to PyPI

### File Structure
```
askur/
├── pyproject.toml          # Main packaging configuration
├── setup.py                # Cython compilation setup
├── MANIFEST.in             # Controls which files are included/excluded
├── .github/workflows/      # Automated build scripts
│   └── build-wheels.yml    # GitHub Actions workflow
├── src/askur/              # Source code
│   ├── filemapping.pyx     # Cython extension (gets compiled)
│   └── testing.py          # Excluded from distribution
└── wheelhouse/             # Local build output directory
```

## Platform-Specific Compilation

### Linux (manylinux)
- Uses Docker containers with older glibc for compatibility
- Builds for `x86_64` and `aarch64` (ARM64) architectures
- Compiler flags: `-O3 -ffast-math -funroll-loops -mtune=native`

### macOS (Universal Wheels)
- Builds for both Intel (`x86_64`) and Apple Silicon (`arm64`)
- Uses `mtune=native` instead of `march=native` for compatibility
- Minimum deployment target: macOS 10.14

### Windows
- Uses MSVC compiler with `/O2 /fp:fast` optimization
- Builds for 64-bit AMD64 architecture only
- Automatically handles Windows-specific compilation differences

## Local Development Workflow

### 1. Set Up Development Environment
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install cython build cibuildwheel twine
```

### 2. Local Testing Build
```bash
# Quick local build for current platform
python -m build

# Test cross-platform build (Linux only)
./build_local.sh
```

### 3. Install and Test Locally
```bash
# Install from built wheel
pip install dist/*.whl --force-reinstall

# Test the installation
python -c "import askur; print('Success!')"
askur-search --help
```

## Cross-Platform Building with CIBuildWheel

### Local Multi-Platform Build
```bash
# Install cibuildwheel
pip install cibuildwheel

# Build for current platform
python -m cibuildwheel --platform auto

# Build for specific platform (if supported)
python -m cibuildwheel --platform linux
python -m cibuildwheel --platform macos
python -m cibuildwheel --platform windows
```

### Configuration Options
The build behavior is controlled by `[tool.cibuildwheel]` in `pyproject.toml`:

```toml
# Python versions to build for
build = ["cp310-*", "cp311-*", "cp312-*", "cp313-*"]

# Platforms to skip (32-bit, older Linux variants)
skip = ["*-win32", "*-manylinux_i686", "*-musllinux*"]

# Architecture support
[tool.cibuildwheel.linux]
archs = ["x86_64", "aarch64"]  # Intel and ARM64

[tool.cibuildwheel.macos]
archs = ["x86_64", "arm64"]    # Intel and Apple Silicon

[tool.cibuildwheel.windows]
archs = ["AMD64"]              # 64-bit Windows only
```

## File Inclusion/Exclusion

### What Gets Included
- All Python source files (`*.py`)
- Cython source files (`*.pyx`) 
- Configuration files (`*.conf`)
- Essential data files (`*.bin`, `*.alphabet`, `trie`)
- Documentation (`README.md`, `LICENSE`)

### What Gets Excluded
Files excluded via `MANIFEST.in` and `pyproject.toml`:
- Test files (`testing.py`, `test_*.py`, `*_test.py`)
- Build artifacts (`*.pyc`, `*.so`, `__pycache__`)
- Development files (`setup.py.bak`, `developement.md`)
- Version control (`.git*`)
- Build directories (`build/`, `dist/`, `wheelhouse/`)

### Excluding Files Example
```toml
# In pyproject.toml
[tool.setuptools.exclude-package-data]
askur = ["testing.py", "test_*.py", "*_test.py"]
```

```
# In MANIFEST.in
global-exclude testing.py
global-exclude test_*.py
global-exclude *_test.py
exclude setup.py.bak
```

## Automated Building with GitHub Actions

### Trigger Events
The build workflow runs on:
- **Push to main**: Builds and uploads to Test PyPI
- **Pull requests**: Builds wheels for testing
- **Releases**: Builds and uploads to production PyPI

### Build Matrix
Creates wheels for:
- **Python versions**: 3.10, 3.11, 3.12, 3.13
- **Operating systems**: Ubuntu (Linux), Windows, macOS
- **Architectures**: x86_64, aarch64 (Linux), arm64 (macOS), AMD64 (Windows)

### Artifacts
Each build creates:
- **Wheels**: Platform-specific binary distributions
- **Source distribution**: Platform-independent source code
- **Test results**: Import and basic functionality tests

## Publishing to PyPI

### Prerequisites
1. **PyPI Account**: Register at [pypi.org](https://pypi.org)
2. **API Tokens**: Create tokens for main and test PyPI
3. **GitHub Secrets**: Add tokens to repository secrets
   - `PYPI_API_TOKEN`: For production PyPI
   - `TEST_PYPI_API_TOKEN`: For test PyPI

### Manual Upload Process
```bash
# Build all distributions
python -m build
python -m cibuildwheel

# Check the packages
twine check dist/* wheelhouse/*

# Upload to Test PyPI first
twine upload --repository testpypi dist/* wheelhouse/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ askur

# Upload to production PyPI
twine upload dist/* wheelhouse/*
```

### Automated Upload
- **Test PyPI**: Automatic on every push to main branch
- **Production PyPI**: Automatic on GitHub releases

## Version Management

### Update Version
1. Edit version in `pyproject.toml`:
   ```toml
   version = "0.2.0"
   ```

2. Create and push a git tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. Create a GitHub release to trigger PyPI upload

## Troubleshooting Common Issues

### Compilation Errors
- **Missing compiler**: Install build tools for your platform
- **Architecture mismatch**: Use `mtune=native` instead of `march=native`
- **Windows MSVC**: Install Visual Studio Build Tools

### Import Errors
- **Missing dependencies**: Check `dependencies` in `pyproject.toml`
- **ABI compatibility**: Use manylinux wheels for broader Linux support
- **Path issues**: Use environment variables for data folder configuration

### Distribution Issues
- **Large package size**: Review included data files
- **Missing files**: Check `MANIFEST.in` includes
- **Unwanted files**: Add exclusions to `MANIFEST.in`

### PyPI Upload Issues
- **Authentication**: Verify API tokens in GitHub secrets
- **Duplicate version**: PyPI doesn't allow re-uploading same version
- **Filename conflicts**: Ensure unique wheel names across platforms

## Quality Assurance

### Pre-Release Checklist
- [ ] All tests pass locally
- [ ] Build succeeds on all platforms
- [ ] Package installs cleanly in fresh environment
- [ ] CLI commands work correctly
- [ ] Import statements succeed
- [ ] Documentation is up to date

### Testing Strategy
1. **Local testing**: Quick iteration on current platform
2. **CI testing**: Comprehensive cross-platform validation
3. **Test PyPI**: End-to-end distribution testing
4. **Production PyPI**: Final release

This build system ensures your Askur package works reliably across all major platforms while maintaining high performance through optimized compilation.