from algopy import Array, Txn, UInt64, arc4, op, subroutine, urange


class Contract(arc4.ARC4Contract):

    @arc4.abimethod()
    def test_array(self) -> None:
        arr = Array[UInt64]()
        assert arr.length == 0
        # TODO: ummm memory leaks?
        # assert arr == Array[UInt64]()

        arr.append(UInt64(42))
        assert arr.length == 1
        assert arr[-1] == 42

        add_x(arr, UInt64(5))
        assert arr.length == 6
        assert arr[-1] == 4

        arr.append(UInt64(43))
        assert arr.length == 7
        assert arr[-1] == 43
        assert arr[0] == 42

        pop_x(arr, UInt64(3))
        assert arr.length == 4
        assert arr[-1] == 2

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
    def overhead(self) -> None:
        pass

    @arc4.abimethod()
    def test_array_too_long(self) -> None:
        array = Array[UInt64]()
        for i in urange(512):
            array.append(i)
        assert array.length == 512, "array is expected length"
        assert array.bytes.length == 4096, "array bytes is expected length"

        array.append(UInt64(512))  # this will fail

    @arc4.abimethod()
    def test_quicksort(self) -> None:
        # create pseudo random array from sender address
        rnd = Array[UInt64]()
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


@subroutine
def quicksort_window(arr: Array[UInt64], window_left: UInt64, window_right: UInt64) -> None:
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


@subroutine
def return_ref(arr: Array[UInt64], arr2: Array[UInt64]) -> Array[UInt64]:
    arr.append(UInt64(99))
    arr2.append(UInt64(100))
    return arr


@subroutine
def add_x(arr: Array[UInt64], x: UInt64) -> None:
    for i in urange(x):
        arr.append(i)


@subroutine
def pop_x(arr: Array[UInt64], x: UInt64) -> None:
    for _i in urange(x):
        arr.pop()
