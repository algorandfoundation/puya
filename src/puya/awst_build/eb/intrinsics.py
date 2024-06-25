import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst.nodes import IntrinsicCall, MethodConstant
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance, builder_for_type
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.intrinsic_models import (
    FunctionOpMapping,
    OpMappingWithOverloads,
    PropertyOpMapping,
)
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class Arc4SignatureBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is None:
            return dummy_value(pytypes.BytesType, location)
        str_value = expect.simple_string_literal(arg, default=expect.default_fixed_value(""))
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate enumeration type", location)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        produces = self.produces()
        value = produces.members.get(name)
        if value is None:
            return super().member_access(name, expr, location)
        return LiteralBuilderImpl(value=value, source_location=location)


class IntrinsicNamespaceTypeBuilder(TypeBuilder[pytypes.IntrinsicNamespaceType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate namespace type", location)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        produces = self.produces()
        mapping = produces.members.get(name)
        if mapping is None:
            return super().member_access(name, expr, location)
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
        self, fullname: str, mapping: OpMappingWithOverloads, location: SourceLocation
    ) -> None:
        self._fullname = fullname
        self._mapping = mapping
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not expect.exactly_n_args(args, location, self._mapping.arity):
            return dummy_value(self._mapping.result, location)
        intrinsic_expr = _map_call(self._mapping, args=args, location=location)
        return builder_for_instance(self._mapping.result, intrinsic_expr)


def _best_op_mapping(
    op_mappings: OpMappingWithOverloads, args: Sequence[NodeBuilder]
) -> FunctionOpMapping:
    """Find op mapping that matches as many arguments to immediate args as possible"""
    literal_arg_positions = {
        arg_idx
        for arg_idx, arg in enumerate(args)
        # we can't handle any form of dynamism for immediates, such as `1 if foo else 2`,
        # so we must check for LiteralBuilder only
        if isinstance(arg, LiteralBuilder)
    }
    for op_mapping in sorted(
        op_mappings.overloads, key=lambda om: len(om.literal_arg_positions), reverse=True
    ):
        if literal_arg_positions.issuperset(op_mapping.literal_arg_positions):
            return op_mapping
    # fall back to first, let argument mapping handle logging errors
    return op_mappings.overloads[0]


def _map_call(
    ast_mapper: OpMappingWithOverloads,
    args: Sequence[NodeBuilder],
    location: SourceLocation,
) -> IntrinsicCall:
    if len(ast_mapper.overloads) == 1:
        (op_mapping,) = ast_mapper.overloads
    else:
        op_mapping = _best_op_mapping(ast_mapper, args)

    immediates = list(op_mapping.immediates)
    stack_args = list[InstanceBuilder]()
    for arg_in, arg_data in zip(args, op_mapping.args, strict=True):
        if isinstance(arg_data, int):
            immediates_index = arg_data
            literal_type = typing.cast(type[str | int], immediates[immediates_index])
            if not (
                isinstance(arg_in, LiteralBuilder)  # see note in _best_op_mapping
                and isinstance(arg_value := arg_in.value, literal_type)
            ):
                logger.error(
                    f"argument must be a literal {literal_type.__name__} value",
                    location=arg_in.source_location,
                )
                immediates[immediates_index] = literal_type()
            else:
                assert isinstance(arg_value, int | str)
                immediates[immediates_index] = arg_value
        else:
            allowed_pytypes = arg_data
            if not isinstance(arg_in.pytype, pytypes.LiteralOnlyType):
                if not (isinstance(arg_in, InstanceBuilder) and arg_in.pytype in allowed_pytypes):
                    logger.error("unexpected argument type", location=arg_in.source_location)
                else:
                    stack_args.append(arg_in)
            else:
                for allowed_type in allowed_pytypes:
                    type_builder = builder_for_type(allowed_type, arg_in.source_location)
                    if isinstance(arg_in, InstanceBuilder) and isinstance(
                        type_builder, TypeBuilder
                    ):
                        try:
                            converted = arg_in.resolve_literal(type_builder)
                        except CodeError:  # TODO: fixme, need a try version or something here
                            pass
                        else:
                            stack_args.append(converted)
                            break
                else:
                    logger.error("unexpected argument type", location=arg_in.source_location)

    return IntrinsicCall(
        op_code=op_mapping.op_code,
        wtype=ast_mapper.result.wtype,
        immediates=typing.cast(list[str | int], immediates),
        stack_args=[a.resolve() for a in stack_args],
        source_location=location,
    )
