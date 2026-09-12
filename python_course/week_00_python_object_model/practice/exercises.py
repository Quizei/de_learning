"""
Week 0 Practice Exercises: Python Object Model
===============================================
Test your understanding of Python's core object model.
Try to predict the output BEFORE running the code.
"""

# ================================
# EXERCISE 1: Predict the Output
# ================================
"""
What will be printed? Think carefully!
"""

def exercise_1():
    print("--- Exercise 1 ---")
    a = [1, 2, 3]
    b = a
    a = a + [4, 5]
    print(f"a = {a}")
    print(f"b = {b}")
    # Your prediction: a = ?, b = ?

# ================================
# EXERCISE 2: Predict the Output
# ================================

def exercise_2():
    print("\n--- Exercise 2 ---")
    a = [1, 2, 3]
    b = a
    a += [4, 5]
    print(f"a = {a}")
    print(f"b = {b}")
    # Your prediction: a = ?, b = ?
    # Why is this different from Exercise 1?

# ================================
# EXERCISE 3: Predict the Output
# ================================

def exercise_3():
    print("\n--- Exercise 3 ---")
    x = 10
    y = x
    x += 5
    print(f"x = {x}")
    print(f"y = {y}")
    # Your prediction: x = ?, y = ?

# ================================
# EXERCISE 4: Predict the Output
# ================================

def exercise_4():
    print("\n--- Exercise 4 ---")

    def modify(lst):
        lst.append(4)
        lst = [5, 6, 7]
        lst.append(8)

    my_list = [1, 2, 3]
    modify(my_list)
    print(f"my_list = {my_list}")
    # Your prediction: my_list = ?

# ================================
# EXERCISE 5: Predict the Output
# ================================

def exercise_5():
    print("\n--- Exercise 5 ---")
    x = "global"

    def outer():
        x = "outer"

        def inner():
            x = "inner"
            print(f"inner: x = {x}")

        inner()
        print(f"outer: x = {x}")

    outer()
    print(f"global: x = {x}")
    # Your prediction for each print?

# ================================
# EXERCISE 6: Predict the Output
# ================================

def exercise_6():
    print("\n--- Exercise 6 ---")

    def make_multiplier(n):
        def multiplier(x):
            return x * n
        return multiplier

    times2 = make_multiplier(2)
    times3 = make_multiplier(3)

    print(f"times2(5) = {times2(5)}")
    print(f"times3(5) = {times3(5)}")
    # Your prediction?

# ================================
# EXERCISE 7: Fix the Bug
# ================================

def exercise_7():
    print("\n--- Exercise 7: Fix the Bug ---")

    def add_item_buggy(item, items=[]):
        items.append(item)
        return items

    print(f"Call 1: {add_item_buggy('a')}")
    print(f"Call 2: {add_item_buggy('b')}")
    print(f"Call 3: {add_item_buggy('c')}")
    # What's the bug? How would you fix it?

# ================================
# EXERCISE 8: is vs ==
# ================================

def exercise_8():
    print("\n--- Exercise 8 ---")
    a = [1, 2, 3]
    b = [1, 2, 3]
    c = a

    print(f"a == b: {a == b}")
    print(f"a is b: {a is b}")
    print(f"a == c: {a == c}")
    print(f"a is c: {a is c}")

    x = 256
    y = 256
    print(f"\n256 is 256: {x is y}")

    x = 257
    y = 257
    print(f"257 is 257: {x is y}")
    # Predict all outputs. Explain why.

# ================================
# EXERCISE 9: Shallow vs Deep Copy
# ================================

def exercise_9():
    print("\n--- Exercise 9 ---")
    import copy

    original = [[1, 2], [3, 4]]
    shallow = original.copy()
    deep = copy.deepcopy(original)

    original[0][0] = 99
    original.append([5, 6])

    print(f"original: {original}")
    print(f"shallow:  {shallow}")
    print(f"deep:     {deep}")
    # Predict all outputs.

# ================================
# EXERCISE 10: Tricky Scope
# ================================

def exercise_10():
    print("\n--- Exercise 10 ---")

    funcs = []
    for i in range(3):
        funcs.append(lambda: i)

    for f in funcs:
        print(f"f() = {f()}")

    # What's printed? Why?
    # How would you fix it to print 0, 1, 2?

# ================================
# RUN ALL EXERCISES
# ================================

def run_all():
    exercise_1()
    exercise_2()
    exercise_3()
    exercise_4()
    exercise_5()
    exercise_6()
    exercise_7()
    exercise_8()
    exercise_9()
    exercise_10()

# ================================
# SOLUTIONS
# ================================

def show_solutions():
    print("\n" + "=" * 50)
    print("SOLUTIONS")
    print("=" * 50)

    print("""
--- Exercise 1 ---
a = [1, 2, 3, 4, 5]
b = [1, 2, 3]

WHY: a + [4,5] creates a NEW list and rebinds 'a' to it.
     'b' still points to the original [1,2,3].

--- Exercise 2 ---
a = [1, 2, 3, 4, 5]
b = [1, 2, 3, 4, 5]

WHY: For lists, += calls extend() which modifies IN PLACE.
     Both 'a' and 'b' point to the same list.

--- Exercise 3 ---
x = 15
y = 10

WHY: Integers are immutable. x += 5 creates a NEW int object.
     'y' still points to the original 10.

--- Exercise 4 ---
my_list = [1, 2, 3, 4]

WHY: lst.append(4) modifies the original list.
     lst = [5,6,7] rebinds the LOCAL 'lst' variable only.
     The original my_list is unaffected by the rebinding.

--- Exercise 5 ---
inner: x = inner
outer: x = outer
global: x = global

WHY: Each scope has its own 'x'. Inner shadows outer, etc.

--- Exercise 6 ---
times2(5) = 10
times3(5) = 15

WHY: Closures capture the enclosing variable 'n'.
     Each call to make_multiplier creates a new closure with its own 'n'.

--- Exercise 7 ---
The bug: Default mutable argument is shared between calls.
Call 1: ['a']
Call 2: ['a', 'b']
Call 3: ['a', 'b', 'c']

FIX:
def add_item_fixed(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

--- Exercise 8 ---
a == b: True  (same values)
a is b: False (different objects)
a == c: True  (same values)
a is c: True  (same object)
256 is 256: True  (cached small int)
257 is 257: May be True or False (implementation dependent)

--- Exercise 9 ---
original: [[99, 2], [3, 4], [5, 6]]
shallow:  [[99, 2], [3, 4]]
deep:     [[1, 2], [3, 4]]

WHY:
- Shallow copy shares inner lists → original[0][0]=99 affects shallow
- Shallow copy is separate container → append doesn't affect shallow
- Deep copy is completely independent

--- Exercise 10 ---
f() = 2
f() = 2
f() = 2

WHY: All lambdas capture the SAME variable 'i', which is 2 after the loop.

FIX: Capture current value as default argument:
    funcs.append(lambda i=i: i)
""")

if __name__ == "__main__":
    print("Try to predict outputs before running!\n")
    run_all()

    print("\n\nWant to see solutions? Uncomment the line below:")
    # show_solutions()
