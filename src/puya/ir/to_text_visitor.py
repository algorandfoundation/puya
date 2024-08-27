import contextlib
import typing
from collections.abc import Iterator, Sequence
from pathlib import Path

from puya import log
from puya.ir import models
from puya.ir.types_ import IRType
from puya.ir.utils import format_bytes
from puya.ir.visitor import IRVisitor
from puya.utils import make_path_relative_to_cwd

logger = log.get_logger(__name__)


class ToTextVisitor(IRVisitor[str]):
    def visit_assignment(self, op: models.Assignment) -> str:
        targets = ", ".join(f"{r.accept(self)}: {r.ir_type.name}" for r in op.targets)
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

    def visit_itxn_constant(self, op: models.ITxnConstant) -> str:
        return f"{op.ir_type.name}({op.value})"

    def visit_compiled_contract_reference(self, const: models.CompiledContractReference) -> str:
        return (
            ", ".join(
                (
                    f"compiled_contract({const.artifact!r}",
                    f"field={const.field.name}",
                    f"program_page={const.program_page}",
                    *(
                        f"{var}={val.accept(self)}"
                        for var, val in const.template_variables.items()
                    ),
                )
            )
            + ")"
        )

    def visit_compiled_logicsig_reference(self, const: models.CompiledLogicSigReference) -> str:
        return (
            ", ".join(
                (
                    f"compiled_logicsig({const.artifact!r}",
                    *(
                        f"{var}={val.accept(self)}"
                        for var, val in const.template_variables.items()
                    ),
                )
            )
            + ")"
        )

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

    def visit_inner_transaction_field(self, field: models.InnerTransactionField) -> str:
        group = field.group_index.accept(self)
        array_access = f"[{field.array_index.accept(self)}]" if field.array_index else ""
        return f"itxn[{group}].{field.field}{array_access}"

    def visit_invoke_subroutine(self, op: models.InvokeSubroutine) -> str:
        args = ", ".join(a.accept(self) for a in op.args)
        return f"{op.target.full_name}({args})"

    def visit_conditional_branch(self, op: models.ConditionalBranch) -> str:
        return f"goto {op.condition.accept(self)} ? block@{op.non_zero.id} : block@{op.zero.id}"

    def visit_goto(self, op: models.Goto) -> str:
        return f"goto block@{op.target.id}"

    def visit_goto_nth(self, op: models.GotoNth) -> str:
        blocks = ", ".join([f"block@{b.id}" for b in op.blocks])
        return f"goto_nth [{blocks}][{op.value.accept(self)}] else {op.default.accept(self)}"

    def visit_switch(self, op: models.Switch) -> str:
        cases = {k.accept(self): f"block@{b.id}" for k, b in op.cases.items()}
        if isinstance(op.default, models.Goto):
            cases["*"] = f"block@{op.default.target.id}"
        else:
            cases["*"] = op.default.accept(self)
        map_ = ", ".join(f"{k} => {v}" for k, v in cases.items())
        return f"switch {op.value.accept(self)} {{{map_}}}"

    def visit_subroutine_return(self, op: models.SubroutineReturn) -> str:
        results = " ".join(r.accept(self) for r in op.result)
        return f"return {results}"

    def visit_template_var(self, deploy_var: models.TemplateVar) -> str:
        return f"TemplateVar[{deploy_var.ir_type.name}]({deploy_var.name})"

    def visit_program_exit(self, op: models.ProgramExit) -> str:
        return f"exit {op.result.accept(self)}"

    def visit_fail(self, op: models.Fail) -> str:
        if op.comment:
            return f"fail // {op.comment}"
        return "fail"

    def visit_phi(self, op: models.Phi) -> str:
        r = op.register
        target = f"{r.accept(self)}: {r.ir_type.name}"
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
            args = ", ".join(f"{r.name}: {r.ir_type.name}" for r in sub.parameters)
            match sub.returns:
                case []:
                    returns = "void"
                case [IRType(name=returns)]:
                    pass
                case _ as ir_types:
                    returns = f"<{', '.join(t.name for t in ir_types)}>"
            emitter.append(f"subroutine {sub.full_name}({args}) -> {returns}:")
            with emitter.indent():
                render_body(emitter, sub.body)


def render_contract(emitter: TextEmitter, contract: models.Contract) -> None:
    emitter.append(f"contract {contract.metadata.ref}:")
    with emitter.indent():
        render_program(emitter, "approval", contract.approval_program)
        emitter.append("")
        render_program(emitter, "clear-state", contract.clear_program)


def render_logic_signature(emitter: TextEmitter, logic_sig: models.LogicSignature) -> None:
    render_program(emitter, f"logicsig {logic_sig.metadata.ref}", logic_sig.program)


def output_artifact_ir_to_path(artifact: models.ModuleArtifact, path: Path) -> None:
    emitter = TextEmitter()
    match artifact:
        case models.Contract():
            render_contract(emitter, artifact)
        case models.LogicSignature():
            render_logic_signature(emitter, artifact)
        case _:
            typing.assert_never(artifact)
    path.write_text("\n".join(emitter.lines), encoding="utf-8")
    logger.debug(f"Output IR to {make_path_relative_to_cwd(path)}")


def ir_to_text(module_irs: dict[str, list[models.Contract]]) -> list[str]:
    emitter = TextEmitter()

    all_contracts = (c for contracts in module_irs.values() for c in contracts)
    for contract in all_contracts:
        render_contract(emitter, contract)
    return emitter.lines
