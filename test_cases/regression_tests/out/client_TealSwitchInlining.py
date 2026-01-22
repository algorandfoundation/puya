# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TealSwitchInlining(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Test for an issue introduced by TEAL block optimizations,
        whereby a target that is referenced multiple times by the same source block
        might be incorrectly inlined, when it should remain a labelled destination.
    
    """
    pass
