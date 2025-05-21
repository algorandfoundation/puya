import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Copy, Expression, FieldExpression, NewStruct
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    InstanceExpressionBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puyapy.awst_build.eb._utils import (
    CopyBuilder,
    compare_bytes,
    constant_bool_and_error,
    dummy_value,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class StructTypeBuilder(TypeBuilder[pytypes.StructType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        assert pytypes.StructBaseType < typ
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
                field_mapping[field_name], pytype.fields[field_name]
            ).resolve()
            for field_name in field_mapping
        }
        assert isinstance(pytype.wtype, wtypes.ARC4Struct)
        expr = NewStruct(wtype=pytype.wtype, values=values, source_location=location)
        return StructExpressionBuilder(expr, pytype)


class StructExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StructType],
    InstanceExpressionBuilder[pytypes.StructType],
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.StructType)
        super().__init__(typ, expr)

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self.resolve()

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case field_name if field := self.pytype.fields.get(field_name):
                result_expr = FieldExpression(
                    base=self.resolve(),
                    name=field_name,
                    source_location=location,
                )
                return builder_for_instance(field, result_expr)
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case "_replace":
                return _Replace(self, self.pytype, location)
            case _:
                return super().member_access(name, location)

    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(self=self, op=op, other=other, source_location=location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class _Replace(FunctionBuilder):
    def __init__(
        self,
        instance: StructExpressionBuilder,
        struct_type: pytypes.StructType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.instance = instance
        self.struct_type = struct_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.struct_type
        field_mapping, _ = get_arg_mapping(
            optional_kw_only=list(pytype.fields),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        base_expr = self.instance.single_eval().resolve()
        values = dict[str, Expression]()
        for field_name, field_pytype in pytype.fields.items():
            new_value = field_mapping.get(field_name)
            if new_value is not None:
                item_builder = expect.argument_of_type_else_dummy(new_value, field_pytype)
                item = item_builder.resolve()
            else:
                field_wtype = field_pytype.checked_wtype(location)
                item = FieldExpression(base=base_expr, name=field_name, source_location=location)
                if not field_wtype.immutable:
                    logger.error(
                        f"mutable field {field_name!r} requires explicit copy", location=location
                    )
                    # implicitly create a copy node so that there is only one error
                    item = Copy(value=item, source_location=location)
            values[field_name] = item
        new_tuple = NewStruct(values=values, wtype=pytype.wtype, source_location=location)
        return StructExpressionBuilder(new_tuple, pytype)
