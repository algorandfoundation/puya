from __future__ import annotations

import abc
import typing

if typing.TYPE_CHECKING:
    from puya.ussemble import models

T = typing.TypeVar("T")


class AVMVisitor(typing.Generic[T]):
    @abc.abstractmethod
    def visit_int_block(self, block: models.IntBlock) -> T: ...

    @abc.abstractmethod
    def visit_bytes_block(self, block: models.BytesBlock) -> T: ...

    @abc.abstractmethod
    def visit_intc(self, load: models.IntC) -> T: ...

    @abc.abstractmethod
    def visit_bytesc(self, load: models.BytesC) -> T: ...

    @abc.abstractmethod
    def visit_push_int(self, load: models.PushInt) -> T: ...

    @abc.abstractmethod
    def visit_push_ints(self, load: models.PushInts) -> T: ...

    @abc.abstractmethod
    def visit_push_bytes(self, load: models.PushBytes) -> T: ...

    @abc.abstractmethod
    def visit_push_bytess(self, load: models.PushBytess) -> T: ...

    @abc.abstractmethod
    def visit_jump(self, jump: models.Jump) -> T: ...

    @abc.abstractmethod
    def visit_multi_jump(self, jump: models.MultiJump) -> T: ...

    @abc.abstractmethod
    def visit_label(self, jump: models.Label) -> T: ...

    @abc.abstractmethod
    def visit_intrinsic(self, intrinsic: models.Intrinsic) -> T: ...
