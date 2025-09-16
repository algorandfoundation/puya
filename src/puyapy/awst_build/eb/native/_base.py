import abc
import typing
from abc import ABC
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ConvertArray,
    Copy,
    Expression,
    IndexExpression,
    NewArray,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    GenericTypeBuilder,
    InstanceExpressionBuilder,
)
from puyapy.awst_build.eb._utils import (
    CopyBuilder,
    cast_to_bytes,
    compare_bytes,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    TypeBuilder,
)

logger = log.get_logger(__name__)


class _ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType], ABC):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    def iterate(self) -> Expression:
        if not self.pytype.items_wtype.immutable:
            # this case is an error raised during AWST validation
            # adding a front end specific message here to compliment the error message
            # raise across all front ends
            logger.info(
                "use `algopy.urange(<array>.length)` to iterate by index",
                location=self.source_location,
            )
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self.pytype.items

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        array_length = self.length(index.source_location)
        index = resolve_negative_literal_index(index, array_length, location)
        result_expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            wtype=self.pytype.items_wtype,
            source_location=location,
        )
        return builder_for_instance(self.pytype.items, result_expr)

    @abc.abstractmethod
    def length(self, location: SourceLocation) -> InstanceBuilder: ...

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return self.length(location)
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(self=self, op=op, other=other, source_location=location)

    @typing.override
    @typing.final
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        logger.error("item containment with arrays is currently unsupported", location=location)
        return dummy_value(pytypes.BoolType, location)

    @typing.override
    @typing.final
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing arrays is currently unsupported", location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return cast_to_bytes(self.resolve(), location)


class _BaseArrayGenericTypeBuilder(GenericTypeBuilder):
    def __init__(
        self,
        generic_typ: pytypes._GenericType[pytypes.ArrayType],
        eb: type[_ArrayExpressionBuilder],
        expected_wtype_type: type[wtypes.WType],
        location: SourceLocation,
    ):
        super().__init__(location)
        self._generic_type = generic_typ
        self._eb = eb
        self._expected_wtype_type = expected_wtype_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        if not arg:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)

        arg_item_type = arg.iterable_item_type()
        typ = self._generic_type.parameterise([arg_item_type], location)
        wtype = typ.wtype
        assert isinstance(wtype, self._expected_wtype_type)

        if arg.pytype.wtype == wtype:
            new_array: Expression = Copy(value=arg.resolve(), source_location=location)
        elif isinstance(
            arg.pytype.wtype,
            wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray,
        ):
            new_array = ConvertArray(expr=arg.resolve(), wtype=wtype, source_location=location)
        elif isinstance(arg, StaticSizedCollectionBuilder):
            item_builders = arg.iterate_static()
            items = [ib.resolve() for ib in item_builders]
            new_array = NewArray(values=items, wtype=wtype, source_location=location)
        else:
            logger.error("unsupported collection type", location=arg.source_location)
            new_array = Copy(value=dummy_value(typ, location).resolve(), source_location=location)
        return self._eb(new_array, typ)


class _BaseArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(
        self,
        *,
        typ: pytypes.PyType,
        generic_typ: pytypes._GenericType[pytypes.ArrayType],
        eb: type[_ArrayExpressionBuilder],
        expected_wtype_type: type[wtypes.WType],
        location: SourceLocation,
    ):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == generic_typ
        assert isinstance(typ.wtype, expected_wtype_type)
        self._eb = eb
        self._expected_wtype_type = expected_wtype_type
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, self._expected_wtype_type)

        arg = expect.at_most_one_arg(args, location)
        if not arg:
            new_array: Expression = NewArray(values=[], wtype=wtype, source_location=location)
        else:
            arg_item_type = arg.iterable_item_type()
            if not (typ.items <= arg_item_type):
                logger.error(
                    "iterable element type does not match collection type",
                    location=arg.source_location,
                )
                arg = dummy_value(typ, location)
            if arg.pytype.wtype == wtype:
                new_array = Copy(value=arg.resolve(), source_location=location)
            elif isinstance(
                arg.pytype.wtype,
                wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray,
            ):
                new_array = ConvertArray(expr=arg.resolve(), wtype=wtype, source_location=location)
            elif isinstance(arg, StaticSizedCollectionBuilder):
                item_builders = arg.iterate_static()
                items = [ib.resolve() for ib in item_builders]
                new_array = NewArray(values=items, wtype=wtype, source_location=location)
            else:
                logger.error("unsupported collection type", location=arg.source_location)
                new_array = Copy(
                    value=dummy_value(typ, location).resolve(), source_location=location
                )

        return self._eb(new_array, self._pytype)
