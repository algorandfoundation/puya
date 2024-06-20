import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    Expression,
    FieldExpression,
    NewStruct,
    ReinterpretCast,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puya.awst_build.eb._utils import bool_eval_to_constant, compare_bytes
from puya.awst_build.eb.arc4.base import CopyBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder
from puya.awst_build.utils import get_arg_mapping, require_instance_builder
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4StructTypeBuilder(BytesBackedTypeBuilder[pytypes.StructType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        assert pytypes.ARC4StructBaseType in typ.mro
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.produces()
        inst_args = [require_instance_builder(arg) for arg in args]
        field_mapping = get_arg_mapping(
            positional_arg_names=list(pytype.fields),
            args=zip(arg_names, inst_args, strict=True),
            location=location,
        )

        values = dict[str, Expression]()
        for field_name, field_type in pytype.fields.items():
            field_value = field_mapping.pop(field_name, None)
            if field_value is None:
                logger.error(f"missing required argument {field_name!r}", location=location)
            elif field_value.pytype != field_type:
                logger.error("unexpected argument type", location=field_value.source_location)
            else:
                values[field_name] = field_value.resolve()
        if field_mapping:
            logger.error(
                f"unexpected keyword arguments: {' '.join(field_mapping)}", location=location
            )

        assert isinstance(pytype.wtype, wtypes.ARC4Struct)
        if values.keys() == pytype.fields.keys():
            expr: Expression = NewStruct(
                wtype=pytype.wtype, values=values, source_location=location
            )
        else:
            expr = ReinterpretCast(
                expr=BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                ),
                wtype=pytype.wtype,
                source_location=location,
            )

        return ARC4StructExpressionBuilder(expr, pytype)


class ARC4StructExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StructType],
    BytesBackedInstanceExpressionBuilder[pytypes.StructType],
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.StructType)
        super().__init__(typ, expr)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case field_name if field := self.pytype.fields.get(field_name):
                result_expr = FieldExpression(
                    base=self.resolve(),
                    name=field_name,
                    wtype=field.wtype,
                    source_location=location,
                )
                return builder_for_instance(field, result_expr)
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case _:
                return super().member_access(name, location)

    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)
