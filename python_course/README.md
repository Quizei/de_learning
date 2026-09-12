# Python Mastery for Data Engineers

An 11-week structured Python course (Week 0-10) designed for intermediate developers preparing for data engineering interviews.

---

## Course Overview

| Week | Topic | Key Skills |
|------|-------|------------|
| 0 | Python Object Model | variable binding, mutability, LEGB scope, is vs ==, copying |
| 1 | Data Structures & Comprehensions | collections, Counter, defaultdict, list/dict comprehensions |
| 2 | Functions Deep Dive | decorators, closures, functools, *args/**kwargs |
| 3 | OOP, Data Classes & Patterns | dunder methods, @dataclass, design patterns |
| 4 | Iterators, Generators & Context Managers | yield, itertools, context managers |
| 5 | File I/O & Data Formats | JSON, CSV, pathlib, large file handling |
| 6 | Exceptions, Logging & Debugging | custom exceptions, logging module, pdb |
| 7 | Concurrency & Parallelism | threading, multiprocessing, asyncio, GIL |
| 8 | APIs, Databases & SQL | requests, SQLAlchemy, connection pooling |
| 9 | Testing, Type Hints & Code Quality | pytest, typing, mypy, mocking |
| 10 | Python Internals & Performance | memory management, profiling, optimization |
| Bonus | Coding Problems | real-world interview problems |

---

## Folder Structure

```
Python_Course_claude/
│
├── week_00_python_object_model/
│   ├── concepts/       # Core object model concepts
│   ├── practice/       # Predict-the-output exercises
│   ├── projects/       # Memory visualizer tool
│   └── README.md       # Week details
│
├── week_01_data_structures_comprehensions/
│   ├── concepts/       # Learning examples
│   ├── practice/       # Exercises
│   ├── projects/       # Mini project
│   └── README.md       # Week details
│
├── week_02_functions_deep_dive/
├── week_03_oop_dataclasses_patterns/
├── week_04_iterators_generators_context/
├── week_05_file_io_data_formats/
├── week_06_exceptions_logging_debugging/
├── week_07_concurrency_parallelism/
├── week_08_apis_databases_sql/
├── week_09_testing_typing_code_quality/
├── week_10_internals_memory_performance/
│
└── bonus_coding_problems/
    ├── easy/
    ├── medium/
    └── hard/
```

---

## Weekly Learning Pattern

Each week follows this structure:

1. **Concepts** - Read and run code examples to understand the topic
2. **Practice** - Solve exercises to reinforce learning
3. **Projects** - Build a mini project applying the week's concepts

---

## Week-by-Week Breakdown

### Week 0: Python Object Model (Foundation)
- How variable names bind to objects in memory
- Mutability vs immutability
- Argument passing (pass by object reference)
- LEGB scope rule (Local, Enclosing, Global, Built-in)
- `is` vs `==` (identity vs equality)
- Shallow vs deep copying
- **Project:** Memory visualizer tool

### Week 1: Advanced Data Structures & Comprehensions
- `collections` module (Counter, defaultdict, deque, namedtuple)
- List, dict, set comprehensions
- Generator expressions
- Walrus operator `:=`
- **Project:** Log analyzer using collections

### Week 2: Functions Deep Dive
- First-class functions
- `*args` and `**kwargs`
- Closures and lexical scoping
- Decorators (basic, with arguments, stacking)
- `functools` (partial, lru_cache, wraps, reduce)
- **Project:** Timing/retry decorator library

### Week 3: OOP, Data Classes & Design Patterns
- Magic/dunder methods
- `@property`, `@staticmethod`, `@classmethod`
- `@dataclass` decorator
- Abstract base classes (ABC)
- Design patterns (Singleton, Factory, Strategy)
- **Project:** Data pipeline configuration system

### Week 4: Iterators, Generators & Context Managers
- Iterator protocol (`__iter__`, `__next__`)
- Generators with `yield` and `yield from`
- `itertools` module
- Context managers (`__enter__`, `__exit__`)
- `contextlib` module
- **Project:** Lazy file reader for large datasets

### Week 5: File I/O & Data Formats
- File handling modes and `pathlib`
- CSV and JSON processing
- Handling large files efficiently
- Data serialization (pickle)
- **Project:** ETL script (CSV to JSON transformer)

### Week 6: Exceptions, Logging & Debugging
- Exception hierarchy and custom exceptions
- try/except/else/finally patterns
- `logging` module configuration
- Debugging with `pdb` and `breakpoint()`
- **Project:** Robust data validator

### Week 7: Concurrency & Parallelism
- Threading and thread synchronization
- Multiprocessing and process pools
- `concurrent.futures` executors
- Async programming with `asyncio`
- GIL and its implications
- **Project:** Parallel data downloader

### Week 8: APIs, Databases & SQL Integration
- REST API consumption with `requests`
- API authentication and error handling
- Database connectivity (sqlite3, psycopg2)
- SQLAlchemy basics
- Parameterized queries
- **Project:** API-to-database ingestion pipeline

### Week 9: Testing, Type Hints & Code Quality
- Unit testing with `pytest`
- Fixtures, parameterized tests, mocking
- Type hints and `typing` module
- Static type checking with `mypy`
- Code formatting and linting
- **Project:** Add tests and types to a data module

### Week 10: Python Internals, Memory & Performance
- Python bytecode and execution model
- Memory management and garbage collection
- GIL internals
- Profiling with `cProfile` and `timeit`
- `__slots__` and optimization techniques
- **Project:** Profile and optimize a slow script

---

## Interview Topics Covered

### Technical Concepts
- [x] Python object model and memory
- [x] Variable binding, mutability, and copying
- [x] Data structures and time complexity
- [x] Decorators and closures
- [x] OOP principles and design patterns
- [x] Generators and memory efficiency
- [x] Concurrency models (threading vs multiprocessing vs async)
- [x] GIL and its implications
- [x] Database connectivity and ORM
- [x] Testing and mocking strategies
- [x] Type hints and static typing
- [x] Performance optimization

### Practical Skills
- [x] File processing and data formats
- [x] API consumption and error handling
- [x] SQL integration with Python
- [x] Writing production-grade code
- [x] Debugging and profiling

### Coding Problems
- [x] Data transformation challenges
- [x] Aggregation and deduplication
- [x] Implementing caches (LRU)
- [x] Stream processing
- [x] Concurrency patterns

---

## How to Use This Course

1. **Start with Week 0** - foundational object model concepts everything else builds on
2. **Follow the weeks in order** - concepts build on each other
3. **Run every code example** - don't just read, execute
4. **Complete all practice exercises** - before looking at solutions
5. **Build the mini projects** - apply what you learned
6. **Time yourself on coding problems** - simulate interview conditions
7. **Review weekly** - revisit concepts before moving on

---

## Progress Tracker

| Week | Concepts | Practice | Project | Status |
|------|----------|----------|---------|--------|
| 0 | [ ] | [ ] | [ ] | Not Started |
| 1 | [ ] | [ ] | [ ] | Not Started |
| 2 | [ ] | [ ] | [ ] | Not Started |
| 3 | [ ] | [ ] | [ ] | Not Started |
| 4 | [ ] | [ ] | [ ] | Not Started |
| 5 | [ ] | [ ] | [ ] | Not Started |
| 6 | [ ] | [ ] | [ ] | Not Started |
| 7 | [ ] | [ ] | [ ] | Not Started |
| 8 | [ ] | [ ] | [ ] | Not Started |
| 9 | [ ] | [ ] | [ ] | Not Started |
| 10 | [ ] | [ ] | [ ] | Not Started |
| Bonus | [ ] | [ ] | [ ] | Not Started |

---

## Resources

### Documentation
- [Python Official Docs](https://docs.python.org/3/)
- [Real Python](https://realpython.com/)

### Practice Platforms
- [LeetCode](https://leetcode.com/) - for coding problems
- [HackerRank](https://www.hackerrank.com/) - Python domain

---

*Course designed for intermediate Python developers targeting data engineering roles.*
