import enum


@enum.unique
class AVMType(enum.Flag):
    bytes = enum.auto()  # noqa: A003
    uint64 = enum.auto()
    any = bytes | uint64  # noqa: A003
