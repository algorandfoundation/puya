import contextlib
import typing
from collections.abc import Iterator, Sequence

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
    _f_stack: list[str] = attrs.field(factory=list)
    """f-stack holds variables above the current frame"""
    _x_stack: list[str] = attrs.field(factory=list)
    """x-stack holds variable that are carried between blocks"""
    _l_stack: list[str] = attrs.field(factory=list)
    """l-stack holds variables that are used within a block"""

    @property
    def f_stack(self) -> Sequence[str]:
        return self._f_stack

    @property
    def x_stack(self) -> Sequence[str]:
        return self._x_stack

    @property
    def l_stack(self) -> Sequence[str]:
        return self._l_stack

    def copy(self) -> "Stack":
        return Stack(
            allow_virtual=self.allow_virtual,
            use_frame=self.use_frame,
            parameters=self.parameters.copy(),
            f_stack=list(self.f_stack),
            x_stack=list(self.x_stack),
            l_stack=list(self.l_stack),
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
        self._f_stack = list(block.f_stack_in)
        self._x_stack = list(block.x_stack_in or ())  # x-stack might not be assigned yet
        self._l_stack = []
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

    def _get_f_stack_dig_bury(self, value: str) -> int:
        return (
            len(self.f_stack)
            + len(self.x_stack)
            + len(self.l_stack)
            - self.f_stack.index(value)
            - 1
        )

    def _f_stack_append(self, local_id: str, *, defined: bool) -> teal.StackManipulation:
        self._f_stack.append(local_id)
        return teal.StackManipulation(
            stack="f",
            manipulation="insert",
            index=len(self.f_stack) - 1,
            local_id=local_id,
            defined=defined,
        )

    def _x_stack_insert(self, local_id: str) -> teal.StackManipulation:
        self._x_stack.insert(0, local_id)
        return teal.StackManipulation(stack="x", manipulation="insert", index=0, local_id=local_id)

    def _x_stack_pop(self, index: int = -1) -> teal.StackManipulation:
        local_id = self._x_stack.pop(index)
        return teal.StackManipulation(
            stack="x", manipulation="pop", index=index, local_id=local_id
        )

    def _l_stack_pop(self, index: int = -1) -> teal.StackManipulation:
        removed = self._l_stack.pop(index)
        return teal.StackManipulation(stack="l", manipulation="pop", index=index, local_id=removed)

    def _l_stack_insert(self, index: int, local_id: str) -> teal.StackManipulation:
        self._l_stack.insert(index, local_id)
        return teal.StackManipulation(
            stack="l", manipulation="insert", index=index, local_id=local_id
        )

    def _l_stack_append(self, local_id: str) -> teal.StackManipulation:
        self._l_stack.append(local_id)
        return teal.StackManipulation(
            stack="l", manipulation="insert", index=len(self._l_stack) - 1, local_id=local_id
        )

    def _l_stack_copy(self, local_id: str) -> teal.StackManipulation:
        return self._l_stack_append(f"{local_id} (copy)")

    def visit_int(self, push: models.Int) -> list[teal.TealOp]:
        append = self._l_stack_append(str(push.value))
        return [
            teal.Int(
                push.value, stack_manipulations=[append], source_location=push.source_location
            )
        ]

    def visit_byte(self, push: models.Byte) -> list[teal.TealOp]:
        append = self._l_stack_append(format_bytes(push.value, push.encoding))
        return [
            teal.Byte(
                push.value,
                push.encoding,
                stack_manipulations=[append],
                source_location=push.source_location,
            )
        ]

    def visit_template_var(self, deploy_var: models.TemplateVar) -> list[teal.TealOp]:
        append = self._l_stack_append(deploy_var.name)
        return [
            teal.TemplateVar(
                name=deploy_var.name,
                op_code=deploy_var.op_code,
                stack_manipulations=[append],
                source_location=deploy_var.source_location,
            )
        ]

    def visit_address(self, addr: models.Address) -> list[teal.TealOp]:
        append = self._l_stack_append(addr.value)
        return [
            teal.Address(
                addr.value, stack_manipulations=[append], source_location=addr.source_location
            )
        ]

    def visit_method(self, method: models.Method) -> list[teal.TealOp]:
        append = self._l_stack_append(f'method<"{method.value}">')
        return [
            teal.Method(
                method.value, stack_manipulations=[append], source_location=method.source_location
            )
        ]

    def visit_comment(self, _comment: models.Comment) -> list[teal.TealOp]:
        return []

    def visit_store_virtual(self, store: models.StoreVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "StoreVirtual op encountered during TEAL generation", store.source_location
            )
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store {store.local_id}")
        self._l_stack_pop()
        return []

    def visit_load_virtual(self, load: models.LoadVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "LoadVirtual op encountered during TEAL generation", load.source_location
            )
        self._l_stack_copy(load.local_id)
        return []

    def _store_f_stack(
        self, local_id: str, source_location: SourceLocation | None
    ) -> teal.Cover | teal.FrameBury | teal.Bury:
        if local_id not in self.f_stack:
            self._stack_error(f"{local_id} not found in f-stack")

        # must calculate bury offsets BEFORE modifying l-stack
        frame_bury = self.f_stack.index(local_id)
        bury = self._get_f_stack_dig_bury(local_id)
        pop = self._l_stack_pop()
        store = teal.StackManipulation(
            stack="f", manipulation="define", index=0, local_id=local_id
        )
        if self.use_frame:
            return teal.FrameBury(
                frame_bury, stack_manipulations=[pop, store], source_location=source_location
            )
        else:
            return teal.Bury(
                bury, stack_manipulations=[pop, store], source_location=source_location
            )

    def _insert_f_stack(self, local_id: str, source_location: SourceLocation | None) -> teal.Cover:
        if local_id in self.f_stack:
            raise self._stack_error(f"Could not insert {local_id} as it is already in f-stack")

        # inserting something at the top of the f-stack
        # is equivalent to inserting at the bottom of the x-stack
        cover = len(self.x_stack) + len(self.l_stack) - 1
        pop = self._l_stack_pop()
        append = self._f_stack_append(local_id, defined=True)
        return teal.Cover(
            cover,
            stack_manipulations=[pop, append],
            source_location=source_location,
        )

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
        append = self._l_stack_copy(local_id)
        if self.use_frame:
            return [
                teal.FrameDig(
                    frame_dig, stack_manipulations=[append], source_location=load.source_location
                )
            ]
        return [teal.Dig(dig, stack_manipulations=[append], source_location=load.source_location)]

    def visit_store_x_stack(self, store: models.StoreXStack) -> list[teal.TealOp]:
        local_id = store.local_id
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store {local_id} to x-stack")

        cover = len(self.x_stack) + len(self.l_stack) - 1
        pop = self._l_stack_pop()
        insert = self._x_stack_insert(local_id)
        return [
            teal.Cover(
                cover,
                stack_manipulations=[pop, insert],
                source_location=store.source_location,
            )
        ]

    def visit_load_x_stack(self, load: models.LoadXStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self.x_stack:
            self._stack_error(f"{local_id} not found in x-stack")
        index = self.x_stack.index(local_id)
        uncover = len(self.l_stack) + (len(self.x_stack) - index - 1)
        pop = self._x_stack_pop(index)
        append = self._l_stack_copy(load.local_id)
        return [
            teal.Uncover(
                uncover,
                stack_manipulations=[
                    pop,
                    append,
                ],
                source_location=load.source_location,
            )
        ]

    def visit_store_l_stack(self, store: models.StoreLStack) -> list[teal.TealOp]:
        cover = store.cover
        local_id = store.local_id
        if cover >= len(self.l_stack):
            self._stack_error(
                f"l-stack too small to store (cover {cover}) {store.local_id} to l-stack"
            )
        index = len(self.l_stack) - cover - 1
        pop = self._l_stack_pop()
        insert = self._l_stack_insert(index, local_id)
        ops = list[teal.TealOp]()
        if store.copy:
            append = self._l_stack_copy(local_id)
            ops.append(
                teal.Dup(stack_manipulations=[append], source_location=store.source_location),
            )
        ops.append(
            teal.Cover(
                cover + 1 if store.copy else cover,
                stack_manipulations=[pop, insert],
                source_location=store.source_location,
            )
        )
        return ops

    def visit_load_l_stack(self, load: models.LoadLStack) -> list[teal.TealOp]:
        local_id = load.local_id
        try:
            index = self.l_stack.index(local_id)
        except ValueError:
            self._stack_error(f"{local_id} not found in l-stack")
        uncover = len(self.l_stack) - index - 1

        if load.copy:
            copy = self._l_stack_copy(local_id)
            return [
                teal.Dig(
                    uncover,
                    stack_manipulations=[copy],
                    source_location=load.source_location,
                )
            ]
        else:
            pop = self._l_stack_pop(index)
            append = self._l_stack_append(local_id)
            return [
                teal.Uncover(
                    uncover,
                    stack_manipulations=[pop, append],
                    source_location=load.source_location,
                )
            ]

    def visit_load_param(self, load: models.LoadParam) -> list[teal.TealOp]:
        if load.local_id not in self.parameters:
            self._stack_error(f"{load.local_id} is not a parameter")
        append = self._l_stack_copy(load.local_id)
        return [
            teal.FrameDig(
                load.index,
                source_location=load.source_location,
                stack_manipulations=[append],
            )
        ]

    def visit_store_param(self, store: models.StoreParam) -> list[teal.TealOp]:
        if not self.l_stack:
            self._stack_error(f"l-stack too small to store param {store.local_id}")
        if store.local_id not in self.parameters:
            self._stack_error(f"{store.local_id} is not a parameter")

        pop = self._l_stack_pop()
        return [
            teal.FrameBury(
                store.index, stack_manipulations=[pop], source_location=store.source_location
            )
        ]

    def visit_proto(self, proto: models.Proto) -> list[teal.TealOp]:
        return [teal.Proto(proto.parameters, proto.returns, source_location=proto.source_location)]

    def visit_allocate(self, allocate: models.Allocate) -> list[teal.TealOp]:
        def with_stack_manipulation(bad_value: teal.TealOp, local_id: str) -> teal.TealOp:
            return attrs.evolve(
                bad_value,
                stack_manipulations=[self._f_stack_append(local_id, defined=False)],
            )

        bad_bytes_value = teal.Int(
            0,
            source_location=allocate.source_location,
        )
        bad_uint_value = teal.Byte(
            value=b"",
            encoding=AVMBytesEncoding.utf8,
            source_location=allocate.source_location,
        )

        return [
            with_stack_manipulation(
                bad_bytes_value if idx < allocate.num_bytes else bad_uint_value,
                local_id,
            )
            for idx, local_id in enumerate(allocate.allocate_on_entry)
        ]

    def visit_pop(self, pop: models.Pop) -> list[teal.TealOp]:
        if len(self.l_stack) < pop.n:
            self._stack_error(f"l-stack too small to pop {pop.n}")
        return [
            teal.Pop(
                stack_manipulations=[self._l_stack_pop()],
                source_location=pop.source_location,
            )
            for _ in range(pop.n)
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

        stack_manipulations = [self._l_stack_pop() for _ in range(callsub.parameters)]
        stack_manipulations.extend(self._l_stack_append(prod) for prod in produces)

        return [
            teal.CallSub(
                target=callsub.target,
                consumes=callsub.parameters,
                produces=callsub.returns,
                stack_manipulations=stack_manipulations,
                source_location=callsub.source_location,
            )
        ]

    def visit_retsub(self, retsub: models.RetSub) -> list[teal.TealOp]:
        if len(self.l_stack) != retsub.returns:
            self._stack_error(
                f"Inconsistent l-stack height for retsub. Expected {retsub.returns}, "
                f"actual {len(self.l_stack)}"
            )

        # TODO: do we need stack manipulations? Probably won't be used since this ends a call frame
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
        self._f_stack = []
        self._x_stack = []
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

        stack_manipulations = [self._l_stack_pop() for _ in range(intrinsic.consumes)]
        stack_manipulations.extend(self._l_stack_append(prod) for prod in produces)

        return [
            teal.Intrinsic(
                op_code=intrinsic.op_code,
                immediates=intrinsic.immediates,
                comment=intrinsic.comment,
                consumes=intrinsic.consumes,
                produces=len(produces),
                stack_manipulations=stack_manipulations,
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
