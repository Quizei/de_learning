"""
Easy List/Array Problems
========================
Common interview questions involving lists.
"""

from typing import List

# ================================
# PROBLEM 1: Two Sum
# ================================

def two_sum(nums: List[int], target: int) -> List[int]:
    """Find indices of two numbers that add up to target."""
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Test
assert two_sum([2, 7, 11, 15], 9) == [0, 1]
assert two_sum([3, 2, 4], 6) == [1, 2]
print("✓ Problem 1: Two Sum")

# ================================
# PROBLEM 2: Find Maximum
# ================================

def find_max(nums: List[int]) -> int:
    """Find maximum without using built-in max()."""
    if not nums:
        raise ValueError("Empty list")
    maximum = nums[0]
    for num in nums[1:]:
        if num > maximum:
            maximum = num
    return maximum

# Test
assert find_max([3, 1, 4, 1, 5, 9, 2, 6]) == 9
print("✓ Problem 2: Find Maximum")

# ================================
# PROBLEM 3: Remove Duplicates from Sorted Array
# ================================

def remove_duplicates_sorted(nums: List[int]) -> int:
    """Remove duplicates in-place, return new length."""
    if not nums:
        return 0

    write_idx = 1
    for i in range(1, len(nums)):
        if nums[i] != nums[i-1]:
            nums[write_idx] = nums[i]
            write_idx += 1
    return write_idx

# Test
nums = [1, 1, 2, 2, 3]
length = remove_duplicates_sorted(nums)
assert length == 3
assert nums[:length] == [1, 2, 3]
print("✓ Problem 3: Remove Duplicates")

# ================================
# PROBLEM 4: Rotate Array
# ================================

def rotate_array(nums: List[int], k: int) -> None:
    """Rotate array to the right by k steps (in-place)."""
    k = k % len(nums)
    nums.reverse()
    nums[:k] = reversed(nums[:k])
    nums[k:] = reversed(nums[k:])

# Test
nums = [1, 2, 3, 4, 5]
rotate_array(nums, 2)
assert nums == [4, 5, 1, 2, 3]
print("✓ Problem 4: Rotate Array")

# ================================
# PROBLEM 5: Merge Sorted Lists
# ================================

def merge_sorted(list1: List[int], list2: List[int]) -> List[int]:
    """Merge two sorted lists into one sorted list."""
    result = []
    i = j = 0

    while i < len(list1) and j < len(list2):
        if list1[i] <= list2[j]:
            result.append(list1[i])
            i += 1
        else:
            result.append(list2[j])
            j += 1

    result.extend(list1[i:])
    result.extend(list2[j:])
    return result

# Test
assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]
print("✓ Problem 5: Merge Sorted Lists")

# ================================
# PROBLEM 6: Find Missing Number
# ================================

def missing_number(nums: List[int]) -> int:
    """Find missing number in range [0, n]."""
    n = len(nums)
    expected_sum = n * (n + 1) // 2
    actual_sum = sum(nums)
    return expected_sum - actual_sum

# Test
assert missing_number([3, 0, 1]) == 2
assert missing_number([0, 1]) == 2
print("✓ Problem 6: Missing Number")

# ================================
# PROBLEM 7: Move Zeros
# ================================

def move_zeros(nums: List[int]) -> None:
    """Move all zeros to end, maintaining order of non-zeros."""
    write_idx = 0
    for num in nums:
        if num != 0:
            nums[write_idx] = num
            write_idx += 1

    for i in range(write_idx, len(nums)):
        nums[i] = 0

# Test
nums = [0, 1, 0, 3, 12]
move_zeros(nums)
assert nums == [1, 3, 12, 0, 0]
print("✓ Problem 7: Move Zeros")

print("\n✅ All easy list problems completed!")
