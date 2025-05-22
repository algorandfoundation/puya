import base64
import typing
from collections.abc import Iterable, Iterator, Mapping

from puya.awst import nodes, wtypes
from puya.awst.visitors import (
    ContractMemberVisitor,
    ExpressionVisitor,
    RootNodeVisitor,
    StatementVisitor,
)
from puya.errors import InternalError


class ToCodeVisitor(
    RootNodeVisitor[list[str]],
    StatementVisitor[list[str]],
    ExpressionVisitor[str],
    ContractMemberVisitor[list[str]],
):
    def __init__(self) -> None:
        self._seen_single_evals = dict[nodes.SingleEvaluation, int]()

    def _single_eval_index(self, tmp: nodes.SingleEvaluation) -> int:
        return self._seen_single_evals.setdefault(tmp, len(self._seen_single_evals))

    @typing.override
    def visit_array_concat(self, expr: nodes.ArrayConcat) -> str:
        left = expr.left.accept(self)
        right = expr.right.accept(self)
        return f"{left} + {right}"

    @typing.override
    def visit_array_extend(self, expr: nodes.ArrayExtend) -> str:
        base = expr.base.accept(self)
        value = expr.other.accept(self)
        return f"{base}.extend({value})"

    @typing.override
    def visit_array_pop(self, expr: nodes.ArrayPop) -> str:
        base = expr.base.accept(self)
        return f"{base}.pop()"

    @typing.override
    def visit_array_length(self, expr: nodes.ArrayLength) -> str:
        base = expr.array.accept(self)
        return f"{base}.length"

    @typing.override
    def visit_array_replace(self, expr: nodes.ArrayReplace) -> str:
        base = expr.base.accept(self)
        index = expr.index.accept(self)
        value = expr.value.accept(self)
        return f"{base}.replace({index}, {value})"

    @typing.override
    def visit_copy(self, expr: nodes.Copy) -> str:
        value = expr.value.accept(self)
        return f"{value}.copy()"

    @typing.override
    def visit_reversed(self, expr: nodes.Reversed) -> str:
        sequence = expr.expr.accept(self)
        return f"reversed({sequence})"

    def visit_module(self, module: nodes.AWST) -> str:
        result = list[str]()
        for stmt in module:
            lines = stmt.accept(self)
            result.extend(lines)
        return "\n".join(result).strip()

    @typing.override
    def visit_arc4_decode(self, expr: nodes.ARC4Decode) -> str:
        return f"arc4_decode({expr.value.accept(self)}, {expr.wtype})"

    @typing.override
    def visit_arc4_encode(self, expr: nodes.ARC4Encode) -> str:
        return f"arc4_encode({expr.value.accept(self)}, {expr.wtype})"

    @typing.override
    def visit_reinterpret_cast(self, expr: nodes.ReinterpretCast) -> str:
        return f"reinterpret_cast<{expr.wtype}>({expr.expr.accept(self)})"

    @typing.override
    def visit_single_evaluation(self, expr: nodes.SingleEvaluation) -> str:
        # only render source the first time it is encountered
        source = "" if expr in self._seen_single_evals else f", source={expr.source.accept(self)}"
        eval_id = self._single_eval_index(expr)

        return "".join(
            (
                f"SINGLE_EVAL(id={eval_id}",
                source,
                ")",
            )
        )

    @typing.override
    def visit_app_state_expression(self, expr: nodes.AppStateExpression) -> str:
        return f"GlobalState[{expr.key.accept(self)}]"

    @typing.override
    def visit_app_account_state_expression(self, expr: nodes.AppAccountStateExpression) -> str:
        return f"LocalState[{expr.key.accept(self)}, {expr.account.accept(self)}]"

    @typing.override
    def visit_box_prefixed_key_expression(self, expr: nodes.BoxPrefixedKeyExpression) -> str:
        return f"BoxMapKey(prefix={expr.prefix.accept(self)}, key={expr.key.accept(self)})"

    @typing.override
    def visit_box_value_expression(self, expr: nodes.BoxValueExpression) -> str:
        return f"Box[{expr.key.accept(self)}]"

    @typing.override
    def visit_new_array(self, expr: nodes.NewArray) -> str:
        args = ", ".join(a.accept(self) for a in expr.values)
        return f"new {expr.wtype}({args})"

    @typing.override
    def visit_new_struct(self, expr: nodes.NewStruct) -> str:
        args = ", ".join([f"{name}=" + value.accept(self) for name, value in expr.values.items()])
        return f"new {expr.wtype}({args})"

    @typing.override
    def visit_enumeration(self, expr: nodes.Enumeration) -> str:
        sequence = expr.expr.accept(self)
        return f"enumerate({sequence})"

    @typing.override
    def visit_bytes_comparison_expression(self, expr: nodes.BytesComparisonExpression) -> str:
        return f"{expr.lhs.accept(self)} {expr.operator} {expr.rhs.accept(self)}"

    @typing.override
    def visit_subroutine_call_expression(self, expr: nodes.SubroutineCallExpression) -> str:
        match expr.target:
            case nodes.InstanceMethodTarget(member_name=member_name):
                target = f"this::{member_name}"
            case nodes.InstanceSuperMethodTarget(member_name=member_name):
                target = f"super::{member_name}"
            case nodes.ContractMethodTarget(cref=cref, member_name=member_name):
                target = "::".join((cref, member_name))
            case nodes.SubroutineID(target):
                pass
            case unhandled:
                typing.assert_never(unhandled)
        args = ", ".join(
            [(f"{a.name}=" if a.name else "") + a.value.accept(self) for a in expr.args]
        )
        return f"{target}({args})"

    @typing.override
    def visit_bytes_binary_operation(self, expr: nodes.BytesBinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    @typing.override
    def visit_boolean_binary_operation(self, expr: nodes.BooleanBinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    @typing.override
    def visit_not_expression(self, expr: nodes.Not) -> str:
        return f"!({expr.expr.accept(self)})"

    @typing.override
    def visit_bytes_augmented_assignment(
        self, statement: nodes.BytesAugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    @typing.override
    def visit_range(self, range_node: nodes.Range) -> str:
        range_args = ", ".join(
            [r.accept(self) for r in [range_node.start, range_node.stop, range_node.step]]
        )
        return f"range({range_args})"

    @typing.override
    def visit_for_in_loop(self, statement: nodes.ForInLoop) -> list[str]:
        sequence = statement.sequence.accept(self)
        loop_body = statement.loop_body.accept(self)
        item_vars = statement.items.accept(self)
        return [
            f"for {item_vars} in {sequence} {{",
            *_indent(loop_body),
            "}",
        ]

    @typing.override
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

    @typing.override
    def visit_app_storage_definition(self, defn: nodes.AppStorageDefinition) -> list[str]:
        raise InternalError("app storage is converted as part of class")

    @typing.override
    def visit_contract(self, c: nodes.Contract) -> list[str]:
        body = [
            "method_resolution_order: (",
            *_indent(f"{cref}," for cref in c.method_resolution_order),
            ")",
        ]
        if c.app_state:
            state_by_kind = dict[nodes.AppStorageKind, list[nodes.AppStorageDefinition]]()
            for state in c.app_state:
                state_by_kind.setdefault(state.kind, []).append(state)
            for kind_name, kind in (
                ("globals", nodes.AppStorageKind.app_global),
                ("locals", nodes.AppStorageKind.account_local),
                ("boxes", nodes.AppStorageKind.box),
            ):
                state_of_kind = state_by_kind.pop(kind, [])
                if state_of_kind:
                    body.extend(
                        [
                            f"{kind_name} {{",
                            *_indent(
                                (
                                    f"[{s.key.accept(self)}]: {s.key_wtype} => {s.storage_wtype}"
                                    if s.key_wtype is not None
                                    else f"[{s.key.accept(self)}]: {s.storage_wtype}"
                                )
                                for s in state_of_kind
                            ),
                            "}",
                        ]
                    )
            if state_by_kind:
                raise InternalError(
                    f"Unhandled app state kinds: {', '.join(map(str, state_by_kind.keys()))}",
                    c.source_location,
                )
        if c.reserved_scratch_space:
            body.extend(
                [
                    "reserved_scratch_space {",
                    *_indent([", ".join(_collapse_sequential_ranges(c.reserved_scratch_space))]),
                    "}",
                ]
            )
        for sub in c.all_methods:
            lines = sub.accept(self)
            body.extend(lines)

        if body and not body[0].strip():
            body = body[1:]

        header = ["contract", c.name]

        return [
            "",
            " ".join(header),
            "{",
            *_indent(body),
            "}",
        ]

    @typing.override
    def visit_logic_signature(self, statement: nodes.LogicSignature) -> list[str]:
        body = statement.program.body.accept(self)
        return [
            "",
            f"logicsig {statement.id}",
            "{",
            *_indent(body),
            "}",
        ]

    @typing.override
    def visit_contract_method(self, statement: nodes.ContractMethod) -> list[str]:
        body = statement.body.accept(self)
        args = ", ".join([f"{a.name}: {a.wtype}" for a in statement.args])
        match statement.arc4_method_config:
            case None:
                deco = "subroutine"
            case nodes.ARC4BareMethodConfig():
                deco = "baremethod"
            case nodes.ARC4ABIMethodConfig(name=config_name):
                if statement.member_name != config_name:
                    deco = f"abimethod[name_override={config_name}]"
                else:
                    deco = "abimethod"
            case other:
                typing.assert_never(other)

        return [
            "",
            f"{deco} {statement.full_name}({args}): {statement.return_type}",
            "{",
            *_indent(body),
            "}",
        ]

    @typing.override
    def visit_assignment_expression(self, expr: nodes.AssignmentExpression) -> str:
        return f"{expr.target.accept(self)}: {expr.target.wtype} := {expr.value.accept(self)}"

    @typing.override
    def visit_assignment_statement(self, stmt: nodes.AssignmentStatement) -> list[str]:
        return [f"{stmt.target.accept(self)}: {stmt.target.wtype} = {stmt.value.accept(self)}"]

    @typing.override
    def visit_uint64_binary_operation(self, expr: nodes.UInt64BinaryOperation) -> str:
        return f"{expr.left.accept(self)} {expr.op.value} {expr.right.accept(self)}"

    @typing.override
    def visit_biguint_binary_operation(self, expr: nodes.BigUIntBinaryOperation) -> str:
        return f"{expr.left.accept(self)} b{expr.op.value} {expr.right.accept(self)}"

    @typing.override
    def visit_uint64_unary_operation(self, expr: nodes.UInt64UnaryOperation) -> str:
        return f"{expr.op.value}({expr.expr.accept(self)})"

    @typing.override
    def visit_bytes_unary_operation(self, expr: nodes.BytesUnaryOperation) -> str:
        return f"b{expr.op.value}({expr.expr.accept(self)})"

    @typing.override
    def visit_integer_constant(self, expr: nodes.IntegerConstant) -> str:
        if expr.teal_alias:
            return expr.teal_alias
        match expr.wtype:
            case wtypes.uint64_wtype:
                suffix = "u"
            case wtypes.biguint_wtype:
                suffix = "n"
            case wtypes.ARC4UIntN(n=n):
                suffix = f"_arc4u{n}"
            case _:
                raise InternalError(
                    f"Numeric type not implemented: {expr.wtype}", expr.source_location
                )
        return f"{expr.value}{suffix}"

    @typing.override
    def visit_decimal_constant(self, expr: nodes.DecimalConstant) -> str:
        d = str(expr.value)
        if expr.wtype.n <= 64:
            suffix = f"arc4u{expr.wtype.n}x{expr.wtype.m}"
        else:
            suffix = f"arc4n{expr.wtype.n}x{expr.wtype.m}"
        return f"{d}{suffix}"

    @typing.override
    def visit_bool_constant(self, expr: nodes.BoolConstant) -> str:
        return "true" if expr.value else "false"

    @typing.override
    def visit_bytes_constant(self, expr: nodes.BytesConstant) -> str:
        match expr.encoding:
            case nodes.BytesEncoding.utf8:
                return _bytes_str(expr.value)
            case nodes.BytesEncoding.base32:
                return f'b32<"{base64.b32encode(expr.value).decode("ascii")}">'
            case nodes.BytesEncoding.base64:
                return f'b64<"{base64.b64encode(expr.value).decode("ascii")}">'
            case nodes.BytesEncoding.base16 | nodes.BytesEncoding.unknown:
                return f'hex<"{expr.value.hex().upper()}">'

    @typing.override
    def visit_string_constant(self, expr: nodes.StringConstant) -> str:
        return repr(expr.value)

    @typing.override
    def visit_void_constant(self, expr: nodes.VoidConstant) -> str:
        return "void"

    @typing.override
    def visit_method_constant(self, expr: nodes.MethodConstant) -> str:
        return f'Method("{expr.value}")'

    @typing.override
    def visit_address_constant(self, expr: nodes.AddressConstant) -> str:
        return f'Address("{expr.value}")'

    @typing.override
    def visit_compiled_contract(self, expr: nodes.CompiledContract) -> str:
        template_vars_fragment = self._template_vars_fragment(expr.prefix, expr.template_variables)
        overrides = ", ".join(
            f"{k.name}={v.accept(self)}" for k, v in expr.allocation_overrides.items()
        )
        return f"compiled_contract({expr.contract},{overrides},{template_vars_fragment})"

    @typing.override
    def visit_compiled_logicsig(self, expr: nodes.CompiledLogicSig) -> str:
        template_vars_fragment = self._template_vars_fragment(expr.prefix, expr.template_variables)
        return f"compiled_logicsig({expr.logic_sig!r}{template_vars_fragment})"

    def _template_vars_fragment(
        self, prefix: str | None, variables: Mapping[str, nodes.Expression]
    ) -> str:
        variables_str = ", ".join(f"{k!r}: {v.accept(self)}" for k, v in variables.items())
        return f", {prefix=!r}, variables={{{variables_str}}}"

    @typing.override
    def visit_conditional_expression(self, expr: nodes.ConditionalExpression) -> str:
        condition = expr.condition.accept(self)
        true = expr.true_expr.accept(self)
        false = expr.false_expr.accept(self)
        return f"({condition}) ? ({true}) : ({false})"

    @typing.override
    def visit_numeric_comparison_expression(self, expr: nodes.NumericComparisonExpression) -> str:
        return f"{expr.lhs.accept(self)} {expr.operator.value} {expr.rhs.accept(self)}"

    @typing.override
    def visit_var_expression(self, expr: nodes.VarExpression) -> str:
        return expr.name

    @typing.override
    def visit_checked_maybe(self, expr: nodes.CheckedMaybe) -> str:
        return f"checked_maybe({expr.expr.accept(self)})"

    @typing.override
    def visit_intrinsic_call(self, expr: nodes.IntrinsicCall) -> str:
        result = expr.op_code
        if expr.immediates:
            result += "<" + ", ".join([str(immediate) for immediate in expr.immediates]) + ">"
        result += "("
        if expr.stack_args:
            result += ", ".join([stack_arg.accept(self) for stack_arg in expr.stack_args])
        result += ")"
        return result

    def visit_size_of(self, call: nodes.SizeOf) -> str:
        return f"size_of({call.size_wtype.name})"

    @typing.override
    def visit_puya_lib_call(self, expr: nodes.PuyaLibCall) -> str:
        result = expr.func.value.id
        result += "("
        if expr.args:
            result += ", ".join(
                [(f"{a.name}=" if a.name else "") + a.value.accept(self) for a in expr.args]
            )
        result += ")"
        return result

    @typing.override
    def visit_group_transaction_reference(self, ref: nodes.GroupTransactionReference) -> str:
        if ref.wtype.transaction_type is None:
            type_ = "any"
        else:
            type_ = ref.wtype.transaction_type.name
        return f"group_transaction(index={ref.index.accept(self)}, type={type_})"

    @typing.override
    def visit_create_inner_transaction(self, expr: nodes.CreateInnerTransaction) -> str:
        fields = []
        for field, value in expr.fields.items():
            fields.append(f"{field.immediate}={value.accept(self)}")
        return f"create_inner_transaction({', '.join(fields)})"

    @typing.override
    def visit_update_inner_transaction(self, expr: nodes.UpdateInnerTransaction) -> str:
        fields = []
        for field, value in expr.fields.items():
            fields.append(f"{field.immediate}={value.accept(self)}")
        return f"update_inner_transaction({expr.itxn.accept(self)},{', '.join(fields)})"

    @typing.override
    def visit_set_inner_transaction_fields(self, node: nodes.SetInnerTransactionFields) -> str:
        begin_or_next = "begin" if node.start_with_begin else "next"
        itxns = f'{", ".join(itxn.accept(self) for itxn in node.itxns)}'

        return f"{begin_or_next}_txn({itxns})"

    @typing.override
    def visit_submit_inner_transaction(self, call: nodes.SubmitInnerTransaction) -> str:
        itxns = f'{", ".join(itxn.accept(self) for itxn in call.itxns)}'
        return f"submit_txn({itxns})"

    @typing.override
    def visit_inner_transaction_field(self, itxn_field: nodes.InnerTransactionField) -> str:
        txn = itxn_field.itxn.accept(self)
        result = f"{txn}.{itxn_field.field.immediate}"
        if itxn_field.array_index is not None:
            index = itxn_field.array_index.accept(self)
            result = f"{result}[{index}]"
        return result

    @typing.override
    def visit_tuple_expression(self, expr: nodes.TupleExpression) -> str:
        if expr.wtype.names:
            items = ", ".join(
                [
                    f"{name}={item.accept(self)}"
                    for name, item in zip(expr.wtype.names, expr.items, strict=True)
                ]
            )
        else:
            items = ", ".join([item.accept(self) for item in expr.items])
        return f"({items})"

    @typing.override
    def visit_tuple_item_expression(self, expr: nodes.TupleItemExpression) -> str:
        base = expr.base.accept(self)
        return f"{base}[{expr.index}]"

    @typing.override
    def visit_field_expression(self, expr: nodes.FieldExpression) -> str:
        base = expr.base.accept(self)
        return f"{base}.{expr.name}"

    @typing.override
    def visit_index_expression(self, expr: nodes.IndexExpression) -> str:
        return f"{expr.base.accept(self)}[{expr.index.accept(self)}]"

    @typing.override
    def visit_slice_expression(self, expr: nodes.SliceExpression) -> str:
        start = expr.begin_index.accept(self) if expr.begin_index else ""
        stop = expr.end_index.accept(self) if expr.end_index else ""

        return f"{expr.base.accept(self)}[{start}:{stop}]"

    @typing.override
    def visit_intersection_slice_expression(self, expr: nodes.IntersectionSliceExpression) -> str:
        start = (
            expr.begin_index.accept(self)
            if isinstance(expr.begin_index, nodes.Expression)
            else (expr.begin_index if expr.begin_index is not None else "")
        )
        stop = (
            expr.end_index.accept(self)
            if isinstance(expr.end_index, nodes.Expression)
            else (expr.end_index if expr.end_index is not None else "")
        )

        return f"{expr.base.accept(self)}[{start}:{stop}]"

    @typing.override
    def visit_block(self, statement: nodes.Block) -> list[str]:
        statements = [line for statement in statement.body for line in statement.accept(self)]
        if statement.label:
            return [f"{statement.label}:", *statements]
        return statements

    @typing.override
    def visit_goto(self, statement: nodes.Goto) -> list[str]:
        return [f"goto {statement.target}"]

    @typing.override
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

    @typing.override
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

    @typing.override
    def visit_while_loop(self, statement: nodes.WhileLoop) -> list[str]:
        loop_body = statement.loop_body.accept(self)
        return [
            f"while ({statement.condition.accept(self)}) {{",
            *_indent(loop_body),
            "}",
        ]

    @typing.override
    def visit_loop_exit(self, _statement: nodes.LoopExit) -> list[str]:
        return ["break"]

    @typing.override
    def visit_return_statement(self, statement: nodes.ReturnStatement) -> list[str]:
        if not statement.value:
            return ["return"]
        return [f"return {statement.value.accept(self)}"]

    @typing.override
    def visit_assert_expression(self, statement: nodes.AssertExpression) -> str:
        error_message = "" if statement.error_message is None else f'"{statement.error_message}"'
        if not statement.condition:
            result = "err("
            if error_message:
                result += error_message
            result += ")"
        else:
            result = f"assert({statement.condition.accept(self)}"
            if error_message:
                result += f", comment={error_message}"
            result += ")"
        return result

    @typing.override
    def visit_loop_continue(self, _statement: nodes.LoopContinue) -> list[str]:
        return ["continue"]

    @typing.override
    def visit_expression_statement(self, statement: nodes.ExpressionStatement) -> list[str]:
        return [
            statement.expr.accept(self),
        ]

    @typing.override
    def visit_uint64_augmented_assignment(
        self, statement: nodes.UInt64AugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    @typing.override
    def visit_biguint_augmented_assignment(
        self, statement: nodes.BigUIntAugmentedAssignment
    ) -> list[str]:
        return [
            f"{statement.target.accept(self)} {statement.op.value}= {statement.value.accept(self)}"
        ]

    @typing.override
    def visit_state_get_ex(self, expr: nodes.StateGetEx) -> str:
        return f"STATE_GET_EX({expr.field.accept(self)})"

    @typing.override
    def visit_state_delete(self, statement: nodes.StateDelete) -> str:
        return f"STATE_DELETE({statement.field.accept(self)})"

    @typing.override
    def visit_state_get(self, expr: nodes.StateGet) -> str:
        return f"STATE_GET({expr.field.accept(self)}, default={expr.default.accept(self)})"

    @typing.override
    def visit_state_exists(self, expr: nodes.StateExists) -> str:
        return f"STATE_EXISTS({expr.field.accept(self)})"

    @typing.override
    def visit_template_var(self, expr: nodes.TemplateVar) -> str:
        return f"TemplateVar[{expr.wtype}]({expr.name})"

    @typing.override
    def visit_biguint_postfix_unary_operation(
        self, expr: nodes.BigUIntPostfixUnaryOperation
    ) -> str:
        return f"{expr.target.accept(self)}{expr.op}"

    @typing.override
    def visit_uint64_postfix_unary_operation(self, expr: nodes.UInt64PostfixUnaryOperation) -> str:
        return f"{expr.target.accept(self)}{expr.op}"

    @typing.override
    def visit_arc4_router(self, expr: nodes.ARC4Router) -> str:
        return "arc4_router()"

    @typing.override
    def visit_emit(self, expr: nodes.Emit) -> str:
        return f"emit({expr.signature!r}, {expr.value.accept(self)})"

    @typing.override
    def visit_comma_expression(self, expr: nodes.CommaExpression) -> str:
        tuple_expr = nodes.TupleExpression.from_items(
            expr.expressions,
            expr.source_location,
        )
        return tuple_expr.accept(self) + "[-1]"


def _indent(lines: Iterable[str], indent_size: str = "  ") -> Iterator[str]:
    yield from (f"{indent_size}{line}" for line in lines)


def _bytes_str(b: bytes) -> str:
    return repr(b)[1:]


def _collapse_sequential_ranges(nums: Iterable[int]) -> Iterable[str]:
    ranges = list[tuple[int, int]]()
    for num in sorted(nums):
        if ranges and num == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], num)
        else:
            ranges.append((num, num))
    for start, stop in ranges:
        if start == stop:
            yield str(start)
        else:
            yield f"{start}..{stop}"
