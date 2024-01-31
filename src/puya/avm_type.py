import enum


@enum.unique
class AVMType(enum.Flag):
    bytes = enum.auto()
    uint64 = enum.auto()
    any = bytes | uint64
