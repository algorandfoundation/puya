from __future__ import annotations

import typing

from puya import log
from puya.awst.nodes import Expression, IntrinsicCall, MethodConstant
from puya.awst_build import pytypes
from puya.awst_build.constants import ARC4_SIGNATURE_ALIAS
from puya.awst_build.eb._base import FunctionBuilder, TypeBuilder
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance, builder_for_type
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.intrinsic_models import FunctionOpMapping, PropertyOpMapping
from puya.awst_build.utils import get_arg_mapping, require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class Arc4SignatureBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [LiteralBuilder(value=str(str_value))]:
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


class IntrinsicEnumTypeBuilder(TypeBuilder[pytypes.IntrinsicEnumType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("Cannot instantiate enumeration type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        produces = self.produces()
        value = produces.members.get(name)
        if value is None:
            raise CodeError(f"Unknown member {name!r} of '{produces}'", location)
        return LiteralBuilderImpl(value=value, source_location=location)


class IntrinsicNamespaceTypeBuilder(TypeBuilder[pytypes.IntrinsicNamespaceType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("Cannot instantiate namespace type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        produces = self.produces()
        mapping = produces.members.get(name)
        if mapping is None:
            raise CodeError(f"Unknown member {name!r} of '{produces}'", location)
        if isinstance(mapping, PropertyOpMapping):
            intrinsic_expr = IntrinsicCall(
                op_code=mapping.op_code,
                immediates=[mapping.immediate],
                wtype=mapping.typ.wtype,
                source_location=location,
            )
            return builder_for_instance(mapping.typ, intrinsic_expr)
        else:
            fullname = ".".join((produces.name, name))
            return IntrinsicFunctionExpressionBuilder(fullname, mapping, location)


class IntrinsicFunctionExpressionBuilder(FunctionBuilder):
    def __init__(
        self, fullname: str, mappings: Sequence[FunctionOpMapping], location: SourceLocation
    ) -> None:
        assert mappings
        self._fullname = fullname
        self._mappings = mappings
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        primary_mapping = self._mappings[0]  # TODO: remove this assumption
        func_arg_names = (*primary_mapping.literal_arg_names, *primary_mapping.stack_inputs.keys())

        args_ = [require_instance_builder(a) for a in args]

        arg_mapping = get_arg_mapping(
            func_arg_names, args=zip(arg_names, args_, strict=False), location=location
        )
        intrinsic_expr = _map_call(
            self._mappings, callee=self._fullname, node_location=location, args=arg_mapping
        )
        return intrinsic_expr


def _best_op_mapping(
    op_mappings: Sequence[FunctionOpMapping], args: dict[str, InstanceBuilder]
) -> FunctionOpMapping:
    """Find op mapping that matches as many arguments to immediate args as possible"""
    literal_arg_names = {
        arg_name for arg_name, arg in args.items() if isinstance(arg, LiteralBuilder)
    }
    for op_mapping in sorted(op_mappings, key=lambda om: len(om.literal_arg_names), reverse=True):
        if literal_arg_names.issuperset(op_mapping.literal_arg_names):
            return op_mapping
    # fall back to first, let argument mapping handle logging errors
    return op_mappings[0]


def _map_call(
    ast_mapper: Sequence[FunctionOpMapping],
    callee: str,
    node_location: SourceLocation,
    args: dict[str, InstanceBuilder],
) -> InstanceBuilder:
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
                    isinstance(arg_in, LiteralBuilder)
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
        arg_in = args.pop(arg_name, None)
        if arg_in is None:
            logger.error(f"Missing expected argument {arg_name}", location=node_location)
        elif isinstance(arg_in, LiteralBuilder):
            literal_value = arg_in.value
            for allowed_type in allowed_pytypes:
                type_builder = builder_for_type(allowed_type, arg_in.source_location)
                if (
                    isinstance(type_builder, LiteralConverter)
                    and arg_in.pytype in type_builder.handled_types
                ):
                    converted = type_builder.convert_literal(arg_in, arg_in.source_location)
                    stack_args.append(converted.resolve())
                    break
            else:
                logger.error(
                    f"Unhandled literal type '{type(literal_value).__name__}' for argument",
                    location=arg_in.source_location,
                )
        else:
            if arg_in.pytype not in allowed_pytypes:
                logger.error(
                    f'Invalid argument type "{arg_in.pytype}"'
                    f' for argument "{arg_name}" when calling {callee}',
                    location=arg_in.source_location,
                )
            stack_args.append(arg_in.resolve())

    for arg_node in args.values():
        logger.error("Unexpected argument", location=arg_node.source_location)

    result_expr = IntrinsicCall(
        op_code=op_mapping.op_code,
        wtype=op_mapping.result.wtype,
        immediates=immediates,
        stack_args=stack_args,
        source_location=node_location,
    )
    return builder_for_instance(op_mapping.result, result_expr)
