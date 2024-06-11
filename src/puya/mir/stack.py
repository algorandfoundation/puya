import contextlib
import typing
from collections.abc import Iterator

import attrs

from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.utils import format_bytes
from puya.mir import models
from puya.mir.visitor import MIRVisitor
from puya.parse import SourceLocation
from puya.teal import models as teal


@attrs.define
class Stack(MIRVisitor[list[teal.TealOp]]):
    allow_virtual: bool = True
    use_frame: bool = False
    parameters: list[str] = attrs.field(factory=list)
    f_stack: list[str] = attrs.field(factory=list)
    """f-stack holds variables above the current frame"""
    x_stack: list[str] = attrs.field(factory=list)
    """x-stack holds variable that are carried between blocks"""
    l_stack: list[str] = attrs.field(factory=list)
    """l-stack holds variables that are used within a block"""

    def copy(self) -> "Stack":
        return Stack(
            allow_virtual=self.allow_virtual,
            use_frame=self.use_frame,
            parameters=self.parameters.copy(),
            f_stack=self.f_stack.copy(),
            x_stack=self.x_stack.copy(),
            l_stack=self.l_stack.copy(),
        )

    @classmethod
    def for_full_stack(
        cls, subroutine: models.MemorySubroutine, block: models.MemoryBasicBlock
    ) -> typing.Self:
        stack = cls()
        stack.begin_block(subroutine, block)
        return stack

    def begin_block(
        self, subroutine: models.MemorySubroutine, block: models.MemoryBasicBlock
    ) -> None:
        self.parameters = [p.local_id for p in subroutine.signature.parameters]
        self.f_stack = list(block.f_stack_in)
        self.x_stack = list(block.x_stack_in or ())  # x-stack might not be assigned yet
        self.l_stack = []
        self.use_frame = not subroutine.is_main

    @property
    def full_stack_desc(self) -> str:
        stack_descs = []
        if self.parameters:
            stack_descs.append("(𝕡) " + ",".join(self.parameters))  # noqa: RUF001
        if self.f_stack:
            stack_descs.append("(𝕗) " + ",".join(self.f_stack))  # noqa: RUF001
        if self.x_stack:
            stack_descs.append("(𝕏) " + ",".join(self.x_stack))  # noqa: RUF001
        stack_descs.append(",".join(self.l_stack))
        return " | ".join(stack_descs)

    def _stack_error(self, msg: str) -> typing.Never:
        raise InternalError(f"{msg}: {self.full_stack_desc}")

    def _l_stack_assign_name(self, value: str) -> None:
        if not self.l_stack:
            self._stack_error(f"l-stack too small to assign name {value}")
        self.l_stack[-1] = value

    def _get_f_stack_dig_bury(self, value: str) -> int:
        return (
            len(self.f_stack)
            + len(self.x_stack)
            + len(self.l_stack)
            - self.f_stack.index(value)
            - 1
        )

    def visit_int(self, push: models.Int) -> list[teal.TealOp]:
        self.l_stack.append(str(push.value))
        return [teal.Int(push.value, source_location=push.source_location)]

    def visit_byte(self, push: models.Byte) -> list[teal.TealOp]:
        self.l_stack.append(format_bytes(push.value, push.encoding))
        return [teal.Byte(push.value, push.encoding, source_location=push.source_location)]

    def visit_template_var(self, deploy_var: models.TemplateVar) -> list[teal.TealOp]:
        self.l_stack.append(deploy_var.name)
        return [
            teal.TemplateVar(
                name=deploy_var.name,
                op_code=deploy_var.op_code,
                source_location=deploy_var.source_location,
            )
        ]

    def visit_address(self, addr: models.Address) -> list[teal.TealOp]:
        self.l_stack.append(addr.value)
        return [teal.Address(addr.value, source_location=addr.source_location)]

    def visit_method(self, method: models.Method) -> list[teal.TealOp]:
        self.l_stack.append(f'method<"{method.value}">')
        return [teal.Method(method.value, source_location=method.source_location)]

    def visit_comment(self, _comment: models.Comment) -> list[teal.TealOp]:
        return []

    def visit_store_virtual(self, store: models.StoreVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "StoreVirtual op encountered during TEAL generation", store.source_location
            )
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store {store.local_id}")
        self.l_stack.pop()
        return []

    def visit_load_virtual(self, load: models.LoadVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "LoadVirtual op encountered during TEAL generation", load.source_location
            )
        self.l_stack.append(load.local_id)
        return []

    def _store_f_stack(
        self, value: str, source_location: SourceLocation | None
    ) -> teal.Cover | teal.FrameBury | teal.Bury:
        if value not in self.f_stack:
            self._stack_error(f"{value} not found in f-stack")

        frame_bury = self.f_stack.index(value)
        bury = self._get_f_stack_dig_bury(value)
        self.l_stack.pop()
        if self.use_frame:
            return teal.FrameBury(frame_bury, source_location=source_location)
        return teal.Bury(bury, source_location=source_location)

    def _insert_f_stack(self, value: str, source_location: SourceLocation | None) -> teal.Cover:
        if value in self.f_stack:
            raise self._stack_error(f"Could not insert {value} as it is already in f-stack")

        # inserting something at the top of the f-stack
        # is equivalent to inserting at the bottom of the x-stack
        cover = len(self.x_stack) + len(self.l_stack) - 1
        self.l_stack.pop()
        self.f_stack.append(value)
        return teal.Cover(cover, source_location=source_location)

    def visit_store_f_stack(self, store: models.StoreFStack) -> list[teal.TealOp]:
        if not self.l_stack:
            self._stack_error(f"l-stack is empty, can not store {store.local_id} to f-stack")

        if store.insert:
            return [self._insert_f_stack(store.local_id, store.source_location)]
        else:
            return [self._store_f_stack(store.local_id, store.source_location)]

    def visit_load_f_stack(self, load: models.LoadFStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self.f_stack:
            self._stack_error(f"{local_id} not found in f-stack")
        frame_dig = self.f_stack.index(local_id)
        dig = self._get_f_stack_dig_bury(local_id)
        self.l_stack.append(local_id)
        if self.use_frame:
            return [teal.FrameDig(frame_dig, source_location=load.source_location)]
        return [
            (
                teal.Dig(dig, source_location=load.source_location)
                if dig
                else teal.Dup(source_location=load.source_location)
            )
        ]

    def visit_store_x_stack(self, store: models.StoreXStack) -> list[teal.TealOp]:
        local_id = store.local_id
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store {local_id} to x-stack")
        # re-alias top of l-stack
        self._l_stack_assign_name(local_id)

        cover = len(self.x_stack) + len(self.l_stack) - 1
        var = self.l_stack[-1] if store.copy else self.l_stack.pop()
        self.x_stack.insert(0, var)
        if store.copy:
            return [
                teal.Dup(source_location=store.source_location),
                teal.Cover(cover, source_location=store.source_location),
            ]
        return [teal.Cover(cover, source_location=store.source_location)]

    def visit_load_x_stack(self, load: models.LoadXStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self.x_stack:
            self._stack_error(f"{local_id} not found in x-stack")
        index = self.x_stack.index(local_id)
        uncover = len(self.l_stack) + (len(self.x_stack) - index - 1)
        self.x_stack.pop(index)
        self.l_stack.append(local_id)
        return [teal.Uncover(uncover, source_location=load.source_location)]

    def visit_store_l_stack(self, store: models.StoreLStack) -> list[teal.TealOp]:
        cover = store.cover
        if cover >= len(self.l_stack):
            self._stack_error(
                f"l-stack too small to store (cover {cover}) {store.local_id} to l-stack"
            )
        # re-alias top of l-stack
        self._l_stack_assign_name(store.local_id)

        index = len(self.l_stack) - cover - 1
        var = self.l_stack[-1] if store.copy else self.l_stack.pop()
        self.l_stack.insert(index, var)
        if store.copy:
            result: list[teal.TealOp] = [teal.Dup(source_location=store.source_location)]
            if cover > 0:
                result.append(teal.Cover(cover + 1, source_location=store.source_location))
            return result
        return [teal.Cover(cover, source_location=store.source_location)]

    def visit_load_l_stack(self, load: models.LoadLStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self.l_stack:
            self._stack_error(f"{local_id} not found in l-stack")
        index = self.l_stack.index(local_id)
        uncover = len(self.l_stack) - index - 1

        if load.copy:
            self.l_stack.append(local_id)
            return [
                (
                    teal.Dup(source_location=load.source_location)
                    if uncover == 0
                    else teal.Dig(uncover, source_location=load.source_location)
                )
            ]
        else:
            self.l_stack.pop(index)
            self.l_stack.append(local_id)
            return [teal.Uncover(uncover, source_location=load.source_location)]

    def visit_load_param(self, load: models.LoadParam) -> list[teal.TealOp]:
        if load.local_id not in self.parameters:
            self._stack_error(f"{load.local_id} is not a parameter")
        self.l_stack.append(load.local_id)
        return [teal.FrameDig(load.index, source_location=load.source_location)]

    def visit_store_param(self, store: models.StoreParam) -> list[teal.TealOp]:
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store param {store.local_id}")
        if store.local_id not in self.parameters:
            self._stack_error(f"{store.local_id} is not a parameter")
        self._l_stack_assign_name(store.local_id)
        if not store.copy:
            self.l_stack.pop()
            return [teal.FrameBury(store.index, source_location=store.source_location)]
        else:
            return [
                teal.Dup(source_location=store.source_location),
                teal.FrameBury(store.index, source_location=store.source_location),
            ]

    def visit_proto(self, proto: models.Proto) -> list[teal.TealOp]:
        return [teal.Proto(proto.parameters, proto.returns, source_location=proto.source_location)]

    def visit_allocate(self, allocate: models.Allocate) -> list[teal.TealOp]:
        self.f_stack.extend(allocate.allocate_on_entry)

        def push_n(value_op: teal.TealOp, n: int) -> list[teal.TealOp]:
            match n:
                case 0:
                    return []
                case 1:
                    return [value_op]
                case 2:
                    return [value_op, teal.Dup(source_location=allocate.source_location)]
                case _:
                    return [value_op, teal.DupN(n=n - 1, source_location=allocate.source_location)]

        bad_bytes_value = teal.Int(0, source_location=allocate.source_location)
        bad_uint_value = teal.Byte(
            value=b"", encoding=AVMBytesEncoding.utf8, source_location=allocate.source_location
        )
        return [
            *push_n(bad_bytes_value, allocate.num_bytes),
            *push_n(bad_uint_value, allocate.num_uints),
        ]

    def visit_pop(self, pop: models.Pop) -> list[teal.TealOp]:
        if len(self.l_stack) < pop.n:
            self._stack_error(f"l-stack too small to pop {pop.n}")
        for _ in range(pop.n):
            self.l_stack.pop()
        return [
            (
                teal.PopN(pop.n, source_location=pop.source_location)
                if pop.n > 1
                else teal.Pop(source_location=pop.source_location)
            )
        ]

    def visit_callsub(self, callsub: models.CallSub) -> list[teal.TealOp]:
        if len(self.l_stack) < callsub.parameters:
            self._stack_error(f"l-stack too small to call {callsub}")
        op_code = f"{{{callsub.target}}}"
        if callsub.returns > 1:
            produces = [f"{op_code}.{n}" for n in range(callsub.returns)]
        elif callsub.returns == 1:
            produces = [op_code]
        else:
            produces = []

        for _ in range(callsub.parameters):
            self.l_stack.pop()
        self.l_stack.extend(produces)

        return [
            teal.CallSub(
                target=callsub.target,
                consumes=callsub.parameters,
                produces=callsub.returns,
                source_location=callsub.source_location,
            )
        ]

    def visit_retsub(self, retsub: models.RetSub) -> list[teal.TealOp]:
        if len(self.l_stack) != retsub.returns:
            self._stack_error(
                f"Inconsistent l-stack height for retsub. Expected {retsub.returns}, "
                f"actual {len(self.l_stack)}"
            )

        sub_l_stack_height = len(self.f_stack) + len(self.x_stack)
        if retsub.returns < sub_l_stack_height:
            # move returns to base of frame in order
            ret_ops: list[teal.TealOp] = [
                teal.FrameBury(n, source_location=retsub.source_location)
                for n in reversed(range(retsub.returns))
            ]
        else:
            # f-stack + x-stack is smaller than number of returns, so move it out of the way
            n = retsub.returns + sub_l_stack_height - 1
            ret_ops = [
                teal.Uncover(n, source_location=retsub.source_location)
            ] * sub_l_stack_height
        ret_ops.append(
            teal.RetSub(consumes=retsub.returns, source_location=retsub.source_location)
        )
        # retsub moves return values down below the frame to the stack height before the sub was
        # called and discards anything above.
        # represent this in the virtual stack with a new stack state with only the current
        # l-stack (i.e. discard all values in parameters, f-stack and x-stack)
        self.parameters = []
        self.f_stack = []
        self.x_stack = []
        return ret_ops

    def visit_intrinsic(self, intrinsic: models.IntrinsicOp) -> list[teal.TealOp]:
        if intrinsic.consumes > len(self.l_stack):
            self._stack_error(
                f"l-stack too small to provide {intrinsic.consumes} arg/s for {intrinsic}: "
            )
        op_code = "{" + intrinsic.op_code + "}"
        if not isinstance(intrinsic.produces, int):
            produces = intrinsic.produces
        elif intrinsic.produces > 1:
            produces = [f"{op_code}.{n}" for n in range(intrinsic.produces)]
        elif intrinsic.produces == 1:
            produces = [op_code]
        else:
            produces = []

        for _ in range(intrinsic.consumes):
            self.l_stack.pop()
        self.l_stack.extend(produces)

        return [
            teal.Intrinsic(
                op_code=intrinsic.op_code,
                immediates=intrinsic.immediates,
                comment=intrinsic.comment,
                consumes=intrinsic.consumes,
                produces=len(produces),
                source_location=intrinsic.source_location,
            )
        ]

    @contextlib.contextmanager
    def _enter_virtual_stack(self) -> Iterator[None]:
        original_allow_virtual = self.allow_virtual
        try:
            self.allow_virtual = True
            yield
        finally:
            self.allow_virtual = original_allow_virtual

    def visit_virtual_stack(self, virtual: models.VirtualStackOp) -> list[teal.TealOp]:
        with self._enter_virtual_stack():
            virtual.original.accept(self)
        return []

    def __str__(self) -> str:
        return self.full_stack_desc
