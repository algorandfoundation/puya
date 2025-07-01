from algopy import (
    ReferenceArray,
    Txn,
    UInt64,
    arc4,
    op,
    subroutine,
    uenumerate,
    urange,
)


class Contract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_array(self) -> None:
        arr = ReferenceArray[UInt64]()
        assert arr.length == 0

        arr.append(UInt64(42))
        assert arr.length == 1
        assert arr[-1] == 42

        add_x(arr, UInt64(5))
        assert arr.length == 6
        assert arr[-1] == 4

        pop_x(arr, x=UInt64(3), expected=UInt64(4))
        assert arr.length == 3
        assert arr[-1] == 1

        arr.append(UInt64(43))
        assert arr.length == 4
        assert arr[-1] == 43
        assert arr[0] == 42

        add_x(arr, UInt64(10))
        assert arr.length == 14
        assert arr[-1] == 9

        arr.append(UInt64(44))
        assert arr.length == 15
        assert arr[-1] == 44

        return_ref(arr, arr)[0] += 2
        assert arr.length == 17
        assert arr[0] == 44
        assert arr[-2] == 99
        assert arr[-1] == 100

    @arc4.abimethod()
    def test_array_extend(self) -> None:
        arr = ReferenceArray[UInt64]()
        add_x(arr, UInt64(1))
        arr2 = ReferenceArray[UInt64]()
        arr2.append(UInt64(1))
        arr2.append(UInt64(2))
        arr2.append(UInt64(3))

        arr.extend(arr2)
        assert arr.length == 4

    @arc4.abimethod()
    def test_array_multiple_append(self) -> None:
        arr = ReferenceArray[UInt64]()
        add_x(arr, UInt64(1))
        arr.append(UInt64(1))
        arr.append(UInt64(2))
        arr.append(UInt64(3))
        assert arr.length == 4

    @arc4.abimethod()
    def overhead(self) -> None:
        pass

    @arc4.abimethod()
    def test_array_too_long(self) -> None:
        array = ReferenceArray[UInt64]()
        for i in urange(512):
            array.append(i)
        assert array.length == 512, "array is expected length"

        array.append(UInt64(512))  # this will fail

    @arc4.abimethod()
    def test_array_copy_and_extend(self) -> None:
        array = ReferenceArray[UInt64]()
        for i in urange(5):
            array.append(i)
        array2 = array.copy()

        array.append(UInt64(5))
        assert array.length == 6
        assert array[-1] == 5, "expected 5"

        assert array2.length == 5
        assert array2[-1] == 4, "expected 4"

        array.extend(array2)
        assert array.length == 11
        assert array2.length == 5
        assert array[-1] == 4, "expected 4"
        assert array[4] == 4, "expected 4"
        assert array[5] == 5, "expected 4"
        assert array[6] == 0, "expected 4"

    @arc4.abimethod()
    def test_array_evaluation_order(self) -> None:
        arr = ReferenceArray[UInt64]()
        arr.append(UInt64(3))
        append_length_and_return(arr).extend(append_length_and_return(arr))
        assert arr.length == 6
        assert arr[0] == 3
        assert arr[1] == 1
        assert arr[2] == 2
        assert arr[3] == 3
        assert arr[4] == 1
        assert arr[5] == 2

        arr[append_length_and_return(arr)[0]] = append_length_and_return(arr)[-1]
        assert arr.length == 8
        assert arr[6] == 6
        assert arr[7] == 7
        assert arr[3] == 6

    @arc4.abimethod()
    def test_array_assignment_maximum_cursage(self) -> None:
        arr = ReferenceArray[UInt64]()
        arr.append(UInt64(3))
        append_length_and_return(arr)[0] = UInt64(42)
        assert arr.length == 2
        assert arr[0] == 42
        assert arr[1] == 1

    @arc4.abimethod()
    def test_allocations(self, num: UInt64) -> None:
        for _i in urange(num):
            alloc_test = ReferenceArray[UInt64]()
            add_x(alloc_test, UInt64(1))

    @arc4.abimethod()
    def test_iteration(self) -> None:
        arr = ReferenceArray[UInt64]()
        for val in urange(5):
            arr.append(val)
        assert arr.length == 5, "expected array of length 5"

        # iterate
        last = UInt64(0)
        for value in arr:
            assert value >= last, "array is not sorted"
            last = value

        # enumerate
        for idx, value in uenumerate(arr):
            assert value == idx, "incorrect array value"

        # reverse
        for value in reversed(arr):
            assert value <= last, "array is not sorted"
            last = value

        arc4_arr = arc4.DynamicArray[arc4.UInt64]()
        native_arr = ReferenceArray[arc4.UInt64]()
        for i in urange(5):
            arc4_arr.append(arc4.UInt64(i))
            native_arr.append(arc4.UInt64(i))
        combined_arr = arc4_arr + native_arr
        assert combined_arr.length == 10
        assert combined_arr[0] == 0
        assert combined_arr[4] == 4
        assert combined_arr[5] == 0
        assert combined_arr[9] == 4

    @arc4.abimethod()
    def test_quicksort(self) -> None:
        # create pseudo random array from sender address
        rnd = ReferenceArray[UInt64]()
        for b in Txn.sender.bytes:
            rnd.append(op.btoi(b))
        assert rnd.length == 32, "expected array of length 32"

        # sort the array
        quicksort_window(rnd, UInt64(0), rnd.length - 1)

        # array should now be in ascending order
        last = UInt64(0)
        for value in rnd:
            assert value >= last, "array is not sorted"
            last = value

    @arc4.abimethod()
    def test_unobserved_write(self) -> None:
        arr = create_array()
        last = arr.length - 1
        arr[last] = UInt64(0)  # write
        assert_last_is_zero(arr)
        arr[last] = UInt64(1)  # write
        assert arr[last] == 1


@subroutine
def quicksort_window(
    arr: ReferenceArray[UInt64], window_left: UInt64, window_right: UInt64
) -> None:
    left = window_left
    right = window_right
    pivot = arr[(window_left + window_right) // 2]
    # partition window around pivot, so everything to the left is less
    # and everything to the right is more or equal
    while True:
        # move left of window towards pivot
        while arr[left] < pivot:
            left += 1
        # move right of window towards pivot
        while pivot < arr[right]:
            # break out of loop if right would go negative
            if not right:
                break
            right -= 1
        else:  # only runs if right is not "negative"
            # if window isn't empty then swap values and move window in
            if left < right:
                arr[left], arr[right] = arr[right], arr[left]
                left += 1
                # break out of loop if right would go negative
                if not right:
                    break
                right -= 1
                # explicit continue to avoid hitting outer break
                if left <= right:
                    continue
                # loop always ends in this scenario
                # and an explict break consumes fewer ops
                break
            # if window is just one item, don't bother swapping, but still adjust window
            if left == right:
                left += 1
                # don't decrement right if it would go negative
                if right:
                    right -= 1
                # loop always ends in this scenario
                # and an explict break consumes fewer ops
                break
        # a negative right will end up here
        break

    # sort left half of window
    if window_left < right:
        quicksort_window(arr, window_left, right)
    # sort right half of window
    if left < window_right:
        quicksort_window(arr, left, window_right)


@subroutine(inline=False)
def create_array() -> ReferenceArray[UInt64]:
    arr = ReferenceArray[UInt64]()
    for i in urange(5):
        arr.append(i)
    return arr


@subroutine(inline=False)
def assert_last_is_zero(arr: ReferenceArray[UInt64]) -> None:
    assert arr[arr.length - 1] == 0


@subroutine
def return_ref(
    arr: ReferenceArray[UInt64], arr2: ReferenceArray[UInt64]
) -> ReferenceArray[UInt64]:
    arr.append(UInt64(99))
    arr2.append(UInt64(100))
    return arr


@subroutine
def add_x(arr: ReferenceArray[UInt64], x: UInt64) -> None:
    for i in urange(x):
        arr.append(i)


@subroutine
def pop_x(arr: ReferenceArray[UInt64], x: UInt64, expected: UInt64) -> None:
    for _i in urange(x):
        popped = arr.pop()
        assert popped == expected
        expected -= 1


@subroutine
def append_length_and_return(arr: ReferenceArray[UInt64]) -> ReferenceArray[UInt64]:
    arr.append(arr.length)
    return arr


@subroutine
def do_something_with_array(arr: ReferenceArray[UInt64]) -> None:
    arr.append(UInt64(1))
