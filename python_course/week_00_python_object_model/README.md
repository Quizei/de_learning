# Week 0: Python Object Model

## Why This Matters

Before diving into advanced Python, you need a rock-solid understanding of **how Python actually works**. These concepts are:

- Asked in almost every Python interview
- The source of most subtle bugs
- The foundation for understanding everything else

**If you understand this week deeply, everything else clicks.**

---

## Topics Covered

### Concepts

1. **Names and Objects** - Variables are names bound to objects, not boxes holding values
2. **Mutability** - Mutable vs immutable types and their implications
3. **Argument Passing** - Python passes object references (not values, not references)
4. **LEGB Scope** - How Python looks up names: Local → Enclosing → Global → Built-in
5. **`is` vs `==`** - Identity vs equality (and when it matters)
6. **Copying** - Shallow vs deep copy and common pitfalls

### Interview Focus

- "How does Python pass arguments to functions?"
- "What's the difference between `is` and `==`?"
- "Why does modifying a list inside a function affect it outside?"
- "Explain Python's scoping rules"
- "What happens when you do `a = b` with a list?"

---

## Folder Structure

- `concepts/` - Detailed explanations with runnable code
- `practice/` - Exercises to test your understanding
- `projects/` - Mini project applying these concepts

---

## Key Mental Models

### 1. Names are Labels, Not Boxes

```python
a = [1, 2, 3]  # 'a' is a label pointing to a list object
b = a          # 'b' is another label pointing to THE SAME object
b.append(4)    # Modifies the shared object
print(a)       # [1, 2, 3, 4] - 'a' sees the change!
```

### 2. Assignment Never Copies

```python
x = [1, 2, 3]
y = x          # y points to same object (no copy!)
y = [4, 5, 6]  # y now points to a NEW object
print(x)       # [1, 2, 3] - x unchanged (rebinding, not mutation)
```

### 3. Mutability Determines Behavior

```python
# Immutable (int) - "modification" creates new object
a = 5
b = a
b += 1         # Creates NEW int object, rebinds b
print(a)       # 5 (unchanged)

# Mutable (list) - modification changes object in place
a = [1, 2]
b = a
b.append(3)    # Modifies THE SAME object
print(a)       # [1, 2, 3] (changed!)
```

---

## Practice Goals

- [ ] Predict output of aliasing scenarios without running code
- [ ] Explain argument passing in your own words
- [ ] Draw memory diagrams for complex examples
- [ ] Identify when to use `copy()` vs `deepcopy()`
- [ ] Debug scope-related issues using LEGB rule
