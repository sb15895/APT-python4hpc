template: titleslide

# Introduction to Performance Programming with Python
## 2

---

# ...where were we?

General performance of default Python interpreter (CPython):
  
- Limited compiler optimisations when generating bytecode

- Virtual machine execution overheads:
  - object boxing & unboxing
  - frequent type checking and lookups
  - relatively expensive:
      - function calls
      - explicit loops & conditionals
      - global-scope variable access 

- Garbage collection through global reference counter




---

# ...where were we?

Fast numerical computing:
- Use NumPy arrays (statically typed, fixed size)

- Use efficient array access syntax to minimise creation of temporaries

- Don't use explicit `for` loops that iterate over NumPy array elements

- Use overloaded array operators (`+`, `-`, `*`, `/`, `**`) and other NumPy [`ufuncs`](https://numpy.org/devdocs/reference/ufuncs.html)
    - = optimised, vectorised machine code
    - avoids type checking

- NumExpr can speed up array expressions by minimising temporaries, optimising cache usage, and vectorisation

- Use dedicated functions provided by NumPy, SciPy, etc.

- Interface Python with (existing) Fortran/C/C++ code by importing functions from shared library (many options, e.g. `ctypes`)
  
---

# What's next?

4 other strategies for speeding up Python performance:

- **CPython extension modules**: extend CPython interpreter with C code

- **Cython**: generate C code and shared library by modifying Python code
  - facilitates creation of CPython extension modules 


- **PyPy**: alternative Python interpreter (`pypy` instead of CPython's `python`)
  - speed from just-in-time (JIT) compilation  

- **Numba**: 
  - JIT compilation using LLVM

---

template:titleslide
# CPython extension modules

---

# CPython extension modules

CPython and NumPy provide a C API, allows you to:
  - Write C code (or C++ with restrictions) that extends CPython 
  - Operate on CPython's underlying C data types directly
    - e.g. C arrays that underlie NumPy arrays
  - Import as Python module after compiling into shared library 

`my_extension.c`:
```C
#include "Python.h"
#include "arrayobject.h"

// Map Python objects (e.g. NumPy arrays) to C, and initialise

// Declare function calls that will be accessible from Python

// C code for performance-critical operations
//   Functions return Python object(s) (e.g. NumPy array), if applicable
```

---

# CPython extension modules

- Typical usage:
 - Accelerator module: self-contained C code, for speed
 - Wrapper/interface module: interface with other C code (libraries)
 - Low-level system access: interface with OS, hardware, ...
  
- NumPy extension modules:
 - Accelerator modules: e.g. inner loops moved to C
 - Wrapper/interface modules: e.g. call Fortran/C linear algebra libraries
 - Low-level: e.g. vectorise operations, control memory layout of arrays

---

# CPython extension modules

- Advantage: extremely flexible

- Disadvantages:
    - May require thorough understanding of CPython and its Python/C API
        - Significant (initial) development effort
        - May be difficult to maintain (C API changes)

- Cython (next) partly automates creation of CPython extension modules
    - Does not require intimate knowledge of CPython
    - Expect Cython to take care of changes in CPython

---

template:titleslide
# Cython

---

# Cython

- Enrich performance-critical Python code with additional syntax
 - Cython = Python + static declarations of C types + calls to C functions

- Cython compiler (`cython`) converts Cython code to C code that calls CPython's C API
    - Effectively creates a CPython extension module for you
    - Automatically generates Python wrappers and C API calls 
        - Unlike manual Python-C interfacing using e.g. `ctypes`!
        - Cython code can manipulate both Python and C variables, conversions occur automatically wherever possible

- Resulting C code is compiled into a shared library for import in Python
    - Using conventional C compiler, e.g. `gcc`
    - Benefits from all the usual static typing-based ahead-of-time (AOT) compilation optimisations

---

# Cython example

Pure Python (**`fib.py`**)

```Python
# Returns the nth Fibonacci number
def fib(n):
    a = 0.0
    b = 1.0
    for i in range(n):
        a, b = a + b, a
    return a
```
Could already Cython-compile, but haven't defined C types so may not be faster. Can use Cython syntax to declare static C types (save as **`fib_cython.pyx`**):

```Cython
# Returns the nth Fibonacci number
def fib(int n):
  cdef int i
  cdef double a = 0.0
  cdef double b = 1.0
  for i in range(n):
    a, b = a + b, a
  return a
```

---

# Cython example

Create `setup.py`, e.g.:
```Python
from distutils.core import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("fib.pyx"),
)
```
Build CPython extension module from the shell:
```
> python setup.py build_ext --inplace
```
   - `cython` compiles (transpiles) `fib.pyx` to `fib.c`
   - `gcc` compiles `fib.c` to `fib.cpython.so`

To use `fib` function from `fib.cpython.so` in a Python script, just do:
```Python
import fib
fib.fib(200)

```



---

# Cython example

Fibonacci example gives the following performance results:

 Implementation                                | Runtime | Speedup
-----------------------------------------------|---------|---------
 Pure Python                                   | 9.21 µs |    1 `x`
 [Cythonized Pure Python (no explicit cdefs)](https://epcced.github.io/APT-python4hpc/lectures/02/cython/fib_python.html)    | 1.38 µs |    7 `x`
 [Cythonized Cython (explicit cdefs)](https://epcced.github.io/APT-python4hpc/lectures/02/cython/fib_cython.html)            |  245 ns |   37 `x`

- Note: C files are 2500 - 3000 lines long!

- Inspect annotated source (generate with `annotate=True` cythonize option)
  - Shows C code generated by each line of Cython
  - Highlights interactions between C code and CPython's C API
      - Helps determine where further optimisation possible 


---


# Cython


Advantages:
- Automates much of CPython extension module creation

- Incremental development and focused optimisation of hotspots

- Automatically perform at compile what would be runtime checks in pure Python, e.g. out-of-bounds array access

- Can create wrapper modules to interface Python with existing code, e.g. C-based high-performance numerical libraries
  - need to `cimport` Cython syntax equivalent of a header file describing external C code to be able to call it within Cython code

- Can also be used to call into Python code from C
  
---

# Cython

Limitations / things to consider:

- Little/no speedup for conventional (non-C-translatable) Python code and Python native data structures (lists, tuples, dicts)

- For Cython code to be fast it should avoid frequent calls to Python (wrapper) functions or access of pure-Python data structures, as this requires bytecode execution through the PVM
  - Cythonize can annotate Cython code to help target optimisation

- Explicit type annotation cumbersome

- Often requires restructuring code

- Code build becomes more complicated, more difficult to maintain


---

template:titleslide
# PyPy

---

# PyPy

- Alternative Python interpreter (i.e. not CPython)
    - Compiler generates code objects (bytecode) from source
    - Evaluator executes bytecode

- Just-in-time (JIT) compilation:
    - Bytecode generation and execution starts straightaway (like CPython)
    - PyPy traces which evaluator operations (not which bytecode) contribute most to execution time (**hotspot detection**)
    - Compiler attempts optimisations of "hot" evaluator operations
        - Constant folding, boolean & arithmetic simplifications
        - Vectorisation
        - Loop unrolling
    - Generates machine code for remaining costly evaluator operations

- Garbage collection does not rely on global reference counter

---

# PyPy

Advantages:
- More general / generic "out of the box" optimisations than CPython
- Code still starts straightaway, no initial compilation cost 
- Easy to use - no changes to existing Python code needed
    - just execute with `pypy` instead of with `python`

Disadvantages:
- Only implements core Python functionality
    - e.g. does not support integration with all of NumPy
    - Not compatible with the majority of packages in the Python ecosystem


---

template:titleslide
# Numba

---

# Numba 

- JIT-compiler within CPython framework that uses LLVM toolchain

- Choose functions to be just-in-time (JIT) compiled with `@jit` decoration

- When a JIT-decorated function is called for the first time, it is compiled into machine code using LLVM 

- Subsequent calls with same argument types execute the machine code

- Uses built-in version of LLVM, so no calls to external compiler/loading libraries

---

# Numba overview

.center[![:scale_img 90%](numba_flowchart.png)]

[source](https://github.com/ContinuumIO/gtc2017-numba)

---

# Numba example

```Python
import numpy as np
from numba import jit

@jit (nopython = True)
def array_sqrt(n, ain, aout):
    for i in range(n):
        aout[i] = np.sqrt(ain[i])

a_in  = np.array([4.0, 9.0, 16.0, 25.0], np.double)
a_out = np.zeros(4, np.double)

array_sqrt(a_in.size, a_in, a_out)
print(a_out)
```
`[2. 3. 4. 5.]`


---

# Numba performance - `nopython` mode

- JIT-decorated function faster if:
  - All underlying types of objects in function code can be inferred
  - No new Python objects created in function code

- Because then:
  - Function code does not require the Python interpreter, e.g. for type checking or Python object handling
  - Numba can compile entire function into machine code with LLVM to execute without using Python interpreter


- "`nopython=True`" in `@jit` decorator means code won't execute otherwise
  - Should enforce for best performance (forced to modify code until it executes)

- Without "`nopython=True`" non-LLVM-compilable code executed by Python interpreter
  - Numba still tries to compile some parts, e.g. `for` loops

---

# Numba performance

 ### Tip: don't 'unvectorise' fast NumPy code!

Numba works well to speed up nonvectorised NumPy code that explicitly iterates over many items

- Does not mean we should rewrite existing vectorised NumPy code to use explicit for loops (slow!) in order for Numba to have a strong effect
  - Any speed up gain from Numba is likely to be cancelled out by removal of vectorised code

---

# Numba performance

Numba works best when:

- Function called many times during execution
 - Compilation is slow, so if the function is not called often, savings in execution time unlikely to compensate for compilation time
 
- Compute time primarily due to NumPy array element memory access or numerical operations more complex than a single NumPy function call

- Original function execution time larger than Numba dispatcher overhead
  - Numba dispatch wrapper transitions from Python interpreter to Numba-compiled machine code
  - Functions taking << 1 µs (no Numba) won't see major improvement
 
---

# PyPy vs Numba

- Both provide JIT-optimised execution of Python code

- Both easy to use:
    - No code changes needed for PyPy
    - Numba uses simple decorators

- Compatibility:
    - PyPy support for NumPy, still relatively immature
    - Numba works with CPython and NumPy
        - not every single Numpy feature, but code will still run

- Performance:
    - It depends... try it!
    - Numba more generally useful for numerical computing
        - can also be used to target GPUs

---

# Next

- Can try Numba in first practical to speed up Python CFD code

- Next lecture covers parallel computing with Python
  - Multithreading in Python
    - Problematic due to the Global Interpreter Lock (GIL) 

  - Implementing thread-based/shared-memory and process-based/distributed-memory parallelism using Numba, Cython, OpenMP and MPI 










