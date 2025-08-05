# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CheckCompiledSig(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def check_sig_with_logic_sig_only_op_compiles(
        self,
    ) -> None: ...
