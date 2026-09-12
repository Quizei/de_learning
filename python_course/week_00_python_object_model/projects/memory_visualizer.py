"""
Week 0 Project: Python Memory Visualizer
=========================================
A tool to visualize how Python objects work in memory.
Demonstrates all Week 0 concepts in action.
"""

from typing import Any, Dict, List, Set
import copy

class MemoryVisualizer:
    """Visualize Python object relationships."""

    def __init__(self):
        self.tracked: Dict[str, Any] = {}
        self.history: List[str] = []

    def track(self, name: str, obj: Any) -> None:
        """Track an object with a given name."""
        self.tracked[name] = obj
        self._log(f"TRACK: {name} -> {self._obj_info(obj)}")

    def show_all(self) -> None:
        """Show all tracked objects and their relationships."""
        print("\n" + "=" * 60)
        print("MEMORY STATE")
        print("=" * 60)

        # Group by object id to show aliasing
        id_to_names: Dict[int, List[str]] = {}
        for name, obj in self.tracked.items():
            obj_id = id(obj)
            if obj_id not in id_to_names:
                id_to_names[obj_id] = []
            id_to_names[obj_id].append(name)

        for obj_id, names in id_to_names.items():
            obj = self.tracked[names[0]]
            print(f"\nObject at {hex(obj_id)}:")
            print(f"  Type:  {type(obj).__name__}")
            print(f"  Value: {repr(obj)}")
            print(f"  Names: {', '.join(names)}")

            if len(names) > 1:
                print(f"  ⚠️  ALIASED! {len(names)} names point to same object")

            # Check mutability
            if self._is_mutable(obj):
                print(f"  📝 Mutable - changes will affect all aliases")
            else:
                print(f"  🔒 Immutable - safe to share")

    def compare(self, name1: str, name2: str) -> None:
        """Compare two tracked objects."""
        if name1 not in self.tracked or name2 not in self.tracked:
            print("Error: Both names must be tracked")
            return

        obj1 = self.tracked[name1]
        obj2 = self.tracked[name2]

        print(f"\n--- Comparing {name1} and {name2} ---")
        print(f"{name1}: {repr(obj1)} (id: {id(obj1)})")
        print(f"{name2}: {repr(obj2)} (id: {id(obj2)})")
        print(f"  {name1} == {name2}: {obj1 == obj2} (equality)")
        print(f"  {name1} is {name2}: {obj1 is obj2} (identity)")

    def demo_assignment(self) -> None:
        """Demonstrate assignment behavior."""
        print("\n" + "=" * 60)
        print("DEMO: Assignment Creates Aliases")
        print("=" * 60)

        original = [1, 2, 3]
        alias = original

        print(f"\noriginal = [1, 2, 3]")
        print(f"alias = original")
        print(f"\n  original: {original} (id: {id(original)})")
        print(f"  alias:    {alias} (id: {id(alias)})")
        print(f"  Same object: {original is alias}")

        print(f"\nNow: alias.append(4)")
        alias.append(4)
        print(f"  original: {original}")
        print(f"  alias:    {alias}")
        print("  ⚠️  Both changed because they're the same object!")

    def demo_mutation_vs_rebinding(self) -> None:
        """Demonstrate mutation vs rebinding."""
        print("\n" + "=" * 60)
        print("DEMO: Mutation vs Rebinding")
        print("=" * 60)

        # Mutation
        print("\n--- Mutation (modifies object) ---")
        a = [1, 2, 3]
        b = a
        print(f"a = [1, 2, 3]; b = a")
        print(f"a.append(4)  # Mutation")
        a.append(4)
        print(f"a: {a}")
        print(f"b: {b}  # b is affected!")

        # Rebinding
        print("\n--- Rebinding (changes what name points to) ---")
        a = [1, 2, 3]
        b = a
        print(f"a = [1, 2, 3]; b = a")
        print(f"a = [4, 5, 6]  # Rebinding")
        a = [4, 5, 6]
        print(f"a: {a}")
        print(f"b: {b}  # b is NOT affected!")

    def demo_function_args(self) -> None:
        """Demonstrate function argument passing."""
        print("\n" + "=" * 60)
        print("DEMO: Function Argument Passing")
        print("=" * 60)

        def mutate(lst):
            lst.append(99)
            print(f"  Inside function (after append): {lst}")

        def rebind(lst):
            lst = [99, 100]
            print(f"  Inside function (after rebind): {lst}")

        print("\n--- Function that mutates ---")
        my_list = [1, 2, 3]
        print(f"Before: {my_list}")
        mutate(my_list)
        print(f"After:  {my_list}  # Changed!")

        print("\n--- Function that rebinds ---")
        my_list = [1, 2, 3]
        print(f"Before: {my_list}")
        rebind(my_list)
        print(f"After:  {my_list}  # Unchanged!")

    def demo_copying(self) -> None:
        """Demonstrate shallow vs deep copy."""
        print("\n" + "=" * 60)
        print("DEMO: Shallow vs Deep Copy")
        print("=" * 60)

        original = [[1, 2], [3, 4]]
        shallow = original.copy()
        deep = copy.deepcopy(original)

        print(f"\noriginal = [[1, 2], [3, 4]]")
        print(f"shallow = original.copy()")
        print(f"deep = copy.deepcopy(original)")

        print(f"\noriginal[0] is shallow[0]: {original[0] is shallow[0]}  # SAME inner list")
        print(f"original[0] is deep[0]:    {original[0] is deep[0]}  # DIFFERENT inner list")

        print(f"\nNow: original[0].append(99)")
        original[0].append(99)
        print(f"original: {original}")
        print(f"shallow:  {shallow}  # Affected!")
        print(f"deep:     {deep}  # Not affected!")

    def demo_scope(self) -> None:
        """Demonstrate LEGB scope."""
        print("\n" + "=" * 60)
        print("DEMO: LEGB Scope")
        print("=" * 60)

        x = "global"

        def outer():
            x = "enclosing"

            def inner():
                x = "local"
                print(f"  Local scope:     x = {x}")

            inner()
            print(f"  Enclosing scope: x = {x}")

        outer()
        print(f"  Global scope:    x = {x}")

    def run_all_demos(self) -> None:
        """Run all demonstrations."""
        self.demo_assignment()
        self.demo_mutation_vs_rebinding()
        self.demo_function_args()
        self.demo_copying()
        self.demo_scope()

        print("\n" + "=" * 60)
        print("KEY TAKEAWAYS")
        print("=" * 60)
        print("""
1. Variables are names (labels), not boxes
2. Assignment binds a name to an object, never copies
3. Multiple names can point to the same object (aliasing)
4. Mutation changes the object; rebinding changes what name points to
5. Function parameters are new names for the same objects
6. Shallow copy shares nested objects; deep copy is independent
7. LEGB: Python looks up names in Local → Enclosing → Global → Built-in
8. 'is' checks identity; '==' checks equality
""")

    def _obj_info(self, obj: Any) -> str:
        return f"{type(obj).__name__}({repr(obj)}) at {hex(id(obj))}"

    def _is_mutable(self, obj: Any) -> bool:
        return isinstance(obj, (list, dict, set, bytearray))

    def _log(self, message: str) -> None:
        self.history.append(message)
        print(message)


def main():
    print("=" * 60)
    print("PYTHON MEMORY VISUALIZER")
    print("Understanding Python's Object Model")
    print("=" * 60)

    viz = MemoryVisualizer()
    viz.run_all_demos()


if __name__ == "__main__":
    main()
