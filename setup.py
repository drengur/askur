from setuptools import setup, Extension
from Cython.Build import cythonize
import platform
import sys

# Compiler directives for maximum optimization
compiler_directives = {
    'language_level': 3,
    'boundscheck': False,
    'wraparound': False,
    'cdivision': True,
    'profile': False,
    'nonecheck': False,
    'overflowcheck': False,
    'embedsignature': True,
}

# Platform-specific compiler arguments
def get_compile_args():
    """Get platform-specific compile arguments."""
    args = ["-O3"]  # Always use O3 optimization
    
    if sys.platform.startswith('win'):
        # Windows (MSVC)
        return ["/O2", "/fp:fast"]
    elif sys.platform == 'darwin':
        # macOS (clang)
        args.extend([
            "-ffast-math",
            "-funroll-loops",
            "-mtune=native"  # Use mtune instead of march for macOS compatibility
        ])
    else:
        # Linux/Unix (gcc/clang)
        args.extend([
            "-ffast-math", 
            "-funroll-loops",
            "-mtune=native"  # More portable than march=native
        ])
    
    return args

def get_link_args():
    """Get platform-specific link arguments."""
    if sys.platform.startswith('win'):
        return []
    else:
        return ["-O3"]

# Extension configuration
extensions = [
    Extension(
        "askur.filemapping",
        ["src/askur/filemapping.pyx"],
        extra_compile_args=get_compile_args(),
        extra_link_args=get_link_args(),
    )
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives=compiler_directives,
        annotate=False,  # Set to True to generate HTML optimization reports
    ),
    zip_safe=False,
)
