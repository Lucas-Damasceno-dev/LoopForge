"""
Conjunto curado de 10 problemas de benchmark com test suites para o LoopForge ELO Rating System.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkProblem:
    id: str
    title: str
    stack: str
    idea: str
    difficulty: str  # easy, medium, hard
    baseline_elo: float = 1200.0
    user_stories: list[dict] = field(default_factory=list)


CURATED_BENCHMARK_PROBLEMS: list[BenchmarkProblem] = [
    BenchmarkProblem(
        id="P-001",
        title="Two Sum & Array Manipulation",
        stack="python",
        idea="Implement a function two_sum(nums: list[int], target: int) -> list[int] that finds indices of two numbers adding to target.",
        difficulty="easy",
        user_stories=[{"id": "US-001", "title": "Two Sum Algorithm", "description": "Find pairs of numbers that match target sum."}],
    ),
    BenchmarkProblem(
        id="P-002",
        title="String Anagram & Palindrome Validator",
        stack="javascript",
        idea="Implement isAnagram(str1, str2) and isPalindrome(str) functions in Node.js.",
        difficulty="easy",
        user_stories=[{"id": "US-002", "title": "String Processing", "description": "Validate anagrams and palindromes."}],
    ),
    BenchmarkProblem(
        id="P-003",
        title="Bounded Stack & Queue Buffer",
        stack="java",
        idea="Implement a thread-safe BoundedBuffer<T> class in Java supporting push and pop operations with capacity limit.",
        difficulty="medium",
        user_stories=[{"id": "US-003", "title": "Bounded Buffer", "description": "Java concurrency buffer."}],
    ),
    BenchmarkProblem(
        id="P-004",
        title="Binary Search & Upper Bound",
        stack="go",
        idea="Implement BinarySearch(arr []int, target int) int and UpperBound(arr []int, target int) int in Go.",
        difficulty="medium",
        user_stories=[{"id": "US-004", "title": "Binary Search", "description": "Fast log(N) array search."}],
    ),
    BenchmarkProblem(
        id="P-005",
        title="LRU Cache Memory Store",
        stack="rust",
        idea="Implement an LRUCache struct in Rust with get(key) and put(key, val) with capacity eviction.",
        difficulty="hard",
        user_stories=[{"id": "US-005", "title": "LRU Cache", "description": "O(1) cache memory manager."}],
    ),
    BenchmarkProblem(
        id="P-006",
        title="HTTP REST Data Validator",
        stack="python",
        idea="Implement a data validation module for email, URL, and phone number sanitization in Python.",
        difficulty="medium",
        user_stories=[{"id": "US-006", "title": "Data Sanitizer", "description": "Validate REST payload fields."}],
    ),
    BenchmarkProblem(
        id="P-007",
        title="JWT Token Decoder & Expiration Check",
        stack="javascript",
        idea="Implement decodeJWT(token) and isTokenExpired(token) utility in Node.js without external dependencies.",
        difficulty="medium",
        user_stories=[{"id": "US-007", "title": "JWT Utility", "description": "Parse JWT payload and check exp claim."}],
    ),
    BenchmarkProblem(
        id="P-008",
        title="Matrix Rotation & Transpose",
        stack="java",
        idea="Implement rotateMatrix(int[][] matrix) to rotate an N x N matrix 90 degrees clockwise in Java.",
        difficulty="medium",
        user_stories=[{"id": "US-008", "title": "Matrix Transpose", "description": "In-place matrix rotation."}],
    ),
    BenchmarkProblem(
        id="P-009",
        title="Concurrent Worker Pool Engine",
        stack="go",
        idea="Implement a WorkerPool in Go with N worker routines processing job channels and gathering results.",
        difficulty="hard",
        user_stories=[{"id": "US-009", "title": "Go Worker Pool", "description": "Process jobs concurrently with channels."}],
    ),
    BenchmarkProblem(
        id="P-010",
        title="Circular Memory Buffer",
        stack="rust",
        idea="Implement a CircularBuffer<T> in Rust supporting push, pop, and clear operations.",
        difficulty="hard",
        user_stories=[{"id": "US-010", "title": "Circular Buffer", "description": "Ring buffer in Rust."}],
    ),
]
