from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy

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
    'optimize.use_switch': True,
    'optimize.unpack_method_calls': True,
}

# Extension configuration
extensions = [
    Extension(
        "filemapping",
        ["src/askur/filemapping.pyx"],
        extra_compile_args=[
            "-O3",           # Maximum optimization
            "-march=native", # Optimize for current CPU
            "-ffast-math",   # Fast math operations
            "-funroll-loops", # Unroll loops for speed
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
        ],
        extra_link_args=["-O3"],
        include_dirs=[numpy.get_include()],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    )
]

setup(
    name="filemapping",
    ext_modules=cythonize(
        extensions,
        compiler_directives=compiler_directives,
        annotate=False,  # True = Generate HTML annotation file to check optimization
    ),
    zip_safe=False,
)
