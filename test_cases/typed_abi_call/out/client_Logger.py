# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Logger(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def echo(
        self,
        value: puyapy.arc4.String,
    ) -> puyapy.arc4.String:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_uint64(
        self,
        value: puyapy.arc4.UInt64,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_uint512(
        self,
        value: puyapy.arc4.UInt512,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_string(
        self,
        value: puyapy.arc4.String,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_bool(
        self,
        value: puyapy.arc4.Bool,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_bytes(
        self,
        value: puyapy.arc4.DynamicBytes,
    ) -> None:
        raise NotImplementedError
