from __future__ import annotations

import abc
import typing

if typing.TYPE_CHECKING:
    from puya.mir import models

_T = typing.TypeVar("_T")


class MIRVisitor(abc.ABC, typing.Generic[_T]):
    @abc.abstractmethod
    def visit_int(self, push: models.Int) -> _T: ...

    @abc.abstractmethod
    def visit_byte(self, push: models.Byte) -> _T: ...

    @abc.abstractmethod
    def visit_comment(self, comment: models.Comment) -> _T: ...

    @abc.abstractmethod
    def visit_store_l_stack(self, store: models.StoreLStack) -> _T: ...

    @abc.abstractmethod
    def visit_load_l_stack(self, load: models.LoadLStack) -> _T: ...

    @abc.abstractmethod
    def visit_store_x_stack(self, store: models.StoreXStack) -> _T: ...

    @abc.abstractmethod
    def visit_load_x_stack(self, load: models.LoadXStack) -> _T: ...

    @abc.abstractmethod
    def visit_store_f_stack(self, store: models.StoreFStack) -> _T: ...

    @abc.abstractmethod
    def visit_load_f_stack(self, load: models.LoadFStack) -> _T: ...

    @abc.abstractmethod
    def visit_load_param(self, load: models.LoadParam) -> _T: ...

    @abc.abstractmethod
    def visit_store_param(self, load: models.StoreParam) -> _T: ...

    @abc.abstractmethod
    def visit_store_virtual(self, store: models.StoreVirtual) -> _T: ...

    @abc.abstractmethod
    def visit_load_virtual(self, load: models.LoadVirtual) -> _T: ...

    @abc.abstractmethod
    def visit_proto(self, proto: models.Proto) -> _T: ...

    @abc.abstractmethod
    def visit_allocate(self, allocate: models.Allocate) -> _T: ...

    @abc.abstractmethod
    def visit_pop(self, pop: models.Pop) -> _T: ...

    @abc.abstractmethod
    def visit_callsub(self, callsub: models.CallSub) -> _T: ...

    @abc.abstractmethod
    def visit_retsub(self, retsub: models.RetSub) -> _T: ...

    @abc.abstractmethod
    def visit_intrinsic(self, intrinsic: models.IntrinsicOp) -> _T: ...

    @abc.abstractmethod
    def visit_virtual_stack(self, nop: models.VirtualStackOp) -> _T: ...

    @abc.abstractmethod
    def visit_address(self, addr: models.Address) -> _T: ...

    @abc.abstractmethod
    def visit_method(self, method: models.Method) -> _T: ...

    @abc.abstractmethod
    def visit_template_var(self, deploy_var: models.TemplateVar) -> _T: ...
