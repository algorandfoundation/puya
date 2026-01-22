# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class LargeBigUInt(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Regression test: compiler crashes with AssertionError when BigUInt
        constants exceed 64 bytes (e.g. 2**512).
    """
    pass
