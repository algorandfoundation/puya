# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Jira241(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def oh_no(
        self,
        wrong_size: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod
    def oh_yes(
        self,
        wrong_size: algopy.arc4.Bool,
    ) -> None: ...
