"""
Easy String Problems
====================
Common interview questions involving strings.
"""

# ================================
# PROBLEM 1: Reverse a String
# ================================

def reverse_string(s: str) -> str:
    """Reverse a string."""
    return s[::-1]

# Test
assert reverse_string("hello") == "olleh"
assert reverse_string("Python") == "nohtyP"
print("✓ Problem 1: Reverse String")

# ================================
# PROBLEM 2: Check Palindrome
# ================================

def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome (ignore case and spaces)."""
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

# Test
assert is_palindrome("racecar") == True
assert is_palindrome("A man a plan a canal Panama") == True
assert is_palindrome("hello") == False
print("✓ Problem 2: Palindrome Check")

# ================================
# PROBLEM 3: Count Character Frequency
# ================================

def char_frequency(s: str) -> dict:
    """Count frequency of each character."""
    from collections import Counter
    return dict(Counter(s))

# Test
result = char_frequency("hello")
assert result['l'] == 2
assert result['h'] == 1
print("✓ Problem 3: Character Frequency")

# ================================
# PROBLEM 4: Find First Non-Repeating Character
# ================================

def first_non_repeating(s: str) -> str:
    """Find first character that appears only once."""
    from collections import Counter
    counts = Counter(s)
    for char in s:
        if counts[char] == 1:
            return char
    return ""

# Test
assert first_non_repeating("leetcode") == "l"
assert first_non_repeating("aabb") == ""
print("✓ Problem 4: First Non-Repeating")

# ================================
# PROBLEM 5: Valid Anagram
# ================================

def is_anagram(s1: str, s2: str) -> bool:
    """Check if two strings are anagrams."""
    from collections import Counter
    return Counter(s1) == Counter(s2)

# Test
assert is_anagram("listen", "silent") == True
assert is_anagram("hello", "world") == False
print("✓ Problem 5: Valid Anagram")

# ================================
# PROBLEM 6: Remove Duplicates
# ================================

def remove_duplicates(s: str) -> str:
    """Remove duplicate characters, keeping first occurrence."""
    seen = set()
    result = []
    for char in s:
        if char not in seen:
            seen.add(char)
            result.append(char)
    return ''.join(result)

# Test
assert remove_duplicates("programming") == "progamin"
print("✓ Problem 6: Remove Duplicates")

# ================================
# PROBLEM 7: Compress String
# ================================

def compress_string(s: str) -> str:
    """Compress string: 'aabbbcc' -> 'a2b3c2'."""
    if not s:
        return ""

    result = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1]:
            count += 1
        else:
            result.append(s[i-1] + str(count))
            count = 1
    result.append(s[-1] + str(count))

    compressed = ''.join(result)
    return compressed if len(compressed) < len(s) else s

# Test
assert compress_string("aabbbcc") == "a2b3c2"
assert compress_string("abc") == "abc"  # No compression needed
print("✓ Problem 7: Compress String")

print("\n✅ All easy string problems completed!")
