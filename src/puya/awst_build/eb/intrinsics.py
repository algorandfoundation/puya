import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst.nodes import IntrinsicCall, MethodConstant
from puya.awst_build import pytypes
from puya.awst_build.constants import ARC4_SIGNATURE_ALIAS
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance, builder_for_type
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.intrinsic_models import FunctionOpMapping, PropertyOpMapping
from puya.awst_build.utils import get_arg_mapping, require_instance_builder
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
        intrinsic_expr = _map_call(self._mappings, args=arg_mapping, location=location)
        return intrinsic_expr


def _best_op_mapping(
    op_mappings: Sequence[FunctionOpMapping], args: dict[str, InstanceBuilder]
) -> FunctionOpMapping:
    """Find op mapping that matches as many arguments to immediate args as possible"""
    literal_arg_names = {
        arg_name
        for arg_name, arg in args.items()
        # we can't handle any form of dynamism for immediates, such as `1 if foo else 2`,
        # so we must check for LiteralBuilder only
        if isinstance(arg, LiteralBuilder)
    }
    for op_mapping in sorted(op_mappings, key=lambda om: len(om.literal_arg_names), reverse=True):
        if literal_arg_names.issuperset(op_mapping.literal_arg_names):
            return op_mapping
    # fall back to first, let argument mapping handle logging errors
    return op_mappings[0]


def _map_call(
    ast_mapper: Sequence[FunctionOpMapping],
    args: dict[str, InstanceBuilder],
    location: SourceLocation,
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
                    logger.error(f"missing expected argument {arg_name!r}", location=location)
                elif not (
                    isinstance(arg_in, LiteralBuilder)  # see note in _best_op_mapping
                    and isinstance(arg_value := arg_in.value, literal_type)
                ):
                    logger.error(
                        f"Argument must be a literal {literal_type.__name__} value",
                        location=arg_in.source_location,
                    )
                else:
                    assert isinstance(arg_value, int | str)
                    immediates.append(arg_value)

    stack_args = list[InstanceBuilder]()
    for arg_name, allowed_pytypes in op_mapping.stack_inputs.items():
        arg_in = args.pop(arg_name, None)
        if arg_in is None:
            logger.error(f"missing expected argument {arg_name!r}", location=location)
        elif isinstance(arg_in.pytype, pytypes.LiteralOnlyType):
            for allowed_type in allowed_pytypes:
                type_builder = builder_for_type(allowed_type, arg_in.source_location)
                if isinstance(type_builder, TypeBuilder):
                    assert isinstance(arg_in, LiteralBuilder)  # TODO: fixme
                    converted = type_builder.try_convert_literal(arg_in, arg_in.source_location)
                    if converted is not None:
                        stack_args.append(converted)
                        break
            else:
                logger.error("invalid argument type", location=arg_in.source_location)
        else:
            if arg_in.pytype not in allowed_pytypes:
                logger.error("invalid argument type", location=arg_in.source_location)
            stack_args.append(arg_in)

    for arg_in in args.values():
        logger.error("unexpected argument", location=arg_in.source_location)

    result_expr = IntrinsicCall(
        op_code=op_mapping.op_code,
        wtype=op_mapping.result.wtype,
        immediates=immediates,
        stack_args=[a.resolve() for a in stack_args],
        source_location=location,
    )
    return builder_for_instance(op_mapping.result, result_expr)
