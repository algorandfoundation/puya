import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path

import structlog

from puya.avm_type import AVMType
from puya.codegen.utils import format_bytes
from puya.ir import models
from puya.ir.visitor import IRVisitor

logger = structlog.get_logger(__name__)


class ToTextVisitor(IRVisitor[str]):
    def visit_assignment(self, op: models.Assignment) -> str:
        targets = ", ".join(f"{r.accept(self)}: {r.atype.name}" for r in op.targets)
        if len(op.targets) > 1:
            targets = f"({targets})"
        source = op.source.accept(self)
        return f"let {targets} = {source}"

    def visit_register(self, op: models.Register) -> str:
        return op.local_id

    def visit_uint64_constant(self, op: models.UInt64Constant) -> str:
        return f"{op.value}u" if not op.teal_alias else op.teal_alias

    def visit_biguint_constant(self, op: models.BigUIntConstant) -> str:
        return f"{op.value}b"

    def visit_bytes_constant(self, op: models.BytesConstant) -> str:
        return format_bytes(op.value, op.encoding)

    def visit_address_constant(self, op: models.AddressConstant) -> str:
        return f"addr {op.value}"

    def visit_method_constant(self, op: models.MethodConstant) -> str:
        return f'method "{op.value}"'

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> str:
        callee = intrinsic.op.code
        immediates = list(map(str, intrinsic.immediates))
        if immediates:
            callee = f"({' '.join((callee, *immediates))})"
        args = " ".join(arg.accept(self) for arg in intrinsic.args)
        if args:
            callee = f"({callee} {args})"
        if intrinsic.comment:
            callee += f" // {intrinsic.comment}"
        return callee

    def visit_invoke_subroutine(self, op: models.InvokeSubroutine) -> str:
        args = ", ".join(a.accept(self) for a in op.args)
        return f"{op.target.full_name}({args})"

    def visit_conditional_branch(self, op: models.ConditionalBranch) -> str:
        return f"goto {op.condition.accept(self)} ? block@{op.non_zero.id} : block@{op.zero.id}"

    def visit_goto(self, op: models.Goto) -> str:
        return f"goto block@{op.target.id}"

    def visit_goto_nth(self, op: models.GotoNth) -> str:
        blocks = ", ".join([f"block@{b.id}" for b in op.blocks])
        return f"goto [{blocks}, ...block@{op.default.id}][{op.value.accept(self)}]"

    def visit_switch(self, op: models.Switch) -> str:
        cases = {k.accept(self): f"block@{b.id}" for k, b in op.cases.items()}
        cases["*"] = f"block@{op.default.id}"
        map_ = ", ".join(f"{k} => {v}" for k, v in cases.items())
        return f"switch {op.value.accept(self)} {{{map_}}}"

    def visit_subroutine_return(self, op: models.SubroutineReturn) -> str:
        results = " ".join(r.accept(self) for r in op.result)
        return f"return {results}"

    def visit_program_exit(self, op: models.ProgramExit) -> str:
        return f"exit {op.result.accept(self)}"

    def visit_fail(self, op: models.Fail) -> str:
        if op.comment:
            return f"fail // {op.comment}"
        return "fail"

    def visit_phi(self, op: models.Phi) -> str:
        r = op.register
        target = f"{r.accept(self)}: {r.atype.name}"
        if op.args:
            args = ", ".join(a.accept(self) for a in op.args)
            source = f"φ({args})"
        else:
            source = "undefined"
        return f"let {target} = {source}"

    def visit_phi_argument(self, op: models.PhiArgument) -> str:
        return f"{op.value.accept(self)} <- block@{op.through.id}"

    def visit_value_tuple(self, tup: models.ValueTuple) -> str:
        return "(" + ", ".join(val.accept(self) for val in tup.values) + ")"


class TextEmitter:
    def __init__(self) -> None:
        self.lines = list[str]()
        self._indent = 0

    def append(self, line: str) -> None:
        self.lines.append((self._indent * " ") + line)

    @contextlib.contextmanager
    def indent(self, spaces: int = 4) -> Iterator[None]:
        self._indent += spaces
        try:
            yield
        finally:
            self._indent -= spaces


def render_body(emitter: TextEmitter, blocks: Sequence[models.BasicBlock]) -> None:
    renderer = ToTextVisitor()
    for block in blocks:
        assert block.terminated
        emitter.append(str(block))
        with emitter.indent():
            for op in block.all_ops:
                emitter.append(op.accept(renderer))


def render_program(emitter: TextEmitter, name: str, program: models.Program) -> None:
    emitter.append(f"program {name}:")
    with emitter.indent():
        for idx, sub in enumerate(program.all_subroutines):
            if idx > 0:
                emitter.append("")
            args = ", ".join(f"{r.name}: {r.atype.name}" for r in sub.parameters)
            match sub.returns:
                case []:
                    returns = "void"
                case [AVMType(name=returns)]:
                    pass
                case _ as atypes:
                    returns = f"<{', '.join(t.name for t in atypes)}>"  # type: ignore[misc]
            emitter.append(f"subroutine {sub.full_name}({args}) -> {returns}:")
            with emitter.indent():
                render_body(emitter, sub.body)


def render_contract(emitter: TextEmitter, contract: models.Contract) -> None:
    emitter.append(f"contract {contract.metadata.full_name}:")
    with emitter.indent():
        render_program(emitter, "approval", contract.approval_program)
        emitter.append("")
        render_program(emitter, "clear-state", contract.clear_program)


def output_contract_ir_to_path(contract: models.Contract, path: Path) -> None:
    emitter = TextEmitter()

    render_contract(emitter, contract)
    path.write_text("\n".join(emitter.lines), encoding="utf-8")
    logger.debug(f"Output IR to {path}")


def ir_to_text(module_irs: dict[str, list[models.Contract]]) -> list[str]:
    emitter = TextEmitter()

    all_contracts = (c for contracts in module_irs.values() for c in contracts)
    for contract in all_contracts:
        render_contract(emitter, contract)
    return emitter.lines
