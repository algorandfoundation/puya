from algopy import Array, UInt64, arc4, subroutine, urange


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


@subroutine
def add_x(arr: Array[UInt64], x: UInt64) -> None:
    for i in urange(x):
        arr.append(i)


@subroutine
def pop_x(arr: Array[UInt64], x: UInt64) -> None:
    for _i in urange(x):
        arr.pop()
