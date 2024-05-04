from __future__ import annotations

import abc
import typing

import mypy.nodes

from puya import log
from puya.awst.nodes import Expression, IntrinsicCall, Literal, MethodConstant
from puya.awst_build.constants import ARC4_SIGNATURE_ALIAS
from puya.awst_build.eb.base import ExpressionBuilder, IntermediateExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.intrinsic_models import FunctionOpMapping, PropertyOpMapping
from puya.awst_build.utils import convert_literal, get_arg_mapping
from puya.errors import InternalError
from puya.utils import StableSet

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class Arc4SignatureBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(str_value))]:
                pass
            case _:
                logger.error(f"Unexpected args for {ARC4_SIGNATURE_ALIAS}", location=location)
                str_value = ""  # dummy value to keep evaluating
        return BytesExpressionBuilder(
            MethodConstant(
                value=str_value,
                source_location=location,
            )
        )


class _Namespace(IntermediateExpressionBuilder, abc.ABC):
    def __init__(self, type_info: mypy.nodes.TypeInfo, location: SourceLocation) -> None:
        self.type_info = type_info
        super().__init__(location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        sym_entry = self.type_info.get(name)
        if sym_entry is None or sym_entry.node is None:
            raise InternalError(
                f"Unknown algopy member: {self.type_info.fullname}.{name}", location
            )
        return self._member_access(name=name, node=sym_entry.node, location=location)

    @abc.abstractmethod
    def _member_access(
        self, name: str, node: mypy.nodes.SymbolNode, location: SourceLocation
    ) -> ExpressionBuilder | Literal: ...


class IntrinsicEnumClassExpressionBuilder(_Namespace):
    def __init__(
        self, data: Mapping[str, str], type_info: mypy.nodes.TypeInfo, location: SourceLocation
    ) -> None:
        super().__init__(type_info, location)
        self._data = data

    @typing.override
    def _member_access(
        self, name: str, node: mypy.nodes.SymbolNode, location: SourceLocation
    ) -> Literal:
        value = self._data.get(name)
        if value is None:
            raise InternalError(
                f"Un-mapped enum value {name!r} for '{self.type_info.fullname}.{name}'", location
            )
        return Literal(value=value, source_location=location)


class IntrinsicNamespaceClassExpressionBuilder(_Namespace):
    def __init__(
        self,
        data: Mapping[str, PropertyOpMapping | Sequence[FunctionOpMapping]],
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ) -> None:
        super().__init__(type_info, location)
        self._data = data

    @typing.override
    def _member_access(
        self, name: str, node: mypy.nodes.SymbolNode, location: SourceLocation
    ) -> ExpressionBuilder:
        mapping = self._data.get(name)
        fullname = ".".join((self.type_info.fullname, name))
        if mapping is None:
            raise InternalError(f"Un-mapped class member {name!r} for {fullname!r}", location)
        match node:
            # methods are either @staticmethod or @classmethod, so will be wrapped in decorator
            case mypy.nodes.Decorator(func=func_def):
                if isinstance(mapping, PropertyOpMapping):
                    raise InternalError(
                        f"Expected function mapping for {fullname!r} but got property", location
                    )
                return IntrinsicFunctionExpressionBuilder(func_def, mapping, location)
            # some class members in the stubs that take no arguments are typed
            # as final class vars, for these get the intrinsic expression by explicitly
            # mapping the member name as a call with no args
            case mypy.nodes.Var():
                if not isinstance(mapping, PropertyOpMapping):
                    raise InternalError(
                        f"Expected property mapping for {fullname!r} but got function", location
                    )
                intrinsic_expr = IntrinsicCall(
                    op_code=mapping.op_code,
                    immediates=[mapping.immediate],
                    wtype=mapping.typ.wtype,
                    source_location=location,
                )
                return var_expression(intrinsic_expr)
        raise InternalError(
            f"Unhandled intrinsic-namespace node type {type(node).__name__}"
            f" for {self.type_info.fullname}.{name}",
            location,
        )


class IntrinsicFunctionExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        func_def: mypy.nodes.FuncDef,
        mappings: Sequence[FunctionOpMapping],
        location: SourceLocation,
    ) -> None:
        self._mappings = mappings
        self.func_def = func_def
        super().__init__(location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        resolved_args: list[Expression | Literal] = [
            a.rvalue() if isinstance(a, ExpressionBuilder) else a for a in args
        ]
        arg_mapping = _get_arg_mapping_funcdef(self.func_def, resolved_args, location, arg_names)
        intrinsic_expr = _map_call(
            self._mappings, callee=self.func_def.fullname, node_location=location, args=arg_mapping
        )
        return var_expression(intrinsic_expr)


def _get_arg_mapping_funcdef(
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


def _best_op_mapping(
    op_mappings: Sequence[FunctionOpMapping], args: dict[str, Expression | Literal]
) -> FunctionOpMapping:
    """Find op mapping that matches as many arguments to immediate args as possible"""
    literal_arg_names = {arg_name for arg_name, arg in args.items() if isinstance(arg, Literal)}
    for op_mapping in sorted(op_mappings, key=lambda om: len(om.literal_arg_names), reverse=True):
        if literal_arg_names.issuperset(op_mapping.literal_arg_names):
            return op_mapping
    # fall back to first, let argument mapping handle logging errors
    return op_mappings[0]


def _map_call(
    ast_mapper: Sequence[FunctionOpMapping],
    callee: str,
    node_location: SourceLocation,
    args: dict[str, Expression | Literal],
) -> IntrinsicCall:
    if len(ast_mapper) == 1:
        (op_mapping,) = ast_mapper
    else:
        op_mapping = _best_op_mapping(ast_mapper, args)

    args = args.copy()  # make a copy since we're going to mutate

    immediates = list[str | int]()
    for immediate in op_mapping.immediates.items():
        match immediate:
            case value, None:
                immediates.append(value)
            case arg_name, literal_type:
                arg_in = args.pop(arg_name, None)
                if arg_in is None:
                    logger.error(f"Missing expected argument {arg_name}", location=node_location)
                elif not (
                    isinstance(arg_in, Literal)
                    and isinstance(arg_value := arg_in.value, literal_type)
                ):
                    logger.error(
                        f"Argument must be a literal {literal_type.__name__} value",
                        location=arg_in.source_location,
                    )
                else:
                    assert isinstance(arg_value, int | str)
                    immediates.append(arg_value)

    stack_args = list[Expression]()
    for arg_name, allowed_pytypes in op_mapping.stack_inputs.items():
        allowed_types = StableSet.from_iter(  # TODO: use PyTypes instead
            pt.wtype for pt in allowed_pytypes
        )
        arg_in = args.pop(arg_name, None)
        if arg_in is None:
            logger.error(f"Missing expected argument {arg_name}", location=node_location)
        elif isinstance(arg_in, Expression):
            # TODO this is identity based, match types instead?
            if arg_in.wtype not in allowed_types:
                logger.error(
                    f'Invalid argument type "{arg_in.wtype}"'
                    f' for argument "{arg_name}" when calling {callee}',
                    location=arg_in.source_location,
                )
            stack_args.append(arg_in)
        else:
            literal_value = arg_in.value
            for allowed_type in allowed_types:
                if allowed_type.is_valid_literal(literal_value):
                    literal_expr = convert_literal(arg_in, allowed_type)
                    stack_args.append(literal_expr)
                    break
            else:
                logger.error(
                    f"Unhandled literal type '{type(literal_value).__name__}' for argument",
                    location=arg_in.source_location,
                )

    for arg_node in args.values():
        logger.error("Unexpected argument", location=arg_node.source_location)

    return IntrinsicCall(
        source_location=node_location,
        wtype=op_mapping.result.wtype,
        op_code=op_mapping.op_code,
        immediates=immediates,
        stack_args=stack_args,
    )
