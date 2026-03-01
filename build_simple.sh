#!/bin/bash
# Simple build script without Docker dependency

set -e

echo "🔧 Simple build for current platform..."

# Install build dependencies
echo "📦 Installing build dependencies..."
uv add build cython

echo "🏗️  Building source distribution and wheel..."
uv run python -m build

echo "✅ Build complete! Files are in ./dist/"
ls -la dist/

echo "🧪 Testing installation..."
# Find the most recent wheel file
WHEEL_FILE=$(ls -t dist/*.whl 2>/dev/null | head -1)
if [ -n "$WHEEL_FILE" ]; then
    echo "Installing: $WHEEL_FILE"
    uv add "$WHEEL_FILE" --force-reinstall
else
    echo "No wheel file found, installing from source..."
    TAR_FILE=$(ls -t dist/*.tar.gz 2>/dev/null | head -1)
    if [ -n "$TAR_FILE" ]; then
        uv add "$TAR_FILE" --force-reinstall
    else
        echo "No distribution files found!"
        exit 1
    fi
fi

echo "🚀 Testing import..."
uv run python -c "import askur; print('✅ Import successful!')"

echo "📋 Testing CLI commands..."
askur-search --help > /dev/null && echo "✅ askur-search command works"
askur-build --help > /dev/null && echo "✅ askur-build command works"

echo "🎉 Simple build and test complete!"
echo ""
echo "Note: For cross-platform builds, use cibuildwheel with Docker:"
echo "  docker --version  # Check if Docker is available"
echo "  python -m cibuildwheel --platform linux"