import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import (
    AssertExpression,
    IntrinsicCall,
    MethodConstant,
    MethodSignature,
    MethodSignatureString,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._literals import LiteralBuilderImpl
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance, builder_for_type
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.intrinsic_models import (
    FunctionOpMapping,
    OpMappingWithOverloads,
    PropertyOpMapping,
)
from puyapy.models import ARC4ABIMethodData

logger = log.get_logger(__name__)


class Arc4SignatureBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [
                ARC4ClientMethodExpressionBuilder(method=fmethod)
                | BaseClassSubroutineInvokerExpressionBuilder(method=fmethod)
            ]:
                if not isinstance(fmethod.metadata, ARC4ABIMethodData):
                    logger.error("method is not an ARC-4 ABI method", location=location)
                    return dummy_value(pytypes.BytesType, location)

                abi_method_data = fmethod.metadata
                method_signature = MethodSignature(
                    name=abi_method_data.config.name,
                    arg_types=[t.checked_wtype(location) for t in abi_method_data.argument_types],
                    return_type=abi_method_data.return_type.checked_wtype(location),
                    resource_encoding=abi_method_data.config.resource_encoding,
                    source_location=args[0].source_location,
                )
                expr = MethodConstant(value=method_signature, source_location=location)
            case _:
                arg = expect.exactly_one_arg(args, location, default=expect.default_none)
                if arg is None:
                    return dummy_value(pytypes.BytesType, location)
                str_value = expect.simple_string_literal(
                    arg, default=expect.default_fixed_value("")
                )
                method_signature_str = MethodSignatureString(
                    value=str_value, source_location=args[0].source_location
                )
                expr = MethodConstant(value=method_signature_str, source_location=location)

        return BytesExpressionBuilder(expr)


class IntrinsicEnumTypeBuilder(TypeBuilder[pytypes.IntrinsicEnumType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate enumeration type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        produces = self.produces()
        value = produces.members.get(name)
        if value is None:
            return super().member_access(name, location)
        return LiteralBuilderImpl(value=value, source_location=location)


class IntrinsicNamespaceTypeBuilder(TypeBuilder[pytypes.IntrinsicNamespaceType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate namespace type", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        produces = self.produces()
        mapping = produces.members.get(name)
        if mapping is None:
            return super().member_access(name, location)
        if isinstance(mapping, PropertyOpMapping):
            intrinsic_expr = IntrinsicCall(
                op_code=mapping.op_code,
                immediates=[mapping.immediate],
                wtype=mapping.wtype,
                source_location=location,
            )
            return builder_for_instance(mapping.typ, intrinsic_expr)
        else:
            fullname = ".".join((produces.name, name))
            return IntrinsicFunctionExpressionBuilder(fullname, mapping, location)


class ErrFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        message: str | None = None
        if arg is not None:
            message = expect.simple_string_literal(arg, default=expect.default_none)
        expr = AssertExpression(
            condition=None,
            error_message=message,
            source_location=location,
        )
        return builder_for_instance(pytypes.NoneType, expr)


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
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not expect.exactly_n_args(args, location, self._mapping.arity):
            return dummy_value(self._mapping.result, location)
        intrinsic_expr = _map_call(self._mapping, args=args, location=location)
        return builder_for_instance(self._mapping.result, intrinsic_expr)


def _fewest_immediates_op_mapping(op_mappings: OpMappingWithOverloads) -> FunctionOpMapping:
    """
    Pick the overload with fewest immediate args.
    The optimiser handles promotion of stack args to immediates if possible.
    """
    return min(op_mappings.overloads, key=lambda om: len(om.literal_arg_positions))


def _extract_op_mapping(
    op_mappings: OpMappingWithOverloads, args: Sequence[NodeBuilder]
) -> FunctionOpMapping:
    """
    Pick the overload matching as many literal uint8-ranged args to immediates as possible.

    Used only for `op.extract`: the immediate form and `extract3` have different semantics
    when length=0, so we can't rely on the optimiser to promote stack args later.
    """
    literal_arg_positions = {
        arg_idx
        for arg_idx, arg in enumerate(args)
        # we can't handle any form of dynamism for immediates, such as `1 if foo else 2`,
        # so we must check for LiteralBuilder only with literal int value within uint8 bounds.
        if isinstance(arg, LiteralBuilder) and type(arg.value) is int and 0 <= arg.value <= 255
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
    elif any(o.op_code == "extract3" for o in ast_mapper.overloads):
        op_mapping = _extract_op_mapping(ast_mapper, args)
    else:
        op_mapping = _fewest_immediates_op_mapping(ast_mapper)

    immediates = list(op_mapping.immediates)
    stack_args = list[InstanceBuilder]()
    for arg, arg_data in zip(args, op_mapping.args, strict=True):
        arg_in = expect.instance_builder(arg, default=expect.default_none)
        if arg_in is None:
            pass
        elif isinstance(arg_data, int):
            immediates_index = arg_data
            literal_type = typing.cast(type[str | int], immediates[immediates_index])
            if not (
                isinstance(arg_in, LiteralBuilder)
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
            if isinstance(arg_in.pytype, pytypes.LiteralOnlyType) or (
                isinstance(arg_in.pytype, pytypes.UnionType)
                and any(isinstance(t, pytypes.LiteralOnlyType) for t in arg_in.pytype.types)
            ):
                for allowed_type in allowed_pytypes:
                    type_builder = builder_for_type(allowed_type, arg_in.source_location)
                    if isinstance(type_builder, TypeBuilder):
                        converted = arg_in.try_resolve_literal(type_builder)
                        if converted is not None:
                            arg_in = converted
                            break
            stack_args.append(expect.argument_of_type_else_dummy(arg_in, *allowed_pytypes))
    return IntrinsicCall(
        op_code=op_mapping.op_code,
        wtype=ast_mapper.result_wtype,
        immediates=typing.cast(list[str | int], immediates),
        stack_args=[a.resolve() for a in stack_args],
        source_location=location,
    )
