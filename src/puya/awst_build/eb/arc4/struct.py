import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, FieldExpression, NewStruct
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puya.awst_build.eb._utils import bool_eval_to_constant, compare_bytes, dummy_value
from puya.awst_build.eb.arc4._base import CopyBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder
from puya.awst_build.utils import get_arg_mapping
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
        field_mapping, any_missing = get_arg_mapping(
            required_positional_names=list(pytype.fields),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(pytype, location)

        values = {
            field_name: expect.argument_of_type_else_dummy(
                field_mapping[field_name], field_type
            ).resolve()
            for field_name, field_type in pytype.fields.items()
        }
        assert isinstance(pytype.wtype, wtypes.ARC4Struct)
        expr: Expression = NewStruct(wtype=pytype.wtype, values=values, source_location=location)
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
