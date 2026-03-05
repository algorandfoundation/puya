"""Example 07: Array Playground

This example demonstrates native arrays, FixedArray, ImmutableArray, ReferenceArray,
and iteration patterns.

Features:
- Array[T] — dynamic, mutable, stack-based with .append(), .pop(), .length
- ReferenceArray[T] — dynamic, mutable, scratch-based with .extend(), .copy(), .freeze()
- ImmutableArray[T] — dynamic, immutable, functional style (append/pop return new array)
- FixedArray[T, N] — fixed-length array with .full(), .replace(), iteration
- freeze() — convert ReferenceArray to ImmutableArray
- urange() — uint64 range iterator (1, 2, and 3 argument forms)
- for...in iteration over all array types

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

import typing

from algopy import Array, FixedArray, ImmutableArray, ReferenceArray, UInt64, arc4, urange


class ArrayPlayground(arc4.ARC4Contract):
    """ABI-routed contract showcasing Array, ReferenceArray, ImmutableArray, FixedArray, freeze, and urange."""
    @arc4.abimethod(create="require")
    def create(self) -> None:
        pass

    # --- Array (dynamic, mutable, stack-based) ---

    @arc4.abimethod
    def test_array(self) -> tuple[UInt64, UInt64, UInt64]:
        """Demonstrate Array[T] — append, pop, setitem, urange building, for...in iteration.

        Returns:
            Tuple of (length_after_build, popped_value, sum_after_mutation)
        """
        arr = Array[UInt64]()

        # Build using urange
        for i in urange(5):
            arr.append(i * 10)  # 0, 10, 20, 30, 40

        length_after = arr.length  # 5

        # Pop last
        popped = arr.pop()  # 40

        # Setitem
        arr[0] = UInt64(99)

        # Sum via iteration
        total = UInt64(0)
        for val in arr:
            total += val  # 99 + 10 + 20 + 30 = 159

        return length_after, popped, total

    # --- ReferenceArray (dynamic, mutable, scratch-based, reference semantics) ---

    @arc4.abimethod
    def test_reference_array(self) -> tuple[UInt64, UInt64, UInt64]:
        """Demonstrate ReferenceArray[T] — dynamic sizing with append, extend, pop, copy.

        Returns:
            Tuple of (length_after_extend, sum_of_all, copy_length)
        """
        arr = ReferenceArray[UInt64]()

        for i in urange(3):
            arr.append(i + 1)  # 1, 2, 3

        arr2 = ReferenceArray[UInt64]()
        arr2.append(UInt64(4))
        arr2.append(UInt64(5))

        arr.extend(arr2)  # 1, 2, 3, 4, 5
        length_after_extend = arr.length  # 5

        # Copy is independent
        arr3 = arr.copy()
        assert arr3.pop() == 5

        # Sum via iteration
        total = UInt64(0)
        for val in arr:
            total += val  # 1+2+3+4+5 = 15

        return length_after_extend, total, arr3.length

    # --- ImmutableArray (dynamic, immutable, functional style) ---

    @arc4.abimethod
    def test_immutable_array(self) -> tuple[UInt64, UInt64, UInt64]:
        """Demonstrate ImmutableArray[T] — functional style where append/pop return new arrays.

        Returns:
            Tuple of (length_after_build, replaced_value, length_after_pop)
        """
        arr = ImmutableArray[UInt64]()

        # append returns new array — must reassign
        for i in urange(4):
            arr = arr.append(i * 5)  # 0, 5, 10, 15

        length = arr.length  # 4

        # Replace at index
        arr = arr.replace(1, UInt64(99))  # 0, 99, 10, 15
        replaced_val = arr[1]  # 99

        # Pop returns new array (without last element)
        arr = arr.pop()  # 0, 99, 10

        return length, replaced_val, arr.length

    # --- FixedArray (fixed size, mutable) ---

    @arc4.abimethod
    def test_fixed_array(self) -> tuple[UInt64, UInt64, UInt64]:
        """Demonstrate FixedArray[T, N] — fixed-length construction with full(), indexing, iteration.

        Returns:
            Tuple of (length, sum_of_elements, replaced_first_element)
        """
        arr = FixedArray[UInt64, typing.Literal[4]].full(UInt64(0))

        # Set values using urange
        for i in urange(4):
            arr[i] = i * 3  # 0, 3, 6, 9

        # Sum via iteration
        total = UInt64(0)
        for val in arr:
            total += val  # 0+3+6+9 = 18

        # replace returns new copy
        arr2 = arr.replace(0, UInt64(100))  # 100, 3, 6, 9

        return arr.length, total, arr2[0]

    # --- Freeze: convert mutable to immutable ---

    @arc4.abimethod
    def test_freeze(self) -> tuple[UInt64, UInt64]:
        """Demonstrate freeze() — convert mutable ReferenceArray to ImmutableArray.

        Returns:
            Tuple of (frozen_length, sum_of_frozen_elements)
        """
        arr = ReferenceArray[UInt64]()
        for i in urange(5):
            arr.append(i + 1)  # 1, 2, 3, 4, 5

        frozen = arr.freeze()

        total = UInt64(0)
        for val in frozen:
            total += val  # 15

        return frozen.length, total

    # --- urange sum ---

    @arc4.abimethod
    def test_urange_sum(self, n: UInt64) -> UInt64:
        """Demonstrate urange() — sum 1..n using urange(start, stop).

        Args:
            n: upper bound (inclusive)

        Returns:
            Sum of 1 through n
        """
        total = UInt64(0)
        for i in urange(1, n + 1):
            total += i
        return total
