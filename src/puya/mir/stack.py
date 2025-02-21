import typing
from collections.abc import Sequence

import attrs

from puya.mir import models
from puya.mir.visitor import MIRVisitor


@attrs.define
class Stack(MIRVisitor[None]):
    parameters: Sequence[str]
    _f_stack: list[str]
    """f-stack holds variables above the current frame"""
    _x_stack: list[str]
    """x-stack holds variable that are carried between blocks"""
    _l_stack: list[str] = attrs.field(factory=list)
    """l-stack holds variables that are used within a block"""

    @classmethod
    def begin_block(
        cls, subroutine: models.MemorySubroutine, block: models.MemoryBasicBlock
    ) -> typing.Self:
        return cls(
            parameters=[p.local_id for p in subroutine.signature.parameters],
            f_stack=list(block.f_stack_in),
            x_stack=list(block.x_stack_in or ()),  # x-stack might not be assigned yet
        )

    @property
    def f_stack(self) -> Sequence[str]:
        return self._f_stack

    @property
    def x_stack(self) -> Sequence[str]:
        return self._x_stack

    @property
    def l_stack(self) -> Sequence[str]:
        return self._l_stack

    @property
    def xl_height(self) -> int:
        return len(self._l_stack) + len(self._x_stack)

    @property
    def fxl_height(self) -> int:
        return len(self._f_stack) + len(self._l_stack) + len(self._x_stack)

    @property
    def full_stack_desc(self) -> str:
        stack_descs = []
        if self.parameters:
            stack_descs.append("(𝕡) " + ",".join(self.parameters))  # noqa: RUF001
        if self._f_stack:
            stack_descs.append("(𝕗) " + ",".join(self._f_stack))  # noqa: RUF001
        if self._x_stack:
            stack_descs.append("(𝕏) " + ",".join(self._x_stack))  # noqa: RUF001
        stack_descs.append(",".join(self._l_stack))
        return " | ".join(stack_descs)

    def _get_f_stack_dig_bury(self, value: str) -> int:
        return (
            len(self._f_stack)
            + len(self._x_stack)
            + len(self._l_stack)
            - self._f_stack.index(value)
            - 1
        )

    def visit_int(self, const: models.Int) -> None:
        self._apply_lstack_effects(const)

    def visit_byte(self, const: models.Byte) -> None:
        self._apply_lstack_effects(const)

    def visit_undefined(self, const: models.Undefined) -> None:
        self._apply_lstack_effects(const)

    def visit_template_var(self, const: models.TemplateVar) -> None:
        self._apply_lstack_effects(const)

    def visit_address(self, const: models.Address) -> None:
        self._apply_lstack_effects(const)

    def visit_method(self, const: models.Method) -> None:
        self._apply_lstack_effects(const)

    def visit_comment(self, _: models.Comment) -> None:
        pass

    def visit_abstract_store(self, store: models.AbstractStore) -> None:
        self._apply_lstack_effects(store)

    def visit_abstract_load(self, load: models.AbstractLoad) -> None:
        self._apply_lstack_effects(load)

    def _store_f_stack(self, store: models.StoreFStack) -> None:
        local_id = store.local_id
        # must calculate bury offsets BEFORE modifying l-stack
        assert local_id in self._f_stack, f"{local_id} not in f-stack"
        bury = self._get_f_stack_dig_bury(local_id)
        assert bury == store.depth, f"expected {bury=} == {store.depth=}"
        self._apply_lstack_effects(store)

    def _insert_f_stack(self, store: models.StoreFStack) -> None:
        local_id = store.local_id
        assert local_id not in self._f_stack, f"{local_id} already in f-stack"
        # inserting something at the top of the f-stack
        # is equivalent to inserting at the bottom of the x-stack
        cover = len(self._x_stack) + len(self._l_stack) - 1
        assert cover == store.depth, f"expected {cover=} == {store.depth=}"
        self._f_stack.append(local_id)
        self._apply_lstack_effects(store)

    def visit_store_f_stack(self, store: models.StoreFStack) -> None:
        assert self._l_stack, f"l-stack is empty, can not store {store.local_id} to f-stack"
        if store.insert:
            self._insert_f_stack(store)
        else:
            self._store_f_stack(store)

    def visit_load_f_stack(self, load: models.LoadFStack) -> None:
        local_id = load.local_id
        assert local_id in self._f_stack, f"{local_id} not found in f-stack"
        dig = self._get_f_stack_dig_bury(local_id)
        assert dig == load.depth, f"expected {dig=} == {load.depth=}"
        self._apply_lstack_effects(load)

    def visit_store_x_stack(self, store: models.StoreXStack) -> None:
        local_id = store.local_id
        assert self._l_stack, f"l-stack too small to store {local_id} to x-stack"

        cover = len(self._x_stack) + len(self._l_stack) - 1
        assert cover == store.depth, f"expected {cover=} == {store.depth=}"
        self._x_stack.insert(0, local_id)
        self._apply_lstack_effects(store)

    def visit_load_x_stack(self, load: models.LoadXStack) -> None:
        local_id = load.local_id
        assert local_id in self._x_stack, f"{local_id} not found in x-stack"
        index = self._x_stack.index(local_id)
        uncover = len(self._l_stack) + len(self._x_stack) - index - 1
        assert uncover == load.depth, f"expected {uncover=} == {load.depth=}"
        self._x_stack.pop(index)
        self._apply_lstack_effects(load)

    def visit_store_l_stack(self, store: models.StoreLStack) -> None:
        cover = store.depth
        local_id = store.local_id
        assert cover < len(
            self._l_stack
        ), f"l-stack too small to store (cover {cover}) {store.local_id} to l-stack"
        index = len(self._l_stack) - cover - 1
        self._l_stack.pop()
        self._l_stack.insert(index, local_id)
        self._apply_lstack_effects(store)

    def visit_load_l_stack(self, load: models.LoadLStack) -> None:
        local_id = load.local_id
        uncover = load.depth
        if uncover is None:  # during l-stack construction depth is not fixed
            index = self._l_stack.index(local_id)
        else:
            index = len(self._l_stack) - uncover - 1
        if not load.copy:
            self._l_stack.pop(index)
        self._apply_lstack_effects(load)

    def visit_load_param(self, load: models.LoadParam) -> None:
        assert load.local_id in self.parameters, f"{load.local_id} is not a parameter"
        self._apply_lstack_effects(load)

    def visit_store_param(self, store: models.StoreParam) -> None:
        assert store.local_id in self.parameters, f"{store.local_id} is not a parameter"
        self._apply_lstack_effects(store)

    def visit_pop(self, pop: models.Pop) -> None:
        self._apply_lstack_effects(pop)

    def visit_callsub(self, callsub: models.CallSub) -> None:
        self._apply_lstack_effects(callsub)

    def visit_retsub(self, retsub: models.RetSub) -> None:
        assert len(self._l_stack) == retsub.returns, (
            f"Inconsistent l-stack height for retsub,"
            f" expected {retsub.returns}, actual: {self._l_stack}"
        )

        # retsub moves return values down below the frame to the stack height before the sub was
        # called and discards anything above.
        # represent this in the virtual stack with a new stack state with only the current
        # l-stack (i.e. discard all values in parameters, f-stack and x-stack)
        self.parameters = []
        self._f_stack = []
        self._x_stack = []

    def visit_conditional_branch(self, op: models.ConditionalBranch) -> None:
        self._apply_lstack_effects(op)

    def visit_err(self, op: models.Err) -> None:
        self._apply_lstack_effects(op)

    def visit_goto(self, op: models.Goto) -> None:
        self._apply_lstack_effects(op)

    def visit_match(self, op: models.Match) -> None:
        self._apply_lstack_effects(op)

    def visit_program_exit(self, op: models.ProgramExit) -> None:
        self._apply_lstack_effects(op)

    def visit_switch(self, op: models.Switch) -> None:
        self._apply_lstack_effects(op)

    def visit_intrinsic(self, intrinsic: models.IntrinsicOp) -> None:
        self._apply_lstack_effects(intrinsic)

    def _apply_lstack_effects(self, op: models.BaseOp) -> None:
        assert len(self._l_stack) >= op.consumes, f"l-stack too small for {op}"
        start = len(self._l_stack) - op.consumes
        self._l_stack[start:] = op.produces
