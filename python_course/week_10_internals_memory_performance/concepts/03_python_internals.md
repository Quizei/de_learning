# Python Internals

Understanding how Python works under the hood.

```python
import dis
import sys
```

## BYTECODE

```python
print("--- Bytecode ---")

def add(a, b):
    return a + b

# Disassemble function
print("Disassembly of add():")
dis.dis(add)

# View code object
print(f"\nCode object attributes:")
print(f"  co_varnames: {add.__code__.co_varnames}")
print(f"  co_argcount: {add.__code__.co_argcount}")
print(f"  co_stacksize: {add.__code__.co_stacksize}")
```

## PYTHON EXECUTION MODEL

```python
print("\n--- Execution Model ---")
print("""
1. Source code (.py)
2. Compiled to bytecode (.pyc)
3. Bytecode executed by Python Virtual Machine (PVM)

The PVM is a stack-based virtual machine that:
- Reads bytecode instructions
- Executes them one by one
- Manages the call stack
""")
```

## NAME RESOLUTION (LEGB)

```python
print("\n--- LEGB Rule ---")
print("""
Python looks up names in this order:
L - Local: Names inside the current function
E - Enclosing: Names in enclosing functions
G - Global: Names at module level
B - Built-in: Names in built-in module
""")

x = "global"

def outer():
    x = "enclosing"

    def inner():
        x = "local"
        print(f"Local x: {x}")

    inner()
    print(f"Enclosing x: {x}")

outer()
print(f"Global x: {x}")
```

## DESCRIPTOR PROTOCOL

```python
print("\n--- Descriptor Protocol ---")

class Descriptor:
    def __get__(self, obj, objtype=None):
        print(f"Getting: obj={obj}, type={objtype}")
        return 42

    def __set__(self, obj, value):
        print(f"Setting to {value}")

class MyClass:
    attr = Descriptor()

obj = MyClass()
print(f"Value: {obj.attr}")
obj.attr = 100
```

## METACLASSES

```python
print("\n--- Metaclasses ---")

class MyMeta(type):
    def __new__(mcs, name, bases, namespace):
        print(f"Creating class: {name}")
        return super().__new__(mcs, name, bases, namespace)

class MyClass(metaclass=MyMeta):
    pass
```

## IMPORT SYSTEM

```python
print("\n--- Import System ---")
print(f"sys.path: {sys.path[:3]}...")  # Search paths
print(f"Loaded modules: {len(sys.modules)} modules")
```

## GIL (GLOBAL INTERPRETER LOCK)

```python
print("\n--- GIL ---")
print("""
The GIL is a mutex that protects access to Python objects.

Key points:
- Only one thread executes Python bytecode at a time
- Released during I/O operations
- CPU-bound threads don't parallelize
- Use multiprocessing for CPU parallelism
- asyncio and threading work for I/O-bound tasks
""")
```

## OBJECT MODEL

```python
print("\n--- Object Model ---")

class Example:
    class_attr = "class"

    def __init__(self):
        self.instance_attr = "instance"

obj = Example()

print(f"Instance __dict__: {obj.__dict__}")
print(f"Class __dict__ keys: {list(Example.__dict__.keys())[:5]}")
print(f"MRO: {Example.__mro__}")
```

## INTERNING

```python
print("\n--- Interning ---")

# Strings can be interned
import sys
s1 = sys.intern("hello world")
s2 = sys.intern("hello world")
print(f"Interned strings same object: {s1 is s2}")

# Small integers are cached
a = 100
b = 100
print(f"Small ints cached: {a is b}")

print("\n✅ Python internals complete!")
```
