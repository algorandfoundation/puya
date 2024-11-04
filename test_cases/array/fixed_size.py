import typing

from algopy import Array, UInt64, arc4, op, subroutine, urange


class Point(typing.NamedTuple):
    x: arc4.UInt64
    y: UInt64


class FixedSizeContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_array(self, x1: arc4.UInt64, y1: UInt64, x2: arc4.UInt64, y2: UInt64) -> UInt64:
        path = Array[Point]()
        assert path.length == 0

        path.append(Point(x=arc4.UInt64(), y=UInt64()))
        path.append(Point(x=x1, y=y1))
        path.append(Point(x=x2, y=y2))

        return path_length(path)


@subroutine
def path_length(path: Array[Point]) -> UInt64:
    last_point = path[0]
    length = UInt64()
    for point_idx in urange(1, path.length):
        point = path[point_idx]
        if point.x < last_point.x:
            dx = last_point.x.native - point.x.native
        else:
            dx = point.x.native - last_point.x.native
        if point.y < last_point.y:
            dy = last_point.y - point.y
        else:
            dy = point.y - last_point.y
        length += op.sqrt(dx * dx + dy * dy)
    return length
