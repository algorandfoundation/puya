# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BigUIntConstDivZero(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Regression test: compiler crashes with ZeroDivisionError when
        attempting to constant-fold a BigUInt floor division by zero.
    """
    pass
