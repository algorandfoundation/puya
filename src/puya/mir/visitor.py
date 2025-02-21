from __future__ import annotations

import abc
import typing

if typing.TYPE_CHECKING:
    from puya.mir import models


class MIRVisitor[T](abc.ABC):
    @abc.abstractmethod
    def visit_int(self, push: models.Int) -> T: ...

    @abc.abstractmethod
    def visit_byte(self, push: models.Byte) -> T: ...

    @abc.abstractmethod
    def visit_undefined(self, push: models.Undefined) -> T: ...

    @abc.abstractmethod
    def visit_comment(self, comment: models.Comment) -> T: ...

    @abc.abstractmethod
    def visit_store_l_stack(self, store: models.StoreLStack) -> T: ...

    @abc.abstractmethod
    def visit_load_l_stack(self, load: models.LoadLStack) -> T: ...

    @abc.abstractmethod
    def visit_store_x_stack(self, store: models.StoreXStack) -> T: ...

    @abc.abstractmethod
    def visit_load_x_stack(self, load: models.LoadXStack) -> T: ...

    @abc.abstractmethod
    def visit_store_f_stack(self, store: models.StoreFStack) -> T: ...

    @abc.abstractmethod
    def visit_load_f_stack(self, load: models.LoadFStack) -> T: ...

    @abc.abstractmethod
    def visit_load_param(self, load: models.LoadParam) -> T: ...

    @abc.abstractmethod
    def visit_store_param(self, load: models.StoreParam) -> T: ...

    @abc.abstractmethod
    def visit_abstract_store(self, store: models.AbstractStore) -> T: ...

    @abc.abstractmethod
    def visit_abstract_load(self, load: models.AbstractLoad) -> T: ...

    @abc.abstractmethod
    def visit_pop(self, pop: models.Pop) -> T: ...

    @abc.abstractmethod
    def visit_callsub(self, callsub: models.CallSub) -> T: ...

    @abc.abstractmethod
    def visit_intrinsic(self, intrinsic: models.IntrinsicOp) -> T: ...

    @abc.abstractmethod
    def visit_retsub(self, retsub: models.RetSub) -> T: ...

    @abc.abstractmethod
    def visit_program_exit(self, op: models.ProgramExit) -> T: ...

    @abc.abstractmethod
    def visit_err(self, op: models.Err) -> T: ...

    @abc.abstractmethod
    def visit_goto(self, op: models.Goto) -> T: ...

    @abc.abstractmethod
    def visit_conditional_branch(self, op: models.ConditionalBranch) -> T: ...

    @abc.abstractmethod
    def visit_switch(self, op: models.Switch) -> T: ...

    @abc.abstractmethod
    def visit_match(self, op: models.Match) -> T: ...

    @abc.abstractmethod
    def visit_address(self, addr: models.Address) -> T: ...

    @abc.abstractmethod
    def visit_method(self, method: models.Method) -> T: ...

    @abc.abstractmethod
    def visit_template_var(self, deploy_var: models.TemplateVar) -> T: ...
