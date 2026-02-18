# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class LoggedErrorsContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_logged_errs(
        self,
        arg: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
