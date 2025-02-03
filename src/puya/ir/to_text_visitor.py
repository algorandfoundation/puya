import contextlib
import typing
from collections.abc import Iterator, Sequence

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.types_ import IRType
from puya.ir.utils import format_bytes, format_error_comment
from puya.ir.visitor import IRVisitor
from puya.utils import make_path_relative_to_cwd

logger = log.get_logger(__name__)


class ToTextVisitor(IRVisitor[str]):
    @typing.override
    def visit_assignment(self, op: models.Assignment) -> str:
        targets = ", ".join(f"{r.accept(self)}: {r.ir_type.name}" for r in op.targets)
        if len(op.targets) > 1:
            targets = f"({targets})"
        source = op.source.accept(self)
        return f"let {targets} = {source}"

    @typing.override
    def visit_register(self, op: models.Register) -> str:
        return op.local_id

    @typing.override
    def visit_undefined(self, op: models.Undefined) -> str:
        return "undefined"

    @typing.override
    def visit_uint64_constant(self, op: models.UInt64Constant) -> str:
        return f"{op.value}u" if not op.teal_alias else op.teal_alias

    @typing.override
    def visit_biguint_constant(self, op: models.BigUIntConstant) -> str:
        return f"{op.value}b"

    @typing.override
    def visit_bytes_constant(self, op: models.BytesConstant) -> str:
        return format_bytes(op.value, op.encoding)

    @typing.override
    def visit_address_constant(self, op: models.AddressConstant) -> str:
        return f"addr {op.value}"

    @typing.override
    def visit_method_constant(self, op: models.MethodConstant) -> str:
        return f'method "{op.value}"'

    @typing.override
    def visit_itxn_constant(self, op: models.ITxnConstant) -> str:
        return f"{op.ir_type.name}({op.value})"

    @typing.override
    def visit_slot_constant(self, op: models.SlotConstant) -> str:
        return f"local.{op.value}"

    @typing.override
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

    @typing.override
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

    @typing.override
    def visit_new_slot(self, new_slot: models.NewSlot) -> str:
        return "new()"

    @typing.override
    def visit_read_slot(self, read: models.ReadSlot) -> str:
        slot = read.slot.accept(self)
        return f"read({slot})"

    @typing.override
    def visit_write_slot(self, write: models.WriteSlot) -> str:
        slot = write.slot.accept(self)
        value = write.value.accept(self)
        return f"write({slot}, {value})"

    @typing.override
    def visit_array_read_index(self, read: models.ArrayReadIndex) -> str:
        return f"{read.array.accept(self)}[{read.index.accept(self)}]"

    @typing.override
    def visit_array_write_index(self, write: models.ArrayWriteIndex) -> str:
        return (
            f"{write.array.accept(self)}[{write.index.accept(self)}] = {write.value.accept(self)}"
        )

    @typing.override
    def visit_array_concat(self, concat: models.ArrayConcat) -> str:
        return f"{concat.array.accept(self)}.concat({concat.other.accept(self)})"

    @typing.override
    def visit_array_encode(self, encode: models.ArrayEncode) -> str:
        values = ", ".join(val.accept(self) for val in encode.values)
        return f"encode<{encode.array_type.element}>({values})"

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> str:
        return f"{pop.array.accept(self)}.pop()"

    @typing.override
    def visit_array_length(self, pop: models.ArrayLength) -> str:
        return f"{pop.array.accept(self)}.length"

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> str:
        callee = intrinsic.op.code
        immediates = list(map(str, intrinsic.immediates))
        if immediates:
            callee = f"({' '.join((callee, *immediates))})"
        args = " ".join(arg.accept(self) for arg in intrinsic.args)
        if args:
            callee = f"({callee} {args})"
        if intrinsic.error_message:
            callee += f" // {format_error_comment(intrinsic.op.code, intrinsic.error_message)}"
        return callee

    @typing.override
    def visit_inner_transaction_field(self, field: models.InnerTransactionField) -> str:
        group = field.group_index.accept(self)
        array_access = f"[{field.array_index.accept(self)}]" if field.array_index else ""
        return f"itxn[{group}].{field.field}{array_access}"

    @typing.override
    def visit_invoke_subroutine(self, op: models.InvokeSubroutine) -> str:
        args = ", ".join(a.accept(self) for a in op.args)
        return f"{op.target.id}({args})"

    @typing.override
    def visit_conditional_branch(self, op: models.ConditionalBranch) -> str:
        return f"goto {op.condition.accept(self)} ? {op.non_zero} : {op.zero}"

    @typing.override
    def visit_goto(self, op: models.Goto) -> str:
        return f"goto {op.target}"

    @typing.override
    def visit_goto_nth(self, op: models.GotoNth) -> str:
        blocks = ", ".join(map(str, op.blocks))
        return f"goto_nth [{blocks}][{op.value.accept(self)}] else goto {op.default}"

    @typing.override
    def visit_switch(self, op: models.Switch) -> str:
        cases = {k.accept(self): str(b) for k, b in op.cases.items()}
        cases["*"] = str(op.default)
        map_ = ", ".join(f"{k} => {v}" for k, v in cases.items())
        return f"switch {op.value.accept(self)} {{{map_}}}"

    @typing.override
    def visit_subroutine_return(self, op: models.SubroutineReturn) -> str:
        results = " ".join(r.accept(self) for r in op.result)
        return f"return {results}"

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> str:
        return f"TemplateVar[{deploy_var.ir_type.name}]({deploy_var.name})"

    @typing.override
    def visit_program_exit(self, op: models.ProgramExit) -> str:
        return f"exit {op.result.accept(self)}"

    @typing.override
    def visit_fail(self, op: models.Fail) -> str:
        if op.error_message:
            return f"fail // {op.error_message}"
        return "fail"

    @typing.override
    def visit_phi(self, op: models.Phi) -> str:
        r = op.register
        target = f"{r.accept(self)}: {r.ir_type.name}"
        if op.args:
            args = ", ".join(a.accept(self) for a in op.args)
            source = f"φ({args})"
        else:
            source = "undefined"
        return f"let {target} = {source}"

    @typing.override
    def visit_phi_argument(self, op: models.PhiArgument) -> str:
        return f"{op.value.accept(self)} <- {op.through}"

    @typing.override
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


def _render_block_name(block: models.BasicBlock) -> str:
    result = f"{block}: // "
    if block.comment:
        result += f"{block.comment}_"
    result += f"L{block.source_location.line}"
    return result


def _render_body(emitter: TextEmitter, blocks: Sequence[models.BasicBlock]) -> None:
    renderer = ToTextVisitor()
    for block in blocks:
        assert block.terminated
        emitter.append(_render_block_name(block))
        with emitter.indent():
            for op in block.all_ops:
                emitter.append(op.accept(renderer))


def render_program(
    context: ArtifactCompileContext, program: models.Program, *, qualifier: str
) -> None:
    path = context.build_output_path(program.kind, qualifier, "ir")
    if path is None:
        return
    emitter = TextEmitter()
    if program.slot_allocation.strategy != models.SlotAllocationStrategy.none:
        emitter.append(
            f"slot_allocation({program.slot_allocation.strategy.name},"
            f" reserved={sorted(program.slot_allocation.reserved)})"
        )
    emitter.append(f"main {program.main.id}:")
    with emitter.indent():
        _render_body(emitter, program.main.body)
    for sub in program.subroutines:
        emitter.append("")
        args = ", ".join(f"{r.name}: {r.ir_type.name}" for r in sub.parameters)
        match sub.returns:
            case []:
                returns = "void"
            case [IRType(name=returns)]:
                pass
            case _ as ir_types:
                returns = f"<{', '.join(t.name for t in ir_types)}>"
        emitter.append(f"subroutine {sub.id}({args}) -> {returns}:")
        with emitter.indent():
            _render_body(emitter, sub.body)
    path.write_text("\n".join(emitter.lines), encoding="utf-8")
    logger.debug(f"Output IR to {make_path_relative_to_cwd(path)}")
