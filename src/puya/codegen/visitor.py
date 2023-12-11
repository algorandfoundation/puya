from __future__ import annotations

import abc
import typing

if typing.TYPE_CHECKING:
    from puya.codegen import ops

_T = typing.TypeVar("_T")


class MIRVisitor(abc.ABC, typing.Generic[_T]):
    @abc.abstractmethod
    def visit_push_int(self, push: ops.PushInt) -> _T:
        ...

    @abc.abstractmethod
    def visit_push_bytes(self, push: ops.PushBytes) -> _T:
        ...

    @abc.abstractmethod
    def visit_comment(self, comment: ops.Comment) -> _T:
        ...

    @abc.abstractmethod
    def visit_store_l_stack(self, store: ops.StoreLStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_load_l_stack(self, load: ops.LoadLStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_store_x_stack(self, store: ops.StoreXStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_load_x_stack(self, load: ops.LoadXStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_store_f_stack(self, store: ops.StoreFStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_load_f_stack(self, load: ops.LoadFStack) -> _T:
        ...

    @abc.abstractmethod
    def visit_load_param(self, load: ops.LoadParam) -> _T:
        ...

    @abc.abstractmethod
    def visit_store_param(self, load: ops.StoreParam) -> _T:
        ...

    @abc.abstractmethod
    def visit_store_virtual(self, store: ops.StoreVirtual) -> _T:
        ...

    @abc.abstractmethod
    def visit_load_virtual(self, load: ops.LoadVirtual) -> _T:
        ...

    @abc.abstractmethod
    def visit_proto(self, proto: ops.Proto) -> _T:
        ...

    @abc.abstractmethod
    def visit_allocate(self, allocate: ops.Allocate) -> _T:
        ...

    @abc.abstractmethod
    def visit_pop(self, pop: ops.Pop) -> _T:
        ...

    @abc.abstractmethod
    def visit_callsub(self, callsub: ops.CallSub) -> _T:
        ...

    @abc.abstractmethod
    def visit_retsub(self, retsub: ops.RetSub) -> _T:
        ...

    @abc.abstractmethod
    def visit_intrinsic(self, intrinsic: ops.IntrinsicOp) -> _T:
        ...

    @abc.abstractmethod
    def visit_virtual_stack(self, nop: ops.VirtualStackOp) -> _T:
        ...

    @abc.abstractmethod
    def visit_push_address(self, addr: ops.PushAddress) -> _T:
        ...

    @abc.abstractmethod
    def visit_push_method(self, addr: ops.PushMethod) -> _T:
        ...
