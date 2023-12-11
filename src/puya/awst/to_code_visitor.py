import base64
import typing as t

from puya.awst import nodes, wtypes
from puya.awst.nodes import AppStateKind
from puya.awst.visitors import (
    ExpressionVisitor,
    ModuleStatementVisitor,
    StatementVisitor,
)
from puya.errors import InternalError


class ToCodeVisitor(
    ModuleStatementVisitor[list[str]],
    StatementVisitor[list[str]],
    ExpressionVisitor[str],
):
    def __init__(self) -> None:
        self._seen_tmp = dict[nodes.TemporaryVariable, int]()

    def _tmp_index(self, tmp: nodes.TemporaryVariable) -> int:
        return self._seen_tmp.setdefault(tmp, len(self._seen_tmp))

    def visit_module(self, module: nodes.Module) -> str:
        result = list[str]()
        for stmt in module.body:
            lines = stmt.accept(self)
            result.extend(lines)
        return "\n".join(result).strip()

    def visit_arc4_decode(self, expr: nodes.ARC4Decode) -> str:
        return f"arc4_decode({expr.value.accept(self)}, {expr.wtype})"

    def visit_arc4_encode(self, expr: nodes.ARC4Encode) -> str:
        return f"arc4_encode({expr.value.accept(self)}, {expr.wtype})"

    def visit_arc4_array_encode(self, expr: nodes.ARC4ArrayEncode) -> str:
        items = ", ".join([value.accept(self) for value in expr.values])
        return f"arc4_array_encode([{items}], {expr.wtype})"

    def visit_contains_expression(self, expr: nodes.Contains) -> str:
        return f"{expr.item.accept(self)} IS IN {expr.sequence.accept(self)}"

    def visit_reinterpret_cast(self, expr: nodes.ReinterpretCast) -> str:
        return f"reinterpret_cast<{expr.wtype}>({expr.expr.accept(self)})"

    def visit_temporary_variable(self, expr: nodes.TemporaryVariable) -> str:
        return f"tmp${self._tmp_index(expr)}"

    def visit_app_state_expression(self, expr: nodes.AppStateExpression) -> str:
        return f"this.globals[{bytes_str(expr.key)}]"

    def visit_app_account_state_expression(self, expr: nodes.AppAccountStateExpression) -> str:
        return f"this.locals[{bytes_str(expr.key)}].account[{expr.account.accept(self)}]"

    def visit_new_array(self, expr: nodes.NewArray) -> str:
        args = ", ".join(a.accept(self) for a in expr.elements)
        return f"new {expr.wtype.element_type}[]({args})"

    def visit_array_append(self, expr: nodes.ArrayAppend) -> str:
        base = expr.array.accept(self)
        elem = expr.element.accept(self)
        return f"{base}.append({elem})"

    def visit_new_struct(self, expr: nodes.NewStruct) -> str:
        args = ", ".join(
            [(f"{a.name}=" if a.name else "") + a.value.accept(self) for a in expr.args]
        )
        return f"new {expr.wtype}({args})"

    def visit_enumeration(self, expr: nodes.Enumeration) -> str:
        sequence = (
            self.visit_range(expr.expr)
            if isinstance(expr.expr, nodes.Range)
            else expr.expr.accept(self)
        )
        return f"enumerate({sequence})"

    def visit_bytes_comparison_expression(self, expr: nodes.BytesComparisonExpression) -> str:
        return f"{expr.lhs.accept(self)} {expr.operator} {expr.rhs.accept(self)}"

    def visit_subroutine_call_expression(self, expr: nodes.SubroutineCallExpression) -> str:
        match expr.target:
            case nodes.InstanceSubroutineTarget() as instance_sub:
                target = f"this::{instance_sub.name}"
            case nodes.BaseClassSubroutineTarget(
                name=func_name,
                base_class=nodes.ContractReference(module_name=module_name, class_name=class_name),
            ):
                target = "::".join((module_name, class_name, func_name))
            case nodes.FreeSubroutineTarget(module_name=module_name, name=func_name):
                target = "::".join((module_name, func_name))
            case _ as unhandled:
                raise InternalError(
                    f"Unhandled subroutine call expression target: {unhandled}",
                    expr.source_location,
                )
        args = ", ".join(
            [(f"{a.name}=" if a.name else "") + a.value.accept(self) for a in expr.args]
        )
        return f"{target}({args})"

    def visit_bytes_binary_operation(self, expr: nodes.BytesBinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    def visit_boolean_binary_operation(self, expr: nodes.BooleanBinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    def visit_not_expression(self, expr: nodes.Not) -> str:
        return f"!({expr.expr.accept(self)})"

    def visit_bytes_augmented_assignment(
        self, statement: nodes.BytesAugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    def visit_range(self, range_node: nodes.Range) -> str:
        range_args = ", ".join(
            [r.accept(self) for r in [range_node.start, range_node.stop, range_node.step]]
        )
        return f"range({range_args})"

    def visit_for_in_loop(self, statement: nodes.ForInLoop) -> list[str]:
        sequence = (
            self.visit_range(statement.sequence)
            if isinstance(statement.sequence, nodes.Range)
            else statement.sequence.accept(self)
        )
        loop_body = statement.loop_body.accept(self)
        item_vars = statement.items.accept(self)
        return [
            f"for {item_vars} in {sequence} {{",
            *_indent(loop_body),
            "}",
        ]

    def visit_subroutine(self, statement: nodes.Subroutine) -> list[str]:
        args = ", ".join([f"{a.name}: {a.wtype}" for a in statement.args])
        body = statement.body.accept(self)
        return [
            "",
            f"subroutine {statement.name}({args}): {statement.return_type}",
            "{",
            *_indent(body),
            "}",
        ]

    def visit_contract_fragment(self, c: nodes.ContractFragment) -> list[str]:
        body = list[str]()
        if c.app_state:
            state_by_kind = dict[AppStateKind, list[nodes.AppStateDefinition]]()
            for state in c.app_state:
                state_by_kind.setdefault(state.kind, []).append(state)
            global_state = state_by_kind.pop(AppStateKind.app_global, [])
            if global_state:
                body.extend(
                    [
                        "globals {",
                        *_indent(f"[{bytes_str(s.key)}]: {s.storage_wtype}" for s in global_state),
                        "}",
                    ]
                )
            local_state = state_by_kind.pop(AppStateKind.account_local, [])
            if local_state:
                body.extend(
                    [
                        "locals {",
                        *_indent(f"[{bytes_str(s.key)}]: {s.storage_wtype}" for s in local_state),
                        "}",
                    ]
                )
            if state_by_kind:
                raise InternalError(
                    f"Unhandled app state kinds: {', '.join(map(str, state_by_kind.keys()))}",
                    c.source_location,
                )
        for special_method, formatter in (
            (c.init, self.visit_contract_init),
            (c.approval_program, self.visit_approval_main),
            (c.clear_program, self.visit_clear_state_main),
        ):
            if special_method is not None:
                lines = formatter(special_method)
                body.extend(lines)
        for sub in c.subroutines:
            lines = sub.accept(self)
            body.extend(lines)

        if body and not body[0].strip():
            body = body[1:]

        header = ["contract", c.name]
        if c.is_abstract:
            header.insert(0, "abstract")

        if c.bases:
            header.append("extends")
            header.append(
                "("
                + ", ".join("::".join((cref.module_name, cref.class_name)) for cref in c.bases)
                + ")"
            )
        return [
            "",
            " ".join(header),
            "{",
            *_indent(body),
            "}",
        ]

    def visit_contract_init(self, statement: nodes.ContractMethod) -> list[str]:
        body = statement.body.accept(self)
        return [
            "",
            "constructor()",
            "{",
            *_indent(body),
            "}",
        ]

    def visit_approval_main(self, statement: nodes.ContractMethod) -> list[str]:
        body = statement.body.accept(self)
        return [
            "",
            f"approval_program(): {statement.return_type}",
            "{",
            *_indent(body),
            "}",
        ]

    def visit_clear_state_main(self, statement: nodes.ContractMethod) -> list[str]:
        body = statement.body.accept(self)
        return [
            "",
            f"clear_state_program(): {statement.return_type}",
            "{",
            *_indent(body),
            "}",
        ]

    def visit_contract_method(self, statement: nodes.ContractMethod) -> list[str]:
        body = statement.body.accept(self)
        args = ", ".join([f"{a.name}: {a.wtype}" for a in statement.args])
        if statement.abimethod_config is not None:
            if statement.abimethod_config.name != statement.name:
                deco = f"abimethod[name_override={statement.abimethod_config.name}]"
            else:
                deco = "abimethod"
        else:
            deco = "subroutine"
        return [
            "",
            f"{deco} {statement.name}({args}): {statement.return_type}",
            "{",
            *_indent(body),
            "}",
        ]

    def visit_assignment_expression(self, expr: nodes.AssignmentExpression) -> str:
        return f"{expr.target.accept(self)}: {expr.target.wtype} := {expr.value.accept(self)}"

    def visit_assignment_statement(self, stmt: nodes.AssignmentStatement) -> list[str]:
        return [f"{stmt.target.accept(self)}: {stmt.target.wtype} = {stmt.value.accept(self)}"]

    def visit_uint64_binary_operation(self, expr: nodes.UInt64BinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    def visit_biguint_binary_operation(self, expr: nodes.BigUIntBinaryOperation) -> str:
        return f"{expr.left.accept(self)} b{expr.op.value} {expr.right.accept(self)}"

    def visit_uint64_unary_operation(self, expr: nodes.UInt64UnaryOperation) -> str:
        return f"{expr.op.value}({expr.expr.accept(self)})"

    def visit_bytes_unary_operation(self, expr: nodes.BytesUnaryOperation) -> str:
        return f"b{expr.op.value}({expr.expr.accept(self)})"

    def visit_integer_constant(self, expr: nodes.IntegerConstant) -> str:
        if expr.teal_alias:
            return expr.teal_alias
        match expr.wtype:
            case wtypes.uint64_wtype:
                suffix = "u"
            case wtypes.biguint_wtype:
                suffix = "n"
            case wtypes.ARC4UIntN(n=n):
                if n <= 64:
                    suffix = f"arc4u{n}"
                else:
                    suffix = f"arc4n{n}"
            case _:
                raise InternalError(
                    f"Numeric type not implemented: {expr.wtype}", expr.source_location
                )
        return f"{expr.value}{suffix}"

    def visit_decimal_constant(self, expr: nodes.DecimalConstant) -> str:
        d = str(expr.value)
        if expr.wtype.n <= 64:
            suffix = f"arc4u{expr.wtype.n}x{expr.wtype.m}"
        else:
            suffix = f"arc4n{expr.wtype.n}x{expr.wtype.m}"
        return f"{d}{suffix}"

    def visit_bool_constant(self, expr: nodes.BoolConstant) -> str:
        return "true" if expr.value else "false"

    def visit_bytes_constant(self, expr: nodes.BytesConstant) -> str:
        match expr.encoding:
            case nodes.BytesEncoding.base16:
                return f'hex<"{expr.value.hex().upper()}">'
            case nodes.BytesEncoding.base32:
                return f'b32<"{base64.b32encode(expr.value).decode("ascii")}">'
            case nodes.BytesEncoding.base64:
                return f'b64<"{base64.b64encode(expr.value).decode("ascii")}">'
            case _:
                return bytes_str(expr.value)

    def visit_method_constant(self, expr: nodes.MethodConstant) -> str:
        return f'Method("{expr.value}")'

    def visit_address_constant(self, expr: nodes.AddressConstant) -> str:
        return f'Address("{expr.value}")'

    def visit_conditional_expression(self, expr: nodes.ConditionalExpression) -> str:
        condition = expr.condition.accept(self)
        true = expr.true_expr.accept(self)
        false = expr.false_expr.accept(self)
        return f"({condition}) ? ({true}) : ({false})"

    def visit_numeric_comparison_expression(self, expr: nodes.NumericComparisonExpression) -> str:
        return f"{expr.lhs.accept(self)} {expr.operator.value} {expr.rhs.accept(self)}"

    def visit_var_expression(self, expr: nodes.VarExpression) -> str:
        return expr.name

    def visit_checked_maybe(self, expr: nodes.CheckedMaybe) -> str:
        return f"checked_maybe({expr.expr.accept(self)})"

    def visit_intrinsic_call(self, expr: nodes.IntrinsicCall) -> str:
        result = expr.op_code
        if expr.immediates:
            result += "<" + ", ".join([str(immediate) for immediate in expr.immediates]) + ">"
        result += "("
        if expr.stack_args:
            result += ", ".join([stack_arg.accept(self) for stack_arg in expr.stack_args])
        result += ")"
        return result

    def visit_tuple_expression(self, expr: nodes.TupleExpression) -> str:
        items = ", ".join([item.accept(self) for item in expr.items])
        return f"({items})"

    def visit_tuple_item_expression(self, expr: nodes.TupleItemExpression) -> str:
        base = expr.base.accept(self)
        return f"{base}[{expr.index}]"

    def visit_field_expression(self, expr: nodes.FieldExpression) -> str:
        base = expr.base.accept(self)
        return f"{base}.{expr.name}"

    def visit_index_expression(self, expr: nodes.IndexExpression) -> str:
        return f"{expr.base.accept(self)}[{expr.index.accept(self)}]"

    def visit_slice_expression(self, expr: nodes.SliceExpression) -> str:
        start = expr.begin_index.accept(self) if expr.begin_index else ""
        stop = expr.end_index.accept(self) if expr.end_index else ""

        return f"{expr.base.accept(self)}[{start}:{stop}]"

    def visit_block(self, statement: nodes.Block) -> list[str]:
        return [line for statement in statement.body for line in statement.accept(self)]

    def visit_if_else(self, statement: nodes.IfElse) -> list[str]:
        if_branch = statement.if_branch.accept(self)
        if_block = [
            f"if ({statement.condition.accept(self)}) {{",
            *_indent(if_branch),
        ]
        if statement.else_branch is not None:
            else_branch = statement.else_branch.accept(self)
            else_block = ["} else {", *_indent(else_branch)]
        else:
            else_block = []
        return [*if_block, *else_block, "}"]

    def visit_switch(self, statement: nodes.Switch) -> list[str]:
        match_block = [f"switch ({statement.value.accept(self)}) {{"]
        for case_value, case_block in statement.cases.items():
            value = case_value.accept(self)
            block = case_block.accept(self)
            match_block.extend(
                _indent(
                    [
                        f"case {value}: {{",
                        *_indent(block),
                        "}",
                    ]
                )
            )
        if statement.default_case:
            default_block = statement.default_case.accept(self)
            match_block.extend(
                _indent(
                    [
                        "case _: {",
                        *_indent(default_block),
                        "}",
                    ]
                )
            )
        match_block.append("}")
        return match_block

    def visit_while_loop(self, statement: nodes.WhileLoop) -> list[str]:
        loop_body = statement.loop_body.accept(self)
        return [
            f"while ({statement.condition.accept(self)}) {{",
            *_indent(loop_body),
            "}",
        ]

    def visit_break_statement(self, _statement: nodes.BreakStatement) -> list[str]:
        return ["break"]

    def visit_constant_declaration(self, statement: nodes.ConstantDeclaration) -> list[str]:
        return [f"{statement.name} = {statement.value!r}"]

    def visit_return_statement(self, statement: nodes.ReturnStatement) -> list[str]:
        if not statement.value:
            return ["return"]
        return [f"return {statement.value.accept(self)}"]

    def visit_continue_statement(self, _statement: nodes.ContinueStatement) -> list[str]:
        return ["continue"]

    def visit_expression_statement(self, statement: nodes.ExpressionStatement) -> list[str]:
        return [
            statement.expr.accept(self),
        ]

    def visit_assert_statement(self, statement: nodes.AssertStatement) -> list[str]:
        condition = statement.condition.accept(self)
        if statement.comment is None:
            return [f"assert({condition})"]
        else:
            return [f'assert({condition}, comment="{statement.comment}")']

    def visit_uint64_augmented_assignment(
        self, statement: nodes.UInt64AugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    def visit_biguint_augmented_assignment(
        self, statement: nodes.BigUIntAugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    def visit_structure_definition(self, statement: nodes.StructureDefinition) -> list[str]:
        return [
            "",
            f"struct {statement.name} {{",
            *_indent(f"{f.name}: {f.wtype}" for f in statement.fields),
            "}",
        ]


def _indent(lines: t.Iterable[str], indent_size: str = "  ") -> t.Iterator[str]:
    yield from (f"{indent_size}{line}" for line in lines)


def bytes_str(b: bytes) -> str:
    return repr(b)[1:]
