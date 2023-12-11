from __future__ import annotations

from typing import TYPE_CHECKING, Never

import mypy.nodes
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BigUIntConstant,
    BoolConstant,
    BytesConstant,
    Expression,
    IntrinsicCall,
    Literal,
    MethodConstant,
    Node,
    UInt64Constant,
)
from puya.awst_build.constants import ARC4_SIGNATURE_ALIAS
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.intrinsic_data import ENUM_CLASSES, STUB_TO_AST_MAPPER
from puya.awst_build.intrinsic_models import ArgMapping, FunctionOpMapping
from puya.awst_build.utils import get_arg_mapping, require_expression_builder
from puya.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class Arc4SignatureBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(str_value))]:
                return var_expression(
                    MethodConstant(
                        value=str_value,
                        source_location=location,
                    )
                )
            case _:
                raise CodeError(f"Unexpected args for {ARC4_SIGNATURE_ALIAS}", location)


class IntrinsicEnumClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, enum_class_fullname: str, location: SourceLocation) -> None:
        self.enum_class = enum_class_fullname
        try:
            self.enum_literals = ENUM_CLASSES[enum_class_fullname]
        except KeyError as ex:
            raise CodeError(f"Unknown enum class '{self.enum_class}'") from ex
        super().__init__(location)

    def member_access(self, name: str, location: SourceLocation) -> Literal:
        try:
            value = self.enum_literals[name]
        except KeyError as ex:
            raise CodeError(f"Unknown enum value '{name}' for '{self.enum_class}'") from ex
        return Literal(
            source_location=location,
            # this works currently because these enums are StrEnum with auto() as their value
            value=value,
        )


class IntrinsicNamespaceClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, type_info: mypy.nodes.TypeInfo, location: SourceLocation) -> None:
        self.type_info = type_info
        super().__init__(location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match self.type_info.names[name]:
            case mypy.nodes.SymbolTableNode(node=mypy.nodes.SymbolNode() as sym_node):
                pass
            case _:
                raise InternalError("symbol table nodes should not be None", location)
        func_def = unwrap_func_def(
            location, sym_node, num_pos_args=0  # assuming no overloads for intrinsic functions
        )
        assert isinstance(func_def, mypy.nodes.FuncDef)
        return IntrinsicFunctionExpressionBuilder(func_def, location)


class IntrinsicFunctionExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, func_def: mypy.nodes.FuncDef, location: SourceLocation) -> None:
        self.func_def = func_def
        super().__init__(location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        resolved_args: list[Expression | Literal] = [
            a.rvalue() if isinstance(a, ExpressionBuilder) else a for a in args
        ]
        arg_mapping = get_arg_mapping_funcdef(self.func_def, resolved_args, location, arg_names)
        intrinsic_expr = map_call(
            callee=self.func_def.fullname, node_location=location, args=arg_mapping
        )
        if intrinsic_expr is None:
            raise CodeError(f"Unknown puyapy function {self.func_def.fullname}")
        return var_expression(intrinsic_expr)


def unwrap_func_def(
    location: SourceLocation, node: mypy.nodes.SymbolNode, num_pos_args: int
) -> mypy.nodes.FuncDef:
    match node:
        case mypy.nodes.FuncDef() as func_def:
            return func_def
        case mypy.nodes.OverloadedFuncDef(impl=impl) as overloaded_func:
            if impl is not None:
                return unwrap_func_def(location, impl, num_pos_args)
            funcs = [unwrap_func_def(location, f, num_pos_args) for f in overloaded_func.items]
            possible_overloads = list[mypy.nodes.FuncDef]()
            for func in funcs:
                func_arg_kinds = [
                    kind
                    for kind, arg in zip(func.arg_kinds, func.arguments, strict=True)
                    if not (arg.variable.is_self or arg.variable.is_cls)
                ]
                min_pos_args = func_arg_kinds.count(mypy.nodes.ArgKind.ARG_POS)
                max_pos_args = min_pos_args + func_arg_kinds.count(mypy.nodes.ArgKind.ARG_OPT)
                if min_pos_args <= num_pos_args <= max_pos_args:
                    possible_overloads.append(func)
            match possible_overloads:
                case []:
                    raise InternalError(
                        f"Could not find valid overload for {overloaded_func.fullname} "
                        f"with {num_pos_args} positional arg/s",
                        location,
                    )
                case [single]:
                    return single
                case _:
                    raise InternalError(
                        f"Could not find exact overload for {overloaded_func.fullname} "
                        f"with {num_pos_args} positional arg/s",
                        location,
                    )
        case mypy.nodes.Decorator(func=func_def):
            return func_def
        case _:
            raise InternalError("Call symbol resolved to non-callable", location)


def get_arg_mapping_funcdef(
    func_def: mypy.nodes.FuncDef,
    args: Sequence[Expression | Literal],
    location: SourceLocation,
    arg_names: Sequence[str | None],
) -> dict[str, Expression | Literal]:
    func_pos_args = [
        arg.variable.name
        for arg, kind in zip(func_def.arguments, func_def.arg_kinds, strict=True)
        if kind in (mypy.nodes.ArgKind.ARG_POS, mypy.nodes.ArgKind.ARG_OPT)
        and not (arg.variable.is_cls or arg.variable.is_self)
    ]
    return get_arg_mapping(
        func_pos_args, args=zip(arg_names, args, strict=True), location=location
    )


def _all_immediates_are_constant(
    op_mapping: FunctionOpMapping, arg_is_constant: dict[str, bool]
) -> bool:
    return all(
        arg_is_constant[immediate.arg_name] if isinstance(immediate, ArgMapping) else True
        for immediate in op_mapping.immediates
    )


def _find_op_mapping(
    op_mappings: list[FunctionOpMapping],
    args: dict[str, Expression | Literal],
    location: SourceLocation,
) -> FunctionOpMapping:
    # find op mapping that matches as many arguments to immediate args as possible
    arg_is_constant = {arg_name: isinstance(arg, Literal) for arg_name, arg in args.items()}
    best_mapping: FunctionOpMapping | None = None
    for op_mapping in op_mappings:
        if _all_immediates_are_constant(op_mapping, arg_is_constant) and (
            best_mapping is None or len(op_mapping.immediates) > len(best_mapping.immediates)
        ):
            best_mapping = op_mapping

    if best_mapping is None:
        raise CodeError(
            "Could not find valid op mapping", location=location
        )  # TODO: raise better error
    return best_mapping


def _code_error(arg: Node, arg_mapping: ArgMapping, callee: str) -> Never:
    # TODO: better error
    raise CodeError(
        f"Invalid argument {arg} for argument {arg_mapping.arg_name} when calling {callee}",
        location=arg.source_location,
    )


def _check_stack_type(arg_mapping: ArgMapping, node: Node, callee: str) -> None:
    valid: bool
    match node:
        case Expression(wtype=wtype):
            # TODO this is identity based, match types instead?
            valid = wtype in arg_mapping.allowed_types
        case _:
            valid = False
    if not valid:
        _code_error(node, arg_mapping, callee)


def _return_types_to_wtype(types: Sequence[wtypes.WType]) -> wtypes.WType:
    if not types:
        return wtypes.void_wtype
    elif len(types) == 1:
        return types[0]
    else:
        return wtypes.WTuple.from_types(types)


def map_call(
    callee: str, node_location: SourceLocation, args: dict[str, Expression | Literal]
) -> IntrinsicCall | None:
    try:
        ast_mapper = STUB_TO_AST_MAPPER[callee]
    except KeyError:
        return None
    op_mapping = _find_op_mapping(ast_mapper, args, node_location)

    immediates = list[str | int]()
    stack_args = list[Expression]()
    for immediate in op_mapping.immediates:
        if isinstance(immediate, str):
            immediates.append(immediate)
        else:
            arg_in = args[immediate.arg_name]
            if isinstance(arg_in, Literal) and immediate.is_allowed_constant(arg_in.value):
                if not isinstance(arg_in.value, int | str):
                    raise InternalError(
                        f"Unexpected literal value type, value = {arg_in.value!r}", node_location
                    )
                immediates.append(arg_in.value)
            else:
                _code_error(arg_in, immediate, callee)

    for arg_mapping in op_mapping.stack_inputs:
        arg_in = args[arg_mapping.arg_name]
        arg: Expression
        match arg_in:
            case Literal(value=bool(bool_value)) as bool_literal:
                arg = BoolConstant(value=bool_value, source_location=bool_literal.source_location)
            case Literal(value=int(int_value)) as int_literal:
                if wtypes.biguint_wtype in arg_mapping.allowed_types:
                    arg = BigUIntConstant(
                        value=int_value, source_location=int_literal.source_location
                    )
                else:
                    arg = UInt64Constant(
                        value=int_value, source_location=int_literal.source_location
                    )
            case Literal(value=bytes(bytes_value)) as bytes_literal:
                arg = BytesConstant(
                    value=bytes_value, source_location=bytes_literal.source_location
                )
            case _:
                arg = require_expression_builder(arg_in).rvalue()
        _check_stack_type(arg_mapping, arg, callee)
        stack_args.append(arg)

    return IntrinsicCall(
        source_location=node_location,
        wtype=_return_types_to_wtype(op_mapping.stack_outputs),
        op_code=op_mapping.op_code,
        immediates=immediates,
        stack_args=stack_args,
    )
