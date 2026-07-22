# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_new_ops(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_poseidon2(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_app_params(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_app_box_ops(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_block(
        self,
    ) -> None: ...
