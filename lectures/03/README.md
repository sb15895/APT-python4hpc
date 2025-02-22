
template: titleslide

# Parallel Computing with Python

---

# Parallel Computing with Python

- Python threads and the Global Interpreter Lock (GIL)

- Threading and interfaced code
  - NumPy/SciPy
  - Cython + OpenMP

- Parallel computing with Numba

- Python `multiprocessing`

- mpi4py

- Python for HPC



*(parts adapted with permission from http://doi.org/10.5281/zenodo.1409686)*

---

template:titleslide
# Python threads and the GIL

---

# Python threads and the GIL

- CPython interpreter process can spawn threads (`import threading`, etc.)
    - implemented as OS-managed threads (e.g. POSIX `pthreads` in Linux)

- Global Interpreter Lock (GIL) is (still) a core component of CPython
    - GIL = a **mutex lock** on threads: only one thread can execute bytecode in the interpreter at any time (like an OpenMP critical section)
        - https://github.com/python/cpython/blob/master/Python/ceval_gil.h

    - Early implementation of mutex lock acquisition and release meant CPU-bound threads (typical for numerical computing) waste vast amounts of time 'battling' to obtain the GIL (massive contention)

    - Newer (Python >3.2) implementation more efficient, but still prevents actual concurrent threaded execution of bytecode
        - Expect bad scaling from multithreaded pure Python code
        - Calling external compiled code is a different story...


---

# Why the GIL?

- Originally created to ensure thread safety for Python garbage collection (avoiding race condition on reference counter)

- Also useful historically for integration into CPython of C library code that was not itself guaranteed to be thread safe

- Easier to get faster single-threaded programs (no necessity to acquire or release locks on all data structures separately)

- Easier to implement than lock-free interpreter or one with finer-grained locks!

- Good enough for originally intended generic purpose (not numerically intensive computing by all threads)

---

# Releasing the GIL

Function calls that release the GIL can be executed concurrently by multiple Python threads

- GIL can be released for NumPy functions that:
  - involve underlying C arrays but *not* Python object arrays (ndarrays)
  - don't have side effects for other threads (e.g. modify global variables) 
  - Implemented in NumPy functions with NPY_ALLOW_THREADS:
     - NumPy > 1.9.0: array indexing (slicing, broadcast etc.)
     - NumPy > 1.12.0: all generalized ufuncs, including most linear algebra

- Can call interfaced / imported Fortran/C/C++ code written to release the GIL as long as it is thread safe
  - Will look at how to do this using Cython + OpenMP threads
  - For good parallel performance, code should be able to release GIL even if not using Python threads 

---

# Releasing the GIL


Even without releasing GIL, can call external non-Python code that runs multithreaded (using OpenMP, pthreads, ...) if it spawns these threads
  - NumPy/SciPy function called by single Python thread may call threaded high-performance maths libraries

example: matrix product
```
>>> C = numpy.dot(A,B)

```
executed by threaded BLAS library if NumPy linked to BLAS at build time


---

template:titleslide
# Cython + OpenMP

---

# Cython + OpenMP

`cython.parallel` module brings OpenMP runtime and thread control to Cython
 - primarily through parallel `for` loop using `cython.parallel.prange`(...):

```Python
# code saved in file ending in .pyx for cython code
from cython.parallel import prange

# First declare the variables we are going to use with cdefs:
cdef int i
cdef int n = 30
cdef int sum = 0

# Use prange instead of native Python's range
for i in prange(n, nogil=True):
    sum += i

print(sum)
```

---

# OpenMP control of Cython parallel region 


- OpenMP automatically starts thread pool and distributes the work according to the chosen schedule (`static`, `dynamic`, `guided`, `runtime`) and chunk size (optional)

- Number of threads specified in function call, OMP_NUM_THREADS, or equal to number of cores available

- Thread-locality (shared/private) and reductions of variables inferred automatically according to OpenMP conventions

- Can access OpenMP using Cython's `cimport` syntax, e.g. `omp_get_thread_num()` as an alternative to `cython.parallel.threadid()`: 

```Python
from cython.parallel cimport parallel
cimport openmp

cdef int num_threads

openmp.omp_set_dynamic(1)
with nogil, parallel():
    num_threads = openmp.omp_get_num_threads()
```

---

# `cimport`

- `cimport` is Cython syntax (not recognised by Python interpreter)

- Imports header file describing external C code (data types, function signatures, variables, etc.) to be able to use these within Cython code 
    - May need to include path in `setup.py` for Cython compiler to find relevant C header files, e.g. for `cimport` `numpy` may need to add:

    ```
    include_dirs=["numpy_include()]
    ```

- Does not imply import of any Python objects from the named `cimport`ed module

---


# `nogil=True`

- `nogil=True` tells Cython to generate C code that will release the GIL
  - Must not manipulate Python objects in any way 
     - Cython compiler will complain
     - like Numba's `nopython` mode
  - Must not *call* anything that manipulates Python objects without first re-acquiring the GIL

- Key to threaded performance 
  - Otherwise Cython might generate C code that hands over to PVM

- Programmer responsible for ensuring thread safety!
  - within code block, and of any code called

---

# `nogil=True`
Suppose we want to print out intermediate values:
```Python
# Thread ID
from cython.parallel import prange

cdef int i
cdef int sum = 0

for i in prange(1000, nogil=True):
    sum += i
    print("Current loop iter:", i)
```

- Cython compiler will throw an error!

Why?

- `print` is a Python native function 
- GIL can not be released on code that involves any Python objects

---

# `nogil=True`

- General workaround strategy: `cimport` a C function or data type (GIL-free!) to replace pure Python code in `nogil=True` region
 - e.g. the `printf()` function from C:

```Python
#Thread ID
from cython.parallel import prange
# Give me a C function!
from libc.stdio cimport printf

cdef int i
cdef int sum = 0

for i in prange(4, nogil=True):
    sum += i
    printf("Current loop iter: %d\n", i)
```

---

# `cython.parallel.parallel`

- Some more general parallel work-sharing region constructs possible using `cython.parallel.parallel()`, e.g.:

```Python
from cython.parallel import parallel, prange
from libc.stdlib cimport abort, malloc, free

cdef Py_ssize_t idx, i, n = 100
cdef int * local_buf
cdef size_t size = 10

with nogil, parallel():
    local_buf = <int *> malloc(sizeof(int) * size)
    if local_buf is NULL:
        abort()

    # populate our local buffer in a sequential loop
    for i in xrange(size):
        local_buf[i] = i * 2

    # share the work using the thread-local buffer(s)
    for i in prange(n, schedule='guided'):
        func(local_buf)

    free(local_buf)
```

---

# Cython "critical sections" 

Can define a "critical section" in Cython by using `with gil` inside a `nogil`-parallel region to isolate operations for thread safety

---

# Compiling...

To compile parallel Cython code into C need to add `-fopenmp` flags to `setup.py`:

```Python
from setuptools import Extension, setup
from Cython.Build import cythonize

ext_modules = [
    Extension(
        "hello",
        ["hello.pyx"],
        extra_compile_args=['-fopenmp'],
        extra_link_args=['-fopenmp'],
    )
]

setup(
    name='hello-parallel-world',
    ext_modules=cythonize(ext_modules),
)
```


---

# Cython for Parallel Computing

- Relatively mature, providing an opportunity to do efficient thread-based parallel programming when we can guarantee not to use Python objects

- cython.parallel provides interface to much of OpenMP API

- Can stick to the basic constructs like `prange` and `with nogil` to access simple parallelism techniques

- Requires more programming effort time compared to e.g. Numba, but offers finer grained control, interoperability with C and C++ code, and access to some of the power of the OpenMP library. 

#### References:
https://cython.readthedocs.io/en/latest/src/userguide/parallelism.html
https://software.intel.com/en-us/articles/thread-parallelism-in-cython

---

template:titleslide
# Parallel computing with Numba

---


# Numba parallel

- Numba can attempt to automatically parallelise a jit-decorated function, request using `@jit(parallel=True, nopython=True)`
 - will attempt to optimize array operations and run them in parallel
 - enables Numba's `prange()` explicit loop parallelisation construct

- `parallel=True` requires `nopython=True`
 - i.e. Numba must be able to do compile-time type inference and not use CPython's C API, including not creating any new Python objects

- Threading layer is implemented using one choice of:
 - OpenMP
 - Intel TBB
 - Numba's internal work queue scheduler

---

# Numba and the GIL

- `@jit(nogil=True)` releases the GIL upon entry to a jit-decorated function

- Allows function code to run concurrently with other threads executing Python or Numba code (either the same compiled function, or another one)

- Have to consider thread safety (consistency, synchronization, race condition, etc.)

---

# Numba parallel

Numba attempts to parallelise:
- common element-wise arithmetic functions between NumPy arrays and between arrays and scalars (e.g. `+`, `-`, `~`, `*`, `**`, `==`, `!=`, `<`)

- NumPy reduction functions (`sum`, `prod`, `min`, `max`, `argmin`, and `argmax`) and array math functions (`mean`, `var`, and `std`)

- NumPy array creation functions (`zeros`, `ones`, `arange`, `linspace`), and several random functions

- NumPy `dot` function between a matrix and a vector, or two vectors

- Above operations for multi-dimensional arrays when operands have matching dimension and size

- Array assignment where the target is a slice and the source another compatible slice or a scalar

- Fusion of adjacent parallel operations to maximize cache locality

---

# Numba parallel

Numba will automatically try to detect loops that can be parallelised
- Can enforce using explicit parallel loop construct `prange`:

```Python
from numba import jit, prange

@jit(nopython=True, parallel=True)
def prange_test(A):   # 'A' would be a 1D numpy array in this example
    s = 0
    for i in prange(A.shape[0]):
        s += A[i]
    return s
```
- `prange` will automatically infer a reduction if a variable is being updated by a binary function/operator (i.e. +, -, /, *)
 - **`s`** above is automatically identified as a reduction variable
- Numba ensures thread safety but programmer must determine if loop can be parallelised without affecting result

- Easier to try auto-parallelisation first, then explicit `prange` if Numba cannot determine automatically if a loop can be parallelised

---

# Numba parallel - summary

- Very easy to implement - just extend JIT decoration of compute-intensive functions

- Some GPU offloading implemented

- Still limited to shared-memory concurrency

---

template:titleslide
# Python `multiprocessing`



---

# Python `multiprocessing`

- `multiprocessing` module creates multiple instances of the Python interpreter, each running as an independent OS-level (sub)process 
 - no GIL contention between instances

- Each Python instance has its own memory space, managed by the OS
 - possible to declare a shared memory between processes, but this brings up synchronisation issues

- Need communication between processes, requires explicit conversion of Python object structure hierarchy into a bytestream ("pickling")
 - Originally designed for file storage of Python objects - slow

- Bytestream sent from one process to another, and reconstituted ("unpickled")

- Approach best suited for independent tasks, or tasks requiring minimal communication

---

# Multiprocessing

- Typically define a task as a Python function

Task distribution / work sharing can use:

- Static data-parallel pool of workers model
 - split up work of predetermined size across available workers/cores
 - useful when workload distribution is static 
 - not adaptable to varying / unpredictable workload
- Queue approach
 - Put data -  wrapped as Python objects - onto one or more work queues
 - Each worker queries queue once done with work to receive more
 - Dynamically adaptable to varying load
 - Communication overheads can dominate, especially due to pickling

- Useful in some (limited) circumstances
    - Can operate across distributed-memory nodes in principle, but tricky in practice - operates via TCP server and needs manual specification of IP addresses - not suitable for HPC deployment

---

# mpi4py

- Python can do MPI!
 - multiple modules, mpi4py most common & mature

```Python
from mpi4py import MPI

comm = MPI.COMM_WORLD

print("Hello from rank {} of {} ...".format(comm.rank, comm.size))

# Wait for everyone to synchronise here:
comm.Barrier()
```

- Launch `n` instances of the Python interpreter:

```
$ mpirun -n 192 python myMPI-ParallelScript.py
```

- Instances share an MPI_COMM_WORLD initialised by the parallel application launcher, like any other MPI application

- Expect all relevant standard-compliant functionality to be present (point-to-point, collectives, etc.)

---

# mpi4py performance

- Sending and receiving of generic Python objects suffers from significant overheads due to  pickling & unpickling (like multiprocessing module)
 - uses lower case functions `send`, `recv`, `gather`

- Contiguous memory buffers such as Numpy arrays can be sent without pickling and with very little overhead, close to efficiency of equivalent calls from C/Fortran
 - uses upper case functions `Send`, `Recv`, `Gather`

---

# Python for HPC?

- Python plays a role in many aspects of scientific computing, and increasingly in HPC

- Only expected to grow with increasing massively-parallel data analytics

- Tightly integrated with some applications

- Even if heaviest computational lifting done by C/C++/Fortran, knowing how to efficiently feed & glue the core compute together with other functionality efficiently is very valuable 


##### References


Python in the NERSC Exascale Science Applications Program for Data:
https://dl.acm.org/citation.cfm?id=3149873

Exascale Deep Learning for Climate Analytics (2018 Gordon Bell Prize):
https://dl.acm.org/citation.cfm?id=3291724


---



