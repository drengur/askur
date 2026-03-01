#!/bin/bash
# Local build script for testing cibuildwheel

set -e

echo "🔧 Installing cibuildwheel..."
uv add  cibuildwheel

echo "🏗️  Building wheels locally..."
uv run -m cibuildwheel --platform linux --output-dir wheelhouse

echo "✅ Build complete! Wheels are in ./wheelhouse/"
ls -la wheelhouse/

echo "🧪 Testing installation..."
uv run pip install wheelhouse/*.whl --force-reinstall

echo "🚀 Testing import..."
uv run python -c "import askur; print('✅ Import successful!')"

echo "🎉 Local build and test complete!"