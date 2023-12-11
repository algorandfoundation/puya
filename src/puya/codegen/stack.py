import contextlib
import typing
from collections.abc import Iterable, Iterator
from copy import deepcopy

import attrs

from puya.codegen import ops, teal
from puya.codegen.utils import format_bytes
from puya.codegen.visitor import MIRVisitor
from puya.codegen.vla import VariableLifetimeAnalysis
from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding


@attrs.define
class _StackState:
    parameters: list[str] = attrs.field(factory=list)
    f_stack: list[str] = attrs.field(factory=list)
    """f-stack holds variables above the current frame"""
    x_stack: list[str] = attrs.field(factory=list)
    """x-stack holds variable that are carried between blocks"""
    l_stack: list[str] = attrs.field(factory=list)
    """l-stack holds variables that are used within a block"""

    @property
    def full_stack(self) -> Iterable[str]:
        yield from self.f_stack
        yield from self.x_stack
        yield from self.l_stack


@attrs.define
class Stack(MIRVisitor[list[teal.TealOp]]):
    allow_virtual: bool = attrs.field(default=True)
    _current_subroutine: ops.MemorySubroutine | None = attrs.field(default=None)
    _use_frame: bool = attrs.field(default=False)
    _vla: VariableLifetimeAnalysis | None = attrs.field(default=None)
    state: _StackState = attrs.field(factory=_StackState)

    @classmethod
    def for_full_stack(
        cls, subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock
    ) -> typing.Self:
        stack = cls()
        stack.begin_block(subroutine, block)
        return stack

    def begin_block(self, subroutine: ops.MemorySubroutine, block: ops.MemoryBasicBlock) -> None:
        if self._current_subroutine != subroutine:
            self._vla = None
        self._current_subroutine = subroutine
        self.state = _StackState(
            parameters=[p.local_id for p in subroutine.signature.parameters],
            f_stack=list(block.f_stack_in),
            x_stack=list(block.x_stack_in or ()),  # x-stack might not be assigned yet
            l_stack=[],
        )
        self._use_frame = not subroutine.is_main

    @property
    def _parameters(self) -> list[str]:
        return self.state.parameters

    @property
    def _f_stack(self) -> list[str]:
        return self.state.f_stack

    @property
    def _x_stack(self) -> list[str]:
        return self.state.x_stack

    @property
    def _l_stack(self) -> list[str]:
        return self.state.l_stack

    @property
    def vla(self) -> VariableLifetimeAnalysis:
        if self._vla is None:
            assert self._current_subroutine
            self._vla = VariableLifetimeAnalysis.analyze(self._current_subroutine)
        assert self._vla
        return self._vla

    @property
    def f_x_l_stack_height(self) -> int:
        return self.f_stack_height + self.x_stack_height + self.l_stack_height

    @property
    def x_l_stack_height(self) -> int:
        return self.x_stack_height + self.l_stack_height

    @property
    def f_stack_height(self) -> int:
        return len(self._f_stack)

    @property
    def x_stack_height(self) -> int:
        return len(self._x_stack)

    @property
    def l_stack_height(self) -> int:
        return len(self._l_stack)

    @property
    def full_stack_desc(self) -> str:
        stack_descs = []
        if self._parameters:
            stack_descs.append("(𝕡) " + ",".join(self._parameters))  # noqa: RUF001
        if self._f_stack:
            stack_descs.append("(𝕗) " + ",".join(self._f_stack))  # noqa: RUF001
        if self._x_stack:
            stack_descs.append("(𝕏) " + ",".join(self._x_stack))  # noqa: RUF001
        stack_descs.append(",".join(self._l_stack))
        return " | ".join(stack_descs)

    def _stack_error(self, msg: str) -> typing.Never:
        raise InternalError(f"{msg}: {self.full_stack_desc}")

    def _l_stack_assign_name(self, value: str) -> None:
        if not self._l_stack:
            self._stack_error(f"l-stack too small to assign name {value}")
        self._l_stack[-1] = value

    def _get_f_stack_dig_bury(self, value: str) -> int:
        return self.f_x_l_stack_height - self._f_stack.index(value) - 1

    def _get_x_stack_cover_n(self) -> int:
        """Return n value for a (un)cover operation with the x stack"""
        return self.x_l_stack_height - 1

    def get_l_stack_cover_n(self) -> int:
        """Return n value for a (un)cover operation with the l stack"""
        return self.l_stack_height - 1

    def visit_push_int(self, push: ops.PushInt) -> list[teal.TealOp]:
        self._l_stack.append(str(push.value))
        return [teal.PushInt(push.value)]

    def visit_push_bytes(self, push: ops.PushBytes) -> list[teal.TealOp]:
        self._l_stack.append(format_bytes(push.value, push.encoding))
        return [teal.PushBytes(push.value, push.encoding)]

    def visit_push_address(self, addr: ops.PushAddress) -> list[teal.TealOp]:
        self._l_stack.append(addr.value)
        return [teal.PushAddress(addr.value)]

    def visit_push_method(self, method: ops.PushMethod) -> list[teal.TealOp]:
        self._l_stack.append(f'method<"{method.value}">')
        return [teal.PushMethod(method.value)]

    def visit_comment(self, _comment: ops.Comment) -> list[teal.TealOp]:
        return []

    def visit_store_virtual(self, store: ops.StoreVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "StoreVirtual op encountered during TEAL generation", store.source_location
            )
        if not self._l_stack:
            self._stack_error(f"l-stack too small to store {store.local_id}")
        self._l_stack.pop()
        return []

    def visit_load_virtual(self, load: ops.LoadVirtual) -> list[teal.TealOp]:
        if not self.allow_virtual:
            raise InternalError(
                "LoadVirtual op encountered during TEAL generation", load.source_location
            )
        self._l_stack.append(load.local_id)
        return []

    def _store_f_stack(self, value: str) -> teal.Cover | teal.FrameBury | teal.Bury:
        """Updates the stack, and if insert returns the cover value, else the bury value"""
        if value not in self._f_stack:
            self._stack_error(f"{value} not found in f-stack")

        frame_bury = self._f_stack.index(value)
        bury = self._get_f_stack_dig_bury(value)
        self._l_stack.pop()
        if self._use_frame:
            return teal.FrameBury(frame_bury)
        return teal.Bury(bury)

    def _insert_f_stack(self, value: str) -> teal.Cover | teal.FrameBury | teal.Bury:
        """Updates the stack, and if insert returns the cover value, else the bury value"""
        if value in self._f_stack:
            raise self._stack_error(f"Could not insert {value} as it is already in f-stack")

        # inserting something at the top of the f-stack
        # is equivalent to inserting at the bottom of the x-stack
        cover = self._get_x_stack_cover_n()
        self._l_stack.pop()
        self._f_stack.append(value)
        return teal.Cover(cover)

    def visit_store_f_stack(self, store: ops.StoreFStack) -> list[teal.TealOp]:
        if not self._l_stack:
            self._stack_error(f"l-stack is empty, can not store {store.local_id} to f-stack")

        if store.insert:
            return [self._insert_f_stack(store.local_id)]
        else:
            return [self._store_f_stack(store.local_id)]

    def visit_load_f_stack(self, load: ops.LoadFStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self._f_stack:
            self._stack_error(f"{local_id} not found in f-stack")
        frame_dig = self._f_stack.index(local_id)
        dig = self._get_f_stack_dig_bury(local_id)
        self._l_stack.append(local_id)
        if self._use_frame:
            return [teal.FrameDig(frame_dig)]
        return [teal.Dig(dig) if dig else teal.Dup()]

    def visit_store_x_stack(self, store: ops.StoreXStack) -> list[teal.TealOp]:
        local_id = store.local_id
        if not self._l_stack:
            self._stack_error(f"l-stack too small to store {local_id} to x-stack")
        # re-alias top of l-stack
        self._l_stack_assign_name(local_id)

        cover = self.x_l_stack_height - 1
        var = self._l_stack[-1] if store.copy else self._l_stack.pop()
        self._x_stack.insert(0, var)
        if store.copy:
            return [teal.Dup(), teal.Cover(cover)]
        return [teal.Cover(cover)]

    def visit_load_x_stack(self, load: ops.LoadXStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self._x_stack:
            self._stack_error(f"{local_id} not found in x-stack")
        index = self._x_stack.index(local_id)
        uncover = self.l_stack_height + (self.x_stack_height - index - 1)
        self._x_stack.pop(index)
        self._l_stack.append(local_id)
        return [teal.Uncover(uncover)]

    def visit_store_l_stack(self, store: ops.StoreLStack) -> list[teal.TealOp]:
        cover = store.cover
        if cover >= self.l_stack_height:
            self._stack_error(
                f"l-stack too small to store (cover {cover}) {store.local_id} to l-stack"
            )
        # re-alias top of l-stack
        self._l_stack_assign_name(store.local_id)

        index = self.l_stack_height - cover - 1
        var = self._l_stack[-1] if store.copy else self._l_stack.pop()
        self._l_stack.insert(index, var)
        if store.copy:
            result: list[teal.TealOp] = [teal.Dup()]
            if cover > 0:
                result.append(teal.Cover(cover + 1))
            return result
        return [teal.Cover(cover)]

    def visit_load_l_stack(self, load: ops.LoadLStack) -> list[teal.TealOp]:
        local_id = load.local_id
        if local_id not in self._l_stack:
            self._stack_error(f"{local_id} not found in l-stack")
        index = self._l_stack.index(local_id)
        uncover = self.l_stack_height - index - 1

        if load.copy:
            self._l_stack.append(local_id)
            return [teal.Dup() if uncover == 0 else teal.Dig(uncover)]
        else:
            self._l_stack.pop(index)
            self._l_stack.append(local_id)
            return [teal.Uncover(uncover)]

    def visit_load_param(self, load: ops.LoadParam) -> list[teal.TealOp]:
        if load.local_id not in self._parameters:
            self._stack_error(f"{load.local_id} is not a parameter")
        self._l_stack.append(load.local_id)
        return [teal.FrameDig(load.index)]

    def visit_store_param(self, store: ops.StoreParam) -> list[teal.TealOp]:
        if not self._l_stack:
            self._stack_error(f"l-stack too small to store param {store.local_id}")
        if store.local_id not in self._parameters:
            self._stack_error(f"{store.local_id} is not a parameter")
        self._l_stack_assign_name(store.local_id)
        if not store.copy:
            self._l_stack.pop()
            return [teal.FrameBury(store.index)]
        else:
            return [teal.Dup(), teal.FrameBury(store.index)]

    def visit_proto(self, proto: ops.Proto) -> list[teal.TealOp]:
        return [teal.Proto(proto.parameters, proto.returns)]

    def visit_allocate(self, allocate: ops.Allocate) -> list[teal.TealOp]:
        self._f_stack.extend(allocate.allocate_on_entry)

        def push_n(value_op: teal.TealOp, n: int) -> list[teal.TealOp]:
            match n:
                case 0:
                    return []
                case 1:
                    return [value_op]
                case 2:
                    return [value_op, teal.Dup()]
                case _ as n:
                    return [value_op, teal.DupN(n=n - 1)]

        bad_bytes_value = teal.PushInt(0)
        bad_uint_value = teal.PushBytes(n=b"", encoding=AVMBytesEncoding.utf8)
        return [
            *push_n(bad_bytes_value, allocate.num_bytes),
            *push_n(bad_uint_value, allocate.num_uints),
        ]

    def visit_pop(self, pop: ops.Pop) -> list[teal.TealOp]:
        if self.l_stack_height < pop.n:
            self._stack_error(f"l-stack too small too pop {pop.n}")
        for _ in range(pop.n):
            self._l_stack.pop()
        return [teal.PopN(pop.n) if pop.n > 1 else teal.Pop()]

    def visit_callsub(self, callsub: ops.CallSub) -> list[teal.TealOp]:
        if self.l_stack_height < callsub.parameters:
            self._stack_error(f"l-stack too small to call {callsub}")
        op_code = f"{{{callsub.target}}}"
        if callsub.returns > 1:
            produces = [f"{op_code}.{n}" for n in range(callsub.returns)]
        elif callsub.returns == 1:
            produces = [op_code]
        else:
            produces = []

        for _ in range(callsub.parameters):
            self._l_stack.pop()
        self._l_stack.extend(produces)

        return [teal.CallSub(target=callsub.target)]

    def visit_retsub(self, retsub: ops.RetSub) -> list[teal.TealOp]:
        if self.l_stack_height != retsub.returns:
            self._stack_error(
                f"Inconsistent l-stack height for retsub. Expected {retsub.returns}, "
                f"actual {self.l_stack_height}"
            )

        sub_l_stack_height = self.f_stack_height + self.x_stack_height
        if retsub.returns < sub_l_stack_height:
            # move returns to base of frame in order
            ret_ops: list[teal.TealOp] = [
                teal.FrameBury(n) for n in reversed(range(retsub.returns))
            ]
        else:
            # f-stack + x-stack is smaller than number of returns, so move it out of the way
            n = retsub.returns + sub_l_stack_height - 1
            ret_ops = [teal.Uncover(n)] * sub_l_stack_height
        ret_ops.append(teal.RetSub())
        # retsub moves return values down below the frame to the stack height before the sub was
        # called and discards anything above.
        # represent this in the virtual stack with a new stack state with only the current
        # l-stack (i.e. discard all values in parameters, f-stack and x-stack)
        self.state = _StackState(l_stack=self._l_stack)
        return ret_ops

    def visit_intrinsic(self, intrinsic: ops.IntrinsicOp) -> list[teal.TealOp]:
        if intrinsic.consumes > self.l_stack_height:
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
            self._l_stack.pop()
        self._l_stack.extend(produces)

        return [
            teal.Intrinsic(
                op_code=intrinsic.op_code,
                immediates=intrinsic.immediates,
                comment=intrinsic.comment,
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

    def visit_virtual_stack(self, virtual: ops.VirtualStackOp) -> list[teal.TealOp]:
        with self._enter_virtual_stack():
            for original in virtual.original:
                original.accept(self)
        return [*(virtual.replacement or ())]

    def clone(self) -> "Stack":
        # deep copy stack state
        state = deepcopy(self.state)
        # share instances of other fields such as current_subroutine and _vla
        return attrs.evolve(self, state=state)

    def __str__(self) -> str:
        return self.full_stack_desc
