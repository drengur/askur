from setuptools import setup, Extension
from Cython.Build import cythonize

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

# Extension configuration
extensions = [
    Extension(
        "askur.filemapping",
        ["src/askur/filemapping.pyx"],
        extra_compile_args=[
            "-O3",           # Maximum optimization
            "-march=native", # Optimize for current CPU
            "-ffast-math",   # Fast math operations
            "-funroll-loops", # Unroll loops for speed
        ],
        extra_link_args=["-O3"],
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
